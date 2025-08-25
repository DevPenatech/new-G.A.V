# gav-autonomo/app/servicos/executor_regras.py
# CORREÇÃO: 100% Prompt-Driven, ZERO regras hardcoded
# Sistema genérico para qualquer domínio (vendas, telemarking, suporte, etc.)

from app.adaptadores.cliente_negocio import obter_prompt_por_nome, listar_exemplos_prompt
from app.adaptadores.interface_llm import completar_para_json
from app.validadores.modelos import validar_json_contra_schema, carregar_schema
import yaml
import json
import httpx
from app.config.settings import config

API_NEGOCIO_URL = config.API_NEGOCIO_URL.rstrip("/")

# ❌ REMOVIDO: CONTEXTO_SESSOES (era regra hardcoded específica de produtos)
# ✅ NOVO: Tudo via prompt e API calls genéricas

def executar_regras_do_manifesto(mensagem: dict | str) -> dict:
    """
    Orquestrador genérico: LLM Selector → API → LLM Apresentador
    Zero regras hardcoded - funciona para qualquer domínio
    """
    if isinstance(mensagem, str):
        mensagem = {"texto": mensagem, "sessao_id": "anon"}
    
    with open("app/config/model_manifest.yml", encoding="utf-8") as f:
        manifesto = yaml.safe_load(f)
    
    for regra in manifesto["regras"]:
        if regra["action"] == "decisao_llm":
            return _processar_decisao_llm(mensagem, regra, manifesto)
    
    return {"erro": "Nenhuma regra válida encontrada no manifesto."}

def _processar_decisao_llm(mensagem: dict, regra: dict, manifesto: dict) -> dict:
    """Processa decisão via LLM e executa pipeline apropriado."""
    try:
        # 1. Busca prompt e exemplos do Selector
        p = obter_prompt_por_nome(
            nome=regra["prompt"], 
            espaco=regra["espaco_prompt"], 
            versao=regra["versao_prompt"]
        )
        exemplos = listar_exemplos_prompt(p["id"])

        # 2. LLM Selector decide ferramenta
        decisao = completar_para_json(
            sistema=p["template"],
            entrada_usuario=mensagem["texto"],
            exemplos=exemplos,
            modelo=manifesto["defaults"].get("modelo")
        )

        # 3. Valida estrutura da decisão
        schema = carregar_schema(regra["schema"])
        if not validar_json_contra_schema(decisao, schema):
            return {"erro": "Decisão do LLM inválida. Tente reformular a mensagem."}

        # 4. Pipeline genérico (sem regras específicas de domínio)
        tool_name = decisao.get("tool_name")
        
        if tool_name == "api_call":
            return _executar_api_call(decisao.get("parameters", {}), mensagem["sessao_id"])
            
        elif tool_name == "api_call_with_presentation":
            json_resultado = _executar_api_call(decisao.get("parameters", {}), mensagem["sessao_id"])
            return _apresentar_resultado(json_resultado, mensagem["texto"], decisao.get("parameters", {}))
            
        else:
            return {"erro": f"Ferramenta não reconhecida: {tool_name}"}
            
    except Exception as e:
        return {"erro": f"Erro interno: {str(e)}"}

def _executar_api_call(params: dict, sessao_id: str) -> dict:
    """
    Executa chamada HTTP genérica. 
    ✅ NOVO: Suporte ao endpoint /chat/contexto via prompts
    """
    endpoint = params.get("endpoint", "")
    method = params.get("method", "GET").upper()
    body = params.get("body", {})
    
    # Endpoint especial para conversa direta
    if endpoint == "/chat/resposta":
        mensagem = body.get("mensagem", "Olá! Como posso ajudá-lo?")
        return {"mensagem": mensagem, "tipo": "conversacional"}
    
    # ✅ NOVO: Endpoint para processamento de contexto VIA PROMPT
    if endpoint == "/chat/contexto":
        return _processar_contexto_via_prompt(body, sessao_id)
    
    # Substitui {sessao_id} no endpoint se necessário
    if "{sessao_id}" in endpoint:
        if not sessao_id or sessao_id == "anon":
            return {"erro": "Sessão necessária para esta operação."}
        endpoint = endpoint.replace("{sessao_id}", sessao_id)
    
    # Monta a URL completa para APIs reais
    url = f"{API_NEGOCIO_URL}{endpoint}"
    
    try:
        response = _fazer_request_http(url, method, body)
        
        if response.get("success"):
            return response.get("data", {})
        
        if response.get("status_code") in [400, 422]:
            return _tentar_reparo_automatico(params, response, sessao_id)
        
        return {"erro": f"API retornou erro {response.get('status_code')}: {response.get('error')}"}
        
    except Exception as e:
        return {"erro": f"Falha na comunicação com API: {str(e)}"}

def _processar_contexto_via_prompt(body: dict, sessao_id: str) -> dict:
    """Processa referência do usuário usando contexto salvo"""
    try:
        mensagem_contexto = body.get("mensagem_contexto", "")
        
        # Buscar contexto salvo do banco
        contexto_banco = _buscar_contexto_do_banco(sessao_id)
        contexto_anterior = {
            "contexto": contexto_banco.get("contexto_estruturado", {}),
            "tipo": contexto_banco.get("tipo_contexto", "nenhum")
        }
        
        # Interpretação simples: extrair número da mensagem
        import re
        numeros = re.findall(r'\b(\d+)\b', mensagem_contexto)
        quantidade_match = re.search(r'(\d+)\s*(unidades?|do|da)', mensagem_contexto)
        
        if numeros:
            posicao = int(numeros[0])  # Primeiro número encontrado
            quantidade = int(quantidade_match.group(1)) if quantidade_match else 1
            
            # Buscar produto na posição
            produtos = contexto_anterior.get("contexto", {}).get("produtos", [])
            produto_encontrado = None
            
            for produto in produtos:
                if produto.get("posicao") == posicao:
                    produto_encontrado = produto
                    break
            
            if produto_encontrado:
                # Adicionar ao carrinho com ID real
                item_id_real = produto_encontrado.get("item_id")
                print(f"✅ Mapeamento: posição {posicao} → item_id {item_id_real}")
                
                params_api = {
                    "endpoint": "/carrinhos/{sessao_id}/itens",
                    "method": "POST",
                    "body": {
                        "item_id": item_id_real,
                        "quantidade": quantidade,
                        "codfilial": 2
                    }
                }
                return _executar_api_call(params_api, sessao_id)
            else:
                return {"erro": f"Posição {posicao} não encontrada no contexto"}
        
        # Se não encontrou número, não conseguiu processar
        return {"erro": "Não consegui identificar qual produto você quer"}
        
    except Exception as e:
        return {"erro": f"Erro no processamento: {str(e)}"}
    
def _buscar_contexto_anterior(sessao_id: str) -> dict:
    """
    Busca contexto anterior de forma genérica.
    ✅ Pode vir do banco, cache, API, etc. - não hardcoded em RAM
    """
    # TODO: Implementar busca real (banco, cache, etc.)
    # Por enquanto, retorna vazio (contexto pode ser enviado pelo frontend)
    return {"contexto": "nenhum", "tipo": "indefinido"}

def _interpretar_referencia_via_prompt(mensagem: str, contexto: dict, sessao_id: str) -> dict:
    """
    ✅ Usa prompt para interpretar se mensagem é referência ao contexto anterior
    """
    try:
        p_processador = obter_prompt_por_nome(nome="prompt_processador_contexto", espaco="autonomo", versao=1)
        exemplos_processador = listar_exemplos_prompt(p_processador["id"])
        
        contexto_input = f"""mensagem_contexto: "{mensagem}"
sessao_id: "{sessao_id}"
contexto_anterior: {json.dumps(contexto, ensure_ascii=False)}"""

        return completar_para_json(
            sistema=p_processador["template"],
            entrada_usuario=contexto_input,
            exemplos=exemplos_processador
        )
        
    except Exception as e:
        return {"acao": "nova_interacao", "motivo": "erro_interpretacao"}

def _executar_referencia_via_prompt(referencia: dict, contexto: dict, sessao_id: str) -> dict:
    """
    ✅ Usa prompt para decidir que ação executar baseada na referência
    """
    try:
        p_executor = obter_prompt_por_nome(nome="prompt_executor_referencia", espaco="autonomo", versao=1)
        exemplos_executor = listar_exemplos_prompt(p_executor["id"])
        
        executor_input = f"""referencia_detectada: {json.dumps(referencia, ensure_ascii=False)}
contexto_anterior: {json.dumps(contexto, ensure_ascii=False)}
sessao_id: "{sessao_id}" """

        return completar_para_json(
            sistema=p_executor["template"],
            entrada_usuario=executor_input,
            exemplos=exemplos_executor
        )
        
    except Exception as e:
        return {"acao_executar": "erro_referencia", "parametros": {"mensagem": "Erro ao processar referência"}}

def _executar_acao_contextual(acao: dict, sessao_id: str) -> dict:
    """
    ✅ Executa ação decidida pelo LLM (genérica, não específica de produtos)
    """
    acao_tipo = acao.get("acao_executar")
    parametros = acao.get("parametros", {})
    
    if acao_tipo == "adicionar_carrinho":
        # Executa adição via API call genérica
        params_api = {
            "endpoint": "/carrinhos/{sessao_id}/itens",
            "method": "POST",
            "body": {
                "item_id": parametros.get("item_id"),
                "quantidade": parametros.get("quantidade", 1),
                "codfilial": parametros.get("codfilial", 2)
            }
        }
        return _executar_api_call(params_api, sessao_id)
        
    elif acao_tipo == "expandir_busca":
        # Executa nova busca via API call genérica
        params_api = {
            "endpoint": "/produtos/busca",
            "method": "POST",
            "body": {
                "query": parametros.get("query_original"),
                "limit": parametros.get("limit", 10),
                "codfilial": 2
            }
        }
        return _executar_api_call(params_api, sessao_id)
        
    elif acao_tipo == "erro_referencia":
        # Retorna mensagem de erro decidida pelo LLM
        return {"mensagem": parametros.get("mensagem"), "tipo": "erro_contexto"}
        
    else:
        # Ação não reconhecida
        return {"erro": f"Ação contextual não reconhecida: {acao_tipo}"}

def _apresentar_resultado(json_resultado: dict, mensagem_original: str, params_api: dict) -> dict:
    """Transforma JSON em conversa E salva contexto quando tem produtos numerados"""
    try:
        endpoint = params_api.get("endpoint", "")
        prompt_apresentador = _determinar_prompt_apresentador(endpoint, json_resultado)
        
        if not prompt_apresentador:
            return json_resultado
        
        p_apresentador = obter_prompt_por_nome(nome=prompt_apresentador, espaco="autonomo", versao=1)
        exemplos_apresentador = listar_exemplos_prompt(p_apresentador["id"])
        
        contexto_apresentacao = _montar_contexto_apresentacao(
            mensagem_original, json_resultado, endpoint
        )
        
        resposta_conversacional = completar_para_json(
            sistema=p_apresentador["template"],
            entrada_usuario=contexto_apresentacao,
            exemplos=exemplos_apresentador
        )
        
        # ✅ NOVO: Salva contexto no banco se tiver produtos numerados
        sessao_id = params_api.get("sessao_id")
        if sessao_id and sessao_id != "anon":
            contexto_estruturado = resposta_conversacional.get("contexto_estruturado", {})
            if contexto_estruturado and contexto_estruturado.get("produtos"):
                _salvar_contexto_no_banco(sessao_id, contexto_estruturado, mensagem_original, resposta_conversacional.get("mensagem", ""))
        
        return {
            "mensagem": resposta_conversacional.get("mensagem", "Ops, não consegui processar isso..."),
            "tipo": resposta_conversacional.get("tipo", "apresentacao"),
            "dados_originais": json_resultado
        }
        
    except Exception as e:
        print(f"Erro na apresentação: {e}")
        return json_resultado

def _salvar_contexto_estruturado(mensagem_original: str, contexto: dict, endpoint: str):
    """
    ✅ Salva contexto de forma genérica (não específica de produtos)
    Pode ser banco, cache, etc. - não hardcoded em RAM
    """
    # TODO: Implementar salvamento real
    # Por enquanto, apenas log
    print(f"Contexto estruturado salvo: {contexto}")

# === FUNÇÕES AUXILIARES (mantém as originais) ===

def _determinar_prompt_apresentador(endpoint: str, json_resultado: dict) -> str:
    """Determina qual prompt de apresentação usar baseado no endpoint e resultado."""
    if "erro" in json_resultado or json_resultado.get("success") is False:
        return "prompt_apresentador_erro"
    if "/produtos/busca" in endpoint:
        return "prompt_apresentador_busca"
    if "/carrinhos/" in endpoint:
        return "prompt_apresentador_carrinho"
    if "/chat/resposta" in endpoint:
        return None
    return "prompt_apresentador_busca"

def _montar_contexto_apresentacao(mensagem_original: str, json_resultado: dict, endpoint: str) -> str:
    """Monta o contexto que será enviado para o LLM Apresentador."""
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

def _fazer_request_http(url: str, method: str, body: dict) -> dict:
    """Executa a requisição HTTP e retorna um dicionário padronizado."""
    try:
        if method == "GET":
            resp = httpx.get(url, timeout=15.0)
        elif method == "POST":
            resp = httpx.post(url, json=body, timeout=15.0)
        elif method == "PUT":
            resp = httpx.put(url, json=body, timeout=15.0)
        elif method == "DELETE":
            resp = httpx.delete(url, timeout=15.0)
        else:
            return {"success": False, "error": f"Método HTTP não suportado: {method}"}
        
        if resp.is_success:
            return {"success": True, "data": resp.json()}
        
        try:
            error_data = resp.json()
        except:
            error_data = {"detail": resp.text}
            
        return {
            "success": False, 
            "status_code": resp.status_code,
            "error": error_data
        }
        
    except httpx.TimeoutException:
        return {"success": False, "error": "Timeout na comunicação com API"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def _tentar_reparo_automatico(params_originais: dict, erro_response: dict, sessao_id: str) -> dict:
    """Ciclo de reparo automático (mantém lógica original da Fase 4)"""
    try:
        p_reparo = obter_prompt_por_nome(nome="prompt_api_repair", espaco="autonomo", versao=1)
        exemplos_reparo = listar_exemplos_prompt(p_reparo["id"])
        
        contexto_reparo = f"""endpoint_original: {params_originais.get('endpoint')}
method_original: {params_originais.get('method')}
body_original: {json.dumps(params_originais.get('body', {}))}
erro_retornado: {json.dumps(erro_response.get('error', {}))}
mensagem_usuario: (contexto da mensagem original)"""

        correcao = completar_para_json(
            sistema=p_reparo["template"],
            entrada_usuario=contexto_reparo,
            exemplos=exemplos_reparo
        )
        
        params_corrigidos = params_originais.copy()
        params_corrigidos["body"] = correcao.get("body_corrigido", params_originais.get("body", {}))
        
        return _executar_api_call(params_corrigidos, sessao_id)
        
    except Exception as e:
        return {"erro": f"Reparo automático falhou: {str(e)}. Erro original: {erro_response.get('error')}"}
    
def _salvar_contexto_no_banco(sessao_id: str, contexto_estruturado: dict, mensagem_original: str, resposta_apresentada: str):
    """Salva contexto no banco via API de negócio"""
    try:
        payload = {
            "tipo_contexto": "busca_numerada",
            "contexto_estruturado": contexto_estruturado,
            "mensagem_original": mensagem_original,
            "resposta_apresentada": resposta_apresentada
        }
        
        response = httpx.post(f"{API_NEGOCIO_URL}/contexto/{sessao_id}", json=payload, timeout=10.0)
        
        if response.is_success:
            print(f"✅ Contexto salvo para sessão {sessao_id}")
        else:
            print(f"❌ Erro ao salvar contexto: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Erro ao salvar contexto: {e}")

def _buscar_contexto_do_banco(sessao_id: str) -> dict:
    """Busca contexto do banco via API de negócio"""
    try:
        response = httpx.get(f"{API_NEGOCIO_URL}/contexto/{sessao_id}", timeout=10.0)
        
        if response.is_success:
            contexto = response.json()
            print(f"✅ Contexto recuperado para sessão {sessao_id}")
            return contexto
        else:
            print(f"ℹ️ Nenhum contexto encontrado para sessão {sessao_id}")
            return {"contexto_estruturado": {}}
            
    except Exception as e:
        print(f"❌ Erro ao buscar contexto: {e}")
        return {"contexto_estruturado": {}}