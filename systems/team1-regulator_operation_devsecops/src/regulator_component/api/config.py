import os

class Config:
    BROKER_TYPE  = os.getenv("BROKER_TYPE", "stub")
    BROKER_URL   = os.getenv("BROKER_URL", "amqp://guest:guest@localhost/")
    EXCHANGE_NAME = "amq.topic"

    TOPIC_FIRMWARE_REQUEST    = "v1.firmware.certification.request"
    TOPIC_DRONE_REQUEST       = "v1.drone.registration.request"
    TOPIC_OPERATOR_REQUEST    = "v1.operator.op1.certificate_request"
    TOPIC_INSURER_REQUEST     = "v1.Insurer.reg1.insurer-service.requests"
    TOPIC_CERT_VERIFY_REQUEST = "v1.regulator.certificate.verify.request"
    TOPIC_CERT_REVOKE_REQUEST = "v1.regulator.certificate.revoke.request"

    TOPIC_FIRMWARE_RESULT      = "v1.firmware.certificate.result"
    TOPIC_DRONE_RESULT         = "v1.drone.registration.result"
    TOPIC_OPERATOR_RESULT      = "v1.operator.op1.certificate_result"
    TOPIC_INSURER_RESPONSE     = "v1.Insurer.reg1.insurer-service.responses"
    TOPIC_CERT_VERIFY_RESPONSE = "v1.regulator.certificate.verify.response"
    TOPIC_CERT_REVOKE_RESPONSE = "v1.regulator.certificate.revoke.response"

    CERT_STORAGE_PATH = os.getenv("CERT_STORAGE_PATH", "certificates.json")
    CRL_STORAGE_PATH  = os.getenv("CRL_STORAGE_PATH",  "crl.json")
    PRIVATE_KEY_PATH  = "keys/regulator_private.pem"
    PUBLIC_KEY_PATH   = "keys/regulator_public.pem"

    MQTT_BROKER    = os.getenv("MQTT_BROKER", "localhost")
    MQTT_PORT      = int(os.getenv("MQTT_PORT", "1883"))
    MQTT_CLIENT_ID = os.getenv("MQTT_CLIENT_ID", "regulator")
    MQTT_USERNAME  = os.getenv("MQTT_USERNAME")
    MQTT_PASSWORD  = os.getenv("MQTT_PASSWORD")
    MQTT_QOS       = int(os.getenv("MQTT_QOS", "1"))

    API_HOST = os.getenv("API_HOST", "127.0.0.1")
    API_PORT = int(os.getenv("API_PORT", "8000"))