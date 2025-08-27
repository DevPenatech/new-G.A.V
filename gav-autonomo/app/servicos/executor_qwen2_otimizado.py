# gav-autonomo/app/servicos/executor_qwen2_otimizado.py
"""
Executor Qwen2:7b Otimizado - Melhor Performance + Formatação Rica
- Qwen2:7b para tudo, mas configurações diferentes para cada fase
- Decisão: timeout 5s, poucos exemplos, temperature baixa
- Apresentação: timeout 10s, exemplos completos, temperature média
- Cache agressivo para manter velocidade
"""

import time
import json
import httpx
import yaml
import hashlib
from typing import Dict, Optional

# Imports existentes
from app.adaptadores.cliente_negocio import obter_prompt_por_nome, listar_exemplos_prompt
from app.validadores.modelos import validar_json_contra_schema, carregar_schema
from app.config.settings import config

# Reutiliza cache
from app.servicos.executor_fallback_inteligente import (
    CACHE_PROMPTS, CACHE_RESPOSTAS_LLM, CACHE_TTL,
    hash_prompt, get_prompt_cached_super, decidir_por_heuristica
)

API_NEGOCIO_URL = config.API_NEGOCIO_URL.rstrip("/")

def executar_regras_qwen2_otimizado(mensagem: dict | str) -> dict:
    """
    Executor otimizado com qwen2:7b configurado especificamente para cada fase
    """
    start_time = time.time()
    
    if isinstance(mensagem, str):
        mensagem = {"texto": mensagem, "sessao_id": "anon"}
    
    try:
        with open("app/config/model_manifest.yml", encoding="utf-8") as f:
            manifesto = yaml.safe_load(f)
        
        for regra in manifesto["regras"]:
            if regra["action"] == "decisao_llm":
                resultado = processar_decisao_qwen2_otimizado(mensagem, regra, manifesto)
                
                tempo_total = time.time() - start_time
                print(f"🚀 Tempo QWEN2 OTIMIZADO: {tempo_total:.2f}s")
                
                if isinstance(resultado, dict):
                    resultado["_performance"] = {
                        "tempo_resposta_ms": round(tempo_total * 1000, 2),
                        "versao": "qwen2_otimizado_v1",
                        "modelo_decisao": "qwen2:7b",
                        "modelo_apresentacao": "qwen2:7b"
                    }
                
                return resultado
    
        return {"erro": "Nenhuma regra válida encontrada no manifesto."}
        
    except Exception as e:
        return {"erro": f"Erro interno: {str(e)}"}

def processar_decisao_qwen2_otimizado(mensagem: dict, regra: dict, manifesto: dict) -> dict:
    """
    Processamento com qwen2:7b otimizado para cada fase
    """
    try:
        # 1. FASE DECISÃO: Qwen2:7b rápido (5s, poucos exemplos)
        print("⚡ Fase 1: Decisão rápida com Qwen2:7b...")
        
        prompt_data = get_prompt_cached_super(
            nome=regra["prompt"],
            espaco=regra["espaco_prompt"], 
            versao=str(regra["versao_prompt"])
        )
        
        if not prompt_data:
            return {"erro": "Prompt não encontrado"}
        
        # Decisão com configurações rápidas
        entrada_usuario = mensagem["texto"]
        cache_hash = hash_prompt(prompt_data["template"], entrada_usuario, 2)  # Força apenas 2 exemplos
        
        decisao = completar_com_qwen2_configurado(
            prompt_data["template_otimizado"], 
            entrada_usuario, 
            cache_hash,
            config_type="decisao",
            exemplos=prompt_data["exemplos"][:2]  # Apenas 2 exemplos
        )
        
        # Fallback heurística se falhar
        if decisao.get("erro") or not decisao.get("tool_name"):
            print("🎯 Qwen2 decisão falhou - usando heurística")
            decisao = decidir_por_heuristica(entrada_usuario)
        
        # Validação
        schema = carregar_schema(regra["schema"])
        if not validar_json_contra_schema(decisao, schema):
            decisao = decidir_por_heuristica(entrada_usuario)
        
        # 2. FASE EXECUÇÃO API
        print("📡 Fase 2: Executando API...")
        tool_name = decisao.get("tool_name")
        
        if tool_name == "api_call":
            return executar_api_call_qwen2(decisao.get("parameters", {}), mensagem["sessao_id"])
            
        elif tool_name == "api_call_with_presentation":
            # Executa API
            json_resultado = executar_api_call_qwen2(decisao.get("parameters", {}), mensagem["sessao_id"])
            
            # 3. FASE APRESENTAÇÃO: Qwen2:7b completo (10s, exemplos completos)
            return aplicar_apresentacao_qwen2_rica(
                json_resultado, 
                mensagem["texto"], 
                decisao.get("parameters", {}),
                mensagem["sessao_id"]
            )
                
        else:
            return {"erro": f"Ferramenta não reconhecida: {tool_name}"}
            
    except Exception as e:
        return {"erro": f"Erro no processamento qwen2: {str(e)}"}

def completar_com_qwen2_configurado(template_compilado: str, entrada_usuario: str, cache_hash: str,
                                   config_type: str = "decisao", exemplos: list = None) -> dict:
    """
    Qwen2:7b com configurações específicas por tipo de tarefa
    """
    
    # Verifica cache
    if cache_hash in CACHE_RESPOSTAS_LLM:
        entry = CACHE_RESPOSTAS_LLM[cache_hash]
        if time.time() - entry["timestamp"] < CACHE_TTL:
            print(f"⚡ Cache HIT - Qwen2 {config_type}")
            return entry["resposta"]
    
    # Monta prompt com exemplos limitados se necessário
    if config_type == "decisao" and exemplos:
        # Para decisão: usa template otimizado simples
        prompt_final = template_compilado.replace("{ENTRADA_USUARIO}", entrada_usuario)
    else:
        # Para apresentação: monta prompt completo
        prompt_final = montar_prompt_completo(template_compilado, entrada_usuario, exemplos or [])
    
    # Configurações por tipo de tarefa
    if config_type == "decisao":
        timeout = 5
        max_tokens = 200
        temperature = 0.05  # Muito baixo para consistência
        print(f"🤖 Qwen2 DECISÃO (timeout: {timeout}s, tokens: {max_tokens})...")
    else:  # apresentacao
        timeout = 20  # AUMENTADO de 10s para 20s
        max_tokens = 600  # REDUZIDO de 800 para 600 (mais rápido)
        temperature = 0.15  # Mais criativo para apresentação
        print(f"🎨 Qwen2 APRESENTAÇÃO (timeout: {timeout}s, tokens: {max_tokens})...")
    
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                f"{config.OLLAMA_HOST}/api/generate",
                json={
                    "model": "qwen2:7b",
                    "prompt": prompt_final,
                    "format": "json",
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "top_p": 0.9,
                        "num_predict": max_tokens,
                        "stop": ["```", "\n\n"] if config_type == "decisao" else ["```"]
                    }
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                conteudo = data.get("response", "").strip()
                
                try:
                    resultado = json.loads(conteudo)
                    
                    # Armazena no cache
                    CACHE_RESPOSTAS_LLM[cache_hash] = {
                        "resposta": resultado,
                        "timestamp": time.time()
                    }
                    
                    return resultado
                    
                except json.JSONDecodeError:
                    # Tenta extrair JSON com regex
                    import re
                    json_match = re.search(r'\{.*\}', conteudo, re.DOTALL)
                    if json_match:
                        try:
                            return json.loads(json_match.group())
                        except:
                            pass
                    
                    print(f"⚠️ Qwen2 {config_type} JSON inválido: {conteudo[:200]}...")
                    return {"erro": f"qwen2_{config_type}_json_invalido"}
    
    except (httpx.TimeoutException, Exception) as e:
        print(f"❌ Qwen2 {config_type} falhou: {e}")
        return {"erro": f"qwen2_{config_type}_failed"}

def montar_prompt_completo(template: str, entrada_usuario: str, exemplos: list) -> str:
    """Monta prompt completo com exemplos para apresentação rica"""
    partes = [template.strip()]
    
    # Adiciona exemplos completos para apresentação rica
    for i, ex in enumerate(exemplos):
        input_ex = ex.get("exemplo_input", "").strip()
        output_ex = ex.get("exemplo_output_json", "").strip()
        
        if input_ex and output_ex:
            partes.append(f"Exemplo {i+1}:")
            partes.append(f"Input: {input_ex}")
            partes.append(f"Output: {output_ex}")
    
    partes.append(f"Entrada atual: {entrada_usuario}")
    
    return "\n\n".join(partes)

def aplicar_apresentacao_qwen2_rica(json_resultado: dict, mensagem_original: str, 
                                   params_api: dict, sessao_id: str) -> dict:
    """
    Apresentação rica usando Qwen2:7b com configurações otimizadas
    """
    
    try:
        endpoint = params_api.get("endpoint", "")
        prompt_apresentador = determinar_prompt_apresentador(endpoint, json_resultado)
        
        if not prompt_apresentador:
            return json_resultado
        
        print("🎨 Aplicando apresentação rica com Qwen2:7b...")
        
        # Busca prompt do apresentador
        prompt_data = get_prompt_cached_super(prompt_apresentador, "autonomo", "1")
        
        if not prompt_data:
            return json_resultado
        
        # Contexto para apresentação
        contexto_apresentacao = montar_contexto_apresentacao_rica(
            mensagem_original, json_resultado, endpoint
        )
        
        # Cache para apresentação
        cache_hash = hash_prompt(
            prompt_data["template"], 
            contexto_apresentacao, 
            len(prompt_data["exemplos"])
        )
        
        # Qwen2:7b configurado para apresentação rica
        resposta_conversacional = completar_com_qwen2_configurado(
            prompt_data["template"],
            contexto_apresentacao,
            cache_hash,
            config_type="apresentacao",
            exemplos=prompt_data["exemplos"]  # Exemplos completos
        )
        
        if "erro" in resposta_conversacional:
            print("⚠️ Apresentação rica falhou, usando fallback estruturado...")
            return aplicar_fallback_estruturado(json_resultado, mensagem_original, endpoint)
        
        # Salva contexto em background
        if sessao_id and sessao_id != "anon":
            contexto_estruturado = resposta_conversacional.get("contexto_estruturado", {})
            if contexto_estruturado and contexto_estruturado.get("produtos"):
                salvar_contexto_background_qwen2(
                    sessao_id, contexto_estruturado, mensagem_original,
                    resposta_conversacional.get("mensagem", "")
                )
        
        resultado_final = {
            "mensagem": resposta_conversacional.get("mensagem", "Resposta processada com sucesso!"),
            "tipo": resposta_conversacional.get("tipo", "apresentacao_rica_qwen2"),
            "dados_originais": json_resultado,
            "usou_llm_apresentacao": True
        }
        
        # Inclui contexto estruturado se presente
        if resposta_conversacional.get("contexto_estruturado"):
            resultado_final["contexto_estruturado"] = resposta_conversacional["contexto_estruturado"]
        
        return resultado_final
        
    except Exception as e:
        print(f"Erro na apresentação Qwen2: {e}")
        return json_resultado

def aplicar_fallback_estruturado(json_resultado: dict, mensagem_original: str, endpoint: str) -> dict:
    """Fallback estruturado quando LLM apresentação falha - garante mensagem sempre"""
    
    if "/produtos/busca" in endpoint:
        resultados = json_resultado.get("resultados", [])
        
        if not resultados:
            return {
                "mensagem": f"Não encontrei produtos para '{mensagem_original}'. Tente outro termo de busca!",
                "tipo": "busca_vazia_fallback",
                "dados_originais": json_resultado
            }
        
        # Cria apresentação estruturada com IDs
        emoji = "🍫" if any(palavra in mensagem_original.lower() for palavra in ["chocolate", "nescau", "achocolatado"]) else "🛒"
        
        mensagem_partes = [f"Encontrei {len(resultados)} produtos para '{mensagem_original}'! {emoji}"]
        mensagem_partes.append("")
        
        produtos_numerados = []
        
        for produto in resultados:
            nome_produto = produto.get("descricaoweb") or produto.get("descricao", "Produto")
            itens = produto.get("itens", [])
            
            if not itens:
                continue
            
            mensagem_partes.append(nome_produto.upper())
            
            for item in itens:
                item_id = item.get("id")
                preco = item.get("poferta") or item.get("pvenda")
                unidade = item.get("unidade", "UN")
                qtunit = item.get("qtunit", 1)
                
                if not item_id or not preco or preco <= 0:
                    continue
                
                desc_quantidade = f"Com {qtunit} {'Unidade' if unidade == 'UN' else unidade}{'s' if qtunit > 1 else ''}"
                mensagem_partes.append(f"{item_id} R$ {preco:.2f} - {desc_quantidade}")
                
                produtos_numerados.append({
                    "item_id": item_id,
                    "produto_nome": nome_produto,
                    "preco": float(preco),
                    "unidade": unidade,
                    "quantidade_pacote": qtunit
                })
            
            mensagem_partes.append("")
        
        mensagem_partes.append("💡 Digite o ID do produto desejado!")
        
        return {
            "mensagem": "\n".join(mensagem_partes),
            "tipo": "busca_fallback_estruturado",
            "contexto_estruturado": {"produtos": produtos_numerados},
            "dados_originais": json_resultado
        }
    
    elif "/carrinhos/" in endpoint:
        if endpoint.endswith("/itens"):
            return {
                "mensagem": "✅ Item adicionado ao carrinho com sucesso! 🛒\n\nSua compra foi registrada. Quer ver o carrinho completo?",
                "tipo": "carrinho_adicionado_fallback",
                "dados_originais": json_resultado
            }
        
        itens = json_resultado.get("itens", [])
        valor_total = json_resultado.get("valor_total", 0)
        
        if not itens:
            return {
                "mensagem": "Seu carrinho está vazio! 🛒\n\nQue tal buscar alguns produtos? Digite o que você precisa!",
                "tipo": "carrinho_vazio_fallback",
                "dados_originais": json_resultado
            }
        
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
            "tipo": "carrinho_fallback_estruturado", 
            "dados_originais": json_resultado
        }
    
    # Fallback genérico
    return {
        "mensagem": "Operação realizada com sucesso! Como posso ajudar mais?",
        "tipo": "fallback_generico",
        "dados_originais": json_resultado
    }

# Funções auxiliares reutilizadas
def executar_api_call_qwen2(params: dict, sessao_id: str) -> dict:
    """Reutiliza execução de API"""
    from app.servicos.executor_fallback_inteligente import executar_api_call_rapido
    return executar_api_call_rapido(params, sessao_id)

def determinar_prompt_apresentador(endpoint: str, json_resultado: dict) -> Optional[str]:
    """Reutiliza determinação de prompt"""
    if "erro" in json_resultado:
        return "prompt_apresentador_erro"
    if "/produtos/busca" in endpoint:
        return "prompt_apresentador_busca"
    if "/carrinhos/" in endpoint:
        return "prompt_apresentador_carrinho"
    return None

def montar_contexto_apresentacao_rica(mensagem_original: str, json_resultado: dict, endpoint: str) -> str:
    """Contexto rico para apresentação"""
    if "/produtos/busca" in endpoint:
        resultados = json_resultado.get("resultados", [])
        status_busca = json_resultado.get("status_busca", "sucesso")
        
        return f"""query_original: "{mensagem_original}"
resultados_json: {json.dumps(json_resultado, ensure_ascii=False)}
status_busca: "{status_busca}"
total_encontrados: {len(resultados)}"""

    elif "/carrinhos/" in endpoint:
        if endpoint.endswith("/itens"):
            acao = "item_adicionado"
        else:
            acao = "carrinho_visualizado" if json_resultado.get("itens") else "carrinho_vazio"
            
        return f"""acao_realizada: "{acao}"
carrinho_json: {json.dumps(json_resultado, ensure_ascii=False)}
mensagem_original: "{mensagem_original}" """

    else:
        return f"""contexto_usuario: "{mensagem_original}"
resultado_api: {json.dumps(json_resultado, ensure_ascii=False)}
endpoint: "{endpoint}" """

def salvar_contexto_background_qwen2(sessao_id: str, contexto_estruturado: dict, 
                                    mensagem_original: str, resposta_apresentada: str):
    """Salva contexto em background"""
    try:
        payload = {
            "tipo_contexto": "busca_qwen2_rica",
            "contexto_estruturado": contexto_estruturado,
            "mensagem_original": mensagem_original,
            "resposta_apresentada": resposta_apresentada
        }
        httpx.post(f"{API_NEGOCIO_URL}/contexto/{sessao_id}", json=payload, timeout=3.0)
    except:
        pass

def get_stats_qwen2_otimizado() -> dict:
    """Stats do sistema Qwen2 otimizado"""
    return {
        "cache_prompts": len(CACHE_PROMPTS),
        "cache_llm_responses": len(CACHE_RESPOSTAS_LLM),
        "version": "qwen2_otimizado_v1",
        "modelo_unico": "qwen2:7b",
        "configuracoes": {
            "decisao": "5s timeout, 200 tokens, temp 0.05, 2 exemplos",
            "apresentacao": "10s timeout, 800 tokens, temp 0.15, exemplos completos"
        },
        "performance_target": "3-5s com formatação original completa"
    }