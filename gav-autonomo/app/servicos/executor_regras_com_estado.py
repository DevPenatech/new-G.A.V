# gav-autonomo/app/servicos/executor_regras_com_estado.py
# CORREÇÃO: Fluxo de quantidade com verificação de estado explícita

from app.adaptadores.cliente_negocio import obter_prompt_por_nome, listar_exemplos_prompt
from app.adaptadores.interface_llm import completar_para_json
from app.validadores.modelos import validar_json_contra_schema, carregar_schema
import yaml
import json
import httpx
import time
import re
from app.config.settings import config

API_NEGOCIO_URL = config.API_NEGOCIO_URL.rstrip("/")

def executar_regras_do_manifesto(mensagem: dict | str) -> dict:
    """
    VERSÃO CORRIGIDA: Verifica estado do contexto antes da decisão LLM
    """
    tempo_inicio = time.time()
    print(f"🚀 Iniciando execução com verificação de estado - {time.strftime('%H:%M:%S')}")
    
    if isinstance(mensagem, str):
        mensagem = {"texto": mensagem, "sessao_id": "anon"}
    elif isinstance(mensagem, dict):
        mensagem = {
            "texto": mensagem.get("texto", ""),
            "sessao_id": mensagem.get("sessao_id") or "anon",
        }
    
    # ===== NOVA LÓGICA: VERIFICAR ESTADO ANTES DE DECIDIR =====
    print("🔍 Verificando estado do contexto...")
    contexto_atual = _buscar_contexto_do_banco(mensagem["sessao_id"])
    
    if contexto_atual:
        tipo_contexto = contexto_atual.get("tipo_contexto", "")
        contexto_estruturado = contexto_atual.get("contexto_estruturado", {})
        
        print(f"   📋 Tipo contexto atual: {tipo_contexto}")
        
        # CASO 1: Aguardando quantidade após seleção de produto
        if tipo_contexto == "aguardando_quantidade":
            print("   🔢 Estado: Aguardando quantidade - processando resposta diretamente")
            return _processar_resposta_quantidade(mensagem, contexto_estruturado)
        
        # CASO 2: Aguardando seleção de produto após busca
        elif tipo_contexto == "busca_numerada" or tipo_contexto == "busca_numerada_rica":
            # Verifica se mensagem é um ID de produto
            if _detectar_selecao_produto(mensagem["texto"]):
                print("   🎯 Estado: Seleção de produto detectada - processando seleção")
                return _processar_selecao_produto_estado(mensagem, contexto_estruturado)
    
    # CASO 3: Fluxo normal - usar decisão LLM
    print("   🤖 Estado: Fluxo normal - decisão via LLM")
    
    with open("app/config/model_manifest.yml", encoding="utf-8") as f:
        manifesto = yaml.safe_load(f)
    
    for regra in manifesto["regras"]:
        if regra["action"] == "decisao_llm":
            resultado = _processar_decisao_llm(mensagem, regra, manifesto)
            
            tempo_total = time.time() - tempo_inicio
            print(f"⏱️ TEMPO TOTAL COM ESTADO: {tempo_total:.2f}s")
            
            if isinstance(resultado, dict):
                resultado["_debug_timing"] = {
                    "tempo_total_segundos": f"{tempo_total:.2f}s",
                    "timestamp_fim": time.strftime('%H:%M:%S')
                }
            
            return resultado
    
    return {"erro": "Nenhuma regra válida encontrada no manifesto."}

def _detectar_selecao_produto(texto: str) -> bool:
    """Detecta se mensagem é seleção de produto por ID"""
    # ID sozinho (4-6 dígitos)
    if re.match(r'^\s*\d{4,6}\s*$', texto):
        return True
    
    # Padrões de seleção
    padroes = [
        r'\b(\d{4,6})\b',  # ID em qualquer lugar
        r'id\s*(\d{4,6})',  # "id 18135"
        r'quero\s*(\d{4,6})',  # "quero 18135"
        r'selecion\w*\s*(\d{4,6})'  # "selecionar 18135"
    ]
    
    for padrao in padroes:
        if re.search(padrao, texto.lower()):
            return True
    
    return False

def _processar_resposta_quantidade(mensagem: dict, contexto_estruturado: dict) -> dict:
    """Processa resposta de quantidade quando estado está aguardando"""
    try:
        print("   🔢 Processando resposta de quantidade...")
        
        # Extrair quantidade da mensagem
        quantidade_match = re.search(r'(\d+)', mensagem["texto"])
        
        if not quantidade_match:
            # Salva estado novamente e pede quantidade
            _salvar_contexto_no_banco(
                mensagem["sessao_id"],
                contexto_estruturado,
                mensagem["texto"],
                "Por favor, informe um número válido. Exemplo: '2' ou '5 unidades'",
                tipo="aguardando_quantidade"  # Mantém o estado
            )
            
            return {
                "mensagem": "Por favor, informe um número válido. Exemplo: '2' ou '5 unidades'",
                "tipo": "erro_quantidade_invalida"
            }
        
        quantidade = int(quantidade_match.group(1))
        produto_selecionado = contexto_estruturado.get("produto_selecionado", {})
        
        if not produto_selecionado:
            return {"erro": "Produto selecionado não encontrado no contexto"}
        
        item_id = produto_selecionado.get("item_id")
        produto_info = produto_selecionado.get("produto_info", {})
        
        print(f"   🛒 Adicionando {quantidade}x item ID {item_id}")
        
        # Adicionar ao carrinho via API
        params_api = {
            "endpoint": "/carrinhos/{sessao_id}/itens",
            "method": "POST",
            "body": {
                "item_id": item_id,
                "quantidade": quantidade,
                "codfilial": 2
            }
        }
        
        resultado_adicao = _executar_api_call(params_api, mensagem["sessao_id"])
        
        if "erro" not in resultado_adicao:
            # LIMPAR ESTADO: volta para contexto normal
            _salvar_contexto_no_banco(
                mensagem["sessao_id"],
                {"produto_selecionado": None},  # Limpa seleção
                mensagem["texto"],
                f"Adicionado {quantidade} unidades",
                tipo="item_adicionado"  # Novo estado
            )
            
            # Personalizar mensagem de sucesso
            preco_unitario = produto_info.get("preco", 0)
            total_item = preco_unitario * quantidade
            nome_produto = produto_info.get("descricao", "Produto")
            
            mensagem_sucesso = f"Perfeito! ✅\n\nAdicionei {quantidade} unidades de:\n{nome_produto}\n\n💰 Valor: {quantidade} × R$ {preco_unitario:.2f} = R$ {total_item:.2f}\n\nQuer adicionar mais produtos ou ver seu carrinho?"
            
            return {
                "mensagem": mensagem_sucesso,
                "tipo": "item_adicionado_com_estado",
                "detalhes": {
                    "item_id": item_id,
                    "quantidade": quantidade,
                    "preco_unitario": preco_unitario,
                    "total": total_item
                }
            }
        else:
            return resultado_adicao
        
    except Exception as e:
        print(f"   ❌ Erro ao processar quantidade: {e}")
        return {"erro": f"Erro no processamento: {str(e)}"}

def _processar_selecao_produto_estado(mensagem: dict, contexto_estruturado: dict) -> dict:
    """Processa seleção de produto quando há contexto de busca"""
    try:
        print("   🎯 Processando seleção de produto...")
        
        # Extrair ID da mensagem
        id_match = re.search(r'\b(\d{4,6})\b', mensagem["texto"])
        if not id_match:
            return {"erro": "ID de produto não identificado"}
        
        item_id_selecionado = int(id_match.group(1))
        produtos_contexto = contexto_estruturado.get("produtos", [])
        
        # Buscar produto selecionado no contexto
        produto_encontrado = None
        for produto in produtos_contexto:
            if produto.get("item_id") == item_id_selecionado:
                produto_encontrado = produto
                break
        
        if not produto_encontrado:
            return {"erro": f"ID {item_id_selecionado} não encontrado na busca anterior."}
        
        # ALTERAR ESTADO: Agora aguarda quantidade
        produto_selecionado = {
            "item_id": item_id_selecionado,
            "produto_info": produto_encontrado,
            "aguardando": "quantidade"
        }
        
        contexto_aguardando = {
            "produto_selecionado": produto_selecionado,
            "produtos_anteriores": produtos_contexto  # Mantém lista para fallback
        }
        
        _salvar_contexto_no_banco(
            mensagem["sessao_id"],
            contexto_aguardando,
            mensagem["texto"],
            "aguardando quantidade",
            tipo="aguardando_quantidade"  # ⚠️ NOVO TIPO
        )
        
        # Mensagem perguntando quantidade
        descricao = produto_encontrado.get("descricao", produto_encontrado.get("produto_nome", "Produto"))
        preco = produto_encontrado.get("preco", 0)
        
        mensagem_quantidade = f"Você escolheu:\n{descricao}\nR$ {preco:.2f}\n\nQuantas unidades você quer?"
        
        return {
            "mensagem": mensagem_quantidade,
            "tipo": "pergunta_quantidade_estado",
            "produto_selecionado": produto_selecionado
        }
        
    except Exception as e:
        print(f"   ❌ Erro ao processar seleção: {e}")
        return {"erro": f"Erro no processamento: {str(e)}"}

def _processar_decisao_llm(mensagem: dict, regra: dict, manifesto: dict) -> dict:
    """Processamento LLM original (mantido igual)"""
    try:
        # Busca prompt e exemplos
        p = obter_prompt_por_nome(
            nome=regra["prompt"], 
            espaco=regra["espaco_prompt"], 
            versao=regra["versao_prompt"]
        )
        exemplos = listar_exemplos_prompt(p["id"])

        # Decisão do LLM
        decisao = completar_para_json(
            sistema=p["template"],
            entrada_usuario=mensagem["texto"],
            exemplos=exemplos,
            modelo=manifesto["defaults"].get("modelo")
        )

        # Validação
        schema = carregar_schema(regra["schema"])
        if not validar_json_contra_schema(decisao, schema):
            return {"erro": "Decisão do LLM inválida. Tente reformular a mensagem."}

        # Execução
        tool_name = decisao.get("tool_name")
        params_api = (decisao.get("parameters") or {}).copy()
        params_api.setdefault("sessao_id", mensagem.get("sessao_id") or "anon")

        if tool_name == "api_call":
            resultado = _executar_api_call(params_api, mensagem["sessao_id"])

        elif tool_name == "api_call_with_presentation":
            # Pipeline duplo
            json_resultado = _executar_api_call(params_api, mensagem["sessao_id"])
            resultado = _apresentar_resultado_original(json_resultado, mensagem["texto"], params_api)
            
        else:
            return {"erro": f"Ferramenta não reconhecida: {tool_name}"}
        
        return resultado
            
    except Exception as e:
        return {"erro": f"Erro interno: {str(e)}"}

def _executar_api_call(params: dict, sessao_id: str) -> dict:
    """Execução de API (mantida igual)"""
    endpoint = params.get("endpoint", "")
    method = params.get("method", "GET").upper()
    body = params.get("body", {})
    
    if endpoint == "/chat/resposta":
        mensagem = body.get("mensagem", "Olá! Como posso ajudá-lo?")
        return {"mensagem": mensagem, "tipo": "conversacional"}
    
    # Substitui sessao_id
    if "{sessao_id}" in endpoint:
        if not sessao_id or sessao_id == "anon":
            return {"erro": "Sessão necessária para esta operação."}
        endpoint = endpoint.replace("{sessao_id}", sessao_id)
    
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

def _apresentar_resultado_original(json_resultado: dict, mensagem_original: str, params_api: dict) -> dict:
    """Apresentação (mantida igual do original)"""
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
        
        # Salva contexto se necessário
        sessao_id = params_api.get("sessao_id")
        if sessao_id and sessao_id != "anon":
            contexto_estruturado = resposta_conversacional.get("contexto_estruturado", {})
            if contexto_estruturado and contexto_estruturado.get("produtos"):
                _salvar_contexto_no_banco(
                    sessao_id, 
                    contexto_estruturado, 
                    mensagem_original, 
                    resposta_conversacional.get("mensagem", ""),
                    tipo="busca_numerada_rica"  # Tipo específico para busca
                )
        
        return {
            "mensagem": resposta_conversacional.get("mensagem", "Ops, não consegui processar isso..."),
            "tipo": resposta_conversacional.get("tipo", "apresentacao"),
            "dados_originais": json_resultado,
            "contexto_estruturado": resposta_conversacional.get("contexto_estruturado", {}),
            "modelo_apresentacao": "llm_original"
        }
        
    except Exception as e:
        print(f"Erro na apresentação: {e}")
        return json_resultado

# ===== FUNÇÕES AUXILIARES (mantidas do original) =====

def _determinar_prompt_apresentador(endpoint: str, json_resultado: dict) -> str:
    if "erro" in json_resultado or json_resultado.get("success") is False:
        return "prompt_apresentador_erro"
    if "/produtos/busca" in endpoint:
        return "prompt_apresentador_busca"
    if "/carrinhos/" in endpoint:
        return "prompt_apresentador_carrinho"
    return "prompt_apresentador_busca"

def _montar_contexto_apresentacao(mensagem_original: str, json_resultado: dict, endpoint: str) -> str:
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
    
def _salvar_contexto_no_banco(sessao_id: str, contexto_estruturado: dict, mensagem_original: str, resposta_apresentada: str, tipo: str = "busca_numerada"):
    """
    VERSÃO ATUALIZADA: Salva contexto com tipo específico
    
    Tipos suportados:
    - 'busca_numerada' ou 'busca_numerada_rica': após busca de produtos
    - 'aguardando_quantidade': após seleção de produto, aguardando quantidade
    - 'item_adicionado': após adicionar item ao carrinho
    """
    try:
        payload = {
            "tipo_contexto": tipo,  # ⚠️ PARÂMETRO DINÂMICO
            "contexto_estruturado": contexto_estruturado,
            "mensagem_original": mensagem_original,
            "resposta_apresentada": resposta_apresentada
        }
        
        response = httpx.post(f"{API_NEGOCIO_URL}/contexto/{sessao_id}", json=payload, timeout=10.0)
        
        if response.is_success:
            print(f"   ✅ Contexto '{tipo}' salvo para sessão {sessao_id}")
        else:
            print(f"   ❌ Erro ao salvar contexto: {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Erro ao salvar contexto: {e}")

def _buscar_contexto_do_banco(sessao_id: str) -> dict:
    """Busca contexto mais recente de uma sessão"""
    try:
        response = httpx.get(f"{API_NEGOCIO_URL}/contexto/{sessao_id}", timeout=10.0)
        
        if response.is_success:
            contexto = response.json()
            print(f"   ✅ Contexto recuperado para sessão {sessao_id}: {contexto.get('tipo_contexto', 'N/A')}")
            return contexto
        else:
            print(f"   ℹ️ Nenhum contexto encontrado para sessão {sessao_id}")
            return {"contexto_estruturado": {}}
            
    except Exception as e:
        print(f"   ❌ Erro ao buscar contexto: {e}")
        return {"contexto_estruturado": {}}