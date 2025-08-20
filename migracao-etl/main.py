# /migracao-etl/main.py

from dotenv import load_dotenv
import os
import time

# Importa as funções que criaremos nos próximos passos
from extract import extrair_dados_oracle
from transform import transformar_dados
from load import carregar_dados_postgres

def main():
    """
    Orquestra o processo completo de ETL:
    1. Carrega as variáveis de ambiente.
    2. Extrai dados do Oracle.
    3. Transforma os dados para o novo modelo.
    4. Carrega os dados transformados no PostgreSQL.
    """
    print(">>> Iniciando processo de ETL: Oracle -> PostgreSQL <<<")
    start_time = time.time()
    
    # Carrega as variáveis de ambiente do arquivo .env
    load_dotenv()
    
    # Valida se as variáveis de ambiente essenciais existem
    oracle_user = os.getenv('ORACLE_USER')
    pg_conn_str = os.getenv('POSTGRES_HOST') # Apenas para checagem
    if not all([oracle_user, pg_conn_str]):
        raise ValueError("Erro: Verifique as variáveis ORACLE_* e POSTGRES_* no arquivo .env.")

    # Passo 2: Extração
    dados_brutos_df = extrair_dados_oracle()
    
    # Passo 3: Transformação
    if not dados_brutos_df.empty:
        datasets_normalizados = transformar_dados(dados_brutos_df)
        
        # Passo 4: Carregamento
        carregar_dados_postgres(datasets_normalizados)
    else:
        print("Nenhum dado encontrado no Oracle para migrar.")

    end_time = time.time()
    print(f"\n>>> Processo de ETL concluído em {end_time - start_time:.2f} segundos. <<<")

if __name__ == '__main__':
    main()