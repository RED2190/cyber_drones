package com.projectci.insurance.producer;

import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Profile;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;

@Service
@Profile("kafka")
@RequiredArgsConstructor
public class KafkaPublisher implements MessagePublisher {
    private final KafkaTemplate<String, Object> kafkaTemplate;
    public void send(String topic, String key, Object payload) {
        kafkaTemplate.send(topic, key, payload);
    }
}