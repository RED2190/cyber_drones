package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"

	"github.com/kirilltahmazidi/aggregator/internal/api"
	"github.com/kirilltahmazidi/aggregator/internal/config"
	"github.com/kirilltahmazidi/aggregator/internal/gateway"
	"github.com/kirilltahmazidi/aggregator/internal/handler"
	"github.com/kirilltahmazidi/aggregator/internal/kafka"
	"github.com/kirilltahmazidi/aggregator/internal/mqtt"
	"github.com/kirilltahmazidi/aggregator/internal/store"
)

func main() {
	log.SetFlags(log.LstdFlags | log.Lshortfile)
	log.Println("[main] aggregator service starting")

	cfg := config.Load()
	if err := cfg.Validate(); err != nil {
		log.Fatalf("[main] invalid config: %v", err)
	}
	log.Printf("[main] config: broker=%s request_topic=%s response_topic=%s operator_transport=%s",
		cfg.KafkaBroker, cfg.RequestTopic, cfg.ResponseTopic, cfg.OperatorTransport)

	s, err := store.New(cfg.DatabaseURL)
	if err != nil {
		log.Fatalf("[main] cannot connect to database: %v", err)
	}
	defer s.Close()
	log.Println("[main] connected to database")

	migration, err := os.ReadFile(cfg.MigrationsPath)
	if err != nil {
		log.Fatalf("[main] cannot read migration file: %v", err)
	}
	if err := s.RunMigrations(string(migration)); err != nil {
		log.Fatalf("[main] migration failed: %v", err)
	}
	log.Println("[main] migrations applied")

	h := handler.New()
	gw := gateway.New(h)
	svc := kafka.NewService(cfg, gw, s)

	publisher := api.NewMultiPublisher(svc)
	var mqttSvc *mqtt.Service
	if cfg.UseMQTTForOperators() {
		mqttSvc, err = mqtt.NewService(cfg, s)
		if err != nil {
			log.Fatalf("[main] mqtt is required by OPERATOR_TRANSPORT=%s: %v", cfg.OperatorTransport, err)
		}
		publisher = api.NewMultiPublisher(svc, mqttSvc)
		log.Println("[main] operator transport mode: kafka + mqtt")
	} else {
		log.Println("[main] operator transport mode: kafka only")
	}

	apiHandler := api.NewHandler(s, publisher, cfg.CommissionRate)
	router := api.NewRouter(apiHandler)
	httpServer := &http.Server{
		Addr:    ":8080",
		Handler: router,
	}

	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer cancel()

	go func() {
		log.Println("[main] HTTP server listening on :8080")
		if err := httpServer.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Printf("[main] HTTP server error: %v", err)
		}
	}()

	go func() {
		<-ctx.Done()
		log.Println("[main] shutting down HTTP server...")
		httpServer.Shutdown(context.Background()) //nolint:errcheck
	}()

	go func() {
		if err := svc.RunOperatorConsumer(ctx); err != nil && err != context.Canceled {
			log.Printf("[main] operator consumer exited: %v", err)
		}
	}()

	if mqttSvc != nil {
		go func() {
			if err := mqttSvc.RunOperatorConsumer(ctx); err != nil && err != context.Canceled {
				log.Printf("[main] mqtt operator consumer exited: %v", err)
			}
		}()
	}

	if err := svc.Run(ctx); err != nil && err != context.Canceled {
		log.Fatalf("[main] service exited with error: %v", err)
	}

	log.Println("[main] aggregator service stopped gracefully")
}
