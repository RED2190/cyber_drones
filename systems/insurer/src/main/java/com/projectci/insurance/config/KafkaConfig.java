package com.projectci.insurance.config;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import com.projectci.insurance.utils.NamespaceUtils;
import jakarta.annotation.PostConstruct;
import lombok.RequiredArgsConstructor;
import org.apache.kafka.clients.admin.AdminClient;
import org.apache.kafka.clients.admin.AdminClientConfig;
import org.apache.kafka.clients.admin.NewTopic;
import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.kafka.clients.producer.ProducerConfig;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.apache.kafka.common.serialization.StringSerializer;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.CommandLineRunner;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.DependsOn;
import org.springframework.context.annotation.Profile;
import org.springframework.context.event.EventListener;
import org.springframework.kafka.config.ConcurrentKafkaListenerContainerFactory;
import org.springframework.kafka.core.*;
import org.springframework.kafka.support.serializer.JacksonJsonDeserializer;
import org.springframework.kafka.support.serializer.JacksonJsonSerializer;

import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Configuration
@Profile("kafka")
@RequiredArgsConstructor
public class KafkaConfig {

    private final NamespaceUtils namespaceUtils;
    private final TopicConfig topicConfig;

    @Value("${spring.kafka.bootstrap-servers}")
    private String bootstrapServers;

    @Value("${spring.kafka.consumer.group-id}")
    private String groupId;

    //@Value("${INSTANCE_ID}")
    private String instanceId;

    @EventListener(ApplicationReadyEvent.class)
    public void init() {
        // Получаем INSTANCE_ID из переменной окружения
        this.instanceId = System.getenv("INSTANCE_ID");
        if (this.instanceId == null || this.instanceId.isEmpty()) {
            this.instanceId = "1"; // значение по умолчанию
        }

        // Теперь namespaceUtils уже инициализирован
        String topicName = getInsuranceRequestTopicName();

        System.out.println("=== KafkaConfig: instanceId = " + this.instanceId + " ===");
        System.out.println("=== Current namespace: " + namespaceUtils.getCurrentNamespace() + " ===");
        System.out.println("=== Kafka Consumer will listen to: " + topicName + " ===");
    }

    /*@Bean
    public ObjectMapper objectMapper() {
        return new ObjectMapper().registerModule(new JavaTimeModule());
    }*/

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

    // SASL helper
    private void applySasl(Map<String, Object> config) {
        String protocol = System.getenv("SPRING_KAFKA_PROPERTIES_SECURITY_PROTOCOL");
        if (protocol != null && !protocol.isEmpty()) {
            config.put("security.protocol", protocol);
            config.put("sasl.mechanism",
                    System.getenv("SPRING_KAFKA_PROPERTIES_SASL_MECHANISM"));
            config.put("sasl.jaas.config",
                    System.getenv("SPRING_KAFKA_PROPERTIES_SASL_JAAS_CONFIG"));
        }
        /*System.out.println("=== KafkaConfig: protocol = " + protocol + " ===");
        System.out.println("=== KafkaConfig: sasl.mechanism = " + System.getenv("SPRING_KAFKA_PROPERTIES_SASL_MECHANISM") + " ===");
        System.out.println("=== KafkaConfig: sasl.jaas.config = " + System.getenv("SPRING_KAFKA_PROPERTIES_SASL_JAAS_CONFIG") + " ===");*/
    }

    // Producer Configuration
    @Bean
    public ProducerFactory<String, Object> producerFactory() {
        Map<String, Object> config = new HashMap<>();
        config.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapServers);
        config.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class);
        config.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, JacksonJsonSerializer.class);
        applySasl(config);
        return new DefaultKafkaProducerFactory<>(config);
    }

    @Bean
    public KafkaTemplate<String, Object> kafkaTemplate() {
        return new KafkaTemplate<>(producerFactory());
    }

    // Consumer Configuration
    @Bean
    public ConsumerFactory<String, Object> consumerFactory() {
        Map<String, Object> config = new HashMap<>();
        config.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapServers);
        config.put(ConsumerConfig.GROUP_ID_CONFIG, groupId);
        config.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class);
        config.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, JacksonJsonDeserializer.class);
        config.put(JacksonJsonDeserializer.TRUSTED_PACKAGES, "com.projectci.insurance.model");
        config.put(JacksonJsonDeserializer.VALUE_DEFAULT_TYPE, "com.projectci.insurance.model.MessageRequest");
        applySasl(config);
        return new DefaultKafkaConsumerFactory<>(config);
    }

    @Bean
    public ConcurrentKafkaListenerContainerFactory<String, Object> kafkaListenerContainerFactory() {
        ConcurrentKafkaListenerContainerFactory<String, Object> factory =
                new ConcurrentKafkaListenerContainerFactory<>();
        factory.setConsumerFactory(consumerFactory());
        return factory;
    }

    // Topics
    @Bean
    public NewTopic insuranceRequestTopic() {
        return new NewTopic(getInsuranceRequestTopicName(), 3, (short) 1);
    }

/*
    @Bean
    public NewTopic insuranceResponseTopic() {
        return new NewTopic(getInsuranceResponseTopicName(), 3, (short) 1);
    }
*/

    @Bean
    public NewTopic incidentTopic() {
        return new NewTopic("incident-reports", 1, (short) 1);
    }
}
