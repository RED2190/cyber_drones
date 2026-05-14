package com.projectci.insurance.service;

import com.projectci.insurance.model.Incident;
import com.projectci.insurance.repository.IncidentRepository;
import lombok.AllArgsConstructor;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Service
@RequiredArgsConstructor
@Slf4j
public class IncidentService {

    private final IncidentRepository incidentRepository;

    public Incident processIncident(Incident incident) {
        log.info("Processing incident: {}", incident);

        // Заглушка: проверяем покрытие
        if (incident.getDamageAmount() == null) {
            incident.setDamageAmount(BigDecimal.ZERO);
        }

        incident.setStatus(Incident.IncidentStatus.PROCESSED);
        incident.setIncidentDate(LocalDateTime.now());

        // Здесь должна быть логика проверки покрытия и расчёта выплаты
        // Заглушка: выплачиваем всю сумму ущерба

        Incident savedIncident = incidentRepository.save(incident);
        log.info("Incident processed: {}", savedIncident);

        return savedIncident;
    }

    public int getIncidentCountForEntity(String entityId, LocalDateTime since) {
        // Заглушка: подсчёт инцидентов для entity
        // В реальности нужно реализовать запрос к БД
        return 0;
    }
}