package com.projectci.insurance.config;

import com.projectci.insurance.utils.NamespaceUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

@Component
public class TopicConfig {

    @Autowired
    private NamespaceUtils namespaceUtils;

    // Базовые методы для формирования топиков
    public String getSystemTopic(String systemName) {
        return namespaceUtils.addNamespace("systems." + systemName);
    }

    public String getComponentTopic(String componentName) {
        return namespaceUtils.addNamespace("components." + componentName);
    }

    // Глобальный топик ошибок (без namespace)
    public static final String DEAD_LETTERS_TOPIC = "errors.dead_letters";

    // Конфигурация для страховой системы
    public static class InsuranceSystem {
        public static final String SYSTEM_NAME = "insurer";

        // Компоненты
        public static class Components {
            public static final String INSURANCE_SERVICE = "insurance_service";
            public static final String POLICY_SERVICE = "policy_service";
            public static final String INCIDENT_SERVICE = "incident_service";
            public static final String KBM_SERVICE = "kbm_service";
        }

        // Actions (те же, что и в GatewayActions)
        public static class Actions {
            public static final String CALCULATION = "insurance.calculation";
            public static final String PURCHASE = "insurance.purchase";
            public static final String INCIDENT = "insurance.incident";
            public static final String POLICY_TERMINATION = "insurance.policy_termination";
        }
    }
}
