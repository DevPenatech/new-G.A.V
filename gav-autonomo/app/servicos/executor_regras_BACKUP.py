# gav-autonomo/app/servicos/executor_regras.py
# FASE 4: Orquestrador 100% genérico via prompt
# Elimina todas as regras hardcoded, tudo vira configuração via prompt

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
    Orquestrador genérico que só executa chamadas HTTP baseadas em decisões do LLM.
    Zero regras hardcoded - tudo configurado via prompt.
    """
    # Guard: se alguém chamar passando string, não quebrar
    if isinstance(mensagem, str):
        mensagem = {"texto": mensagem, "sessao_id": "anon"}
    
    with open("app/config/model_manifest.yml", encoding="utf-8") as f:
        manifesto = yaml.safe_load(f)
    
    for regra in manifesto["regras"]:
        if regra["action"] == "decisao_llm":
            return _processar_decisao_llm(mensagem, regra, manifesto)
    
    return {"erro": "Nenhuma regra válida encontrada no manifesto."}

def _processar_decisao_llm(mensagem: dict, regra: dict, manifesto: dict) -> dict:
    """Processa uma decisão via LLM e executa a chamada HTTP resultante."""
    try:
        # 1. Busca prompt e exemplos
        p = obter_prompt_por_nome(
            nome=regra["prompt"], 
            espaco=regra["espaco_prompt"], 
            versao=regra["versao_prompt"]
        )
        exemplos = listar_exemplos_prompt(p["id"])

        # 2. Pede decisão ao LLM
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

        # 4. Executa a ferramenta genérica
        if decisao.get("tool_name") == "api_call":
            return _executar_api_call(decisao.get("parameters", {}), mensagem["sessao_id"])
        else:
            return {"erro": f"Ferramenta não reconhecida: {decisao.get('tool_name')}"}
            
    except Exception as e:
        return {"erro": f"Erro interno: {str(e)}"}

def _executar_api_call(params: dict, sessao_id: str) -> dict:
    """
    Executa uma chamada HTTP genérica baseada nos parâmetros do LLM.
    Implementa ciclo de reparo automático em caso de erro 4xx/422.
    """
    endpoint = params.get("endpoint", "")
    method = params.get("method", "GET").upper()
    body = params.get("body", {})
    
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

def _handle_resposta_conversacional(mensagem: str) -> dict:
    """
    Lida com respostas conversacionais que não são chamadas de API.
    Endpoint especial /chat/resposta que não existe na API real.
    """
    return {"mensagem": mensagem, "tipo": "conversacional"}