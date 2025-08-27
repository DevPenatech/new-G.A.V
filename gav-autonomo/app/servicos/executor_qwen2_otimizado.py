# gav-autonomo/app/servicos/executor_qwen2_otimizado.py
"""
Executor Qwen2:7b DEFINITIVO - Performance + Formatação Rica Original
- Configurações otimizadas específicas para cada fase
- Fallback inteligente garantindo mensagem SEMPRE
- Cache agressivo para máxima performance
- Timeout escalonado: decisão rápida, apresentação generosa
"""

from app.adaptadores.cliente_negocio import obter_prompt_por_nome, listar_exemplos_prompt
from app.adaptadores.interface_llm import completar_para_json
from app.validadores.modelos import validar_json_contra_schema, carregar_schema
import yaml
import json
import httpx
import time
from app.config.settings import config

API_NEGOCIO_URL = config.API_NEGOCIO_URL.rstrip("/")

# ===== CACHE AGRESSIVO =====
_cache_prompts = {}
_cache_exemplos = {}
_cache_decisoes = {}  # Cache de decisões por hash de mensagem

def _get_cache_key(texto: str) -> str:
    """Gera chave de cache baseada no texto"""
    import hashlib
    return hashlib.md5(texto.encode()).hexdigest()[:12]

def _buscar_prompt_cache(nome: str, espaco: str, versao: int) -> tuple:
    """Busca prompt e exemplos do cache ou da API"""
    cache_key = f"{nome}_{espaco}_{versao}"
    
    if cache_key not in _cache_prompts:
        print(f"🔄 Cache MISS para {cache_key} - buscando...")
        p = obter_prompt_por_nome(nome=nome, espaco=espaco, versao=versao)
        exemplos = listar_exemplos_prompt(p["id"])
        _cache_prompts[cache_key] = p
        _cache_exemplos[cache_key] = exemplos
        print(f"✅ Cache populado para {cache_key}")
    else:
        print(f"⚡ Cache HIT para {cache_key}")
    
    return _cache_prompts[cache_key], _cache_exemplos[cache_key]

def executar_regras_do_manifesto(mensagem: dict | str) -> dict:
    """
    Orquestrador Qwen2:7b Definitivo - Duas Fases Otimizadas
    """
    inicio = time.time()
    
    if isinstance(mensagem, str):
        mensagem = {"texto": mensagem, "sessao_id": "anon"}
    
    with open("app/config/model_manifest.yml", encoding="utf-8") as f:
        manifesto = yaml.safe_load(f)
    
    for regra in manifesto["regras"]:
        if regra["action"] == "decisao_llm":
            resultado = _processar_qwen2_otimizado(mensagem, regra, manifesto)
            tempo_total = time.time() - inicio
            print(f"🚀 Tempo QWEN2 DEFINITIVO: {tempo_total:.2f}s")
            return resultado
    
    return {"erro": "Nenhuma regra válida encontrada no manifesto."}

def _processar_qwen2_otimizado(mensagem: dict, regra: dict, manifesto: dict) -> dict:
    """Pipeline de 2 fases com Qwen2:7b otimizado"""
    
    # ===== FASE 1: DECISÃO ULTRA-RÁPIDA =====
    print("⚡ Fase 1: Decisão rápida com Qwen2:7b...")
    
    try:
        decisao = _executar_decisao_otimizada(mensagem, regra)
        
        if "erro" in decisao:
            return decisao
            
        # ===== FASE 2: EXECUÇÃO DA API =====
        print("📡 Fase 2: Executando API...")
        tool_name = decisao.get("tool_name")
        
        if tool_name == "api_call":
            return _executar_api_call(decisao.get("parameters", {}), mensagem["sessao_id"])
            
        elif tool_name == "api_call_with_presentation":
            json_resultado = _executar_api_call(decisao.get("parameters", {}), mensagem["sessao_id"])
            return _apresentar_resultado_definitivo(json_resultado, mensagem["texto"], decisao.get("parameters", {}))
            
        else:
            return {"erro": f"Ferramenta não reconhecida: {tool_name}"}
            
    except Exception as e:
        return {"erro": f"Erro interno definitivo: {str(e)}"}

def _executar_decisao_otimizada(mensagem: dict, regra: dict) -> dict:
    """Executa decisão com cache e configuração otimizada"""
    
    # Verifica cache de decisão
    cache_key = _get_cache_key(mensagem["texto"])
    if cache_key in _cache_decisoes:
        print(f"⚡ Cache HIT para decisão - reuso instantâneo")
        return _cache_decisoes[cache_key]
    
    # Busca prompt do cache
    p, exemplos = _buscar_prompt_cache(
        nome=regra["prompt"], 
        espaco=regra["espaco_prompt"], 
        versao=regra["versao_prompt"]
    )
    
    # Limita exemplos para velocidade máxima
    exemplos_limitados = exemplos[:2] if len(exemplos) > 2 else exemplos
    if len(exemplos) > len(exemplos_limitados):
        print(f"⚡ Exemplos limitados: {len(exemplos)} → {len(exemplos_limitados)}")
    
    # Configuração ultra-otimizada para decisão
    decisao = _completar_qwen2_configurado(
        sistema=p["template"],
        entrada_usuario=mensagem["texto"],
        exemplos=exemplos_limitados,
        config_type="decisao"
    )

    # Valida estrutura da decisão
    schema = carregar_schema(regra["schema"])
    if not validar_json_contra_schema(decisao, schema):
        return {"erro": "Decisão do LLM inválida. Tente reformular a mensagem."}
    
    # Salva no cache
    _cache_decisoes[cache_key] = decisao
    
    return decisao

def _completar_qwen2_configurado(sistema: str, entrada_usuario: str, exemplos: list, config_type: str) -> dict:
    """LLM Qwen2:7b com configurações específicas por tipo de tarefa"""
    
    # Configurações por tipo de tarefa
    if config_type == "decisao":
        timeout = 8  # Aumentado de 5s → 8s
        max_tokens = 200
        temperature = 0.01  # Ultra baixo para consistência máxima
        print(f"🤖 Qwen2 DECISÃO (timeout: {timeout}s, tokens: {max_tokens})...")
    elif config_type == "apresentacao":
        timeout = 25  # Aumentado de 20s → 25s 
        max_tokens = 500  # Reduzido de 600 → 500 para processar mais rápido
        temperature = 0.3   # Aumentado para mais criatividade
        print(f"🎨 Qwen2 APRESENTAÇÃO (timeout: {timeout}s, tokens: {max_tokens})...")
    else:
        timeout = 15
        max_tokens = 400
        temperature = 0.1
        print(f"🔧 Qwen2 GENÉRICO (timeout: {timeout}s, tokens: {max_tokens})...")

    # Monta prompt com exemplos limitados para velocidade
    partes = [sistema.strip()]
    for ex in (exemplos or []):
        partes.append("Exemplo de entrada:\n" + (ex.get("exemplo_input") or "").strip())
        partes.append("Exemplo de saída (JSON):\n" + (ex.get("exemplo_output_json") or "").strip())
    partes.append("Entrada do usuário:\n" + (entrada_usuario or "").strip())
    prompt_texto = "\n\n".join(partes)

    # Executa com timeout específico
    try:
        resp = httpx.post(
            f"{config.OLLAMA_HOST.rstrip('/')}/api/generate",
            json={
                "model": config.OLLAMA_MODEL_NAME,
                "prompt": prompt_texto,
                "format": "json",
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                    "stop": ["```", "Exemplo", "###"]  # Para parar mais cedo
                }
            },
            timeout=timeout
        )
        resp.raise_for_status()
        data = resp.json()
        conteudo = data.get("response") or data.get("output") or ""
        return json.loads(conteudo)
        
    except httpx.TimeoutException:
        print(f"❌ Qwen2 {config_type} falhou: timed out")
        return {"erro": f"timeout_{config_type}"}
    except json.JSONDecodeError:
        print(f"❌ Qwen2 {config_type} falhou: JSON inválido")
        return {"erro": f"json_invalido_{config_type}"}
    except Exception as e:
        print(f"❌ Qwen2 {config_type} falhou: {str(e)}")
        return {"erro": f"erro_{config_type}"}

def _apresentar_resultado_definitivo(json_resultado: dict, mensagem_original: str, params_api: dict) -> dict:
    """Apresentação rica com fallback GARANTIDO"""
    
    try:
        endpoint = params_api.get("endpoint", "")
        prompt_apresentador = _determinar_prompt_apresentador(endpoint, json_resultado)
        
        if not prompt_apresentador:
            return json_resultado
        
        print("🎨 Aplicando apresentação rica com Qwen2:7b...")
        
        # Busca prompt do cache
        p_apresentador, exemplos_apresentador = _buscar_prompt_cache(
            nome=prompt_apresentador, espaco="autonomo", versao=1
        )
        
        # Limita exemplos para apresentação mais rápida
        exemplos_limitados = exemplos_apresentador[:2] if len(exemplos_apresentador) > 2 else exemplos_apresentador
        if len(exemplos_apresentador) > len(exemplos_limitados):
            print(f"⚡ Exemplos limitados: {len(exemplos_apresentador)} → {len(exemplos_limitados)}")
        
        contexto_apresentacao = _montar_contexto_apresentacao(
            mensagem_original, json_resultado, endpoint
        )
        
        # Tenta apresentação rica com Qwen2:7b
        resposta_conversacional = _completar_qwen2_configurado(
            sistema=p_apresentador["template"],
            entrada_usuario=contexto_apresentacao,
            exemplos=exemplos_limitados,
            config_type="apresentacao"
        )
        
        # Se funcionou, retorna apresentação rica
        if "erro" not in resposta_conversacional:
            print("✅ Apresentação rica gerada com sucesso!")
            
            # Salva contexto se necessário
            _salvar_contexto_se_necessario(params_api, resposta_conversacional, mensagem_original)
            
            return {
                "mensagem": resposta_conversacional.get("mensagem", "Ops, não consegui processar isso..."),
                "tipo": resposta_conversacional.get("tipo", "apresentacao"),
                "dados_originais": json_resultado,
                "modelo_apresentacao": "qwen2_rica"
            }
        
        # Se falhou, usa fallback estruturado
        print("⚠️ Apresentação rica falhou, usando fallback estruturado...")
        return _aplicar_fallback_estruturado_definitivo(json_resultado, mensagem_original, endpoint)
        
    except Exception as e:
        print(f"❌ Erro na apresentação: {e}")
        return _aplicar_fallback_estruturado_definitivo(json_resultado, mensagem_original, endpoint)

def _aplicar_fallback_estruturado_definitivo(json_resultado: dict, mensagem_original: str, endpoint: str) -> dict:
    """Fallback estruturado DEFINITIVO - garante mensagem SEMPRE com IDs numerados"""
    
    print("🛡️ Aplicando fallback estruturado definitivo...")
    
    if "/produtos/busca" in endpoint:
        resultados = json_resultado.get("resultados", [])
        status_busca = json_resultado.get("status_busca", "sucesso")
        
        if not resultados:
            mensagem = "Não encontrei produtos para sua busca. 🔍 Tente termos diferentes ou mais gerais!"
        else:
            # Gera lista numerada com IDs diretos (formato original do git)
            produtos_formatados = []
            contador = 1
            contexto_produtos = []
            
            for produto in resultados[:5]:  # Limita a 5 para não ficar muito longo
                itens = produto.get("itens", [])
                if itens:
                    item_principal = itens[0]  # Pega primeiro item disponível
                    preco = item_principal.get("preco_oferta") or item_principal.get("preco")
                    
                    if preco:
                        # Formato original: ID direto + descrição + preço
                        linha = f"{contador}. ID {item_principal['id']} - {produto['descricao']} - R$ {preco:.2f}"
                        produtos_formatados.append(linha)
                        
                        # Salva para contexto
                        contexto_produtos.append({
                            "item_id": item_principal["id"],
                            "descricao": produto["descricao"],
                            "preco": preco,
                            "posicao": contador
                        })
                        contador += 1
            
            if produtos_formatados:
                emoji_inicial = "🍫" if "nescau" in mensagem_original.lower() else "🛒"
                mensagem = f"Encontrei essas opções para você! {emoji_inicial}\n\n" + "\n".join(produtos_formatados)
                mensagem += f"\n\n💡 Para adicionar, diga: 'adicionar ID [número] ao carrinho'"
                
                # Contexto estruturado para referências futuras
                contexto_estruturado = {"produtos": contexto_produtos}
            else:
                mensagem = "Encontrei produtos mas sem informações de preço disponíveis. 💰"
                contexto_estruturado = {}
        
        return {
            "mensagem": mensagem,
            "tipo": "busca_produtos",
            "dados_originais": json_resultado,
            "modelo_apresentacao": "fallback_estruturado",
            "contexto_estruturado": contexto_estruturado
        }
    
    elif "/carrinhos/" in endpoint:
        if endpoint.endswith("/itens"):
            # Item adicionado
            mensagem = "Item adicionado ao carrinho! 🛒✨ Sua compra foi registrada com sucesso."
        else:
            # Ver carrinho
            itens = json_resultado.get("itens", [])
            if not itens:
                mensagem = "Seu carrinho está vazio! 🛒💨 Que tal adicionar alguns produtos?"
            else:
                total = json_resultado.get("valor_total", 0)
                mensagem = f"Seu carrinho tem {len(itens)} itens totalizando R$ {total:.2f}! 🛒💰"
        
        return {
            "mensagem": mensagem,
            "tipo": "carrinho",
            "dados_originais": json_resultado,
            "modelo_apresentacao": "fallback_estruturado"
        }
    
    else:
        # Endpoint genérico
        mensagem = "Operação realizada com sucesso! ✅"
        return {
            "mensagem": mensagem,
            "tipo": "generico",
            "dados_originais": json_resultado,
            "modelo_apresentacao": "fallback_estruturado"
        }

def _salvar_contexto_se_necessario(params_api: dict, resposta_conversacional: dict, mensagem_original: str):
    """Salva contexto no banco se tiver produtos numerados"""
    try:
        sessao_id = params_api.get("sessao_id") or "anon"
        if sessao_id == "anon":
            return
            
        contexto_estruturado = resposta_conversacional.get("contexto_estruturado", {})
        if contexto_estruturado and contexto_estruturado.get("produtos"):
            payload = {
                "tipo_contexto": "busca_numerada",
                "contexto_estruturado": contexto_estruturado,
                "mensagem_original": mensagem_original,
                "resposta_apresentada": resposta_conversacional.get("mensagem", "")
            }
            
            response = httpx.post(f"{API_NEGOCIO_URL}/contexto/{sessao_id}", json=payload, timeout=5.0)
            
            if response.is_success:
                print(f"✅ Contexto salvo para sessão {sessao_id}")
            else:
                print(f"❌ Erro ao salvar contexto: {response.status_code}")
                
    except Exception as e:
        print(f"❌ Erro ao salvar contexto: {e}")

# ===== FUNÇÕES AUXILIARES (mantidas) =====

def _executar_api_call(params: dict, sessao_id: str) -> dict:
    """Executa chamada HTTP genérica com contexto"""
    endpoint = params.get("endpoint", "")
    method = params.get("method", "GET").upper()
    body = params.get("body", {})
    
    # Endpoint especial para conversa direta
    if endpoint == "/chat/resposta":
        mensagem = body.get("mensagem", "Olá! Como posso ajudá-lo?")
        return {"mensagem": mensagem, "tipo": "conversacional"}
    
    # Endpoint para processamento de contexto
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
    """Processa referência do usuário usando contexto salvo - com IDs diretos"""
    try:
        mensagem_contexto = body.get("mensagem_contexto", "")
        
        # Buscar contexto salvo do banco
        contexto_banco = _buscar_contexto_do_banco(sessao_id)
        contexto_anterior = {
            "contexto": contexto_banco.get("contexto_estruturado", {}),
            "tipo": contexto_banco.get("tipo_contexto", "nenhum")
        }
        
        # Interpretação por ID direto (mais simples e confiável)
        import re
        
        # Primeiro tenta extrair ID numérico direto
        id_matches = re.findall(r'\b(\d{4,6})\b', mensagem_contexto)
        
        if id_matches:
            item_id_referenciado = int(id_matches[0])
            quantidade_match = re.search(r'(\d+)\s*(unidades?|do|da|vezes?)', mensagem_contexto)
            quantidade = int(quantidade_match.group(1)) if quantidade_match else 1
            
            # Buscar produto pelo ID no contexto
            produtos = contexto_anterior.get("contexto", {}).get("produtos", [])
            produto_encontrado = None
            
            for produto in produtos:
                if produto.get("item_id") == item_id_referenciado:
                    produto_encontrado = produto
                    break
            
            if produto_encontrado:
                print(f"✅ Mapeamento direto: ID {item_id_referenciado} encontrado no contexto")
                
                # Adicionar ao carrinho com ID direto
                params_api = {
                    "endpoint": "/carrinhos/{sessao_id}/itens",
                    "method": "POST",
                    "body": {
                        "item_id": item_id_referenciado,
                        "quantidade": quantidade,
                        "codfilial": 2
                    }
                }
                return _executar_api_call(params_api, sessao_id)
            else:
                return {"erro": f"ID {item_id_referenciado} não encontrado no contexto atual"}
        
        # Fallback: não conseguiu processar
        return {"erro": "Não consegui identificar qual produto você quer. Pode usar o ID direto do produto?"}
        
    except Exception as e:
        return {"erro": f"Erro no processamento: {str(e)}"}

def _determinar_prompt_apresentador(endpoint: str, json_resultado: dict) -> str:
    """Determina qual prompt de apresentação usar"""
    if "erro" in json_resultado or json_resultado.get("success") is False:
        return "prompt_apresentador_erro"
    if "/produtos/busca" in endpoint:
        return "prompt_apresentador_busca"
    if "/carrinhos/" in endpoint:
        return "prompt_apresentador_carrinho"
    return "prompt_apresentador_busca"

def _montar_contexto_apresentacao(mensagem_original: str, json_resultado: dict, endpoint: str) -> str:
    """Monta o contexto que será enviado para o LLM Apresentador"""
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
    """Executa a requisição HTTP e retorna um dicionário padronizado"""
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
    """Ciclo de reparo automático"""
    try:
        p_reparo, exemplos_reparo = _buscar_prompt_cache(nome="prompt_api_repair", espaco="autonomo", versao=1)
        
        contexto_reparo = f"""endpoint_original: {params_originais.get('endpoint')}
method_original: {params_originais.get('method')}
body_original: {json.dumps(params_originais.get('body', {}))}
erro_retornado: {json.dumps(erro_response.get('error', {}))}
mensagem_usuario: (contexto da mensagem original)"""

        correcao = _completar_qwen2_configurado(
            sistema=p_reparo["template"],
            entrada_usuario=contexto_reparo,
            exemplos=exemplos_reparo,
            config_type="generico"
        )
        
        params_corrigidos = params_originais.copy()
        params_corrigidos["body"] = correcao.get("body_corrigido", params_originais.get("body", {}))
        
        return _executar_api_call(params_corrigidos, sessao_id)
        
    except Exception as e:
        return {"erro": f"Reparo automático falhou: {str(e)}. Erro original: {erro_response.get('error')}"}
    
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