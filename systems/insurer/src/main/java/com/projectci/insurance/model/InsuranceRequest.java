package com.projectci.insurance.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;
import lombok.Data;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import jakarta.validation.constraints.NotBlank;
import lombok.Getter;
import lombok.Setter;

import java.math.BigDecimal;
import java.util.List;

@Data
@JsonIgnoreProperties(ignoreUnknown = true)
public class InsuranceRequest {
    @JsonProperty("request_id")
    private String requestId;

    @NotBlank
    @JsonProperty("order_id")
    private String orderId;

    @JsonProperty("manufacturer_id")
    private String manufacturerId;
    @JsonProperty("operator_id")
    private String operatorId;
    @JsonProperty("drone_id")
    private String droneId;

    // Цели безопасности
    //@JsonProperty("drone_id")
    /*private String droneSafetyPurpose;
    private String requiredSafetyPurpose;*/
    @JsonProperty("security_goals")
    private List<String> securityGoals;
    @JsonProperty("coverage_amount")
    private BigDecimal coverageAmount;

    // Для расчёта (ОФ1-ОФ2)
    @JsonProperty("calculation_id")
    private String calculationId; // ID предварительного расчёта

    // Для инцидентов (ОФ4)
    @JsonProperty("incident")
    private Incident incident;

    // Тип запроса: CALCULATION, PURCHASE, INCIDENT, POLICY_TERMINATION
    /*@JsonProperty("request_type")
    private RequestType requestType;

    public enum RequestType {
        CALCULATION,    // ОФ1
        PURCHASE,       // ОФ2
        INCIDENT,       // ОФ4
        POLICY_TERMINATION // ОФ3
    }*/
}