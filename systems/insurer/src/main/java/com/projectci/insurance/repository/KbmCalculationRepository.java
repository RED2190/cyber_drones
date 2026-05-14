package com.projectci.insurance.repository;

import com.projectci.insurance.model.KbmCalculation;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

@Repository
public interface KbmCalculationRepository extends JpaRepository<KbmCalculation, String> {

    // Найти последний расчёт КБМ для производителя
    Optional<KbmCalculation> findFirstByEntityIdAndEntityTypeOrderByCalculationDateDesc(
            String entityId, String entityType);

    // Найти все расчёты КБМ для производителя за период
    List<KbmCalculation> findByEntityIdAndEntityTypeAndCalculationDateBetween(
            String entityId, String entityType, LocalDateTime startDate, LocalDateTime endDate);

    // Найти расчёты КБМ, связанные с конкретным инцидентом
    List<KbmCalculation> findByRelatedIncidentId(String incidentId);

    // Получить историю изменений КБМ для сущности
    @Query("SELECT k FROM KbmCalculation k WHERE k.entityId = :entityId AND k.entityType = :entityType ORDER BY k.calculationDate DESC")
    List<KbmCalculation> findKbmHistory(@Param("entityId") String entityId, @Param("entityType") String entityType);

    // Получить среднее значение КБМ для всех производителей
    @Query("SELECT AVG(k.newKbm) FROM KbmCalculation k WHERE k.entityType = 'MANUFACTURER'")
    Optional<Double> getAverageManufacturerKbm();

    // Получить среднее значение КБМ для всех операторов
    @Query("SELECT AVG(k.newKbm) FROM KbmCalculation k WHERE k.entityType = 'OPERATOR'")
    Optional<Double> getAverageOperatorKbm();

    // Подсчитать количество инцидентов для сущности за последние N дней
    @Query("SELECT COUNT(k) FROM KbmCalculation k WHERE k.entityId = :entityId AND k.entityType = :entityType AND k.calculationDate >= :since")
    long countIncidentsForEntity(@Param("entityId") String entityId,
                                 @Param("entityType") String entityType,
                                 @Param("since") LocalDateTime since);

    // Найти все записи КБМ, где КБМ превышает пороговое значение
    List<KbmCalculation> findByEntityTypeAndNewKbmGreaterThan(String entityType, java.math.BigDecimal threshold);

    // Проверить, существует ли расчёт для конкретного инцидента
    boolean existsByRelatedIncidentId(String incidentId);

    // Удалить старые записи (например, старше 1 года)
    @Query("DELETE FROM KbmCalculation k WHERE k.calculationDate < :date")
    void deleteOlderThan(@Param("date") LocalDateTime date);
}
