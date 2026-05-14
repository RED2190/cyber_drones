package response

import (
	"fmt"
	"log"
	"time"

	"github.com/kirilltahmazidi/aggregator/internal/models"
)

// Ok builds a successful response envelope for the given request and payload.
func Ok(req models.Request, payload interface{}) models.Response {
	return models.Response{
		Action:        models.ResponseAction,
		Payload:       payload,
		Sender:        models.DefaultSender,
		CorrelationID: req.GetCorrelationID(),
		Success:       true,
		Timestamp:     time.Now().UTC().Format(time.RFC3339Nano),
	}
}

// Err logs the error and builds a failure response envelope for the given request.
// component is used as the log prefix (e.g. "registry_component").
func Err(component string, req models.Request, msg string) models.Response {
	log.Printf("[%s] error correlation_id=%s: %s", component, req.GetCorrelationID(), msg)
	return models.Response{
		Action:        models.ResponseAction,
		Sender:        models.DefaultSender,
		CorrelationID: req.GetCorrelationID(),
		Success:       false,
		Error:         msg,
		Timestamp:     time.Now().UTC().Format(time.RFC3339Nano),
	}
}

// Errorf is a convenience wrapper around Err that formats the message.
func Errorf(component string, req models.Request, format string, args ...interface{}) models.Response {
	return Err(component, req, fmt.Sprintf(format, args...))
}
