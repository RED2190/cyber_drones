package api

import (
	"context"
	"errors"
	"fmt"
	"log"

	"github.com/kirilltahmazidi/aggregator/internal/models"
	"github.com/kirilltahmazidi/aggregator/internal/store"
)

// MultiPublisher распределяет операции публикации на несколько бекендов (Kafka, MQTT)
type MultiPublisher struct {
	backends []Publisher
}

func NewMultiPublisher(backends ...Publisher) *MultiPublisher {
	return &MultiPublisher{backends: backends}
}

func (m *MultiPublisher) PublishOrder(ctx context.Context, order *store.Order) error {
	var errs []error
	hasBackend := false
	success := false

	for _, b := range m.backends {
		if b == nil {
			continue
		}
		hasBackend = true
		if err := b.PublishOrder(ctx, order); err != nil {
			log.Printf("[publish] order: backend failed: %v", err)
			errs = append(errs, err)
			continue
		}
		success = true
	}

	if success {
		return nil
	}
	if !hasBackend {
		return fmt.Errorf("no publisher backends configured")
	}
	return errors.Join(errs...)
}

func (m *MultiPublisher) PublishConfirmPrice(ctx context.Context, payload models.ConfirmPricePayload) error {
	var errs []error
	hasBackend := false
	success := false

	for _, b := range m.backends {
		if b == nil {
			continue
		}
		hasBackend = true
		if err := b.PublishConfirmPrice(ctx, payload); err != nil {
			log.Printf("[publish] confirm_price: backend failed: %v", err)
			errs = append(errs, err)
			continue
		}
		success = true
	}

	if success {
		return nil
	}
	if !hasBackend {
		return fmt.Errorf("no publisher backends configured")
	}
	return errors.Join(errs...)
}
