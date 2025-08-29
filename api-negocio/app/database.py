# api-negocio/app/database.py

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from .config import settings

# Cria o "motor" de conexão com o banco de dados usando a URL do nosso config
engine = create_engine(settings.DATABASE_URL)

# Cria uma fábrica de sessões que usaremos para interagir com o banco
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Função para testar a conexão
def testar_conexao():
    try:
        with engine.connect() as connection:
            # Executa uma consulta simples para verificar se a conexão é bem-sucedida
            connection.execute(text("SELECT 1"))
        return "connected"
    except Exception as e:
        print(f"Erro ao conectar ao banco de dados: {e}")
        return "connection_failed"