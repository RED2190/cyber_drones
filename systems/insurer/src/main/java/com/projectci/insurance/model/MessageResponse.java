package com.projectci.insurance.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;
import com.fasterxml.jackson.annotation.JsonInclude;
import java.time.LocalDateTime;
import java.util.Map;
import java.util.UUID;

@Data
@NoArgsConstructor
@AllArgsConstructor
@JsonInclude(JsonInclude.Include.NON_NULL)
public class MessageResponse {

    // Обязательные поля для всех сообщений
    @JsonProperty("message_id")
    private String messageId;      // Уникальный ID сообщения
    @JsonProperty("action")
    private String action;          // Тип действия (из GatewayActions)
    @JsonProperty("sender")
    private String sender;          // ID отправителя
    @JsonProperty("correlation_id")
    private String correlationId;   // Для request-response
    @JsonProperty("timestamp")
    private Long timestamp;         // Временная метка

    // Полезная нагрузка
    @JsonProperty("payload")
    private InsuranceResponse payload;

    // Метаданные
    @JsonProperty("message_type")
    private String messageType;     // "request", "response", "event"
    @JsonProperty("headers")
    private Map<String, String> headers;
    @JsonProperty("success")
    boolean success;

    // Статический метод для создания ответа
    public static MessageResponse createResponse(String correlationId, InsuranceResponse payload, boolean success) {
        MessageResponse message = new MessageResponse();
        message.setMessageId(UUID.randomUUID().toString());
        message.setCorrelationId(correlationId);
        message.setPayload(payload);
        message.setTimestamp(System.currentTimeMillis());
        message.setMessageType("response");
        message.setSuccess(success);
        return message;
    }
}
