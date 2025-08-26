# gav-autonomo/app/main.py
"""
FIX DIRETO - Integra apresentação rica diretamente no main.py
Elimina problemas de import de arquivos externos
"""

import time
import re
from fastapi import FastAPI
from pydantic import BaseModel

# Import da versão que está funcionando (fallback)
from app.servicos.executor_fallback_inteligente import (
    executar_regras_com_fallback, 
    get_fallback_stats
)

app = FastAPI(title="G.A.V. Autonomo - Fix Direto com Apresentação Rica")

class EntradaChat(BaseModel):
    texto: str
    sessao_id: str

def gerar_apresentacao_rica_integrada(json_resultado: dict, mensagem_original: str, endpoint: str) -> dict:
    """Apresentação rica integrada diretamente no main.py"""
    
    if "erro" in json_resultado:
        return {
            "mensagem": "Desculpe, houve um problema. Tente novamente ou reformule sua pergunta.",
            "tipo": "erro_rico",
            "dados_originais": json_resultado
        }
    
    if "/produtos/busca" in endpoint:
        resultados = json_resultado.get("resultados", [])
        
        if not resultados:
            return {
                "mensagem": f"Não encontrei produtos para '{mensagem_original}'. Tente outro termo de busca!",
                "tipo": "busca_vazia_rica",
                "dados_originais": json_resultado
            }
        
        # Detecta emoji
        emoji = "🍫" if any(palavra in mensagem_original.lower() for palavra in ["chocolate", "nescau", "achocolatado"]) else "🛒"
        
        # Monta mensagem rica
        mensagem_partes = [f"Encontrei {len(resultados)} produtos para '{mensagem_original}'! {emoji}"]
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
                
                # Formata quantidade
                if qtunit == 1:
                    desc_quantidade = f"Com 1 {'Unidade' if unidade == 'UN' else unidade}"
                else:
                    unidade_nome = {
                        "UN": "Unidades", "CX": "Caixas", "PC": "Pacotes", 
                        "KG": "Kilos", "LT": "Latas"
                    }.get(unidade, unidade + "s")
                    desc_quantidade = f"Com {qtunit} {unidade_nome}"
                
                # Adiciona linha do item
                mensagem_partes.append(f"{item_id} R$ {preco:.2f} - {desc_quantidade}")
                
                # Para contexto estruturado
                produtos_numerados.append({
                    "item_id": item_id,
                    "produto_nome": nome_produto,
                    "preco": float(preco),
                    "unidade": unidade,
                    "quantidade_pacote": qtunit
                })
            
            mensagem_partes.append("")  # Linha em branco
        
        # Call-to-action
        mensagem_partes.append("💡 Digite o ID do produto desejado!")
        
        return {
            "mensagem": "\n".join(mensagem_partes),
            "tipo": "busca_rica_integrada",
            "contexto_estruturado": {"produtos": produtos_numerados},
            "dados_originais": json_resultado
        }
    
    elif "/carrinhos/" in endpoint:
        if endpoint.endswith("/itens"):
            return {
                "mensagem": "✅ Item adicionado ao carrinho com sucesso! 🛒\n\nSua compra foi registrada. Quer ver o carrinho completo?",
                "tipo": "carrinho_adicionado_rico",
                "dados_originais": json_resultado
            }
        
        itens = json_resultado.get("itens", [])
        valor_total = json_resultado.get("valor_total", 0)
        
        if not itens:
            return {
                "mensagem": "Seu carrinho está vazio! 🛒\n\nQue tal buscar alguns produtos? Digite o que você precisa!",
                "tipo": "carrinho_vazio_rico",
                "dados_originais": json_resultado
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
        
        return {
            "mensagem": "\n".join(mensagem_partes),
            "tipo": "carrinho_rico_integrado",
            "dados_originais": json_resultado
        }
    
    # Fallback genérico
    return {
        "mensagem": "✅ Operação realizada com sucesso!",
        "tipo": "sucesso_generico",
        "dados_originais": json_resultado
    }

@app.get("/ping")
async def ping():
    """Status com fix direto"""
    stats = get_fallback_stats()
    return {
        "status": "ok", 
        "version": "FIX_DIRETO_v1",
        "apresentacao": "rica_integrada",
        "cache_prompts": stats.get("cache_prompts", 0),
        "performance": "ultra_rapida_com_formatacao"
    }

@app.get("/health")
async def health():
    """Health check do fix direto"""
    stats = get_fallback_stats()
    return {
        "status": "healthy",
        "version": "FIX_DIRETO_v1",
        "features": [
            "apresentacao_rica_integrada",
            "ids_numerados_para_selecao", 
            "emojis_contextuais",
            "performance_sub_100ms",
            "formatacao_original_restaurada"
        ],
        "cache_stats": stats
    }

@app.post("/chat")
async def receber_mensagem(body: EntradaChat):
    """Endpoint com apresentação rica integrada"""
    inicio = time.time()
    
    # Usa executor que está funcionando (fallback)
    resultado = executar_regras_com_fallback(body.model_dump())
    
    # Se tem dados originais, aplica apresentação rica
    if isinstance(resultado, dict) and resultado.get("dados_originais") and resultado.get("tipo", "").endswith("_fallback"):
        # Detecta endpoint da decisão original
        endpoint = ""
        if "resultados" in resultado.get("dados_originais", {}):
            endpoint = "/produtos/busca"
        elif "itens" in resultado.get("dados_originais", {}):
            endpoint = "/carrinhos/"
        
        if endpoint:
            print("🎨 Aplicando apresentação rica integrada...")
            resultado = gerar_apresentacao_rica_integrada(
                resultado["dados_originais"], 
                body.texto, 
                endpoint
            )
    
    tempo_resposta = time.time() - inicio
    
    # Performance sempre presente
    if isinstance(resultado, dict):
        resultado["_performance"] = {
            "tempo_resposta_ms": round(tempo_resposta * 1000, 2),
            "versao": "FIX_DIRETO_v1",
            "apresentacao_rica": resultado.get("tipo", "").endswith("_rica") or resultado.get("tipo", "").endswith("_integrada")
        }
    
    return resultado

@app.get("/cache/stats")
async def cache_stats():
    """Stats do fix direto"""
    return get_fallback_stats()

@app.get("/demo/exemplo")
async def demo_exemplo():
    """Demonstra como fica a resposta rica"""
    exemplo_resultado = {
        "resultados": [
            {
                "id": 9089,
                "codprod": 63930,
                "descricao": "ACHOC.PO NESCAU LT. 1X200G",
                "descricaoweb": "ACHOCOLATADO PÓ NESCAU LATA 200G",
                "itens": [
                    {"id": 18135, "unidade": "LT", "qtunit": 1, "pvenda": 6.79, "poferta": 6.79},
                    {"id": 18136, "unidade": "CX", "qtunit": 24, "pvenda": 162.96, "poferta": 158.07}
                ]
            }
        ]
    }
    
    resultado_rico = gerar_apresentacao_rica_integrada(exemplo_resultado, "buscar nescau", "/produtos/busca")
    
    return {
        "entrada_original": exemplo_resultado,
        "saida_rica": resultado_rico,
        "diferenca": "Transformou JSON técnico em conversa rica com IDs numerados"
    }

@app.post("/cache/clear")
async def clear_cache():
    """Limpa cache"""
    from app.servicos.executor_fallback_inteligente import CACHE_PROMPTS, CACHE_RESPOSTAS_LLM
    CACHE_PROMPTS.clear()
    CACHE_RESPOSTAS_LLM.clear()
    return {"status": "cache_cleared", "version": "FIX_DIRETO_v1"}