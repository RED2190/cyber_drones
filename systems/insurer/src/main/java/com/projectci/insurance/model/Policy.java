package com.projectci.insurance.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.persistence.*;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Entity
@Table(name = "policies")
@Data
public class Policy {
    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @JsonProperty("id")
    private String id;

    @Column(unique = true)
    @JsonProperty("policy_number")
    private String policyNumber;
    @JsonProperty("policy_type")
    private PolicyType policyType;

    @JsonProperty("order_id")
    private String orderId;
    @JsonProperty("manufacturer_id")
    private String manufacturerId;
    @JsonProperty("operator_id")
    private String operatorId;
    @JsonProperty("drone_id")
    private String droneId;

    @JsonProperty("start_date")
    private LocalDateTime startDate;
    @JsonProperty("end_date")
    private LocalDateTime endDate;

    @JsonProperty("cost")
    private BigDecimal cost;
    @JsonProperty("coverage_amount")
    private BigDecimal coverageAmount;
    @JsonProperty("kfleet_history")
    private BigDecimal droneKbm;

    @Enumerated(EnumType.STRING)
    @JsonProperty("status")
    private PolicyStatus status;

    public enum PolicyStatus {
        active,
        terminated
    }

    public enum PolicyType {
        annual,
        mission
    }
}