package tests

import (
	"context"
	"fmt"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"testing"
	"time"

	"github.com/testcontainers/testcontainers-go"
	"github.com/testcontainers/testcontainers-go/wait"
)

const (
	testDBUser     = "aggregator"
	testDBPassword = "secret"
	testDBName     = "aggregator_test"
)

func TestMain(m *testing.M) {
	if os.Getenv("RUN_INTEGRATION_STACK") != "1" {
		os.Exit(m.Run())
	}

	ctx := context.Background()

	postgresContainer, dbURL, err := startPostgresContainer(ctx)
	if err != nil {
		fmt.Fprintf(os.Stderr, "failed to start postgres testcontainer: %v\n", err)
		os.Exit(1)
	}

	aggregatorCmd, binaryPath, err := startAggregatorProcess(dbURL)
	if err != nil {
		fmt.Fprintf(os.Stderr, "failed to start aggregator process: %v\n", err)
		_ = postgresContainer.Terminate(context.Background())
		os.Exit(1)
	}
	defer func() {
		_ = os.Remove(binaryPath)
	}()

	if err := waitHTTPHealthy("http://localhost:8080/health", 120*time.Second); err != nil {
		fmt.Fprintf(os.Stderr, "aggregator did not become healthy: %v\n", err)
		stopAggregatorProcess(aggregatorCmd)
		_ = postgresContainer.Terminate(context.Background())
		os.Exit(1)
	}

	_ = os.Setenv("AGGREGATOR_BASE_URL", "http://localhost:8080")
	_ = os.Setenv("KAFKA_BROKER", "localhost:29092")
	_ = os.Setenv("TEST_DB_URL", dbURL)

	code := m.Run()

	stopAggregatorProcess(aggregatorCmd)
	_ = postgresContainer.Terminate(context.Background())

	os.Exit(code)
}

func startPostgresContainer(ctx context.Context) (testcontainers.Container, string, error) {
	req := testcontainers.ContainerRequest{
		Image:        "postgres:16-alpine",
		ExposedPorts: []string{"5432/tcp"},
		Env: map[string]string{
			"POSTGRES_USER":     testDBUser,
			"POSTGRES_PASSWORD": testDBPassword,
			"POSTGRES_DB":       testDBName,
		},
		WaitingFor: wait.ForAll(
			wait.ForListeningPort("5432/tcp"),
			wait.ForLog("database system is ready to accept connections"),
		).WithDeadline(90 * time.Second),
	}

	container, err := testcontainers.GenericContainer(ctx, testcontainers.GenericContainerRequest{
		ContainerRequest: req,
		Started:          true,
	})
	if err != nil {
		return nil, "", err
	}

	host, err := container.Host(ctx)
	if err != nil {
		_ = container.Terminate(context.Background())
		return nil, "", err
	}
	port, err := container.MappedPort(ctx, "5432/tcp")
	if err != nil {
		_ = container.Terminate(context.Background())
		return nil, "", err
	}

	databaseURL := fmt.Sprintf(
		"postgres://%s:%s@%s:%s/%s?sslmode=disable",
		testDBUser,
		testDBPassword,
		host,
		port.Port(),
		testDBName,
	)

	return container, databaseURL, nil
}

func startAggregatorProcess(databaseURL string) (*exec.Cmd, string, error) {
	wd, err := os.Getwd()
	if err != nil {
		return nil, "", err
	}

	srcDir := filepath.Join(wd, "..", "src")
	binaryPath := filepath.Join(os.TempDir(), fmt.Sprintf("aggregator-it-%d", time.Now().UnixNano()))

	buildCmd := exec.Command("go", "build", "-o", binaryPath, "./cmd/main.go")
	buildCmd.Dir = srcDir
	buildCmd.Stdout = os.Stdout
	buildCmd.Stderr = os.Stderr
	if err := buildCmd.Run(); err != nil {
		return nil, "", err
	}

	cmd := exec.Command(binaryPath)
	cmd.Dir = srcDir
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.Env = append(os.Environ(),
		"DATABASE_URL="+databaseURL,
		"MIGRATIONS_PATH=migrations/001_init.sql",
		"KAFKA_BROKER=localhost:29092",
		"KAFKA_REQUEST_TOPIC=aggregator.requests",
		"KAFKA_RESPONSE_TOPIC=aggregator.responses",
		"KAFKA_CONSUMER_GROUP=aggregator-test-group",
		"KAFKA_DLT_TOPIC=aggregator.dead-letter",
		"KAFKA_OPERATOR_TOPIC=v1.aggregator_insurer.local.operator.requests",
		"KAFKA_OPERATOR_RESPONSE_TOPIC=v1.aggregator_insurer.local.operator.responses",
	)

	if err := cmd.Start(); err != nil {
		_ = os.Remove(binaryPath)
		return nil, "", err
	}

	return cmd, binaryPath, nil
}

func stopAggregatorProcess(cmd *exec.Cmd) {
	if cmd == nil || cmd.Process == nil {
		return
	}

	_ = cmd.Process.Signal(os.Interrupt)

	done := make(chan error, 1)
	go func() {
		done <- cmd.Wait()
	}()

	select {
	case <-time.After(10 * time.Second):
		_ = cmd.Process.Kill()
		<-done
	case <-done:
	}
}

func waitHTTPHealthy(url string, timeout time.Duration) error {
	client := &http.Client{Timeout: 2 * time.Second}
	deadline := time.Now().Add(timeout)

	for time.Now().Before(deadline) {
		resp, err := client.Get(url)
		if err == nil {
			_ = resp.Body.Close()
			if resp.StatusCode == http.StatusOK {
				return nil
			}
		}
		time.Sleep(time.Second)
	}

	return fmt.Errorf("health endpoint %s did not return 200 in time", url)
}
