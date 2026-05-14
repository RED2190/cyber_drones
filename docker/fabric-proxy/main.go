package main

import (
	"crypto/x509"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"time"

	"github.com/hyperledger/fabric-gateway/pkg/client"
	"github.com/hyperledger/fabric-gateway/pkg/identity"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials"
)

type InvokeRequest struct {
	Channel   string   `json:"channel"`
	Chaincode string   `json:"chaincode"`
	Method    string   `json:"method"`
	Args      []string `json:"args"`
}

type InvokeResponse struct {
	TransactionID string `json:"transaction_id,omitempty"`
	Result        string `json:"result"`
}

type ErrorResponse struct {
	Error string `json:"error"`
}

var gateway *client.Gateway

func env(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func envDuration(key string, fallback time.Duration) time.Duration {
	if v := os.Getenv(key); v != "" {
		if sec, err := strconv.Atoi(v); err == nil && sec > 0 {
			return time.Duration(sec) * time.Second
		}
	}
	return fallback
}

func newGrpcConnection() (*grpc.ClientConn, error) {
	tlsCertPath := filepath.Join(env("FABRIC_CRYPTO_PATH", "/crypto"),
		"peerOrganizations",
		env("FABRIC_PEER_ORG", "aggregator.drone-network.local"),
		"peers",
		env("FABRIC_PEER_HOST", "peer0.aggregator.drone-network.local"),
		"tls", "ca.crt",
	)

	certPEM, err := os.ReadFile(tlsCertPath)
	if err != nil {
		return nil, fmt.Errorf("read TLS cert: %w", err)
	}

	pool := x509.NewCertPool()
	if !pool.AppendCertsFromPEM(certPEM) {
		return nil, fmt.Errorf("failed to add TLS cert to pool")
	}

	transportCreds := credentials.NewClientTLSFromCert(pool,
		env("FABRIC_PEER_HOST", "peer0.aggregator.drone-network.local"))

	return grpc.NewClient(
		env("FABRIC_PEER_ENDPOINT", "peer0.aggregator.drone-network.local:7051"),
		grpc.WithTransportCredentials(transportCreds),
	)
}

func newIdentity() (*identity.X509Identity, error) {
	certPath := filepath.Join(env("FABRIC_CRYPTO_PATH", "/crypto"),
		"peerOrganizations",
		env("FABRIC_PEER_ORG", "aggregator.drone-network.local"),
		"users",
		env("FABRIC_USER", "Admin@aggregator.drone-network.local"),
		"msp", "signcerts",
	)

	entries, err := os.ReadDir(certPath)
	if err != nil {
		return nil, fmt.Errorf("read signcerts dir: %w", err)
	}
	if len(entries) == 0 {
		return nil, fmt.Errorf("no certificates in %s", certPath)
	}

	certPEM, err := os.ReadFile(filepath.Join(certPath, entries[0].Name()))
	if err != nil {
		return nil, fmt.Errorf("read cert: %w", err)
	}

	cert, err := identity.CertificateFromPEM(certPEM)
	if err != nil {
		return nil, fmt.Errorf("parse cert: %w", err)
	}

	mspID := env("FABRIC_MSP_ID", "AggregatorMSP")
	id, err := identity.NewX509Identity(mspID, cert)
	if err != nil {
		return nil, fmt.Errorf("create identity: %w", err)
	}
	return id, nil
}

func newSign() (identity.Sign, error) {
	keyPath := filepath.Join(env("FABRIC_CRYPTO_PATH", "/crypto"),
		"peerOrganizations",
		env("FABRIC_PEER_ORG", "aggregator.drone-network.local"),
		"users",
		env("FABRIC_USER", "Admin@aggregator.drone-network.local"),
		"msp", "keystore",
	)

	entries, err := os.ReadDir(keyPath)
	if err != nil {
		return nil, fmt.Errorf("read keystore dir: %w", err)
	}
	if len(entries) == 0 {
		return nil, fmt.Errorf("no keys in %s", keyPath)
	}

	keyPEM, err := os.ReadFile(filepath.Join(keyPath, entries[0].Name()))
	if err != nil {
		return nil, fmt.Errorf("read key: %w", err)
	}

	privateKey, err := identity.PrivateKeyFromPEM(keyPEM)
	if err != nil {
		return nil, fmt.Errorf("parse key: %w", err)
	}

	return identity.NewPrivateKeySign(privateKey)
}

func handleInvoke(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "POST only", http.StatusMethodNotAllowed)
		return
	}

	var req InvokeRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid JSON: "+err.Error())
		return
	}

	if req.Channel == "" {
		req.Channel = env("FABRIC_CHANNEL", "dronechannel")
	}
	if req.Chaincode == "" {
		req.Chaincode = env("FABRIC_CHAINCODE", "drone-chaincode")
	}

	network := gateway.GetNetwork(req.Channel)
	contract := network.GetContract(req.Chaincode)

	byteArgs := make([]string, len(req.Args))
	copy(byteArgs, req.Args)

	result, err := contract.SubmitTransaction(req.Method, byteArgs...)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	writeJSON(w, http.StatusOK, InvokeResponse{
		Result: string(result),
	})
}

func handleQuery(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "POST only", http.StatusMethodNotAllowed)
		return
	}

	var req InvokeRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid JSON: "+err.Error())
		return
	}

	if req.Channel == "" {
		req.Channel = env("FABRIC_CHANNEL", "dronechannel")
	}
	if req.Chaincode == "" {
		req.Chaincode = env("FABRIC_CHAINCODE", "drone-chaincode")
	}

	network := gateway.GetNetwork(req.Channel)
	contract := network.GetContract(req.Chaincode)

	result, err := contract.EvaluateTransaction(req.Method, req.Args...)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	writeJSON(w, http.StatusOK, InvokeResponse{
		Result: string(result),
	})
}

func handleHealth(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func writeJSON(w http.ResponseWriter, code int, v interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	json.NewEncoder(w).Encode(v)
}

func writeError(w http.ResponseWriter, code int, msg string) {
	writeJSON(w, code, ErrorResponse{Error: msg})
}

func main() {
	log.Println("[fabric-proxy] Starting...")

	conn, err := newGrpcConnection()
	if err != nil {
		log.Fatalf("gRPC connection failed: %v", err)
	}
	defer conn.Close()

	id, err := newIdentity()
	if err != nil {
		log.Fatalf("Identity failed: %v", err)
	}

	sign, err := newSign()
	if err != nil {
		log.Fatalf("Sign failed: %v", err)
	}

	evalTimeout := envDuration("FABRIC_EVALUATE_TIMEOUT_SEC", 30*time.Second)
	endorseTimeout := envDuration("FABRIC_ENDORSE_TIMEOUT_SEC", 30*time.Second)
	submitTimeout := envDuration("FABRIC_SUBMIT_TIMEOUT_SEC", 15*time.Second)
	commitStatusTimeout := envDuration("FABRIC_COMMIT_STATUS_TIMEOUT_SEC", 1*time.Minute)
	log.Printf("[fabric-proxy] Timeouts: evaluate=%v endorse=%v submit=%v commitStatus=%v", evalTimeout, endorseTimeout, submitTimeout, commitStatusTimeout)

	gw, err := client.Connect(
		id,
		client.WithSign(sign),
		client.WithClientConnection(conn),
		client.WithEvaluateTimeout(evalTimeout),
		client.WithEndorseTimeout(endorseTimeout),
		client.WithSubmitTimeout(submitTimeout),
		client.WithCommitStatusTimeout(commitStatusTimeout),
	)
	if err != nil {
		log.Fatalf("Gateway connect failed: %v", err)
	}
	defer gw.Close()

	gateway = gw
	log.Println("[fabric-proxy] Connected to Fabric Gateway")

	mux := http.NewServeMux()
	mux.HandleFunc("/api/invoke", handleInvoke)
	mux.HandleFunc("/api/query", handleQuery)
	mux.HandleFunc("/health", handleHealth)

	port := env("PORT", "3000")
	log.Printf("[fabric-proxy] Listening on :%s\n", port)
	if err := http.ListenAndServe(":"+port, mux); err != nil {
		log.Fatalf("Server error: %v", err)
	}
}
