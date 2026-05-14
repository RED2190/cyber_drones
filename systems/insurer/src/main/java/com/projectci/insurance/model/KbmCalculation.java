package com.projectci.insurance.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;
import jakarta.persistence.*;
import lombok.Data;
import java.math.BigDecimal;
import java.time.LocalDateTime;

@Entity
@Table(name = "kbm_calculations")
@Data
public class KbmCalculation {
    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @JsonProperty("id")
    private String id;

    @JsonProperty("entity_id")
    private String entityId; // manufacturerId или operatorId
    @JsonProperty("entity_type")
    private String entityType; // MANUFACTURER, OPERATOR

    @JsonProperty("current_kbm")
    private BigDecimal currentKbm;
    @JsonProperty("new_kbm")
    private BigDecimal newKbm;

    @JsonProperty("incident_count")
    private int incidentCount;
    @JsonProperty("calculation_date")
    private LocalDateTime calculationDate;

    @JsonProperty("related_incident_id")
    private String relatedIncidentId;
}
