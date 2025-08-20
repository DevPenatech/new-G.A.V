# /migracao-etl/transform.py
import pandas as pd

def transformar_dados(df_bruto: pd.DataFrame) -> dict:
    print("\n--- Iniciando Etapa 2: Transformação dos Dados ---")
    
    if df_bruto.empty:
        return {}

    df_bruto.columns = [x.lower() for x in df_bruto.columns]

    # --- ETAPA DE LIMPEZA ---
    # 1. Remove caracteres de tabulação
    colunas_texto = df_bruto.select_dtypes(include=['object']).columns
    print(f"Limpando caracteres de tabulação das colunas: {list(colunas_texto)}")
    for col in colunas_texto:
        df_bruto[col] = df_bruto[col].str.replace('\t', ' ', regex=False)

    # 2. CORREÇÃO: Remove linhas onde a unidade de venda é nula
    linhas_antes = len(df_bruto)
    df_bruto.dropna(subset=['unidade'], inplace=True)
    linhas_depois = len(df_bruto)
    if linhas_antes > linhas_depois:
        print(f"-> Foram removidas {linhas_antes - linhas_depois} linhas com 'unidade' nula.")

    # 1. CRIAR O DATAFRAME `produtos`
    print("Normalizando tabela 'produtos'...")
    df_produtos = df_bruto[['codprod', 'descricao', 'descricaoweb', 'departamento', 'categoria', 'marca']]
    df_produtos = df_produtos.drop_duplicates(subset=['codprod']).reset_index(drop=True)
    print(f"-> Encontradas {len(df_produtos)} famílias de produtos únicas.")
    
    # 2. CRIAR O DATAFRAME `produto_itens`
    print("Normalizando tabela 'produto_itens'...")
    df_itens = df_bruto[['codprod', 'unidade', 'qtunit']]
    df_itens = df_itens.drop_duplicates(subset=['codprod', 'unidade']).reset_index(drop=True)
    df_itens['qtunit'] = df_itens['qtunit'].fillna(1).astype(int)
    print(f"-> Encontradas {len(df_itens)} variações (SKUs) únicas.")

    # 3. CRIAR O DATAFRAME `produto_precos`
    print("Normalizando tabela 'produto_precos'...")
    df_precos = df_bruto[['codprod', 'unidade', 'codfilial', 'pvenda', 'poferta']]
    df_precos = df_precos.drop_duplicates(subset=['codprod', 'unidade', 'codfilial']).reset_index(drop=True)
    print(f"-> Encontrados {len(df_precos)} registros de preços únicos.")
    
    return {
        "produtos": df_produtos,
        "itens": df_itens,
        "precos": df_precos
    }