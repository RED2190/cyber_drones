package com.projectci.insurance.consumer;

import com.projectci.insurance.model.MessageRequest;
import com.projectci.insurance.model.MessageResponse;
import com.projectci.insurance.service.InsuranceService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.annotation.Profile;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Component;

@Component
@Profile("kafka")
@Slf4j
public class KafkaInsuranceConsumer {

    private final InsuranceService insuranceService;

    public KafkaInsuranceConsumer(InsuranceService insuranceService) {
        this.insuranceService = insuranceService;
    }

    @KafkaListener(topics = "#{@insuranceRequestTopicName}")
    public void consumeKafka(MessageRequest message) {
        log.info("Received via Kafka: {}", message);
        try {
            insuranceService.processInsuranceRequest(message);
        } catch (Exception e) {
            log.error("Error processing Kafka request", e);
        }
    }
}
