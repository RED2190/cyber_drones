package com.projectci.insurance.service;

import com.projectci.insurance.config.InsuranceProperties;
import com.projectci.insurance.model.InsuranceRequest;
import com.projectci.insurance.model.Policy;
import com.projectci.insurance.repository.PolicyRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.Optional;
import java.util.UUID;

@Service
@RequiredArgsConstructor
@Slf4j
public class PolicyService {

    private final PolicyRepository policyRepository;
    private final InsuranceProperties properties;

    public Policy createPolicy(InsuranceRequest request, Policy.PolicyType type) {
        Policy policy = new Policy();
        policy.setPolicyNumber("POL-" + UUID.randomUUID().toString().substring(0, 8).toUpperCase());
        policy.setOrderId(request.getOrderId());
        policy.setManufacturerId(request.getManufacturerId());
        policy.setOperatorId(request.getOperatorId());
        policy.setDroneId(request.getDroneId());


        switch (type) {
            case mission:
                // Заглушка: полис действует 30 дней
                policy.setStartDate(LocalDateTime.now());
                policy.setEndDate(LocalDateTime.now().plusDays(properties.getPolicyDurationDays()));
            case annual:
                policy.setStartDate(LocalDateTime.now());
                policy.setEndDate(LocalDateTime.now().plusYears(1L));
        }
        // Заглушка: стоимость из пропертей
        policy.setCost(request.getCoverageAmount().multiply( new BigDecimal("0.08").multiply(properties.getBaseKbm())));
        policy.setCoverageAmount(properties.getBaseCost().multiply(new java.math.BigDecimal("10"))); // покрытие в 10 раз больше

        policy.setStatus(Policy.PolicyStatus.active);
        policy.setPolicyType(type);

        policy.setDroneKbm(properties.getBaseKbm());

        return policyRepository.save(policy);
    }

    public boolean terminatePolicyByOrderId(String orderId) {
        Optional<Policy> policyOpt = policyRepository.findByOrderId(orderId);

        if (policyOpt.isPresent()) {
            Policy policy = policyOpt.get();
            policy.setStatus(Policy.PolicyStatus.terminated);
            policy.setEndDate(LocalDateTime.now());
            policyRepository.save(policy);
            log.info("Policy {} terminated for order {}", policy.getId(), orderId);
            return true;
        }

        log.warn("Policy not found for order {}", orderId);
        return false;
    }

    public Optional<Policy> getActivePolicyForOrder(String orderId) {
        return policyRepository.findByOrderId(orderId)
                .filter(p -> p.getStatus() == Policy.PolicyStatus.active);
    }
}
