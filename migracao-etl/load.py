# /migracao-etl/load.py

import os
import io
import pandas as pd
from sqlalchemy import create_engine, text # Adicionamos a importação de 'text'
import csv

def carregar_dados_postgres(datasets: dict):
    print("\n--- Iniciando Etapa 3: Carregamento de Dados no PostgreSQL ---")
    
    user = os.getenv('POSTGRES_USER')
    password = os.getenv('POSTGRES_PASSWORD')
    # Usamos 'localhost' aqui porque o script roda fora do Docker
    host = 'localhost' 
    port = os.getenv('POSTGRES_PORT')
    db = os.getenv('POSTGRES_DB')
    
    conn_str = f'postgresql://{user}:{password}@{host}:{port}/{db}'
    engine = create_engine(conn_str)

    try:
        # Usamos uma transação para garantir que tudo seja salvo ou nada seja.
        with engine.begin() as conn:
            # --- 1. Carregar Produtos ---
            print("Carregando tabela 'produtos'...")
            df_produtos = datasets['produtos']
            
            # Envolvemos o SQL com a função text()
            conn.execute(text(
                """
                CREATE TEMP TABLE temp_produtos (
                    codprod INTEGER, descricao TEXT, descricaoweb TEXT, 
                    departamento VARCHAR(100), categoria VARCHAR(100), marca VARCHAR(100)
                ) ON COMMIT DROP;
                """
            ))
            _fast_copy(df_produtos, 'temp_produtos', conn)
            
            conn.execute(text(
                """
                INSERT INTO produtos (codprod, descricao, descricaoweb, departamento, categoria, marca)
                SELECT codprod, descricao, descricaoweb, departamento, categoria, marca FROM temp_produtos
                ON CONFLICT (codprod) DO UPDATE SET
                    descricao = EXCLUDED.descricao,
                    descricaoweb = EXCLUDED.descricaoweb,
                    departamento = EXCLUDED.departamento,
                    categoria = EXCLUDED.categoria,
                    marca = EXCLUDED.marca;
                """
            ))
            print(f"-> {len(df_produtos)} registros de produtos processados (UPSERT).")

            # --- 2. Carregar Itens ---
            print("Carregando tabela 'produto_itens'...")
            df_itens = datasets['itens']
            conn.execute(text("CREATE TEMP TABLE temp_itens (codprod INTEGER, unidade VARCHAR(10), qtunit INTEGER) ON COMMIT DROP;"))
            _fast_copy(df_itens, 'temp_itens', conn)
            conn.execute(text(
                """
                INSERT INTO produto_itens (produto_id, unidade, qtunit)
                SELECT p.id, ti.unidade, ti.qtunit 
                FROM temp_itens ti
                JOIN produtos p ON p.codprod = ti.codprod
                ON CONFLICT (produto_id, unidade) DO UPDATE SET
                    qtunit = EXCLUDED.qtunit;
                """
            ))
            print(f"-> {len(df_itens)} registros de itens processados (UPSERT).")

            # --- 3. Carregar Preços ---
            print("Carregando tabela 'produto_precos'...")
            df_precos = datasets['precos']
            conn.execute(text(
                """
                CREATE TEMP TABLE temp_precos (
                    codprod INTEGER, unidade VARCHAR(10), codfilial INTEGER, 
                    pvenda NUMERIC(10,2), poferta NUMERIC(10,2)
                ) ON COMMIT DROP;
                """
            ))
            _fast_copy(df_precos, 'temp_precos', conn)
            conn.execute(text(
                """
                INSERT INTO produto_precos (item_id, codfilial, pvenda, poferta)
                SELECT pi.id, tp.codfilial, tp.pvenda, tp.poferta
                FROM temp_precos tp
                JOIN produtos p ON p.codprod = tp.codprod
                JOIN produto_itens pi ON pi.produto_id = p.id AND pi.unidade = tp.unidade
                ON CONFLICT (item_id, codfilial) DO UPDATE SET
                    pvenda = EXCLUDED.pvenda,
                    poferta = EXCLUDED.poferta,
                    atualizado_em = NOW();
                """
            ))
            print(f"-> {len(df_precos)} registros de preços processados (UPSERT).")
            
            print("\nCarregamento no PostgreSQL concluído com sucesso.")

    except Exception as e:
        print(f"Um erro ocorreu durante o carregamento no PostgreSQL: {e}")

def _fast_copy(df: pd.DataFrame, table_name: str, connection):
    """Função auxiliar para usar o comando COPY do Postgres com um DataFrame."""
    output = io.StringIO()
    # 2. ADICIONE O PARÂMETRO 'quoting=csv.QUOTE_MINIMAL' ABAIXO:
    # Isso instrui o pandas a colocar aspas em campos que contenham
    # o separador (TAB), aspas ou quebras de linha, resolvendo nosso problema.
    df.to_csv(output, sep='\t', header=False, index=False, na_rep='\\N', quoting=csv.QUOTE_MINIMAL)
    output.seek(0)
    
    dbapi_conn = connection.connection
    with dbapi_conn.cursor() as cursor:
        cursor.copy_from(output, table_name, null="\\N", sep='\t')