from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import logging

from broker import BrokerService
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Regulator Component API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

broker = BrokerService()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------- MODELS --------

class FirmwareRequest(BaseModel):
    request_id: str
    developer_id: str
    drone_type: str
    firmware: Dict[str, Any]

    class Config:
        json_schema_extra = {
            "example": {
                "request_id": "fw-1",
                "developer_id": "dev_001",
                "drone_type": "quad",
                "firmware": {
                    "commit_hash": "abc123",
                    "version": "1.0.0",
                    "repository_url": "https://github.com/example/repo"
                }
            }
        }


class DroneRequest(BaseModel):
    request_id: str
    drone: Dict[str, Any]
    firmware: Dict[str, Any]

    class Config:
        json_schema_extra = {
            "example": {
                "request_id": "dr-1",
                "drone": {
                    "serial_number": "SN-00001",
                    "model": "DJI Mavic 3",
                    "manufacturer": "DJI"
                },
                "firmware": {
                    "version": "1.0.0",
                    "certificate_id": "CERT-..."
                }
            }
        }


class InsurerRequest(BaseModel):
    message_id: str
    insurer_id: str
    order_id: str
    amount: float
    incident_id: str

    class Config:
        json_schema_extra = {
            "example": {
                "message_id": "ins-1",
                "insurer_id": "ins_company_001",
                "order_id": "order-001",
                "amount": 1000.0,
                "incident_id": "incident-001"
            }
        }


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    broker_connected: bool
    service: str


# -------- ROOT ENDPOINTS --------

@app.get("/")
async def root():
    return {
        "service": "Regulator Component API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "health":   {"method": "GET",  "path": "/health"},
            "firmware": {"method": "POST", "path": "/firmware"},
            "drone":    {"method": "POST", "path": "/drone"},
            "insurer":  {"method": "POST", "path": "/insurer"},
            "docs":     {"method": "GET",  "path": "/docs"}
        }
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(),
        broker_connected=broker is not None,
        service="regulator-component"
    )


@app.get("/ping")
async def ping():
    return {"pong": True, "timestamp": datetime.now().isoformat()}


# -------- BUSINESS LOGIC ENDPOINTS --------

@app.post("/firmware", summary="Firmware certification")
async def firmware_check(req: FirmwareRequest):
    try:
        logger.info(f"Processing firmware request: {req.request_id}")

        payload = req.dict()
        payload["timestamp"] = datetime.utcnow().isoformat()

        result = await broker.send_and_wait(
            Config.TOPIC_FIRMWARE_REQUEST,
            Config.TOPIC_FIRMWARE_RESULT,
            payload
        )

        logger.info(f"Firmware request {req.request_id} completed")
        return {
            "status": "success",
            "request_id": req.request_id,
            "result": result,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error processing firmware request {req.request_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process firmware request: {str(e)}")


@app.post("/drone", summary="Drone registration")
async def drone_register(req: DroneRequest):
    try:
        logger.info(f"Processing drone request: {req.request_id}")

        payload = req.dict()
        payload["timestamp"] = datetime.utcnow().isoformat()

        result = await broker.send_and_wait(
            Config.TOPIC_DRONE_REQUEST,
            Config.TOPIC_DRONE_RESULT,
            payload
        )

        logger.info(f"Drone request {req.request_id} completed")
        return {
            "status": "success",
            "request_id": req.request_id,
            "result": result,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error processing drone request {req.request_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process drone request: {str(e)}")


@app.post("/insurer", summary="Insurance check")
async def insurer_check(req: InsurerRequest):
    try:
        logger.info(f"Processing insurer request: {req.message_id}")

        payload = req.dict()
        payload["timestamp"] = datetime.utcnow().isoformat()

        result = await broker.send_and_wait(
            Config.TOPIC_INSURER_REQUEST,
            Config.TOPIC_INSURER_RESPONSE,
            payload
        )

        logger.info(f"Insurer request {req.message_id} completed")
        return {
            "status": "success",
            "message_id": req.message_id,
            "result": result,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error processing insurer request {req.message_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process insurer request: {str(e)}")


# -------- STARTUP & SHUTDOWN --------

@app.on_event("startup")
async def startup_event():
    logger.info("Starting Regulator Component API...")
    logger.info(f"  - Firmware:  {Config.TOPIC_FIRMWARE_REQUEST} -> {Config.TOPIC_FIRMWARE_RESULT}")
    logger.info(f"  - Drone:     {Config.TOPIC_DRONE_REQUEST} -> {Config.TOPIC_DRONE_RESULT}")
    logger.info(f"  - Insurer:   {Config.TOPIC_INSURER_REQUEST} -> {Config.TOPIC_INSURER_RESPONSE}")
    logger.info("Regulator Component API started successfully!")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Regulator Component API...")


# -------- MAIN --------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True, log_level="info")

# -------- МОДЕЛИ ДЛЯ ПРОВЕРКИ СЕРТИФИКАТА --------

class CertificateVerifyRequest(BaseModel):
    check_type: str  # "drone" или "firmware"
    serial_number: Optional[str] = None   # для дрона
    drone_type: Optional[str] = None      # для прошивки
    firmware_version: Optional[str] = None  # для прошивки

# -------- НОВЫЙ ЭНДПОИНТ ПРОВЕРКИ (использует MQTT) --------

@app.post("/certificate/verify")
async def verify_certificate(req: CertificateVerifyRequest):
    """
    Проверяет статус сертификата через MQTT.
    Для дрона: передайте check_type="drone" и serial_number.
    Для прошивки: check_type="firmware", drone_type и firmware_version.
    """
    try:
        logger.info(f"Certificate verify request: {req.dict()}")
        
        # Формируем payload как ожидает ваш MQTT-обработчик
        payload = req.dict()
        payload["timestamp"] = datetime.now(timezone.utc).isoformat()
        
        result = await broker.send_and_wait(
            Config.TOPIC_CERT_VERIFY_REQUEST,
            Config.TOPIC_CERT_VERIFY_RESPONSE,
            payload
        )
        
        return {
            "status": "success",
            "result": result,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Certificate verify error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
