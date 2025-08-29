# app/config/settings.py

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    API_NEGOCIO_URL: str
    OLLAMA_HOST: str
    OLLAMA_MODEL_NAME: str = "qwen2:7b"
    OLLAMA_TEMPERATURE: float = 0.1
    OLLAMA_MAX_TOKENS: int = 1024
    OLLAMA_JSON_MODE: bool = True
    
    class Config:
        env_file = ".env"

config = Settings()  # ✅ Aqui você instancia a configuração global
