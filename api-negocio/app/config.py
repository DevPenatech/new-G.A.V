# api-negocio/app/config.py

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Carrega as variáveis do arquivo .env
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Mapeia as variáveis de ambiente para os atributos da classe
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int
    POSTGRES_DB: str

    # Gera a URL de conexão do banco de dados automaticamente
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

# Cria uma instância única das configurações para ser usada em toda a aplicação
settings = Settings()