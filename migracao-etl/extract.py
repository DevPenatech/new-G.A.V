# /migracao-etl/extract.py

import os
import oracledb
import pandas as pd
from sqlalchemy import create_engine

# A query que você forneceu continua a mesma.
ORACLE_QUERY = """
    SELECT 
        PCEMBALAGEM.CODPROD,
        PCPRODUT.DESCRICAO || ' ' || PCEMBALAGEM.EMBALAGEM AS DESCRICAO, 
        PCEMBALAGEM.DESCRICAOWEB, 
        PCDEPTO.DESCRICAO AS DEPARTAMENTO, 
        PCCATEGORIA.CATEGORIA, 
        PCMARCA.MARCA,
        PCEMBALAGEM.UNIDADE,
        PCEMBALAGEM.QTUNIT, 
        NVL((PCTABPR.PVENDA * PCEMBALAGEM.QTUNIT), 1) AS PVENDA, 
        ((PCTABPR.PVENDA * PCEMBALAGEM.QTUNIT) * PCEMBALAGEM.FATORPRECO) AS POFERTA,
        PCEMBALAGEM.CODFILIAL
    FROM PCEMBALAGEM 
    LEFT JOIN PCPRODUT ON PCEMBALAGEM.CODPROD = PCPRODUT.CODPROD
    LEFT JOIN PCCATEGORIA ON PCPRODUT.CODCATEGORIA = PCCATEGORIA.CODCATEGORIA
    LEFT JOIN PCDEPTO ON PCPRODUT.CODEPTO = PCDEPTO.CODEPTO
    LEFT JOIN PCMARCA ON PCPRODUT.CODMARCA = PCMARCA.CODMARCA
    LEFT JOIN PCTABPR ON PCTABPR.NUMREGIAO = 102 AND PCTABPR.CODPROD = PCEMBALAGEM.CODPROD
    WHERE PCEMBALAGEM.DTINATIVO IS NULL 
    AND PCEMBALAGEM.CODFILIAL = 2
    AND PCMARCA.MARCA IS NOT NULL 
    AND PCPRODUT.ENVIARFORCAVENDAS = 'S'
    AND PCPRODUT.OBS2 <> 'FL'
"""

def extrair_dados_oracle() -> pd.DataFrame:
    """
    Conecta-se ao Oracle usando o método direto do oracledb,
    executa a query e retorna os dados como um DataFrame do Pandas.
    """
    print("\n--- Iniciando Etapa 1: Extração de Dados do Oracle ---")
    
    oracle_conn = None
    try:
        # Pega as credenciais do arquivo .env
        # ATENÇÃO: Verifique se seu .env tem ORACLE_USER, ORACLE_PASSWORD, ORACLE_DSN
        user = os.getenv('ORACLE_USER')
        password = os.getenv('ORACLE_PASSWORD')
        dsn = os.getenv('ORACLE_DSN')

        print(f"Conectando ao Oracle DSN: {dsn} (Método Direto)...")
        
        # USANDO O MÉTODO DE CONEXÃO DIRETA QUE JÁ FUNCIONA PARA VOCÊ
        oracle_conn = oracledb.connect(user=user, password=password, dsn=dsn)
        print("Conectado ao Oracle com sucesso.")

        print("Executando query de extração... Isso pode levar alguns minutos.")
        # O Pandas também aceita o objeto de conexão direta
        dados_brutos_df = pd.read_sql(ORACLE_QUERY, oracle_conn)
        
        print(f"Extração concluída com sucesso. Total de {len(dados_brutos_df)} linhas encontradas.")
        return dados_brutos_df

    except oracledb.Error as error:
        print(f"Erro de banco de dados ao conectar ou extrair do Oracle: {error}")
        return pd.DataFrame()
    except Exception as e:
        print(f"Um erro inesperado ocorreu na extração: {e}")
        return pd.DataFrame()
    finally:
        if oracle_conn:
            oracle_conn.close()
            print("Conexão com Oracle fechada.")