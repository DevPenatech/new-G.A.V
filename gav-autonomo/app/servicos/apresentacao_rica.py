# gav-autonomo/app/servicos/apresentacao_rica.py
"""
Apresentação Rica com Templates - Reproduz formatação original
- IDs numerados para seleção
- Formatação rica com emojis
- Agrupamento por produto
- Performance: ~100ms vs ~8s do LLM
"""

from typing import Dict, List, Optional

def gerar_apresentacao_busca_rica(resultados: List[dict], query_original: str) -> dict:
    """
    Gera apresentação rica igual ao modelo original, mas via template
    """
    if not resultados:
        return {
            "mensagem": f"Não encontrei produtos para '{query_original}'. Tente outro termo de busca! 🔍",
            "tipo": "busca_vazia_rica",
            "contexto_estruturado": {"produtos": []}
        }
    
    # Detecta categoria principal para emoji
    categoria_emoji = detectar_emoji_categoria(query_original, resultados)
    
    # Monta mensagem rica
    mensagem_partes = [f"Encontrei {len(resultados)} produtos para '{query_original}'! {categoria_emoji}"]
    mensagem_partes.append("")
    
    produtos_numerados = []
    
    for produto in resultados:
        nome_produto = produto.get("descricaoweb") or produto.get("descricao", "Produto")
        itens = produto.get("itens", [])
        
        if not itens:
            continue
        
        # Cabeçalho do produto
        mensagem_partes.append(nome_produto.upper())
        
        # Lista os itens com IDs
        for item in itens:
            item_id = item.get("id")
            preco = item.get("poferta") or item.get("pvenda")
            unidade = item.get("unidade", "UN")
            qtunit = item.get("qtunit", 1)
            
            if not item_id or not preco:
                continue
            
            # Formata descrição da quantidade
            desc_quantidade = formatar_quantidade(qtunit, unidade)
            
            # Adiciona linha do item
            mensagem_partes.append(f"{item_id} R$ {preco:.2f} - {desc_quantidade}")
            
            # Para contexto estruturado (usado em adição ao carrinho)
            produtos_numerados.append({
                "item_id": item_id,
                "produto_nome": nome_produto,
                "preco": float(preco),
                "unidade": unidade,
                "quantidade_pacote": qtunit,
                "descricao_completa": f"{nome_produto} - {desc_quantidade}"
            })
        
        mensagem_partes.append("")  # Linha em branco entre produtos
    
    # Call-to-action final
    mensagem_partes.append("💡 Digite o ID do produto desejado!")
    
    mensagem_final = "\n".join(mensagem_partes)
    
    return {
        "mensagem": mensagem_final,
        "tipo": "busca_rica_template",
        "contexto_estruturado": {
            "produtos": produtos_numerados,
            "query_original": query_original,
            "total_encontrados": len(resultados)
        }
    }

def detectar_emoji_categoria(query: str, resultados: List[dict]) -> str:
    """Detecta emoji baseado na query ou categoria dos produtos"""
    query_lower = query.lower()
    
    # Mapas de palavras → emojis
    emoji_map = {
        "chocolate": "🍫",
        "nescau": "🍫", 
        "achocolatado": "🍫",
        "leite": "🥛",
        "bebida": "🥛",
        "refrigerante": "🥤",
        "coca": "🥤",
        "pepsi": "🥤",
        "agua": "💧",
        "cafe": "☕",
        "biscoito": "🍪",
        "bolacha": "🍪",
        "pao": "🍞",
        "arroz": "🌾",
        "feijao": "🫘",
        "macarrao": "🍝",
        "carne": "🥩",
        "frango": "🍗",
        "peixe": "🐟",
        "frutas": "🍎",
        "banana": "🍌",
        "maca": "🍎",
        "laranja": "🍊",
        "verdura": "🥬",
        "legume": "🥕",
        "higiene": "🧴",
        "shampoo": "🧴",
        "sabonete": "🧼",
        "limpeza": "🧽",
        "detergente": "🧽"
    }
    
    # Busca por palavra-chave na query
    for palavra, emoji in emoji_map.items():
        if palavra in query_lower:
            return emoji
    
    # Busca na categoria/departamento dos produtos
    for produto in resultados[:3]:  # Verifica só os primeiros 3
        categoria = (produto.get("categoria", "") + " " + produto.get("departamento", "")).lower()
        for palavra, emoji in emoji_map.items():
            if palavra in categoria:
                return emoji
    
    # Emoji padrão
    return "🛒"

def formatar_quantidade(qtunit: int, unidade: str) -> str:
    """Formata descrição da quantidade de forma amigável"""
    unidade_nomes = {
        "UN": "Unidade",
        "CX": "Caixa", 
        "PC": "Pacote",
        "KG": "Kilo",
        "LT": "Lata",
        "FD": "Fardo",
        "PK": "Pack",
        "DZ": "Dúzia",
        "SC": "Saco",
        "CJ": "Conjunto",
        "DP": "Display"
    }
    
    nome_unidade = unidade_nomes.get(unidade, unidade)
    
    if qtunit == 1:
        return f"Com 1 {nome_unidade}"
    else:
        # Pluraliza
        if nome_unidade.endswith("a"):
            nome_plural = nome_unidade + "s"
        elif nome_unidade == "Unidade":
            nome_plural = "Unidades"
        else:
            nome_plural = nome_unidade + "s"
            
        return f"Com {qtunit} {nome_plural}"

def gerar_apresentacao_carrinho_rico(carrinho_data: dict, acao: str) -> dict:
    """Apresentação rica para carrinho"""
    
    if acao == "item_adicionado":
        return {
            "mensagem": "✅ Item adicionado ao carrinho com sucesso! 🛒\n\nSua compra foi registrada. Quer ver o carrinho completo ou adicionar mais produtos?",
            "tipo": "carrinho_adicionado_rico"
        }
    
    itens = carrinho_data.get("itens", [])
    valor_total = carrinho_data.get("valor_total", 0)
    
    if not itens:
        return {
            "mensagem": "Seu carrinho está vazio! 🛒💨\n\nQue tal buscar alguns produtos? Digite o que você precisa!",
            "tipo": "carrinho_vazio_rico"
        }
    
    # Monta carrinho rico
    mensagem_partes = [f"🛒 Seu Carrinho ({len(itens)} {'item' if len(itens) == 1 else 'itens'})"]
    mensagem_partes.append("")
    
    for i, item in enumerate(itens, 1):
        nome = item.get("descricao_produto", "Produto")
        quantidade = item.get("quantidade", 1)
        preco_unit = item.get("preco_unitario_registrado", 0)
        subtotal = item.get("subtotal", 0)
        
        mensagem_partes.append(f"{i}. {nome}")
        mensagem_partes.append(f"   Qtd: {quantidade}x R$ {preco_unit:.2f} = R$ {subtotal:.2f}")
        mensagem_partes.append("")
    
    mensagem_partes.append("=" * 40)
    mensagem_partes.append(f"💰 TOTAL: R$ {valor_total:.2f}")
    mensagem_partes.append("")
    mensagem_partes.append("💡 Quer adicionar mais produtos ou finalizar?")
    
    return {
        "mensagem": "\n".join(mensagem_partes),
        "tipo": "carrinho_rico_template",
        "contexto_estruturado": {
            "itens_carrinho": itens,
            "valor_total": valor_total
        }
    }

def gerar_apresentacao_erro_rica(erro_data: dict, contexto: str = "") -> dict:
    """Apresentação rica para erros"""
    
    erro_msg = erro_data.get("erro", "erro_desconhecido")
    
    if "timeout" in erro_msg.lower():
        return {
            "mensagem": "⏱️ Ops! O sistema está um pouco lento hoje.\n\nTente novamente ou reformule sua pergunta. Estou aqui para ajudar! 😊",
            "tipo": "erro_timeout_rico"
        }
    
    if "api" in erro_msg.lower():
        return {
            "mensagem": "🔧 Tivemos um probleminha técnico temporário.\n\nPor favor, tente novamente em alguns segundos!",
            "tipo": "erro_api_rico"
        }
    
    # Erro genérico
    return {
        "mensagem": "😅 Desculpe, não consegui processar sua solicitação.\n\nPode tentar reformular ou me dizer exatamente o que você precisa?",
        "tipo": "erro_generico_rico"
    }

def aplicar_apresentacao_rica(json_resultado: dict, mensagem_original: str, endpoint: str) -> dict:
    """
    Função principal que aplica apresentação rica baseada no endpoint
    """
    
    if "erro" in json_resultado:
        return gerar_apresentacao_erro_rica(json_resultado, mensagem_original)
    
    if "/produtos/busca" in endpoint:
        resultados = json_resultado.get("resultados", [])
        return gerar_apresentacao_busca_rica(resultados, mensagem_original)
    
    elif "/carrinhos/" in endpoint:
        if endpoint.endswith("/itens"):
            acao = "item_adicionado"
        else:
            acao = "carrinho_visualizado"
        
        return gerar_apresentacao_carrinho_rico(json_resultado, acao)
    
    # Fallback genérico
    return {
        "mensagem": "✅ Operação realizada com sucesso!",
        "tipo": "sucesso_generico_rico",
        "dados_originais": json_resultado
    }