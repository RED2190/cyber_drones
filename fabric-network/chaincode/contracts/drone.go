package contracts

import (
	"encoding/json"
	"fmt"
	"strconv"
	"time"

	"github.com/hyperledger/fabric-chaincode-go/pkg/cid"
	"github.com/hyperledger/fabric-contract-api-go/contractapi"
)

const (
	roleAdmin        = "admin"
	roleManufacturer = "manufacturer"
	roleCertCenter   = "cert_center"
	roleOperator     = "operator"
	roleAggregator   = "aggregator"
	roleInsurer      = "insurer"
	roleOrvd         = "orvd"
	roleRegulator    = "regulator"
)

const (
	objectDronePass            = "drone_pass"
	objectInsurance            = "insurance"
	objectOrder                = "order"
	objectFlightPermission     = "flight_permission"
	objectMissionInsurance     = "mission_insurance"
	objectRestrictionViolation = "restriction_violation"
	objectTypeCertificate      = "type_certificate"
)

type TypeCertificate struct {
	ID                 string   `json:"id"`
	Model              string   `json:"model"`
	ManufacturerID     string   `json:"manufacturer_id"`
	HardwareObjectives []string `json:"hardware_objectives"`
}

type DronePass struct {
	ID                 string `json:"id"`
	DeveloperID        string `json:"manufacturer_id"`
	Model              string `json:"model"`
	Type               string `json:"type"`
	WeightKg           int    `json:"weight_kg"`
	MaxFlightRangeKm   int    `json:"max_flight_range_km"`
	MaxPayloadWeightKg int    `json:"max_payload_weight_kg"`
	ReleaseYear        int    `json:"release_year"`
	FirmwareID         string `json:"firmware_id"`
	TypeCertificateID  string `json:"type_certificate_id"`
}

type InsuranceRecord struct {
	DroneID        string `json:"drone_id"`
	InsurerID      string `json:"insurer_id"`
	CoverageAmount int    `json:"coverage_amount"`
	IncidentCount  int    `json:"incident_count"`
	Status         string `json:"status"`
	ValidFrom      string `json:"valid_from"`
	ValidTo        string `json:"valid_to"`
}

type IncidentRecord struct {
	ID          string             `json:"id"` //
	DroneID     string             `json:"drone_id"`
	OrderID     string             `json:"order_id,omitempty"`
	Type        string             `json:"type"`
	Timestamp   time.Time          `json:"timestamp"`
	Description string             `json:"description,omitempty"`
	Reporter    string             `json:"reporter"`
	Status      string             `json:"status"`
	Evidence    []IncidentEvidence `json:"evidence"`
}

type IncidentEvidence struct {
	EvidenceType string    `json:"evidence_type"`
	FileHash     string    `json:"file_hash"`
	Timestamp    time.Time `json:"timestamp"`
}

type DronePropertiesContract struct {
	contractapi.Contract
}

func (c *DronePropertiesContract) IssueTypeCertificate(
	ctx contractapi.TransactionContextInterface,
	id string,
	model string,
	manufacturerID string,
	hardwareObjectives []string,
) error {
	if err := assertRole(ctx, roleCertCenter, roleAdmin); err != nil {
		return err
	}

	exists, err := c.typeCertificateExists(ctx, id)
	if err != nil {
		return err
	}
	if exists {
		return fmt.Errorf("type certificate %s already exists", id)
	}

	cert := TypeCertificate{
		ID:                 id,
		Model:              model,
		ManufacturerID:     manufacturerID,
		HardwareObjectives: hardwareObjectives,
	}

	key, err := makeCompositeKey(ctx, objectTypeCertificate, id)
	if err != nil {
		return err
	}

	ctx.GetStub().SetEvent("TypeCertificateIssued", []byte(id))

	return putState(ctx, key, cert)
}

func (c *DronePropertiesContract) typeCertificateExists(
	ctx contractapi.TransactionContextInterface,
	id string,
) (bool, error) {
	key, err := makeCompositeKey(ctx, objectTypeCertificate, id)
	if err != nil {
		return false, err
	}
	bytes, err := ctx.GetStub().GetState(key)
	if err != nil {
		return false, err
	}
	return bytes != nil, nil
}

func (c *DronePropertiesContract) CreateDronePass(
	ctx contractapi.TransactionContextInterface,
	id string,
	developerID string,
	model string,
	droneType string,
	weightKg int,
	maxFlightRangeKm int,
	maxPayloadWeightKg int,
	releaseYear int,
	firmwareID string,
	typeCertificateID string,
) error {
	if err := assertRole(ctx, roleCertCenter, roleAdmin); err != nil {
		return err
	}

	exists, err := c.dronePassExists(ctx, id)
	if err != nil {
		return err
	}
	if exists {
		return fmt.Errorf("drone pass %d already exists", id)
	}

	certKey, err := makeCompositeKey(ctx, objectTypeCertificate, typeCertificateID)
	if err != nil {
		return err
	}
	certBytes, err := ctx.GetStub().GetState(certKey)
	if err != nil {
		return err
	}
	if certBytes == nil {
		return fmt.Errorf("type certificate %s not found", typeCertificateID)
	}

	firmwareKey, err := makeFirmwareKey(ctx, firmwareID)
	if err != nil {
		return err
	}
	firmwareBytes, err := ctx.GetStub().GetState(firmwareKey)
	if err != nil {
		return err
	}
	if firmwareBytes == nil {
		return fmt.Errorf("firmware %s not found", firmwareID)
	}

	pass := DronePass{
		ID:                 id,
		DeveloperID:        developerID,
		Model:              model,
		Type:               droneType,
		WeightKg:           weightKg,
		MaxFlightRangeKm:   maxFlightRangeKm,
		MaxPayloadWeightKg: maxPayloadWeightKg,
		ReleaseYear:        releaseYear,
		FirmwareID:         firmwareID,
		TypeCertificateID:  typeCertificateID,
	}

	key, err := makeCompositeKey(ctx, objectDronePass, id)
	if err != nil {
		return err
	}
	return putState(ctx, key, pass)
}

func (c *DronePropertiesContract) ReadDronePass(ctx contractapi.TransactionContextInterface, id string) (*DronePass, error) {
	key, err := makeCompositeKey(ctx, objectDronePass, id)
	if err != nil {
		return nil, err
	}

	bytes, err := ctx.GetStub().GetState(key)
	if err != nil {
		return nil, err
	}
	if bytes == nil {
		return nil, fmt.Errorf("drone pass %d not found", id)
	}

	var pass DronePass
	if err := json.Unmarshal(bytes, &pass); err != nil {
		return nil, err
	}
	return &pass, nil
}

func (c *DronePropertiesContract) UpdateDronePass(
	ctx contractapi.TransactionContextInterface,
	id string,
	developerID string,
	model string,
	droneType string,
	weightKg int,
	maxFlightRangeKm int,
	maxPayloadWeightKg int,
	releaseYear int,
	firmwareID string,
	typeCertificateID string,
) error {
	if err := assertRole(ctx, roleCertCenter, roleAdmin); err != nil {
		return err
	}

	pass, err := c.ReadDronePass(ctx, id)
	if err != nil {
		return err
	}

	pass.DeveloperID = developerID
	pass.Model = model
	pass.Type = droneType
	pass.WeightKg = weightKg
	pass.MaxFlightRangeKm = maxFlightRangeKm
	pass.MaxPayloadWeightKg = maxPayloadWeightKg
	pass.ReleaseYear = releaseYear
	pass.FirmwareID = firmwareID
	pass.TypeCertificateID = typeCertificateID

	key, err := makeCompositeKey(ctx, objectDronePass, id)
	if err != nil {
		return err
	}
	return putState(ctx, key, pass)
}

func (c *DronePropertiesContract) DeleteDronePass(ctx contractapi.TransactionContextInterface, id string) error {
	if err := assertRole(ctx, roleCertCenter, roleAdmin); err != nil {
		return err
	}

	key, err := makeCompositeKey(ctx, objectDronePass, id)
	if err != nil {
		return err
	}

	exists, err := c.dronePassExists(ctx, id)
	if err != nil {
		return err
	}
	if !exists {
		return fmt.Errorf("drone pass %d not found", id)
	}

	return ctx.GetStub().DelState(key)
}

func (c *DronePropertiesContract) ListDronePasses(ctx contractapi.TransactionContextInterface) ([]*DronePass, error) {
	resultsIterator, err := ctx.GetStub().GetStateByPartialCompositeKey(objectDronePass, []string{})
	if err != nil {
		return nil, err
	}
	defer resultsIterator.Close()

	var items []*DronePass
	for resultsIterator.HasNext() {
		result, err := resultsIterator.Next()
		if err != nil {
			return nil, err
		}

		var pass DronePass
		if err := json.Unmarshal(result.Value, &pass); err != nil {
			continue
		}
		if pass.ID != "" {
			items = append(items, &pass)
		}
	}
	return items, nil
}

func (c *DronePropertiesContract) dronePassExists(ctx contractapi.TransactionContextInterface, id string) (bool, error) {
	key, err := makeCompositeKey(ctx, objectDronePass, id)
	if err != nil {
		return false, err
	}
	bytes, err := ctx.GetStub().GetState(key)
	if err != nil {
		return false, err
	}
	return bytes != nil, nil
}

// ============ Insurance Record Functions ============

func (c *DronePropertiesContract) CreateInsuranceRecord(
	ctx contractapi.TransactionContextInterface,
	droneID string,
	insurerID string,
	coverageAmount int,
	incidentCount int,
	validFrom string,
	validTo string,
) error {
	if err := assertRole(ctx, roleInsurer, roleAdmin); err != nil {
		return err
	}

	exists, err := c.insuranceExists(ctx, droneID)
	if err != nil {
		return err
	}
	if exists {
		return fmt.Errorf("insurance record for drone %d already exists", droneID)
	}

	record := InsuranceRecord{
		DroneID:        droneID,
		InsurerID:      insurerID,
		CoverageAmount: coverageAmount,
		IncidentCount:  incidentCount,
		Status:         "active",
		ValidFrom:      validFrom,
		ValidTo:        validTo,
	}

	key, err := makeCompositeKey(ctx, objectInsurance, droneID)
	if err != nil {
		return err
	}
	return putState(ctx, key, record)
}

func (c *DronePropertiesContract) ReadInsuranceRecord(
	ctx contractapi.TransactionContextInterface,
	droneID string,
) (*InsuranceRecord, error) {
	key, err := makeCompositeKey(ctx, objectInsurance, droneID)
	if err != nil {
		return nil, err
	}

	bytes, err := ctx.GetStub().GetState(key)
	if err != nil {
		return nil, err
	}
	if bytes == nil {
		return nil, fmt.Errorf("insurance record for drone %d not found", droneID)
	}

	var record InsuranceRecord
	if err := json.Unmarshal(bytes, &record); err != nil {
		return nil, err
	}
	return &record, nil
}

func (c *DronePropertiesContract) UpdateInsuranceStatus(
	ctx contractapi.TransactionContextInterface,
	droneID string,
	status string,
) error {
	if err := assertRole(ctx, roleInsurer, roleAdmin); err != nil {
		return err
	}

	record, err := c.ReadInsuranceRecord(ctx, droneID)
	if err != nil {
		return err
	}

	// Validate status
	validStatuses := map[string]bool{"active": true, "expired": true, "cancelled": true}
	if !validStatuses[status] {
		return fmt.Errorf("invalid status: %s (must be active, expired, or cancelled)", status)
	}

	record.Status = status

	key, err := makeCompositeKey(ctx, objectInsurance, droneID)
	if err != nil {
		return err
	}
	return putState(ctx, key, record)
}

func (c *DronePropertiesContract) insuranceExists(ctx contractapi.TransactionContextInterface, droneID string) (bool, error) {
	key, err := makeCompositeKey(ctx, objectInsurance, droneID)
	if err != nil {
		return false, err
	}
	bytes, err := ctx.GetStub().GetState(key)
	if err != nil {
		return false, err
	}
	return bytes != nil, nil
}

func (c *DronePropertiesContract) UpdateIncidentCount(
	ctx contractapi.TransactionContextInterface,
	droneID string,
	newCount int,
) error {
	if err := assertRole(ctx, roleInsurer, roleAdmin); err != nil {
		return err
	}

	if newCount < 0 {
		return fmt.Errorf("incident count cannot be negative: %d", newCount)
	}

	record, err := c.ReadInsuranceRecord(ctx, droneID)
	if err != nil {
		return err
	}

	if record.Status != "active" {
		return fmt.Errorf("cannot update incident count for insurance with status: %s", record.Status)
	}

	record.IncidentCount = newCount

	key, err := makeCompositeKey(ctx, objectInsurance, droneID)
	if err != nil {
		return err
	}
	return putState(ctx, key, record)
}

// ============ Helper Functions ============

func putState(ctx contractapi.TransactionContextInterface, key string, value interface{}) error {
	bytes, err := json.Marshal(value)
	if err != nil {
		return err
	}
	return ctx.GetStub().PutState(key, bytes)
}

func makeCompositeKey(ctx contractapi.TransactionContextInterface, objectType string, id string) (string, error) {
	if id == "" {
		return "", fmt.Errorf("id is required")
	}
	return ctx.GetStub().CreateCompositeKey(objectType, []string{id})
}

func intIDToString(id int) (string, error) {
	if id <= 0 {
		return "", fmt.Errorf("id must be positive")
	}
	return strconv.Itoa(id), nil
}

func assertRole(ctx contractapi.TransactionContextInterface, allowed ...string) error {
	role, ok, err := cid.GetAttributeValue(ctx.GetStub(), "role")
	if err != nil {
		return err
	}

	if !ok {
		mspID, err := cid.GetMSPID(ctx.GetStub())
		if err != nil {
			return fmt.Errorf("failed to get MSP ID: %w", err)
		}

		mspToRole := map[string]string{
			"AggregatorMSP":   roleAggregator,
			"OperatorMSP":     roleOperator,
			"InsurerMSP":      roleInsurer,
			"CertCenterMSP":   roleCertCenter,
			"ManufacturerMSP": roleManufacturer,
			"OrvdMSP":         roleOrvd,
			"RegulatorMSP":    roleRegulator,
		}

		mappedRole, exists := mspToRole[mspID]
		if !exists {
			return fmt.Errorf("unknown MSP ID: %s", mspID)
		}
		role = mappedRole
	}

	for _, candidate := range allowed {
		if role == candidate {
			return nil
		}
	}
	return fmt.Errorf("role %s is not permitted", role)
}
