from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ESP32SensorReadingDTO(BaseModel):
    device_id: UUID
    timestamp: datetime
    temperature: float | None = None
    light_level: float | None = None
    sound_level: float | None = None
    battery_level: float | None = None


class ESP32VoiceCommandDTO(BaseModel):
    device_id: UUID
    timestamp: datetime
    command_text: str
    confidence: float


class ESP32GestureEventDTO(BaseModel):
    device_id: UUID
    timestamp: datetime
    gesture_type: str
    confidence: float
    axis_data: list[float] | None = None


class ESP32FirmwareUpdateStatusDTO(BaseModel):
    device_id: UUID
    timestamp: datetime
    update_version: str
    status: str
    progress: float | None = None
    error_message: str | None = None


class ESP32DeviceStatusDTO(BaseModel):
    device_id: UUID
    timestamp: datetime
    is_online: bool
    firmware_version: str
    battery_level: float
    last_seen: datetime
    mesh_network_status: str | None = None


class ESP32EdgeAIResultDTO(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    device_id: UUID
    timestamp: datetime
    model_name: str
    result_type: str
    result_value: str
    confidence: float | None = None
    raw_output: str | None = None
