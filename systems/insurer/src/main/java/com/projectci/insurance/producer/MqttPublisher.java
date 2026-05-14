package com.projectci.insurance.producer;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Profile;
import org.springframework.integration.mqtt.support.MqttHeaders; // Для заголовка TOPIC
import org.springframework.integration.support.MessageBuilder;   // Построитель сообщения
import org.springframework.messaging.Message;               // Интерфейс сообщения
import org.springframework.messaging.MessageChannel;        // Канал отправки
import org.springframework.stereotype.Service;

@Service
@Profile("mqtt")
public class MqttPublisher implements MessagePublisher {
    private final MessageChannel mqttOutboundChannel;
    private final ObjectMapper objectMapper; // Внедряем стандартный Jackson mapper

    public MqttPublisher(MessageChannel mqttOutboundChannel, ObjectMapper objectMapper) {
        this.mqttOutboundChannel = mqttOutboundChannel;
        this.objectMapper = objectMapper;
    }

    @Override
    public void send(String topic, String key, Object payload) {
        try {
            // Ручная сериализация перед отправкой в канал
            String jsonContent = objectMapper.writeValueAsString(payload);

            Message<String> message = MessageBuilder
                    .withPayload(jsonContent)
                    .setHeader(MqttHeaders.TOPIC, topic)
                    .build();

            mqttOutboundChannel.send(message);
        } catch (JsonProcessingException e) {
            throw new RuntimeException("MQTT Serialization failed", e);
        }
    }
}
