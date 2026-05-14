package com.projectci.insurance.producer;

public interface MessagePublisher {
    void send(String topic, String key, Object payload);
}
