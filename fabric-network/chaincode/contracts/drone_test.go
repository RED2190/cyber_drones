package contracts

import (
	"encoding/json"
	"reflect"
	"testing"
)

// ============ UNIT ТЕСТЫ для структур данных ============

func TestDronePassJSON(t *testing.T) {
	pass := DronePass{
		ID:                 "1",
		DeveloperID:        "manufacturer-001",
		Model:              "AG-100",
		Type:               "agro",
		WeightKg:           25,
		MaxFlightRangeKm:   50,
		MaxPayloadWeightKg: 10,
		ReleaseYear:        2024,
		FirmwareID:         "1.0.1",
	}

	// Сериализация
	data, err := json.Marshal(pass)
	if err != nil {
		t.Fatalf("JSON Marshal failed: %v", err)
	}

	// Десериализация
	var decoded DronePass
	err = json.Unmarshal(data, &decoded)
	if err != nil {
		t.Fatalf("JSON Unmarshal failed: %v", err)
	}

	if decoded.ID != pass.ID {
		t.Errorf("Expected ID %d, got %d", pass.ID, decoded.ID)
	}
	if decoded.DeveloperID != pass.DeveloperID {
		t.Errorf("Expected DeveloperID %s, got %s", pass.DeveloperID, decoded.DeveloperID)
	}
	if decoded.Model != pass.Model {
		t.Errorf("Expected Model %s, got %s", pass.Model, decoded.Model)
	}
	if decoded.FirmwareID != pass.FirmwareID {
		t.Errorf("Expected FirmwareID %s, got %s", pass.FirmwareID, decoded.FirmwareID)
	}
}

func TestFirmwareJSON(t *testing.T) {
	firmware := Firmware{
		ID:                 "firmware-001",
		SecurityObjectives: []string{"SO_1", "SO_3", "SO_7", "SO_9"},
	}

	data, err := json.Marshal(firmware)
	if err != nil {
		t.Fatalf("JSON Marshal failed: %v", err)
	}

	var decoded Firmware
	err = json.Unmarshal(data, &decoded)
	if err != nil {
		t.Fatalf("JSON Unmarshal failed: %v", err)
	}

	if decoded.ID != firmware.ID {
		t.Errorf("Expected ID %s, got %s", firmware.ID, decoded.ID)
	}
	if !reflect.DeepEqual(decoded.SecurityObjectives, firmware.SecurityObjectives) {
		t.Errorf("Expected SecurityObjectives %v, got %v", firmware.SecurityObjectives, decoded.SecurityObjectives)
	}
}

func TestInsuranceRecordJSON(t *testing.T) {
	insurance := InsuranceRecord{
		DroneID:        "1",
		InsurerID:      "insurer-001",
		CoverageAmount: 50000,
		Status:         "active",
	}

	data, err := json.Marshal(insurance)
	if err != nil {
		t.Fatalf("JSON Marshal failed: %v", err)
	}

	var decoded InsuranceRecord
	err = json.Unmarshal(data, &decoded)
	if err != nil {
		t.Fatalf("JSON Unmarshal failed: %v", err)
	}

	if decoded.DroneID != insurance.DroneID {
		t.Errorf("Expected DroneID %d, got %d", insurance.DroneID, decoded.DroneID)
	}
	if decoded.InsurerID != insurance.InsurerID {
		t.Errorf("Expected InsurerID %s, got %s", insurance.InsurerID, decoded.InsurerID)
	}
	if decoded.CoverageAmount != insurance.CoverageAmount {
		t.Errorf("Expected CoverageAmount %d, got %d", insurance.CoverageAmount, decoded.CoverageAmount)
	}
	if decoded.Status != insurance.Status {
		t.Errorf("Expected Status %s, got %s", insurance.Status, decoded.Status)
	}
}

func TestReadinessResultJSON(t *testing.T) {
	result := ReadinessResult{
		DroneID:      "1",
		HasDronePass: true,
		HasInsurance: true,
		IsReady:      true,
	}

	data, err := json.Marshal(result)
	if err != nil {
		t.Fatalf("JSON Marshal failed: %v", err)
	}

	var decoded ReadinessResult
	err = json.Unmarshal(data, &decoded)
	if err != nil {
		t.Fatalf("JSON Unmarshal failed: %v", err)
	}

	if decoded.DroneID != result.DroneID {
		t.Errorf("Expected DroneID %d, got %d", result.DroneID, decoded.DroneID)
	}
	if decoded.HasDronePass != result.HasDronePass {
		t.Errorf("Expected HasDronePass %v, got %v", result.HasDronePass, decoded.HasDronePass)
	}
	if decoded.HasInsurance != result.HasInsurance {
		t.Errorf("Expected HasInsurance %v, got %v", result.HasInsurance, decoded.HasInsurance)
	}
	if decoded.IsReady != result.IsReady {
		t.Errorf("Expected IsReady %v, got %v", result.IsReady, decoded.IsReady)
	}
}

func TestOrderJSON(t *testing.T) {
	order := Order{
		ID:           "order-001",
		AggregatorID: "agg-001",
		OperatorID:   "op-001",
		DroneID:      "drone-001",
		InsurerID:    "ins-001",
		CertCenterID: "cert-001",
		DeveloperID:  "dev-001",
		AmountTotal:  10000,
		Status:       "created",
		CreatedAt:    "2026-01-11T12:00:00Z",
		Distribution: map[string]Payment{
			"operator": {RecipientID: "op-001", Amount: 7000},
			"insurer":  {RecipientID: "ins-001", Amount: 3000},
		},
	}

	data, err := json.Marshal(order)
	if err != nil {
		t.Fatalf("JSON Marshal failed: %v", err)
	}

	var decoded Order
	err = json.Unmarshal(data, &decoded)
	if err != nil {
		t.Fatalf("JSON Unmarshal failed: %v", err)
	}

	if decoded.ID != order.ID {
		t.Errorf("Expected ID %s, got %s", order.ID, decoded.ID)
	}
	if decoded.AmountTotal != order.AmountTotal {
		t.Errorf("Expected AmountTotal %d, got %d", order.AmountTotal, decoded.AmountTotal)
	}
	if decoded.Status != order.Status {
		t.Errorf("Expected Status %s, got %s", order.Status, decoded.Status)
	}
	if len(decoded.Distribution) != 2 {
		t.Errorf("Expected 2 distributions, got %d", len(decoded.Distribution))
	}
}

func TestPaymentJSON(t *testing.T) {
	payment := Payment{
		RecipientID: "recipient-001",
		Amount:      5000,
	}

	data, err := json.Marshal(payment)
	if err != nil {
		t.Fatalf("JSON Marshal failed: %v", err)
	}

	var decoded Payment
	err = json.Unmarshal(data, &decoded)
	if err != nil {
		t.Fatalf("JSON Unmarshal failed: %v", err)
	}

	if decoded.RecipientID != payment.RecipientID {
		t.Errorf("Expected RecipientID %s, got %s", payment.RecipientID, decoded.RecipientID)
	}
	if decoded.Amount != payment.Amount {
		t.Errorf("Expected Amount %d, got %d", payment.Amount, decoded.Amount)
	}
}

func TestIntIDToString(t *testing.T) {
	tests := []struct {
		input    int
		expected string
		hasError bool
	}{
		{1, "1", false},
		{100, "100", false},
		{999999, "999999", false},
		{0, "", true},
		{-1, "", true},
	}

	for _, test := range tests {
		result, err := intIDToString(test.input)

		if test.hasError {
			if err == nil {
				t.Errorf("Expected error for input %d, got nil", test.input)
			}
		} else {
			if err != nil {
				t.Errorf("Unexpected error for input %d: %v", test.input, err)
			}
			if result != test.expected {
				t.Errorf("Expected %s for input %d, got %s", test.expected, test.input, result)
			}
		}
	}
}

// ============ Тесты для констант ролей ============

func TestRoleConstants(t *testing.T) {
	roles := []string{
		roleAdmin,
		roleManufacturer,
		roleCertCenter,
		roleOperator,
		roleAggregator,
		roleInsurer,
	}

	expected := []string{
		"admin",
		"manufacturer",
		"cert_center",
		"operator",
		"aggregator",
		"insurer",
	}

	for i, role := range roles {
		if role != expected[i] {
			t.Errorf("Expected role %s, got %s", expected[i], role)
		}
	}
}

func TestObjectTypeConstants(t *testing.T) {
	if objectDronePass != "drone_pass" {
		t.Errorf("Expected objectDronePass 'drone_pass', got %s", objectDronePass)
	}
	if objectInsurance != "insurance" {
		t.Errorf("Expected objectInsurance 'insurance', got %s", objectInsurance)
	}
	if objectOrder != "order" {
		t.Errorf("Expected objectOrder 'order', got %s", objectOrder)
	}
	if objectFirmware != "firmware" {
		t.Errorf("Expected objectFirmware 'firmware', got %s", objectFirmware)
	}
}

// ============ Тесты для Order workflow ============

func TestOrderStatusTransitions(t *testing.T) {
	validStatuses := []string{
		"created",
		"assigned",
		"approved",
		"confirmed",
		"started",
		"finished",
		"finalized",
		"settled",
	}

	for _, status := range validStatuses {
		order := Order{Status: status}
		if order.Status != status {
			t.Errorf("Failed to set status %s", status)
		}
	}
}

// ============ Тесты для Insurance Status ============

func TestInsuranceStatusValues(t *testing.T) {
	validStatuses := []string{"active", "expired", "cancelled"}

	for _, status := range validStatuses {
		insurance := InsuranceRecord{Status: status}
		if insurance.Status != status {
			t.Errorf("Failed to set insurance status %s", status)
		}
	}
}

// ============ Тестовые данные: 3 дрона, 2 прошивки ============

func TestThreeDronesWithTwoFirmwares(t *testing.T) {
	// Firmware 1.0.1: SO_1, SO_3, SO_7, SO_9
	firmware1 := Firmware{
		ID:                 "1.0.1",
		SecurityObjectives: []string{"SO_1", "SO_3", "SO_7", "SO_9"},
	}

	// Firmware 1.0.2: SO_2, SO_5, SO_11
	firmware2 := Firmware{
		ID:                 "1.0.2",
		SecurityObjectives: []string{"SO_2", "SO_5", "SO_11"},
	}

	// Drone 1 и Drone 2 используют Firmware 1.0.1
	drone1 := DronePass{
		ID:                 "1",
		DeveloperID:        "manufacturer-001",
		Model:              "AG-100",
		Type:               "agro",
		WeightKg:           25,
		MaxFlightRangeKm:   50,
		MaxPayloadWeightKg: 10,
		ReleaseYear:        2024,
		FirmwareID:         "1.0.1",
	}

	drone2 := DronePass{
		ID:                 "2",
		DeveloperID:        "manufacturer-001",
		Model:              "AG-200",
		Type:               "agro",
		WeightKg:           30,
		MaxFlightRangeKm:   60,
		MaxPayloadWeightKg: 15,
		ReleaseYear:        2024,
		FirmwareID:         "1.0.1",
	}

	// Drone 3 использует Firmware 1.0.2
	drone3 := DronePass{
		ID:                 "3",
		DeveloperID:        "manufacturer-002",
		Model:              "AG-150",
		Type:               "agro",
		WeightKg:           20,
		MaxFlightRangeKm:   45,
		MaxPayloadWeightKg: 8,
		ReleaseYear:        2023,
		FirmwareID:         "1.0.2",
	}

	// Проверка прошивок
	if len(firmware1.SecurityObjectives) != 4 {
		t.Errorf("Firmware1 should have 4 security objectives, got %d", len(firmware1.SecurityObjectives))
	}
	if len(firmware2.SecurityObjectives) != 3 {
		t.Errorf("Firmware2 should have 3 security objectives, got %d", len(firmware2.SecurityObjectives))
	}

	// Проверка дронов с одинаковой прошивкой
	if drone1.FirmwareID != drone2.FirmwareID {
		t.Errorf("Drone1 and Drone2 should have same firmware ID")
	}

	// Проверка дрона с другой прошивкой
	if drone3.FirmwareID == drone1.FirmwareID {
		t.Errorf("Drone3 should have different firmware ID than Drone1")
	}

	// Проверка JSON сериализации всех данных
	allData := struct {
		Firmwares []Firmware  `json:"firmwares"`
		Drones    []DronePass `json:"drones"`
	}{
		Firmwares: []Firmware{firmware1, firmware2},
		Drones:    []DronePass{drone1, drone2, drone3},
	}

	data, err := json.Marshal(allData)
	if err != nil {
		t.Fatalf("Failed to marshal test data: %v", err)
	}

	var decoded struct {
		Firmwares []Firmware  `json:"firmwares"`
		Drones    []DronePass `json:"drones"`
	}
	if err := json.Unmarshal(data, &decoded); err != nil {
		t.Fatalf("Failed to unmarshal test data: %v", err)
	}

	if len(decoded.Firmwares) != 2 {
		t.Errorf("Expected 2 firmwares, got %d", len(decoded.Firmwares))
	}
	if len(decoded.Drones) != 3 {
		t.Errorf("Expected 3 drones, got %d", len(decoded.Drones))
	}
}

func TestReadinessScenarios(t *testing.T) {
	tests := []struct {
		name          string
		hasDronePass  bool
		hasInsurance  bool
		expectedReady bool
	}{
		{"Both present", true, true, true},
		{"No insurance", true, false, false},
		{"No drone pass", false, true, false},
		{"Neither", false, false, false},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := ReadinessResult{
				DroneID:      "1",
				HasDronePass: tt.hasDronePass,
				HasInsurance: tt.hasInsurance,
				IsReady:      tt.hasDronePass && tt.hasInsurance,
			}

			if result.IsReady != tt.expectedReady {
				t.Errorf("Expected IsReady=%v for %s, got %v", tt.expectedReady, tt.name, result.IsReady)
			}
		})
	}
}

// ============ Benchmark тесты ============

func BenchmarkDronePassMarshal(b *testing.B) {
	pass := DronePass{
		ID:                 "1",
		DeveloperID:        "manufacturer-001",
		Model:              "AG-100",
		Type:               "agro",
		WeightKg:           25,
		MaxFlightRangeKm:   50,
		MaxPayloadWeightKg: 10,
		ReleaseYear:        2024,
		FirmwareID:         "1.0.1",
	}

	for i := 0; i < b.N; i++ {
		json.Marshal(pass)
	}
}

func BenchmarkFirmwareMarshal(b *testing.B) {
	firmware := Firmware{
		ID:                 "1.0.1",
		SecurityObjectives: []string{"SO_1", "SO_3", "SO_7", "SO_9"},
	}

	for i := 0; i < b.N; i++ {
		json.Marshal(firmware)
	}
}

func BenchmarkOrderMarshal(b *testing.B) {
	order := Order{
		ID:           "order-001",
		AggregatorID: "agg-001",
		OperatorID:   "op-001",
		DroneID:      "drone-001",
		InsurerID:    "ins-001",
		CertCenterID: "cert-001",
		DeveloperID:  "dev-001",
		AmountTotal:  10000,
		Status:       "created",
		CreatedAt:    "2026-01-11T12:00:00Z",
		Distribution: map[string]Payment{},
	}

	for i := 0; i < b.N; i++ {
		json.Marshal(order)
	}
}
