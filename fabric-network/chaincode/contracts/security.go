package contracts

import (
	"encoding/json"
	"fmt"
	"time"

	"github.com/hyperledger/fabric-chaincode-go/pkg/cid"
	"github.com/hyperledger/fabric-contract-api-go/contractapi"
)

const objectFirmware = "firmware"

type Firmware struct {
	ID                 string   `json:"id"`
	SecurityObjectives []string `json:"security_objectives"`
	SoftwareObjectives []string `json:"software_objectives"`
	CertifiedAt        string   `json:"certified_at"`
	CertifiedBy        string   `json:"certified_by"`
}

type FirmwareContract struct {
	contractapi.Contract
}

func (c *FirmwareContract) CertifyFirmware(
	ctx contractapi.TransactionContextInterface,
	id string,
	securityObjectives []string,
	softwareObjectives []string,
	certifiedAt string,
	CertifiedBy string,
) error {
	if err := assertRole(ctx, roleCertCenter, roleAdmin); err != nil {
		return err
	}

	exists, err := c.firmwareExists(ctx, id)
	if err != nil {
		return err
	}
	if exists {
		return fmt.Errorf("firmware %s already certified", id)
	}

	certifierID, err := cid.GetID(ctx.GetStub())
	if err != nil {
		certifierID = "unknown"
	}

	firmware := Firmware{
		ID:                 id,
		SecurityObjectives: securityObjectives,
		SoftwareObjectives: softwareObjectives,
		CertifiedAt:        time.Now().UTC().Format(time.RFC3339),
		CertifiedBy:        certifierID,
	}

	key, err := makeFirmwareKey(ctx, id)
	if err != nil {
		return err
	}
	return putState(ctx, key, firmware)
}

func (c *FirmwareContract) ReadFirmware(
	ctx contractapi.TransactionContextInterface,
	id string,
) (*Firmware, error) {
	key, err := makeFirmwareKey(ctx, id)
	if err != nil {
		return nil, err
	}

	bytes, err := ctx.GetStub().GetState(key)
	if err != nil {
		return nil, err
	}
	if bytes == nil {
		return nil, fmt.Errorf("firmware %s not found", id)
	}

	var firmware Firmware
	if err := json.Unmarshal(bytes, &firmware); err != nil {
		return nil, err
	}
	return &firmware, nil
}

func (c *FirmwareContract) UpdateFirmware(
	ctx contractapi.TransactionContextInterface,
	id string,
	version string,
	securityObjectives []string,
	softwareObjectives []string,
) error {
	if err := assertRole(ctx, roleCertCenter, roleAdmin); err != nil {
		return err
	}

	firmware, err := c.ReadFirmware(ctx, id)
	if err != nil {
		return err
	}

	firmware.SecurityObjectives = securityObjectives
	firmware.SoftwareObjectives = softwareObjectives

	key, err := makeFirmwareKey(ctx, id)
	if err != nil {
		return err
	}

	return putState(ctx, key, firmware)
}

func (c *FirmwareContract) ListFirmwares(
	ctx contractapi.TransactionContextInterface,
) ([]*Firmware, error) {
	iterator, err := ctx.GetStub().GetStateByPartialCompositeKey(objectFirmware, []string{})
	if err != nil {
		return nil, err
	}
	defer iterator.Close()

	var items []*Firmware
	for iterator.HasNext() {
		result, err := iterator.Next()
		if err != nil {
			return nil, err
		}
		var firmware Firmware
		if err := json.Unmarshal(result.Value, &firmware); err != nil {
			continue
		}
		items = append(items, &firmware)
	}
	return items, nil
}

func (c *FirmwareContract) RevokeFirmwareCertification(
	ctx contractapi.TransactionContextInterface,
	id string,
) error {
	if err := assertRole(ctx, roleCertCenter, roleAdmin); err != nil {
		return err
	}

	exists, err := c.firmwareExists(ctx, id)
	if err != nil {
		return err
	}
	if !exists {
		return fmt.Errorf("firmware %s not found", id)
	}

	key, err := makeFirmwareKey(ctx, id)
	if err != nil {
		return err
	}
	return ctx.GetStub().DelState(key)
}

func (c *FirmwareContract) firmwareExists(
	ctx contractapi.TransactionContextInterface,
	id string,
) (bool, error) {
	key, err := makeFirmwareKey(ctx, id)
	if err != nil {
		return false, err
	}

	bytes, err := ctx.GetStub().GetState(key)
	if err != nil {
		return false, err
	}
	return bytes != nil, nil
}

func makeFirmwareKey(ctx contractapi.TransactionContextInterface, id string) (string, error) {
	if id == "" {
		return "", fmt.Errorf("firmware id is required")
	}
	return ctx.GetStub().CreateCompositeKey(objectFirmware, []string{id})
}
