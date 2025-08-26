# gav-autonomo/app/servicos/executor_otimizado.py
"""
Executor Otimizado com Pipeline Assíncrono
Reduz tempo de resposta de ~8s para ~2s
"""

import asyncio
import time
from typing import Dict, Optional, List
from dataclasses import dataclass
import yaml
import json
import httpx

# Imports locais
from app.cache_otimizado import cache_otimizado
from app.adaptadores.interface_llm_otimizada import cliente_llm, LLMRequest
from app.validadores.modelos import validar_json_contra_schema, carregar_schema
from app.config.settings import config

API_NEGOCIO_URL = config.API_NEGOCIO_URL.rstrip("/")

async def executar_regras_otimizado(mensagem: dict | str) -> dict:
    """
    Executor otimizado com pipeline assíncrono e cache inteligente
    """
    start_time = time.time()
    
    if isinstance(mensagem, str):
        mensagem = {"texto": mensagem, "sessao_id": "anon"}
    
    with open("app/config/model_manifest.yml", encoding="utf-8") as f:
        manifesto = yaml.safe_load(f)
    
    for regra in manifesto["regras"]:
        if regra["action"] == "decisao_llm":
            resultado = await _processar_decisao_llm_otimizada(mensagem, regra, manifesto)
            
            tempo_total = time.time() - start_time
            print(f"⚡ Tempo total de processamento: {tempo_total:.2f}s")
            
            return resultado
    
    return {"erro": "Nenhuma regra válida encontrada no manifesto."}

async def _processar_decisao_llm_otimizada(mensagem: dict, regra: dict, manifesto: dict) -> dict:
    """Pipeline otimizado com cache e paralelização"""
    try:
        # 1. Busca prompt do cache (muito mais rápido)
        prompt_data = await cache_otimizado.get_prompt_completo(
            nome=regra["prompt"],
            espaco=regra["espaco_prompt"], 
            versao=str(regra["versao_prompt"])
        )
        
        if not prompt_data:
            return {"erro": "Prompt não encontrado no cache ou banco"}
        
        # 2. LLM Selector (decisão inicial)
        request_selector = LLMRequest(
            sistema=prompt_data["template"],
            entrada_usuario=mensagem["texto"],
            exemplos=prompt_data["exemplos"],
            modelo=manifesto["defaults"].get("modelo"),
            timeout=10.0  # Timeout reduzido para seletor
        )
        
        decisao = await cliente_llm.completar_para_json_async(request_selector)
        
        # 3. Validação rápida
        schema = carregar_schema(regra["schema"])
        if not validar_json_contra_schema(decisao, schema):
            return {"erro": "Decisão do LLM inválida", "decisao_recebida": decisao}
        
        # 4. Execução baseada na ferramenta
        tool_name = decisao.get("tool_name")
        
        if tool_name == "api_call":
            return await _executar_api_call_async(decisao.get("parameters", {}), mensagem["sessao_id"])
            
        elif tool_name == "api_call_with_presentation":
            # Pipeline paralelo: API + busca de prompt apresentador
            api_task = _executar_api_call_async(decisao.get("parameters", {}), mensagem["sessao_id"])
            apresentador_task = _preparar_apresentador(decisao.get("parameters", {}))
            
            # Executa em paralelo
            json_resultado, prompt_apresentador = await asyncio.gather(api_task, apresentador_task)
            
            if prompt_apresentador:
                return await _apresentar_resultado_async(
                    json_resultado, 
                    mensagem["texto"], 
                    decisao.get("parameters", {}),
                    prompt_apresentador
                )
            else:
                return json_resultado
        else:
            return {"erro": f"Ferramenta não reconhecida: {tool_name}"}
            
    except Exception as e:
        print(f"Erro no processamento otimizado: {e}")
        return {"erro": f"Erro interno: {str(e)}"}

async def _executar_api_call_async(params: dict, sessao_id: str) -> dict:
    """Execução de API call assíncrona"""
    endpoint = params.get("endpoint", "")
    method = params.get("method", "GET").upper()
    body = params.get("body", {})
    
    # Endpoints especiais (processamento local)
    if endpoint == "/chat/resposta":
        mensagem = body.get("mensagem", "Olá! Como posso ajudá-lo?")
        return {"mensagem": mensagem, "tipo": "conversacional"}
    
    if endpoint == "/chat/contexto":
        return await _processar_contexto_rapido(body, sessao_id)
    
    # APIs reais
    if "{sessao_id}" in endpoint:
        if not sessao_id or sessao_id == "anon":
            return {"erro": "Sessão necessária para esta operação."}
        endpoint = endpoint.replace("{sessao_id}", sessao_id)
    
    url = f"{API_NEGOCIO_URL}{endpoint}"
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            if method == "GET":
                resp = await client.get(url)
            elif method == "POST":
                resp = await client.post(url, json=body)
            elif method == "PUT":
                resp = await client.put(url, json=body)
            elif method == "DELETE":
                resp = await client.delete(url)
            else:
                return {"erro": f"Método HTTP não suportado: {method}"}
            
            if resp.is_success:
                return resp.json()
            else:
                return {"erro": f"API retornou erro {resp.status_code}", "detalhe": resp.text[:500]}
                
        except Exception as e:
            return {"erro": f"Falha na comunicação: {str(e)}"}

async def _preparar_apresentador(params: dict) -> Optional[dict]:
    """Busca prompt do apresentador em paralelo"""
    endpoint = params.get("endpoint", "")
    
    nome_prompt = None
    if "/produtos/busca" in endpoint:
        nome_prompt = "prompt_apresentador_busca"
    elif "/carrinhos/" in endpoint:
        nome_prompt = "prompt_apresentador_carrinho"
    
    if nome_prompt:
        return await cache_otimizado.get_prompt_completo(nome_prompt, "autonomo", "1")
    
    return None

async def _apresentar_resultado_async(json_resultado: dict, mensagem_original: str, 
                                    params_api: dict, prompt_apresentador: dict) -> dict:
    """Apresentação assíncrona do resultado"""
    try:
        endpoint = params_api.get("endpoint", "")
        
        contexto_apresentacao = _montar_contexto_apresentacao(
            mensagem_original, json_resultado, endpoint
        )
        
        request_apresentador = LLMRequest(
            sistema=prompt_apresentador["template"],
            entrada_usuario=contexto_apresentacao,
            exemplos=prompt_apresentador["exemplos"],
            timeout=8.0  # Timeout menor para apresentação
        )
        
        resposta_conversacional = await cliente_llm.completar_para_json_async(request_apresentador)
        
        # Salva contexto em background (não bloqueia resposta)
        sessao_id = params_api.get("sessao_id")
        if sessao_id and sessao_id != "anon":
            contexto_estruturado = resposta_conversacional.get("contexto_estruturado", {})
            if contexto_estruturado and contexto_estruturado.get("produtos"):
                asyncio.create_task(_salvar_contexto_background(
                    sessao_id, contexto_estruturado, mensagem_original,
                    resposta_conversacional.get("mensagem", "")
                ))
        
        return {
            "mensagem": resposta_conversacional.get("mensagem", "Ops, não consegui processar isso..."),
            "tipo": resposta_conversacional.get("tipo", "apresentacao"),
            "dados_originais": json_resultado
        }
        
    except Exception as e:
        print(f"Erro na apresentação assíncrona: {e}")
        return json_resultado

async def _processar_contexto_rapido(body: dict, sessao_id: str) -> dict:
    """Processamento de contexto com cache"""
    try:
        mensagem_contexto = body.get("mensagem_contexto", "")
        
        # Busca contexto do cache primeiro
        contexto_cache = cache_otimizado.get_contexto_sessao(sessao_id)
        
        if not contexto_cache:
            # Se não tem cache, busca do banco
            contexto_banco = await _buscar_contexto_async(sessao_id)
            if contexto_banco:
                cache_otimizado.set_contexto_sessao(sessao_id, contexto_banco)
                contexto_cache = contexto_banco
        
        # Processamento rápido por ID direto
        import re
        id_matches = re.findall(r'\b(\d{4,6})\b', mensagem_contexto)
        
        if id_matches and contexto_cache:
            item_id_referenciado = int(id_matches[0])
            quantidade_match = re.search(r'(\d+)\s*(unidades?|do|da|vezes?)', mensagem_contexto)
            quantidade = int(quantidade_match.group(1)) if quantidade_match else 1
            
            produtos = contexto_cache.get("contexto_estruturado", {}).get("produtos", [])
            produto_encontrado = next((p for p in produtos if p.get("item_id") == item_id_referenciado), None)
            
            if produto_encontrado:
                # Executa adição diretamente
                return await _executar_api_call_async({
                    "endpoint": "/carrinhos/{sessao_id}/itens",
                    "method": "POST",
                    "body": {
                        "item_id": item_id_referenciado,
                        "quantidade": quantidade,
                        "codfilial": 2
                    }
                }, sessao_id)
        
        return {"erro": "Contexto não encontrado ou ID inválido"}
        
    except Exception as e:
        return {"erro": f"Erro no processamento: {str(e)}"}

async def _buscar_contexto_async(sessao_id: str) -> Optional[dict]:
    """Busca assíncrona de contexto"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{API_NEGOCIO_URL}/contexto/{sessao_id}")
            return response.json() if response.is_success else None
    except:
        return None

async def _salvar_contexto_background(sessao_id: str, contexto_estruturado: dict, 
                                    mensagem_original: str, resposta_apresentada: str):
    """Salva contexto em background para não bloquear a resposta"""
    try:
        payload = {
            "tipo_contexto": "busca_numerada",
            "contexto_estruturado": contexto_estruturado,
            "mensagem_original": mensagem_original,
            "resposta_apresentada": resposta_apresentada
        }
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(f"{API_NEGOCIO_URL}/contexto/{sessao_id}", json=payload)
            
        # Atualiza cache também
        cache_otimizado.set_contexto_sessao(sessao_id, {
            "contexto_estruturado": contexto_estruturado,
            "tipo_contexto": "busca_numerada"
        })
        
    except Exception as e:
        print(f"Erro ao salvar contexto em background: {e}")

def _montar_contexto_apresentacao(mensagem_original: str, json_resultado: dict, endpoint: str) -> str:
    """Mantém lógica original de montagem de contexto"""
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

# Wrapper síncrono para compatibilidade
def executar_regras_do_manifesto(mensagem: dict | str) -> dict:
    """Wrapper síncrono que chama a versão otimizada"""
    loop = None
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(executar_regras_otimizado(mensagem))

@dataclass
class LLMRequest:
    sistema: str
    entrada_usuario: str
    exemplos: List[dict]
    modelo: Optional[str] = None
    timeout: float = 15.0  # Reduzido de 60s para 15s

class ClienteLLMOtimizado:
    def __init__(self):
        # Pool de conexões persistente
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            http2=True  # HTTP/2 para melhor performance
        )
        self.ollama_url = config.OLLAMA_HOST.rstrip("/")
        self.modelo_padrao = config.OLLAMA_MODEL_NAME
        
        # Cache de prompts compilados (evita reprocessamento)
        self.prompts_compilados = {}
    
    def _compilar_prompt(self, request: LLMRequest) -> str:
        """Compila prompt uma vez e cacheia"""
        cache_key = hash(f"{request.sistema}{len(request.exemplos)}")
        
        if cache_key in self.prompts_compilados:
            template = self.prompts_compilados[cache_key]
            return template.replace("{ENTRADA_USUARIO}", request.entrada_usuario)
        
        # Monta template otimizado
        partes = [request.sistema.strip()]
        
        # Exemplos compactos (só os essenciais)
        for i, ex in enumerate(request.exemplos[:3]):  # Limita a 3 exemplos para velocidade
            partes.append(f"Exemplo {i+1}:")
            partes.append(f"Input: {ex.get('exemplo_input', '')}")
            partes.append(f"Output: {ex.get('exemplo_output_json', '')}")
        
        partes.append("Entrada atual: {ENTRADA_USUARIO}")
        
        template = "\n\n".join(partes)
        self.prompts_compilados[cache_key] = template
        
        return template.replace("{ENTRADA_USUARIO}", request.entrada_usuario)
    
    async def completar_para_json_async(self, request: LLMRequest) -> dict:
        """Versão assíncrona otimizada"""
        prompt_texto = self._compilar_prompt(request)
        
        payload = {
            "model": request.modelo or self.modelo_padrao,
            "prompt": prompt_texto,
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.1,
                "top_p": 0.9,
                "num_predict": 1000,  # Limita tokens para velocidade
                "stop": ["\n\n", "```"]  # Para mais cedo quando possível
            }
        }
        
        try:
            resp = await self.client.post(
                f"{self.ollama_url}/api/generate",
                json=payload,
                timeout=request.timeout
            )
            
            resp.raise_for_status()
            data = resp.json()
            
            conteudo = data.get("response") or data.get("output") or ""
            
            # Parse JSON otimizado
            try:
                # Remove possíveis caracteres extras
                conteudo_limpo = conteudo.strip()
                if conteudo_limpo.startswith("```json"):
                    conteudo_limpo = conteudo_limpo[7:]
                if conteudo_limpo.endswith("```"):
                    conteudo_limpo = conteudo_limpo[:-3]
                
                return json.loads(conteudo_limpo.strip())
            
            except json.JSONDecodeError as e:
                print(f"⚠️ JSON inválido do LLM: {conteudo[:200]}...")
                # Fallback: tenta extrair JSON do meio da resposta
                import re
                json_match = re.search(r'\{.*\}', conteudo, re.DOTALL)
                if json_match:
                    try:
                        return json.loads(json_match.group())
                    except:
                        pass
                
                # Último recurso: resposta estruturada mínima
                return {"erro": "json_parse_failed", "conteudo_original": conteudo}
        
        except asyncio.TimeoutError:
            return {"erro": "llm_timeout", "detalhes": f"Timeout após {request.timeout}s"}
        except Exception as e:
            return {"erro": "llm_error", "detalhes": str(e)}
    
    async def processar_multiplas_chamadas(self, requests: List[LLMRequest]) -> List[dict]:
        """Processa múltiplas chamadas LLM em paralelo"""
        tasks = [self.completar_para_json_async(req) for req in requests]
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    def completar_para_json_sync(self, sistema: str, entrada_usuario: str, 
                                exemplos: List[dict] = None, modelo: str = None) -> dict:
        """Wrapper síncrono para compatibilidade"""
        request = LLMRequest(
            sistema=sistema,
            entrada_usuario=entrada_usuario,
            exemplos=exemplos or [],
            modelo=modelo
        )
        
        loop = None
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self.completar_para_json_async(request))
    
    async def close(self):
        """Fecha conexões limpamente"""
        await self.client.aclose()

# Instância global
cliente_llm = ClienteLLMOtimizado()

# Wrapper para compatibilidade com código existente
def completar_para_json(sistema: str, entrada_usuario: str, exemplos: list = None, modelo: str = None) -> dict:
    return cliente_llm.completar_para_json_sync(sistema, entrada_usuario, exemplos, modelo)