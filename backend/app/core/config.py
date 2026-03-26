from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    INFLUX_TOKEN: str
    INFLUX_ORG: str
    INFLUX_BUCKET: str = "Iot_Project"
    API_KEY_EDGE: str
    
    # Adiciona estas duas linhas para o Pydantic saber ler do Cofre/Env!
    MINIO_ROOT_USER: str
    MINIO_ROOT_PASSWORD: str
    
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")

settings = Settings()