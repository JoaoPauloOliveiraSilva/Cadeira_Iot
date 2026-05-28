from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    INFLUX_TOKEN: str
    INFLUX_ORG: str
    INFLUX_BUCKET: str = "vigilancia"
    INFLUXDB_URL: str

    API_KEY_EDGE: str
    API_KEY_DASHBOARD: str | None = None

    MINIO_ROOT_USER: str
    MINIO_ROOT_PASSWORD: str
    MINIO_URL: str
    MINIO_BUCKET: str = "iotproject"
    MINIO_SECURE: bool = False

    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    MQTT_BROKER: str = "localhost"
    MQTT_PORT: int = 1883
    MQTT_USERNAME: str | None = None
    MQTT_PASSWORD: str | None = None
    MQTT_ENABLED: bool = False

    MAX_UPLOAD_BYTES: int = Field(default=100 * 1024 * 1024, ge=1)
    MAX_QUERY_MINUTES: int = Field(default=60 * 24 * 30, ge=1)
    DEFAULT_QUERY_MINUTES: int = Field(default=60 * 24, ge=1)
    ALLOWED_MEDIA_TYPES: str = "video/mp4,video/webm,image/jpeg,image/png,audio/wav,audio/mpeg"
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env", "../../.env"),
        extra="ignore",
        case_sensitive=False,
    )

    @field_validator("MQTT_USERNAME", "MQTT_PASSWORD", "API_KEY_DASHBOARD", mode="before")
    @classmethod
    def blank_strings_to_none(cls, value):
        if value == "":
            return None
        return value

    @property
    def allowed_media_types(self) -> set[str]:
        return {item.strip() for item in self.ALLOWED_MEDIA_TYPES.split(",") if item.strip()}

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.CORS_ORIGINS.split(",") if item.strip()]


settings = Settings()
