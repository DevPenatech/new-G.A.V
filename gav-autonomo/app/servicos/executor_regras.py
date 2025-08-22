# gav-autonomo/app/servicos/executor_regras.py
# FASE 5A: Pipeline de Apresentação - JSON → Conversa Natural
# Mantém arquitetura 100% prompt, adiciona segunda etapa de apresentação

from app.adaptadores.cliente_negocio import obter_prompt_por_nome, listar_exemplos_prompt
from app.adaptadores.interface_llm import completar_para_json
from app.validadores.modelos import validar_json_contra_schema, carregar_schema
import yaml
import json
import httpx
from app.config.settings import config

API_NEGOCIO_URL = config.API_NEGOCIO_URL.rstrip("/")

def executar_regras_do_manifesto(mensagem: dict | str) -> dict:
    """
    Orquestrador com pipeline de 2 etapas:
    1) LLM Selector → decide API call
    2) LLM Apresentador → JSON → conversa (se api_call_with_presentation)
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

        # 4. Pipeline de execução
        tool_name = decisao.get("tool_name")
        
        if tool_name == "api_call":
            # Pipeline simples: API → retorna JSON direto
            return _executar_api_call(decisao.get("parameters", {}), mensagem["sessao_id"])
            
        elif tool_name == "api_call_with_presentation":
            # Pipeline duplo: API → LLM Apresentador → conversa
            json_resultado = _executar_api_call(decisao.get("parameters", {}), mensagem["sessao_id"])
            return _apresentar_resultado(json_resultado, mensagem["texto"], decisao.get("parameters", {}))
            
        else:
            return {"erro": f"Ferramenta não reconhecida: {tool_name}"}
            
    except Exception as e:
        return {"erro": f"Erro interno: {str(e)}"}

def _apresentar_resultado(json_resultado: dict, mensagem_original: str, params_api: dict) -> dict:
    """
    NOVA FUNÇÃO: Segunda etapa do pipeline
    Transforma JSON da API em conversa natural via LLM Apresentador
    """
    try:
        # Determina tipo de apresentação baseado no endpoint
        endpoint = params_api.get("endpoint", "")
        prompt_apresentador = _determinar_prompt_apresentador(endpoint, json_resultado)
        
        if not prompt_apresentador:
            # Fallback: se não conseguir apresentar, retorna JSON original
            return json_resultado
        
        # Busca prompt e exemplos do Apresentador
        p_apresentador = obter_prompt_por_nome(nome=prompt_apresentador, espaco="autonomo", versao=1)
        exemplos_apresentador = listar_exemplos_prompt(p_apresentador["id"])
        
        # Monta contexto para o LLM Apresentador
        contexto_apresentacao = _montar_contexto_apresentacao(
            mensagem_original, json_resultado, endpoint
        )
        
        # LLM Apresentador: JSON → conversa
        resposta_conversacional = completar_para_json(
            sistema=p_apresentador["template"],
            entrada_usuario=contexto_apresentacao,
            exemplos=exemplos_apresentador
        )
        
        # Retorna mensagem conversacional
        return {
            "mensagem": resposta_conversacional.get("mensagem", "Ops, não consegui processar isso..."),
            "tipo": resposta_conversacional.get("tipo", "apresentacao"),
            "dados_originais": json_resultado  # Para debugging
        }
        
    except Exception as e:
        # Fallback em caso de erro: retorna JSON original
        print(f"Erro na apresentação: {e}")
        return json_resultado

def _determinar_prompt_apresentador(endpoint: str, json_resultado: dict) -> str:
    """Determina qual prompt de apresentação usar baseado no endpoint e resultado."""
    
    # Detecta erro
    if "erro" in json_resultado or json_resultado.get("success") is False:
        return "prompt_apresentador_erro"
    
    # Endpoints de busca
    if "/produtos/busca" in endpoint:
        return "prompt_apresentador_busca"
    
    # Endpoints de carrinho
    if "/carrinhos/" in endpoint:
        return "prompt_apresentador_carrinho"
    
    # Conversa pura
    if "/chat/resposta" in endpoint:
        # Já é conversa, não precisa apresentar
        return None
    
    # Default para casos novos
    return "prompt_apresentador_busca"

def _montar_contexto_apresentacao(mensagem_original: str, json_resultado: dict, endpoint: str) -> str:
    """Monta o contexto que será enviado para o LLM Apresentador."""
    
    if "/produtos/busca" in endpoint:
        # Contexto para apresentação de busca
        resultados = json_resultado.get("resultados", [])
        status_busca = json_resultado.get("status_busca", "sucesso")
        
        return f"""query_original: "{mensagem_original}"
resultados_json: {json.dumps(json_resultado, ensure_ascii=False)}
status_busca: "{status_busca}"
total_encontrados: {len(resultados)}"""

    elif "/carrinhos/" in endpoint:
        # Contexto para apresentação de carrinho
        if endpoint.endswith("/itens"):
            acao = "item_adicionado"
        else:
            acao = "carrinho_visualizado" if json_resultado.get("itens") else "carrinho_vazio"
            
        return f"""acao_realizada: "{acao}"
carrinho_json: {json.dumps(json_resultado, ensure_ascii=False)}
mensagem_original: "{mensagem_original}" """

    else:
        # Contexto genérico
        return f"""contexto_usuario: "{mensagem_original}"
resultado_api: {json.dumps(json_resultado, ensure_ascii=False)}
endpoint: "{endpoint}" """

def _executar_api_call(params: dict, sessao_id: str) -> dict:
    """
    Executa uma chamada HTTP genérica (mantém lógica original da Fase 4).
    """
    endpoint = params.get("endpoint", "")
    method = params.get("method", "GET").upper()
    body = params.get("body", {})
    
    # Endpoint especial para conversa direta
    if endpoint == "/chat/resposta":
        mensagem = body.get("mensagem", "Olá! Como posso ajudá-lo?")
        return {"mensagem": mensagem, "tipo": "conversacional"}
    
    # Substitui {sessao_id} no endpoint se necessário
    if "{sessao_id}" in endpoint:
        if not sessao_id or sessao_id == "anon":
            return {"erro": "Sessão necessária para esta operação."}
        endpoint = endpoint.replace("{sessao_id}", sessao_id)
    
    # Monta a URL completa
    url = f"{API_NEGOCIO_URL}{endpoint}"
    
    try:
        # Executa a chamada HTTP
        response = _fazer_request_http(url, method, body)
        
        # Se sucesso, retorna diretamente
        if response.get("success"):
            return response.get("data", {})
        
        # Se erro 4xx/422, tenta reparo automático
        if response.get("status_code") in [400, 422]:
            return _tentar_reparo_automatico(params, response, sessao_id)
        
        # Outros erros retorna como está
        return {"erro": f"API retornou erro {response.get('status_code')}: {response.get('error')}"}
        
    except Exception as e:
        return {"erro": f"Falha na comunicação com API: {str(e)}"}

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
        
        # Se requisição bem-sucedida (2xx)
        if resp.is_success:
            return {"success": True, "data": resp.json()}
        
        # Se erro, tenta extrair mensagem de erro
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
    """
    Ciclo de reparo automático: envia erro para LLM e tenta novamente com payload corrigido.
    (Mantém lógica original da Fase 4)
    """
    try:
        # Busca o prompt de reparo
        p_reparo = obter_prompt_por_nome(nome="prompt_api_repair", espaco="autonomo", versao=1)
        exemplos_reparo = listar_exemplos_prompt(p_reparo["id"])
        
        # Monta contexto para o LLM de reparo
        contexto_reparo = f"""endpoint_original: {params_originais.get('endpoint')}
method_original: {params_originais.get('method')}
body_original: {json.dumps(params_originais.get('body', {}))}
erro_retornado: {json.dumps(erro_response.get('error', {}))}
mensagem_usuario: (contexto da mensagem original)"""

        # Pede ao LLM para corrigir o payload
        correcao = completar_para_json(
            sistema=p_reparo["template"],
            entrada_usuario=contexto_reparo,
            exemplos=exemplos_reparo
        )
        
        # Aplica a correção
        params_corrigidos = params_originais.copy()
        params_corrigidos["body"] = correcao.get("body_corrigido", params_originais.get("body", {}))
        
        # Tenta novamente com payload corrigido
        return _executar_api_call(params_corrigidos, sessao_id)
        
    except Exception as e:
        # Se o reparo falhar, retorna o erro original
        return {"erro": f"Reparo automático falhou: {str(e)}. Erro original: {erro_response.get('error')}"}