package contracts

import (
	"encoding/json"
	"fmt"
	"time"

	"github.com/hyperledger/fabric-chaincode-go/pkg/cid"
	"github.com/hyperledger/fabric-contract-api-go/contractapi"
)

type Order struct {
	ID                      string             `json:"id"`
	AggregatorID            string             `json:"aggregator_id"`
	OperatorID              string             `json:"operator_id"`
	DroneID                 string             `json:"drone_id"`
	InsurerID               string             `json:"insurer_id"`
	CertCenterID            string             `json:"cert_center_id"`
	DeveloperID             string             `json:"manufacturer_id"`
	AmountTotal             int                `json:"amount_total"`
	Status                  string             `json:"status"`
	CreatedAt               string             `json:"created_at"`
	Distribution            map[string]Payment `json:"distribution"`
	InsuranceCoverageAmount int                `json:"insurance_coverage_amount"`
	MissionInsuranceID      string             `json:"mission_insurance_id"`
	FlightPermissionID      string             `json:"flight_permission_id"`
	Details                 []OrderDetail      `json:"details"`
}

type Payment struct {
	RecipientID string `json:"recipient_id"`
	Amount      int    `json:"amount"`
}

type OrderDetail struct {
	DroneID            string   `json:"drone_id"`
	SecurityObjectives []string `json:"security_objectives"`
	EnvironmentalLimit []string `json:"environmental_limit"`
	OperationArea      string   `json:"operation_area"`
}

type MissionInsurance struct {
	ID             string `json:"id"`
	OrderID        string `json:"order_id"`
	DroneID        string `json:"drone_id"`
	InsurerID      string `json:"insurer_id"`
	CoverageAmount int    `json:"coverage_amount"`
	Status         string `json:"status"`
	IncidentReport string `json:"incident_report"`
}

type FlightPermission struct {
	ID           string `json:"id"`
	OrderID      string `json:"order_id"`
	Status       string `json:"status"`
	ValidFrom    string `json:"valid_from"`
	ValidTo      string `json:"valid_to"`
	ApprovedBy   string `json:"approved_by"`
	RejectReason string `json:"reject_reason"`
}

type RestrictionViolation struct {
	ID         string `json:"id"`
	OrderID    string `json:"order_id"`
	DroneID    string `json:"drone_id"`
	Rule       string `json:"rule"`
	Timestamp  string `json:"timestamp"`
	ReportedBy string `json:"reported_by"`
}

type OrderContract struct {
	contractapi.Contract
}

const defaultRiskReserveID = "risk_reserve"

func (c *OrderContract) CreateOrder(
	ctx contractapi.TransactionContextInterface,
	id string,
	aggregatorID string,
	operatorID string,
	droneID string,
	insurerID string,
	certCenterID string,
	developerID string,
	fleetPrice int,
	aggregatorFee int,
	insurancePremium int,
	riskReserve int,
	insuranceCoverageAmount int,
	missionInsuranceID string,
	details []OrderDetail,
) error {
	if err := assertRole(ctx, roleAggregator, roleAdmin); err != nil {
		return err
	}

	exists, err := c.orderExists(ctx, id)
	if err != nil {
		return err
	}
	if exists {
		return fmt.Errorf("order %s already exists", id)
	}

	now := time.Now().UTC().Format(time.RFC3339)

	distribution, finalAmount, err := calculateOrderDistribution(
		fleetPrice,
		aggregatorFee,
		insurancePremium,
		riskReserve,
		aggregatorID,
		operatorID,
		insurerID,
		certCenterID,
	)
	if err != nil {
		return err
	}

	order := Order{
		ID:                      id,
		AggregatorID:            aggregatorID,
		OperatorID:              operatorID,
		DroneID:                 droneID,
		InsurerID:               insurerID,
		CertCenterID:            certCenterID,
		DeveloperID:             developerID,
		AmountTotal:             finalAmount,
		Status:                  "created",
		CreatedAt:               now,
		Distribution:            distribution,
		InsuranceCoverageAmount: insuranceCoverageAmount,
		MissionInsuranceID:      missionInsuranceID,
		Details:                 details,
	}

	key, err := makeCompositeKey(ctx, objectOrder, id)
	if err != nil {
		return err
	}
	return putState(ctx, key, order)
}

func (c *OrderContract) AssignOrder(ctx contractapi.TransactionContextInterface, id string, operatorID string, droneID string, details []OrderDetail) error {
	if err := assertRole(ctx, roleAggregator, roleAdmin); err != nil {
		return err
	}

	order, err := c.ReadOrder(ctx, id)
	if err != nil {
		return err
	}

	order.OperatorID = operatorID
	order.DroneID = droneID
	if details != nil {
		order.Details = details
	}
	order.Status = "assigned"

	key, err := makeCompositeKey(ctx, objectOrder, id)
	if err != nil {
		return err
	}
	return putState(ctx, key, order)
}

func (c *OrderContract) ApproveOrder(ctx contractapi.TransactionContextInterface, id string) error {
	if err := assertRole(ctx, roleInsurer, roleAdmin); err != nil {
		return err
	}
	order, err := c.ReadOrder(ctx, id)
	if err != nil {
		return err
	}
	order.Status = "approved"
	key, err := makeCompositeKey(ctx, objectOrder, id)
	if err != nil {
		return err
	}
	return putState(ctx, key, order)
}

func (c *OrderContract) ConfirmOrder(ctx contractapi.TransactionContextInterface, id string) error {
	if err := assertRole(ctx, roleOperator, roleAdmin); err != nil {
		return err
	}
	order, err := c.ReadOrder(ctx, id)
	if err != nil {
		return err
	}
	order.Status = "confirmed"
	key, err := makeCompositeKey(ctx, objectOrder, id)
	if err != nil {
		return err
	}
	return putState(ctx, key, order)
}

func (c *OrderContract) StartOrder(ctx contractapi.TransactionContextInterface, id string) error {
	if err := assertRole(ctx, roleOperator, roleAdmin); err != nil {
		return err
	}

	order, err := c.ReadOrder(ctx, id)
	if err != nil {
		return err
	}

	if order.FlightPermissionID == "" {
		return fmt.Errorf("Нет разрешения ОрВД для заказа %s", id)
	}

	permission, err := c.ReadFlightPermission(ctx, order.FlightPermissionID)
	if err != nil {
		return err
	}

	if permission.Status != "approved" {
		return fmt.Errorf("Разрешение ОрВД не одобрено, статус: %s", permission.Status)
	}

	now := time.Now().UTC()
	validFrom, _ := time.Parse(time.RFC3339, permission.ValidFrom)
	validTo, _ := time.Parse(time.RFC3339, permission.ValidTo)

	if now.Before(validFrom) {
		return fmt.Errorf("Полет еще нельзя начать, разрешение с %s", permission.ValidFrom)
	}
	if now.After(validTo) {
		return fmt.Errorf("Срок действия разрешения истек %s", permission.ValidTo)
	}

	if len(order.Details) > 0 && order.Details[0].OperationArea != "" {
		conflict, msg, err := c.CheckZoneConflict(ctx, order.Details[0].OperationArea, now.Format(time.RFC3339))
		if err != nil {
			return err
		}
		if conflict {
			return fmt.Errorf("Обнаружен конфликт с запретной зоной: %s", msg)
		}
	}

	order.Status = "started"

	key, err := makeCompositeKey(ctx, objectOrder, id)
	if err != nil {
		return err
	}
	return putState(ctx, key, order)
}

func (c *OrderContract) FinishOrder(ctx contractapi.TransactionContextInterface, id string) error {
	if err := assertRole(ctx, roleOperator, roleAdmin); err != nil {
		return err
	}
	order, err := c.ReadOrder(ctx, id)
	if err != nil {
		return err
	}
	order.Status = "finished"
	key, err := makeCompositeKey(ctx, objectOrder, id)
	if err != nil {
		return err
	}
	return putState(ctx, key, order)
}

func (c *OrderContract) FinalizeOrder(ctx contractapi.TransactionContextInterface, id string) error {
	if err := assertRole(ctx, roleAggregator, roleAdmin); err != nil {
		return err
	}
	order, err := c.ReadOrder(ctx, id)
	if err != nil {
		return err
	}
	order.Status = "finalized"
	key, err := makeCompositeKey(ctx, objectOrder, id)
	if err != nil {
		return err
	}
	return putState(ctx, key, order)
}

func (c *OrderContract) DistributeFunds(ctx contractapi.TransactionContextInterface, id string, distribution map[string]Payment, notes string) error {
	if err := assertRole(ctx, roleAggregator, roleAdmin); err != nil {
		return err
	}
	order, err := c.ReadOrder(ctx, id)
	if err != nil {
		return err
	}
	order.Distribution = distribution
	order.Status = "settled"
	key, err := makeCompositeKey(ctx, objectOrder, id)
	if err != nil {
		return err
	}
	return putState(ctx, key, order)
}

func (c *OrderContract) ReadOrder(ctx contractapi.TransactionContextInterface, id string) (*Order, error) {
	key, err := makeCompositeKey(ctx, objectOrder, id)
	if err != nil {
		return nil, err
	}
	bytes, err := ctx.GetStub().GetState(key)
	if err != nil {
		return nil, err
	}
	if bytes == nil {
		return nil, fmt.Errorf("order %s not found", id)
	}
	var order Order
	if err := json.Unmarshal(bytes, &order); err != nil {
		return nil, err
	}
	return &order, nil
}

func (c *OrderContract) orderExists(ctx contractapi.TransactionContextInterface, id string) (bool, error) {
	key, err := makeCompositeKey(ctx, objectOrder, id)
	if err != nil {
		return false, err
	}
	bytes, err := ctx.GetStub().GetState(key)
	if err != nil {
		return false, err
	}
	return bytes != nil, nil
}

func calculateOrderDistribution(
	fleetPrice int,
	aggregatorFee int,
	insurancePremium int,
	riskReserve int,
	aggregatorID string,
	operatorID string,
	insurerID string,
	certCenterID string,
) (map[string]Payment, int, error) {
	if fleetPrice < 0 || aggregatorFee < 0 || insurancePremium < 0 || riskReserve < 0 {
		return nil, 0, fmt.Errorf("amounts must be non-negative")
	}

	finalTotal := fleetPrice + aggregatorFee + insurancePremium + riskReserve

	distribution := map[string]Payment{
		"operator":     {RecipientID: operatorID, Amount: fleetPrice},
		"aggregator":   {RecipientID: aggregatorID, Amount: aggregatorFee},
		"insurer":      {RecipientID: insurerID, Amount: insurancePremium},
		"cert_center":  {RecipientID: certCenterID, Amount: 0},
		"risk_reserve": {RecipientID: defaultRiskReserveID, Amount: riskReserve},
	}

	return distribution, finalTotal, nil
}

// ============ Drone Readiness Check ============

type ReadinessResult struct {
	DroneID      string `json:"drone_id"`
	HasDronePass bool   `json:"has_drone_pass"`
	HasInsurance bool   `json:"has_insurance"`
	IsReady      bool   `json:"is_ready"`
}

func (c *OrderContract) CheckDroneReadiness(
	ctx contractapi.TransactionContextInterface,
	droneID string,
) (*ReadinessResult, error) {
	result := &ReadinessResult{
		DroneID: droneID,
	}

	// Check if drone pass exists
	dronePassKey, err := makeCompositeKey(ctx, objectDronePass, droneID)
	if err != nil {
		return nil, err
	}
	dronePassBytes, err := ctx.GetStub().GetState(dronePassKey)
	if err != nil {
		return nil, err
	}
	result.HasDronePass = dronePassBytes != nil

	// Check if active insurance exists
	insuranceKey, err := makeCompositeKey(ctx, objectInsurance, droneID)
	if err != nil {
		return nil, err
	}
	insuranceBytes, err := ctx.GetStub().GetState(insuranceKey)
	if err != nil {
		return nil, err
	}

	if insuranceBytes != nil {
		var insurance InsuranceRecord
		if err := json.Unmarshal(insuranceBytes, &insurance); err == nil {
			result.HasInsurance = insurance.Status == "active"
		}
	}

	// Drone is ready if both conditions are met
	result.IsReady = result.HasDronePass && result.HasInsurance

	return result, nil
}

// Функции по страховке миссии

func (c *OrderContract) CalculateMissionInsurance(
	ctx contractapi.TransactionContextInterface,
	droneID string,
	flightDuration int,
	riskLevel string,
) (int, error) {
	// Пока что заглушка
	return 1000, nil
}

func (c *OrderContract) CreateMissionInsurance(
	ctx contractapi.TransactionContextInterface,
	id string,
	orderID string,
	droneID string,
	insurerID string,
	coverageAmount int,
	incidentReport string,
) error {
	if err := assertRole(ctx, roleInsurer, roleAdmin); err != nil {
		return err
	}

	baseKey, err := makeCompositeKey(ctx, objectInsurance, droneID)
	if err != nil {
		return err
	}

	baseBytes, err := ctx.GetStub().GetState(baseKey)
	if err != nil {
		return err
	}
	if baseBytes == nil {
		return fmt.Errorf("Общая страховка для дрона %s не найдена", droneID)
	}

	var baseInsurance InsuranceRecord
	if err := json.Unmarshal(baseBytes, &baseInsurance); err != nil {
		return err
	}

	if baseInsurance.Status != "active" {
		return fmt.Errorf("Общая страховка не активна, статус: %s", baseInsurance.Status)
	}

	exists, err := c.missionInsuranceExists(ctx, id)
	if err != nil {
		return err
	}
	if exists {
		return fmt.Errorf("Страховка на миссию %s уже существует", id)
	}

	missionInsurance := MissionInsurance{
		ID:             id,
		OrderID:        orderID,
		DroneID:        droneID,
		InsurerID:      insurerID,
		CoverageAmount: coverageAmount,
		Status:         "active",
		IncidentReport: incidentReport,
	}

	key, err := makeCompositeKey(ctx, objectMissionInsurance, id)
	if err != nil {
		return err
	}

	return putState(ctx, key, missionInsurance)
}

func (c *OrderContract) ReadMissionInsurance(
	ctx contractapi.TransactionContextInterface,
	id string,
) (*MissionInsurance, error) {
	key, err := makeCompositeKey(ctx, objectMissionInsurance, id)
	if err != nil {
		return nil, err
	}

	bytes, err := ctx.GetStub().GetState(key)
	if err != nil {
		return nil, err
	}
	if bytes == nil {
		return nil, fmt.Errorf("Страховка на мисиию %s не найдена", id)
	}

	var missionInsurance MissionInsurance
	if err := json.Unmarshal(bytes, &missionInsurance); err != nil {
		return nil, err
	}
	return &missionInsurance, nil
}

func (c *OrderContract) UpdateMissionInsuranceStatus(
	ctx contractapi.TransactionContextInterface,
	id string,
	status string,
) error {
	if err := assertRole(ctx, roleInsurer, roleAdmin); err != nil {
		return err
	}

	validStatuses := map[string]bool{
		"active":  true,
		"used":    true,
		"expired": true,
	}
	if !validStatuses[status] {
		return fmt.Errorf("Невалидный статус: %s", status)
	}

	missionInsurance, err := c.ReadMissionInsurance(ctx, id)
	if err != nil {
		return err
	}

	missionInsurance.Status = status

	key, err := makeCompositeKey(ctx, objectMissionInsurance, id)
	if err != nil {
		return err
	}

	return putState(ctx, key, missionInsurance)
}

func (c *OrderContract) missionInsuranceExists(
	ctx contractapi.TransactionContextInterface,
	id string,
) (bool, error) {
	key, err := makeCompositeKey(ctx, objectMissionInsurance, id)
	if err != nil {
		return false, err
	}

	bytes, err := ctx.GetStub().GetState(key)
	if err != nil {
		return false, err
	}
	return bytes != nil, nil
}

// Проверка требуемых целей безопасностей

func (c *OrderContract) validateDroneFirmware(
	ctx contractapi.TransactionContextInterface,
	droneID string,
	requiredObjectives []string,
) error {

	dronePassKey, err := makeCompositeKey(ctx, objectDronePass, droneID)
	if err != nil {
		return err
	}

	dronePassBytes, err := ctx.GetStub().GetState(dronePassKey)
	if err != nil {
		return err
	}
	if dronePassBytes == nil {
		return fmt.Errorf("Дрон %s не найден", droneID)
	}

	var dronePass DronePass
	if err := json.Unmarshal(dronePassBytes, &dronePass); err != nil {
		return err
	}

	if dronePass.FirmwareID == "" {
		return fmt.Errorf("У дрона %s не указана прошивка", droneID)
	}

	firmwareKey, err := makeFirmwareKey(ctx, dronePass.FirmwareID)
	if err != nil {
		return err
	}

	firmwareBytes, err := ctx.GetStub().GetState(firmwareKey)
	if err != nil {
		return err
	}
	if firmwareBytes == nil {
		return fmt.Errorf("Прошивка %s не найдена", dronePass.FirmwareID)
	}

	var firmware Firmware
	if err := json.Unmarshal(firmwareBytes, &firmware); err != nil {
		return err
	}

	if len(requiredObjectives) > 0 {
		firmwareObjectives := make(map[string]bool)
		for _, obj := range firmware.SecurityObjectives {
			firmwareObjectives[obj] = true
		}

		missingObjectives := []string{}
		for _, required := range requiredObjectives {
			if !firmwareObjectives[required] {
				missingObjectives = append(missingObjectives, required)
			}
		}

		if len(missingObjectives) > 0 {
			return fmt.Errorf("Прошивка %s не поддерживает требуемые security objectives: %v",
				dronePass.FirmwareID, missingObjectives)
		}
	}
	return nil
}

// Функции ОрВД и регулятора

func (c *OrderContract) RequestFlightPermission(
	ctx contractapi.TransactionContextInterface,
	orderID string,
	validFrom string,
	validTo string,
) error {
	if err := assertRole(ctx, roleAggregator, roleOperator, roleAdmin); err != nil {
		return err
	}

	order, err := c.ReadOrder(ctx, orderID)
	if err != nil {
		return err
	}

	permissionID := fmt.Sprintf("PERM-%s", orderID)

	exists, err := c.flightPermissionExists(ctx, permissionID)
	if err != nil {
		return err
	}
	if exists {
		return fmt.Errorf("Разрешение %s уже существует", permissionID)
	}

	permission := FlightPermission{
		ID:        permissionID,
		OrderID:   orderID,
		Status:    "requested",
		ValidFrom: validFrom,
		ValidTo:   validTo,
	}

	key, err := makeCompositeKey(ctx, objectFlightPermission, permissionID)
	if err != nil {
		return err
	}

	order.FlightPermissionID = permissionID
	orderKey, err := makeCompositeKey(ctx, objectOrder, orderID)
	if err != nil {
		return err
	}
	if err := putState(ctx, orderKey, order); err != nil {
		return err
	}

	return putState(ctx, key, permission)
}

func (c *OrderContract) ApproveFlightPermission(
	ctx contractapi.TransactionContextInterface,
	permissionID string,
) error {
	if err := assertRole(ctx, roleOrvd, roleAdmin); err != nil {
		return err
	}

	permission, err := c.ReadFlightPermission(ctx, permissionID)
	if err != nil {
		return err
	}

	if permission.Status != "requested" {
		return fmt.Errorf("Разрешение уже обработано, статус: %s", permission.Status)
	}

	approverID, err := cid.GetID(ctx.GetStub())
	if err != nil {
		approverID = "orvd"
	}

	permission.Status = "approved"
	permission.ApprovedBy = approverID

	key, err := makeCompositeKey(ctx, objectFlightPermission, permissionID)
	if err != nil {
		return err
	}

	return putState(ctx, key, permission)
}

func (c *OrderContract) RejectFlightPermission(
	ctx contractapi.TransactionContextInterface,
	permissionID string,
	reason string,
) error {
	if err := assertRole(ctx, roleOrvd, roleAdmin); err != nil {
		return err
	}

	permission, err := c.ReadFlightPermission(ctx, permissionID)
	if err != nil {
		return err
	}

	if permission.Status != "requested" {
		return fmt.Errorf("Разрешение уже обработано, статус: %s", permission.Status)
	}

	permission.Status = "rejected"
	permission.RejectReason = reason

	key, err := makeCompositeKey(ctx, objectFlightPermission, permissionID)
	if err != nil {
		return err
	}

	return putState(ctx, key, permission)
}

func (c *OrderContract) ReadFlightPermission(
	ctx contractapi.TransactionContextInterface,
	permissionID string,
) (*FlightPermission, error) {
	key, err := makeCompositeKey(ctx, objectFlightPermission, permissionID)
	if err != nil {
		return nil, err
	}

	bytes, err := ctx.GetStub().GetState(key)
	if err != nil {
		return nil, err
	}
	if bytes == nil {
		return nil, fmt.Errorf("Разрешение %s не найдено", permissionID)
	}

	var permission FlightPermission
	if err := json.Unmarshal(bytes, &permission); err != nil {
		return nil, err
	}
	return &permission, nil
}

func (c *OrderContract) CloseFlightPermission(
	ctx contractapi.TransactionContextInterface,
	permissionID string,
) error {
	if err := assertRole(ctx, roleOperator, roleAggregator, roleAdmin); err != nil {
		return err
	}

	permission, err := c.ReadFlightPermission(ctx, permissionID)
	if err != nil {
		return err
	}

	if permission.Status != "approved" {
		return fmt.Errorf("Можно закрыть только одобренное разрешение, статус: %s", permission.Status)
	}

	permission.Status = "closed"

	key, err := makeCompositeKey(ctx, objectFlightPermission, permissionID)
	if err != nil {
		return err
	}

	return putState(ctx, key, permission)
}

func (c *OrderContract) flightPermissionExists(
	ctx contractapi.TransactionContextInterface,
	permissionID string,
) (bool, error) {
	key, err := makeCompositeKey(ctx, objectFlightPermission, permissionID)
	if err != nil {
		return false, err
	}
	bytes, err := ctx.GetStub().GetState(key)
	if err != nil {
		return false, err
	}
	return bytes != nil, nil
}

func (c *OrderContract) ReportViolation(
	ctx contractapi.TransactionContextInterface,
	orderID string,
	droneID string,
	rule string,
) error {
	if err := assertRole(ctx, roleRegulator, roleAdmin); err != nil {
		return err
	}

	_, err := c.ReadOrder(ctx, orderID)
	if err != nil {
		return fmt.Errorf("Заказ %s не найден: %v", orderID, err)
	}

	violationID := fmt.Sprintf("VIO-%s-%d", orderID, time.Now().UnixNano())

	violation := RestrictionViolation{
		ID:         violationID,
		OrderID:    orderID,
		DroneID:    droneID,
		Rule:       rule,
		Timestamp:  time.Now().UTC().Format(time.RFC3339),
		ReportedBy: "regulator",
	}

	key, err := makeCompositeKey(ctx, objectRestrictionViolation, violationID)
	if err != nil {
		return err
	}

	return putState(ctx, key, violation)
}

func (c *OrderContract) CheckZoneConflict(
	ctx contractapi.TransactionContextInterface,
	area string,
	flightTime string,
) (bool, string, error) {
	return false, "", nil
}
