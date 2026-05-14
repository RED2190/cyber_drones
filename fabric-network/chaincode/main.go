package main

import (
	"fmt"

	"github.com/hyperledger/fabric-contract-api-go/contractapi"

	"econom_prototype/contracts"
)

func main() {
	chaincode, err := contractapi.NewChaincode(
		&contracts.DronePropertiesContract{},
		&contracts.FirmwareContract{},
		&contracts.OrderContract{},
	)
	if err != nil {
		panic(fmt.Errorf("error creating chaincode: %w", err))
	}
	if err := chaincode.Start(); err != nil {
		panic(fmt.Errorf("error starting chaincode: %w", err))
	}
}
