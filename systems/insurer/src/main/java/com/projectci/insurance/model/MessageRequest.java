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
public class MessageRequest {

    // Обязательные поля для всех сообщений
    @JsonProperty("message_id")
    private String messageId;      // Уникальный ID сообщения
    @JsonProperty("action")
    private insuranceAction action;          // Тип действия (из GatewayActions)
    @JsonProperty("sender")
    private String sender;          // ID отправителя
    @JsonProperty("reply_to")
    private String replyTo;
    @JsonProperty("correlation_id")
    private String correlationId;   // Для request-response
    @JsonProperty("timestamp")
    private Long timestamp;         // Временная метка

    // Полезная нагрузка
    @JsonProperty("payload")
    private InsuranceRequest payload;

    // Метаданные
    @JsonProperty("message_type")
    private String messageType;     // "request", "response", "event"
    @JsonProperty("headers")
    private Map<String, String> headers;

    public enum insuranceAction {
        annual_insurance,
        mission_insurance,
        calculate_policy,
        purchase_policy,
        report_incident,
        terminate_policy
    }

    // Статический метод для создания запроса
    public static MessageRequest createRequest(insuranceAction action, String sender, InsuranceRequest payload) {
        MessageRequest message = new MessageRequest();
        message.setMessageId(UUID.randomUUID().toString());
        message.setAction(action);
        message.setSender(sender);
        message.setPayload(payload);
        message.setTimestamp(System.currentTimeMillis());
        message.setMessageType("request");
        return message;
    }

}
