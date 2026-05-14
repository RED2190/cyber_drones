package com.projectci.insurance.repository;

import com.projectci.insurance.model.Policy;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface PolicyRepository extends JpaRepository<Policy, String> {
    Optional<Policy> findByOrderId(String orderId);
    Optional<Policy> findByPolicyNumber(String policyNumber);
    List<Policy> findByManufacturerIdAndStatus(String manufacturerId, Policy.PolicyStatus status);
    List<Policy> findByOperatorIdAndStatus(String operatorId, Policy.PolicyStatus status);
}
