# app/config/settings.py

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    API_NEGOCIO_URL: str
    OLLAMA_HOST: str
    OLLAMA_MODEL_NAME: str
    
    class Config:
        env_file = ".env"

config = Settings()  # ✅ Aqui você instancia a configuração global
