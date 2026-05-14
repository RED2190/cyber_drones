package com.projectci.insurance.utils;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import jakarta.annotation.PostConstruct;

@Component
public class NamespaceUtils {

    @Value("${system.namespace:}")
    private String namespace;

    private String prefix;

    @PostConstruct
    public void init() {
        this.prefix = (namespace != null && !namespace.isEmpty())
                ? namespace + "."
                : "";
        System.out.println("Namespace configured: '" + namespace + "', prefix: '" + prefix + "'");
    }

    public String getPrefix() {
        return prefix;
    }

    public String addNamespace(String topic) {
        return prefix + topic;
    }

    public String getCurrentNamespace() {
        return namespace;
    }

    public boolean hasNamespace() {
        return !prefix.isEmpty();
    }
}
