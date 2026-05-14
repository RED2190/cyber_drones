package com.projectci.insurance.repository;

import com.projectci.insurance.model.Incident;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface IncidentRepository extends JpaRepository<Incident, String> {
    Optional<Incident> findByIncidentId(String incidentId);
    List<Incident> findByOrderId(String orderId);
    List<Incident> findByPolicyId(String policyId);
    //List<Incident> findByReporterId(String reporterId);
}
