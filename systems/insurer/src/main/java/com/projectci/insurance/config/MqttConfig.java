package com.projectci.insurance.config;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import jakarta.annotation.PostConstruct;
import lombok.RequiredArgsConstructor;
import org.eclipse.paho.client.mqttv3.MqttConnectOptions;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Profile;
import org.springframework.context.event.EventListener;
import org.springframework.integration.annotation.ServiceActivator;
import org.springframework.integration.channel.DirectChannel;
import org.springframework.integration.core.MessageProducer;
import org.springframework.integration.mqtt.core.DefaultMqttPahoClientFactory;
import org.springframework.integration.mqtt.core.MqttPahoClientFactory;
import org.springframework.integration.mqtt.inbound.MqttPahoMessageDrivenChannelAdapter;
import org.springframework.integration.mqtt.outbound.MqttPahoMessageHandler;
import org.springframework.integration.mqtt.support.DefaultPahoMessageConverter;
import org.springframework.messaging.MessageChannel;
import org.springframework.messaging.MessageHandler;
import org.springframework.messaging.converter.MessageConverter;

@Configuration
@Profile("mqtt")
@RequiredArgsConstructor
public class MqttConfig {

    private final TopicConfig topicConfig;

    private String instanceId;
    @Value("${MQTT_SERVER:tcp://mosquitto:1883}")
    private String mqttUrl;

    @Value("${MQTT_USERNAME:}")
    private String mqttUsername;

    @Value("${MQTT_PASSWORD:}")
    private String mqttPassword;

    @Bean
    public MqttPahoClientFactory mqttClientFactory() {
        DefaultMqttPahoClientFactory factory = new DefaultMqttPahoClientFactory();
        MqttConnectOptions options = new MqttConnectOptions();
        options.setServerURIs(new String[] { mqttUrl });
        options.setAutomaticReconnect(true);
        options.setCleanSession(true);
        options.setConnectionTimeout(10);

        if (mqttUsername != null && !mqttUsername.isEmpty()) {
            options.setUserName(mqttUsername);
            if (mqttPassword != null) {
                options.setPassword(mqttPassword.toCharArray());
            }
        }

        factory.setConnectionOptions(options);
        return factory;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void init() {
        // Получаем INSTANCE_ID из переменной окружения
        this.instanceId = System.getenv("INSTANCE_ID");
        if (this.instanceId == null || this.instanceId.isEmpty()) {
            this.instanceId = "1"; // значение по умолчанию
        }
        System.out.println("=== MqttConfig: instanceId = " + this.instanceId + " ===");
        System.out.println("Mqtt Consumer started. Listening to: " + getInsuranceRequestTopicName());
    }

    public String getInsuranceRequestTopicName() {
        //return String.format("v1.%s.%s.%s.requests", "Insurer", instanceId, "insurer-service");
        return topicConfig.getSystemTopic("insurer");
    }
    @Bean
    public String insuranceRequestTopicName() {
        return getInsuranceRequestTopicName();
    }

    /*public String getInsuranceResponseTopicName() {
        return String.format("v1.%s.%s.%s.responses", "Insurer", instanceId, "insurer-service");
    }
    @Bean
    public String insuranceResponseTopicName() {
        return getInsuranceResponseTopicName();
    }*/

    // Outbound (Sending)
    @Bean
    @ServiceActivator(inputChannel = "mqttOutboundChannel")
    public MessageHandler mqttOutbound() {
        MqttPahoMessageHandler messageHandler = new MqttPahoMessageHandler("producer-client", mqttClientFactory());
        messageHandler.setAsync(true);
        messageHandler.setDefaultTopic("default");
        return messageHandler;
    }

    @Bean
    public MessageChannel mqttOutboundChannel() {
        return new DirectChannel();
    }

    // Inbound (Receiving)
    @Bean
    public MessageProducer inbound(MqttPahoClientFactory factory,
                                   @Qualifier("insuranceRequestTopicName") String topic) {
        MqttPahoMessageDrivenChannelAdapter adapter =
                new MqttPahoMessageDrivenChannelAdapter("consumer-" + (this.instanceId != null ? this.instanceId : "1"), factory, topic);

        DefaultPahoMessageConverter converter = new DefaultPahoMessageConverter();
        converter.setPayloadAsBytes(false); // Сообщение будет приходить как String

        adapter.setConverter(converter);
        adapter.setOutputChannel(mqttInputChannel());
        adapter.setAutoStartup(true);
        return adapter;
    }

    @Bean
    public MessageChannel mqttInputChannel() {
        return new DirectChannel();
    }
}

