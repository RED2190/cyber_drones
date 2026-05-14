import os

class Config:
    # --- Брокер сообщений (общий) ---
    # По умолчанию выбираем kafka, так как это указано в логах main.py
    BROKER_TYPE = os.getenv("BROKER_TYPE", "kafka")
    BROKER_URL = os.getenv("BROKER_URL", "localhost")
    EXCHANGE_NAME = "amq.topic"
    
    # --- Топики входящие ---
    TOPIC_FIRMWARE_REQUEST = "v1.firmware.certification.request"
    TOPIC_DRONE_REQUEST = "v1.drone.registration.request"
    TOPIC_OPERATOR_REQUEST = "v1.operator.op1.certificate_request"
    TOPIC_INSURER_REQUEST = "v1.Insurer.reg1.insurer-service.requests"
    TOPIC_CERT_VERIFY_REQUEST = "v1.regulator.certificate.verify.request"
    TOPIC_CERT_REVOKE_REQUEST = "v1.regulator.certificate.revoke.request"
    
    # --- Топики исходящие ---
    TOPIC_FIRMWARE_RESULT = "v1.firmware.certificate.result"
    TOPIC_DRONE_RESULT = "v1.drone.registration.result"
    TOPIC_OPERATOR_RESULT = "v1.operator.op1.certificate_result"
    TOPIC_INSURER_RESPONSE = "v1.Insurer.reg1.insurer-service.responses"
    TOPIC_CERT_VERIFY_RESPONSE = "v1.regulator.certificate.verify.response"
    TOPIC_CERT_REVOKE_RESPONSE = "v1.regulator.certificate.revoke.response"
    
    # --- Хранилище сертификатов ---
    # На основе твоего скриншота, файлы лежат в корне Regulator/
    CERT_STORAGE_PATH = os.getenv("CERT_STORAGE_PATH", "certificates.json")
    CRL_STORAGE_PATH = os.getenv("CRL_STORAGE_PATH", "crl.json")
    
    # --- Ключи ---
    # На основе твоего скриншота, папка keys/ существует
    PRIVATE_KEY_PATH = "keys/regulator_private.pem"
    PUBLIC_KEY_PATH = "keys/regulator_public.pem"
    
    # --- Параметры покрытия (Cyberimmune) ---
    COVERAGE_THRESHOLD_TRUSTED = 60      # БТ5
    COVERAGE_THRESHOLD_INTEGRITY = 70    # БТ6
    
    # --- Mocks для тестирования ---
    MOCK_SECURITY_TESTS = True
    MOCK_COVERAGE = True

    # --- Настройки Kafka ---
    KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    KAFKA_CLIENT_ID = os.getenv("KAFKA_CLIENT_ID", "regulator")
    KAFKA_GROUP_ID = os.getenv("KAFKA_GROUP_ID", "regulator_group")
    KAFKA_USERNAME = os.getenv("KAFKA_USERNAME")
    KAFKA_PASSWORD = os.getenv("KAFKA_PASSWORD")
    
    # --- Настройки MQTT ---
    MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
    MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
    MQTT_CLIENT_ID = os.getenv("MQTT_CLIENT_ID", "regulator")
    MQTT_USERNAME = os.getenv("MQTT_USERNAME")
    MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
    MQTT_QOS = int(os.getenv("MQTT_QOS", "1"))