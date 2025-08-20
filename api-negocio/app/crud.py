# /api-negocio/app/crud.py

from sqlalchemy.orm import Session
from sqlalchemy import text
from . import esquemas
import json
import re

# Dicionário em memória para "cachear" os aliases de unidade e evitar buscas repetidas no banco
_aliases_de_unidade_cache = None

def _get_aliases_de_unidade(db: Session) -> dict:
    """Busca os aliases da tabela e os armazena em cache na memória."""
    global _aliases_de_unidade_cache
    if _aliases_de_unidade_cache is None:
        print("Buscando e cacheando aliases de unidade do banco de dados...")
        stmt = text("SELECT alias, unidade_principal FROM unidade_aliases WHERE ativo = TRUE")
        resultados = db.execute(stmt).fetchall()
        _aliases_de_unidade_cache = {row.alias: row.unidade_principal for row in resultados}
    return _aliases_de_unidade_cache


def _extrair_atributos_da_query(db: Session, query: str) -> (str, dict):
    """
    Usa regex e a tabela de aliases para extrair atributos da query.
    """
    filtros = {}
    query_limpa = query.lower() # Normaliza para minúsculas
    
    # 1. Extrai aliases de unidade (ex: caixa, lata, pack)
    aliases_map = _get_aliases_de_unidade(db)
    unidades_encontradas = set()
    for alias, unidade_principal in aliases_map.items():
        # \b -> word boundary, para não pegar 'caixao' quando busca por 'caixa'
        padrao_alias = re.compile(r'\b' + re.escape(alias) + r's?\b', re.IGNORECASE)
        if padrao_alias.search(query_limpa):
            unidades_encontradas.add(unidade_principal)
            query_limpa = padrao_alias.sub('', query_limpa)

    if unidades_encontradas:
        filtros['unidades'] = list(unidades_encontradas)

    # 2. Extrai volumes (ex: 500ml)
    padrao_volume = re.compile(r'(\d+)\s?(ml|l|g|kg)\b', re.IGNORECASE)
    match = padrao_volume.search(query_limpa)
    if match:
        valor = match.group(1)
        unidade_vol = match.group(2).lower()
        filtros['volume'] = f"%{valor}{unidade_vol}%"
        query_limpa = padrao_volume.sub('', query_limpa)

    return query_limpa.strip(), filtros


def buscar_produtos(db: Session, query: str, codfilial: int, ordenar_por: str = "relevancia", limit: int = 10):
    """
    Executa a busca em até duas etapas e retorna os resultados junto com um status da busca.
    """
    query_para_fts, filtros = _extrair_atributos_da_query(db, query)
    
    # --- ETAPA 1: BUSCA ESTRITA ---
    print("Executando busca estrita...")
    resultados = _executar_busca(db, query_para_fts, filtros, codfilial, ordenar_por, limit, estrita=True)

    # --- ETAPA 2: LÓGICA DE FALLBACK ---
    if not resultados and 'unidades' in filtros:
        print("Busca estrita falhou. Tentando fallback sem filtro de unidade...")
        filtros_fallback = filtros.copy()
        del filtros_fallback['unidades']
        
        resultados_fallback = _executar_busca(db, query_para_fts, filtros_fallback, codfilial, ordenar_por, limit, estrita=False)
        # Retorna o resultado do fallback com um status indicando o que aconteceu
        return {"resultados": resultados_fallback, "status_busca": "fallback"}
        
    # Se a busca estrita funcionou, retorna com status de sucesso
    return {"resultados": resultados, "status_busca": "sucesso"}


def _executar_busca(db: Session, query_para_fts: str, filtros: dict, codfilial: int, ordenar_por: str, limit: int, estrita: bool):
    """Função auxiliar que executa a lógica de busca no banco de dados."""
    query_fts_formatada = " & ".join(query_para_fts.split()) if query_para_fts else None

    params = {'limit': limit, 'codfilial': codfilial}
    where_clauses = []
    join_clauses = ["LEFT JOIN produto_itens pi ON p.id = pi.produto_id"]
    order_by_clause = ""
    group_by_clause = "GROUP BY p.id"

    # ... (toda a lógica de montagem de join, select, order by, etc. que já tínhamos) ...
    if ordenar_por in ["preco_asc", "preco_desc"]:
        join_clauses.append("LEFT JOIN produto_precos pp ON pi.id = pp.item_id AND pp.codfilial = :codfilial")
        # ... (lógica de ordenação por preço)
    if not order_by_clause:
        if query_fts_formatada: order_by_clause = "ORDER BY rank DESC"
        else: order_by_clause = "ORDER BY p.id"
    if query_fts_formatada:
        select_clause = "p.*, MAX(ts_rank(produtos_fts_document(p.descricaoweb, p.descricao, p.marca, p.categoria, p.departamento), to_tsquery('portuguese', :query_fts))) as rank"
        where_clauses.append("produtos_fts_document(p.descricaoweb, p.descricao, p.marca, p.categoria, p.departamento) @@ to_tsquery('portuguese', :query_fts)")
        params['query_fts'] = query_fts_formatada
    else: select_clause = "p.*"
    if 'volume' in filtros:
        where_clauses.append("(p.descricao ILIKE :volume OR p.descricaoweb ILIKE :volume)")
        params['volume'] = filtros['volume']
    if 'unidades' in filtros:
        where_clauses.append("pi.unidade = ANY(:unidades)")
        params['unidades'] = filtros['unidades']

    if not where_clauses: return []

    sql = f"""
        SELECT {select_clause} FROM produtos p {" ".join(join_clauses)}
        WHERE {" AND ".join(where_clauses)} {group_by_clause} {order_by_clause} LIMIT :limit
    """
    
    resultados = db.execute(text(sql), params).fetchall()
    
    produtos_encontrados = []
    for row in resultados:
        produto_dict = dict(row._mapping)
        item_params = {"pid": produto_dict['id'], "codfilial": codfilial}
        item_where_clauses = ["pi.produto_id = :pid"]
        
        if estrita and 'unidades' in filtros:
            item_where_clauses.append("pi.unidade = ANY(:unidades)")
            item_params['unidades'] = filtros['unidades']

        # Se a busca original (estrita) tinha um filtro de unidade, agora na exibição nós o ignoramos
        # para mostrar todas as opções disponíveis no fallback.
        # if 'unidades' in filtros:
        #     item_where_clauses.append("pi.unidade = ANY(:unidades)")
        #     item_params['unidades'] = filtros['unidades']

        stmt_itens_sql = f"""
            SELECT pi.id, pi.unidade, pi.qtunit, pp.pvenda, pp.poferta
            FROM produto_itens pi LEFT JOIN produto_precos pp ON pi.id = pp.item_id AND pp.codfilial = :codfilial
            WHERE {" AND ".join(item_where_clauses)} ORDER BY pi.id
        """
        
        itens_result = db.execute(text(stmt_itens_sql), item_params).fetchall()
        produto_dict['itens'] = [dict(item_row._mapping) for item_row in itens_result]
        
        if produto_dict['itens']:
            produtos_encontrados.append(produto_dict)
            
    return produtos_encontrados

def criar_log_interacao(db: Session, log: esquemas.LogBase) -> int:
    # AQUI ESTÁ A CORREÇÃO:
    # Removemos a conversão manual para ::jsonb do SQL.
    # O SQLAlchemy e o driver Psycopg2 são inteligentes o suficiente
    # para lidar com a conversão de uma string JSON para o tipo jsonb.
    stmt = text("""
        INSERT INTO interacao_log (sessao_id, mensagem_usuario, resposta_json)
        VALUES (:sessao_id, :mensagem_usuario, :resposta_json)
        RETURNING id;
    """)
    result = db.execute(stmt, {
        "sessao_id": log.sessao_id, 
        "mensagem_usuario": log.mensagem_usuario, 
        "resposta_json": json.dumps(log.resposta_json) # Continuamos passando uma string JSON
    })
    db.commit()
    return result.scalar_one()

def atualizar_log_com_feedback(db: Session, feedback: esquemas.Feedback):
    # MESMA CORREÇÃO APLICADA AQUI:
    stmt = text("""
        UPDATE interacao_log SET feedback_tipo = :tipo, feedback_esperado = :esperado
        WHERE sessao_id = :sessao_id AND mensagem_usuario = :query AND id = (
            SELECT MAX(id) FROM interacao_log WHERE sessao_id = :sessao_id AND mensagem_usuario = :query
        );
    """)
    db.execute(stmt, {
        "tipo": feedback.tipo,
        "esperado": json.dumps(feedback.resposta_esperada), # Passamos como string JSON
        "sessao_id": feedback.sessao_id,
        "query": feedback.query
    })
    db.commit()
    
def get_ou_criar_carrinho_por_sessao(db: Session, sessao_id: str) -> dict:
    """
    Verifica se existe um carrinho 'aberto' para a sessão.
    Se não existir, cria um novo. Retorna os dados do carrinho.
    """
    # Usamos ON CONFLICT para fazer um "INSERT se não existir" de forma atômica
    stmt = text("""
        INSERT INTO carrinhos (sessao_id, status)
        VALUES (:sessao_id, 'aberto')
        ON CONFLICT (sessao_id) WHERE (status = 'aberto')
        DO NOTHING;
    """)
    db.execute(stmt, {"sessao_id": sessao_id})

    # Agora buscamos o carrinho que garantidamente existe
    stmt_select = text("SELECT id, sessao_id, status FROM carrinhos WHERE sessao_id = :sessao_id AND status = 'aberto'")
    resultado = db.execute(stmt_select, {"sessao_id": sessao_id}).first()
    db.commit()
    return resultado._mapping if resultado else None


def adicionar_item_ao_carrinho(db: Session, carrinho_id: int, item_data: esquemas.ItemCarrinhoEntrada):
    """
    Adiciona um item a um carrinho. Se o item já existir, atualiza a quantidade.
    Usa o preço da tabela produto_precos.
    """
    # Primeiro, busca o preço atual do item na filial correta
    stmt_preco = text("""
        SELECT COALESCE(poferta, pvenda) as preco 
        FROM produto_precos 
        WHERE item_id = :item_id AND codfilial = :codfilial
    """)
    preco_result = db.execute(stmt_preco, {"item_id": item_data.item_id, "codfilial": item_data.codfilial}).scalar_one_or_none()

    if preco_result is None:
        raise ValueError(f"Preço para o item {item_data.item_id} na filial {item_data.codfilial} não encontrado.")

    # Lógica de UPSERT para o item no carrinho
    stmt_upsert = text("""
        INSERT INTO carrinho_itens (carrinho_id, item_id, quantidade, preco_unitario_registrado)
        VALUES (:carrinho_id, :item_id, :quantidade, :preco)
        ON CONFLICT (carrinho_id, item_id) DO UPDATE SET
            quantidade = carrinho_itens.quantidade + :quantidade;
    """)
    db.execute(stmt_upsert, {
        "carrinho_id": carrinho_id,
        "item_id": item_data.item_id,
        "quantidade": item_data.quantidade,
        "preco": preco_result
    })
    db.commit()


def get_carrinho_detalhado(db: Session, carrinho_id: int):
    """
    Busca um carrinho e todos os seus itens com detalhes dos produtos.
    """
    # Buscamos o carrinho principal
    carrinho = db.execute(text("SELECT * FROM carrinhos WHERE id = :id"), {"id": carrinho_id}).first()
    if not carrinho:
        return None

    # Buscamos os itens, juntando com as tabelas de produto para obter a descrição
    stmt_itens = text("""
        SELECT 
            ci.item_id,
            ci.quantidade,
            ci.preco_unitario_registrado,
            (ci.quantidade * ci.preco_unitario_registrado) as subtotal,
            p.descricao as descricao_produto
        FROM carrinho_itens ci
        JOIN produto_itens pi ON ci.item_id = pi.id
        JOIN produtos p ON pi.produto_id = p.id
        WHERE ci.carrinho_id = :carrinho_id;
    """)
    itens = db.execute(stmt_itens, {"carrinho_id": carrinho_id}).fetchall()
    
    # Monta o objeto final
    carrinho_dict = dict(carrinho._mapping)
    carrinho_dict['itens'] = [dict(item._mapping) for item in itens]
    carrinho_dict['valor_total'] = sum(item['subtotal'] for item in carrinho_dict['itens'])
    
    return carrinho_dict

def get_prompt_ativo_por_nome(db: Session, nome: str) -> str:
    """Busca o template de um prompt ativo pelo seu nome único."""
    stmt = text("SELECT template FROM prompt_templates WHERE nome = :nome AND ativo = TRUE ORDER BY versao DESC LIMIT 1")
    resultado = db.execute(stmt, {"nome": nome}).scalar_one_or_none()
    if not resultado:
        # Um fallback de emergência caso o prompt não seja encontrado no banco
        return "Você é um assistente prestativo. Responda em JSON."
    return resultado

def get_all_unidade_aliases(db: Session) -> list:
    """Busca todos os aliases de unidade ativos."""
    stmt = text("SELECT alias, unidade_principal FROM unidade_aliases WHERE ativo = TRUE")
    return db.execute(stmt).fetchall()