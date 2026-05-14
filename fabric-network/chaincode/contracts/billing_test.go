package contracts

import "testing"

func TestCalculateOrderDistributionSampleInputs(t *testing.T) {
	fleetPrice := 81000
	aggregatorFee := 5000
	insurancePremium := 23000
	riskReserve := 20000

	aggID := "agg-001"
	opID := "op-001"
	insID := "ins-001"
	certID := "cert-001"

	dist, total, err := calculateOrderDistribution(
		fleetPrice,
		aggregatorFee,
		insurancePremium,
		riskReserve,
		aggID,
		opID,
		insID,
		certID,
	)
	if err != nil {
		t.Fatalf("calculateOrderDistribution failed: %v", err)
	}

	expectedTotal := fleetPrice + aggregatorFee + insurancePremium + riskReserve
	if total != expectedTotal {
		t.Fatalf("expected total %d, got %d", expectedTotal, total)
	}

	if dist["operator"].Amount != fleetPrice || dist["operator"].RecipientID != opID {
		t.Errorf("operator distribution mismatch: %+v", dist["operator"])
	}
	if dist["aggregator"].Amount != aggregatorFee || dist["aggregator"].RecipientID != aggID {
		t.Errorf("aggregator distribution mismatch: %+v", dist["aggregator"])
	}
	if dist["insurer"].Amount != insurancePremium || dist["insurer"].RecipientID != insID {
		t.Errorf("insurer distribution mismatch: %+v", dist["insurer"])
	}
	if dist["risk_reserve"].Amount != riskReserve || dist["risk_reserve"].RecipientID != defaultRiskReserveID {
		t.Errorf("risk reserve distribution mismatch: %+v", dist["risk_reserve"])
	}
	if dist["cert_center"].Amount != 0 || dist["cert_center"].RecipientID != certID {
		t.Errorf("cert center distribution mismatch: %+v", dist["cert_center"])
	}
}
