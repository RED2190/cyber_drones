package com.projectci.insurance.consumer;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.projectci.insurance.model.InsuranceRequest;
import com.projectci.insurance.model.MessageRequest;
import com.projectci.insurance.service.InsuranceService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.annotation.Profile;
import org.springframework.integration.annotation.ServiceActivator;
import org.springframework.stereotype.Component;

@Component
@Profile("mqtt")
@Slf4j
public class MqttInsuranceConsumer {

    private final InsuranceService insuranceService;
    private final ObjectMapper objectMapper;

    public MqttInsuranceConsumer(InsuranceService insuranceService, ObjectMapper objectMapper) {
        this.insuranceService = insuranceService;
        this.objectMapper = objectMapper;
    }

    @ServiceActivator(inputChannel = "mqttInputChannel")
    public void consumeMqtt(String payload) {
        try {
            log.info("Received via MQTT: {}", payload);
            MessageRequest message = objectMapper.readValue(payload, MessageRequest.class);
            insuranceService.processInsuranceRequest(message);
        } catch (JsonProcessingException e) {
            log.error("Failed to deserialize MQTT message: {}", payload, e);
        } catch (Exception e) {
            log.error("Error processing MQTT request", e);
            // TODO: отправить в dead letters
        }
    }
}
