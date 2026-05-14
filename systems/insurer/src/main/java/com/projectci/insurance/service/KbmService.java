package com.projectci.insurance.service;

import com.projectci.insurance.config.InsuranceProperties;
import com.projectci.insurance.model.Incident;
import com.projectci.insurance.model.InsuranceRequest;
import com.projectci.insurance.model.KbmCalculation;
import com.projectci.insurance.repository.KbmCalculationRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

@Service
@RequiredArgsConstructor
@Slf4j
public class KbmService {

    private final InsuranceProperties properties;
    private final KbmCalculationRepository kbmRepository;

    // Заглушка: хранилище КБМ в памяти (в реальности - БД)
    private final Map<String, BigDecimal> manufacturerKbms = new ConcurrentHashMap<>();
    private final Map<String, BigDecimal> operatorKbms = new ConcurrentHashMap<>();

    public BigDecimal getManufacturerKbm(String manufacturerId) {
        return manufacturerKbms.getOrDefault(manufacturerId, properties.getBaseKbm());
    }

    public BigDecimal getOperatorKbm(String operatorId) {
        return operatorKbms.getOrDefault(operatorId, properties.getBaseKbm());
    }

    public BigDecimal calculatePolicyCost(InsuranceRequest request) {
        // Заглушка: простая формула стоимости
        BigDecimal baseCost = properties.getBaseCost();
        BigDecimal manufacturerKbm = getManufacturerKbm(request.getManufacturerId());
        BigDecimal operatorKbm = getOperatorKbm(request.getOperatorId());

        // Стоимость = базовая * КБМ_производителя * КБМ_оператора
        return baseCost
                .multiply(manufacturerKbm)
                .multiply(operatorKbm)
                .setScale(2, RoundingMode.HALF_UP);
    }

    public KbmCalculation recalculateKbm(String entityId, String entityType, Incident incident) {
        log.info("Recalculating KBM for {}: {}", entityType, entityId);

        BigDecimal currentKbm = entityType.equals("MANUFACTURER")
                ? getManufacturerKbm(entityId)
                : getOperatorKbm(entityId);

        // ОФ5: Пересчёт КБМ с учётом инцидентов
        // Заглушка: увеличиваем КБМ на 10% при инциденте
        BigDecimal newKbm = currentKbm.multiply(new BigDecimal("1.1"));

        // Сохраняем результат
        KbmCalculation calculation = new KbmCalculation();
        calculation.setEntityId(entityId);
        calculation.setEntityType(entityType);
        calculation.setCurrentKbm(currentKbm);
        calculation.setNewKbm(newKbm);
        calculation.setIncidentCount(1); // Заглушка
        calculation.setCalculationDate(LocalDateTime.now());
        calculation.setRelatedIncidentId(incident != null ? incident.getId() : null);

        KbmCalculation saved = kbmRepository.save(calculation);

        // Обновляем текущее значение
        if (entityType.equals("MANUFACTURER")) {
            manufacturerKbms.put(entityId, newKbm);
        } else {
            operatorKbms.put(entityId, newKbm);
        }

        log.info("KBM updated from {} to {}", currentKbm, newKbm);

        return saved;
    }
}
