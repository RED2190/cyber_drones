package com.projectci.insurance.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;

@Component
@ConfigurationProperties(prefix = "insurance")
@Data
public class InsuranceProperties {
    // Заглушки для расчётов
    private BigDecimal baseCost = new BigDecimal("150000");
    private Integer policyDurationDays = 30;
    private BigDecimal baseKbm = new BigDecimal("1.0");
}