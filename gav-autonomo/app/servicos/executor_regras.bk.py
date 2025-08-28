# gav-autonomo/app/servicos/executor_regras.py
# VERSÃO ORIGINAL DO GIT + MÉTRICAS DE TEMPO
# Volta para o que funcionava, mas com medição detalhada de performance

from app.adaptadores.cliente_negocio import obter_prompt_por_nome, listar_exemplos_prompt
from app.adaptadores.interface_llm import completar_para_json
from app.validadores.modelos import validar_json_contra_schema, carregar_schema
import yaml
import json
import httpx
import time
from app.config.settings import config

API_NEGOCIO_URL = config.API_NEGOCIO_URL.rstrip("/")

def executar_regras_do_manifesto(mensagem: dict | str) -> dict:
    """
    VERSÃO ORIGINAL DO GIT com medição de tempo detalhada
    """
    tempo_inicio = time.time()
    print(f"🚀 Iniciando execução - {time.strftime('%H:%M:%S')}")
    print(f"🧭 sessão: {mensagem['sessao_id']}")
    
    if isinstance(mensagem, str):
        mensagem = {"texto": mensagem, "sessao_id": "anon"}
    elif isinstance(mensagem, dict):
        # Normaliza e protege o sessao_id quando vier do endpoint
        mensagem = {
            "texto": mensagem.get("texto", ""),
            "sessao_id": mensagem.get("sessao_id") or "anon",
        }
    else:
        raise TypeError(f"mensagem deve ser dict|str, recebi: {type(mensagem).__name__}")
    
    with open("app/config/model_manifest.yml", encoding="utf-8") as f:
        manifesto = yaml.safe_load(f)
    
    for regra in manifesto["regras"]:
        if regra["action"] == "decisao_llm":
            resultado = _processar_decisao_llm(mensagem, regra, manifesto)
            
            # Métricas finais
            tempo_total = time.time() - tempo_inicio
            print(f"⏱️ TEMPO TOTAL: {tempo_total:.2f}s")
            
            # Adiciona métricas na resposta
            if isinstance(resultado, dict):
                resultado["_debug_timing"] = {
                    "tempo_total_segundos": f"{tempo_total:.2f}s",
                    "timestamp_fim": time.strftime('%H:%M:%S')
                }
            
            return resultado
    
    return {"erro": "Nenhuma regra válida encontrada no manifesto."}

def _processar_decisao_llm(mensagem: dict, regra: dict, manifesto: dict) -> dict:
    """VERSÃO ORIGINAL: Processa decisão via LLM e executa pipeline"""
    try:
        # ===== ETAPA 1: BUSCAR PROMPT E EXEMPLOS =====
        print("📖 Etapa 1: Buscando prompt e exemplos...")
        tempo_1 = time.time()
        
        p = obter_prompt_por_nome(
            nome=regra["prompt"], 
            espaco=regra["espaco_prompt"], 
            versao=regra["versao_prompt"]
        )
        exemplos = listar_exemplos_prompt(p["id"])
        
        tempo_1_fim = time.time()
        print(f"   ⏱️ Busca prompt: {tempo_1_fim - tempo_1:.2f}s")

        # ===== ETAPA 2: LLM DECISÃO =====
        print("🤖 Etapa 2: LLM tomando decisão...")
        tempo_2 = time.time()
        
        decisao = completar_para_json(
            sistema=p["template"],
            entrada_usuario=mensagem["texto"],
            exemplos=exemplos,
            modelo=manifesto["defaults"].get("modelo")
        )
        
        tempo_2_fim = time.time()
        print(f"   ⏱️ LLM decisão: {tempo_2_fim - tempo_2:.2f}s")
        print(f"   ✅ Decisão: {decisao.get('tool_name', 'N/A')}")

        # ===== ETAPA 3: VALIDAÇÃO =====
        print("✔️ Etapa 3: Validando decisão...")
        tempo_3 = time.time()
        
        schema = carregar_schema(regra["schema"])
        if not validar_json_contra_schema(decisao, schema):
            return {"erro": "Decisão do LLM inválida. Tente reformular a mensagem."}
        
        tempo_3_fim = time.time()
        print(f"   ⏱️ Validação: {tempo_3_fim - tempo_3:.3f}s")

        # ===== ETAPA 4: EXECUÇÃO =====
        tool_name = decisao.get("tool_name")
        print(f"🔧 Etapa 4: Executando {tool_name}...")
        tempo_4 = time.time()
        

        # Propaga o sessao_id para os parâmetros da ferramenta (o LLM não manda isso)
        params_api = (decisao.get("parameters") or {}).copy()
        params_api.setdefault("sessao_id", mensagem.get("sessao_id") or "anon")
        print(f"   📝 Session ID (propagado): {params_api.get('sessao_id')}")

        if tool_name == "api_call":
            resultado = _executar_api_call(params_api, mensagem["sessao_id"])

        elif tool_name == "api_call_with_presentation":
            # PIPELINE DUPLO ORIGINAL
            json_resultado = _executar_api_call(params_api, mensagem["sessao_id"])
            # Passa os mesmos params com sessao_id incluído para a apresentação
            resultado = _apresentar_resultado_original(json_resultado, mensagem["texto"], params_api)

            
        else:
            return {"erro": f"Ferramenta não reconhecida: {tool_name}"}
        
        tempo_4_fim = time.time()
        print(f"   ⏱️ Execução: {tempo_4_fim - tempo_4:.2f}s")
        
        return resultado
            
    except Exception as e:
        print(f"❌ Erro interno: {str(e)}")
        return {"erro": f"Erro interno: {str(e)}"}

def _executar_api_call(params: dict, sessao_id: str) -> dict:
    """VERSÃO ORIGINAL: Executa chamada HTTP"""
    print(f"   🌐 Executando API call...")
    tempo_api = time.time()
    
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
        print(f"      🔗 Endpoint resolvido: {endpoint}")
    
    # Monta a URL completa para APIs reais
    url = f"{API_NEGOCIO_URL}{endpoint}"
    print(f"      📡 Chamando: {method} {url}")
    
    try:
        response = _fazer_request_http(url, method, body)
        
        tempo_api_fim = time.time()
        print(f"      ⏱️ Tempo API: {tempo_api_fim - tempo_api:.2f}s")
        
        if response.get("success"):
            return response.get("data", {})
        
        if response.get("status_code") in [400, 422]:
            print("      🔧 Tentando reparo automático...")
            return _tentar_reparo_automatico(params, response, sessao_id)
        
        return {"erro": f"API retornou erro {response.get('status_code')}: {response.get('error')}"}
        
    except Exception as e:
        tempo_api_fim = time.time()
        print(f"      ❌ Erro API ({tempo_api_fim - tempo_api:.2f}s): {str(e)}")
        return {"erro": f"Falha na comunicação com API: {str(e)}"}

def _apresentar_resultado_original(json_resultado: dict, mensagem_original: str, params_api: dict) -> dict:
    """VERSÃO ORIGINAL: Apresentação rica com LLM"""
    print("🎨 Aplicando apresentação conversacional...")
    tempo_apresentacao = time.time()
    
    try:
        endpoint = params_api.get("endpoint", "")
        prompt_apresentador = _determinar_prompt_apresentador(endpoint, json_resultado)
        
        if not prompt_apresentador:
            print("   ⏭️ Sem apresentação necessária")
            return json_resultado
        
        print(f"   📝 Usando prompt: {prompt_apresentador}")
        tempo_prompt = time.time()
        
        p_apresentador = obter_prompt_por_nome(nome=prompt_apresentador, espaco="autonomo", versao=1)
        exemplos_apresentador = listar_exemplos_prompt(p_apresentador["id"])
        
        tempo_prompt_fim = time.time()
        print(f"   ⏱️ Busca prompt apresentador: {tempo_prompt_fim - tempo_prompt:.2f}s")
        
        contexto_apresentacao = _montar_contexto_apresentacao(
            mensagem_original, json_resultado, endpoint
        )
        
        print("   🤖 LLM processando apresentação...")
        tempo_llm_apresentacao = time.time()
        
        resposta_conversacional = completar_para_json(
            sistema=p_apresentador["template"],
            entrada_usuario=contexto_apresentacao,
            exemplos=exemplos_apresentador
        )
        
        tempo_llm_apresentacao_fim = time.time()
        print(f"   ⏱️ LLM apresentação: {tempo_llm_apresentacao_fim - tempo_llm_apresentacao:.2f}s")
        
        # Salva contexto se necessário
        sessao_id = params_api.get("sessao_id")
        
        print(f"   📝 Session ID: {sessao_id}")
        
        if sessao_id and sessao_id != "anon":
            contexto_estruturado = resposta_conversacional.get("contexto_estruturado", {})
            if contexto_estruturado and contexto_estruturado.get("produtos"):
                _salvar_contexto_no_banco(sessao_id, contexto_estruturado, mensagem_original, resposta_conversacional.get("mensagem", ""))
        
        tempo_apresentacao_fim = time.time()
        print(f"   ⏱️ Total apresentação: {tempo_apresentacao_fim - tempo_apresentacao:.2f}s")
        
        return {
            "mensagem": resposta_conversacional.get("mensagem", "Ops, não consegui processar isso..."),
            "tipo": resposta_conversacional.get("tipo", "apresentacao"),
            "dados_originais": json_resultado,
            "contexto_estruturado": resposta_conversacional.get("contexto_estruturado", {}),
            "modelo_apresentacao": "llm_original"
        }
        
    except Exception as e:
        tempo_apresentacao_fim = time.time()
        print(f"   ❌ Erro apresentação ({tempo_apresentacao_fim - tempo_apresentacao:.2f}s): {e}")
        print("   🛡️ Voltando para dados originais...")
        return json_resultado

def _processar_contexto_via_prompt(body: dict, sessao_id: str) -> dict:
    """Processa diferentes tipos de seleção e contexto"""
    try:
        mensagem_contexto = body.get("mensagem_contexto", "")
        print(f"   🔍 Processando contexto: '{mensagem_contexto}'")
        
        # Detectar tipo de mensagem pelos prefixos
        if mensagem_contexto.startswith("SELECAO_ID_SEM_QUANTIDADE:"):
            item_id = mensagem_contexto.replace("SELECAO_ID_SEM_QUANTIDADE:", "")
            return _processar_selecao_id_sem_quantidade(item_id, sessao_id)
            
        elif mensagem_contexto.startswith("SELECAO_DESCRICAO_SEM_QUANTIDADE:"):
            descricao = mensagem_contexto.replace("SELECAO_DESCRICAO_SEM_QUANTIDADE:", "")
            return _processar_selecao_descricao_sem_quantidade(descricao, sessao_id)
            
        elif mensagem_contexto.startswith("ADICAO_DESCRICAO_COM_QUANTIDADE:"):
            partes = mensagem_contexto.replace("ADICAO_DESCRICAO_COM_QUANTIDADE:", "").split(":", 1)
            if len(partes) >= 2:
                quantidade = int(partes[0])
                descricao = partes[1]
                return _processar_adicao_descricao_com_quantidade(quantidade, descricao, sessao_id)
        
        # Fallback para lógica antiga (IDs diretos)
        import re
        id_matches = re.findall(r'\b(\d{4,6})\b', mensagem_contexto)
        
        if id_matches:
            item_id_referenciado = int(id_matches[0])
            quantidade_match = re.search(r'(\d+)\s*(unidades?|do|da|vezes?)', mensagem_contexto)
            quantidade = int(quantidade_match.group(1)) if quantidade_match else 1
            
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
        
        return {"erro": "Não consegui processar sua seleção. Tente novamente."}
        
    except Exception as e:
        return {"erro": f"Erro no processamento: {str(e)}"}

def _processar_selecao_id_sem_quantidade(item_id_str: str, sessao_id: str) -> dict:
    """Processa seleção por ID quando usuário não informou quantidade"""
    try:
        item_id = int(item_id_str)
        
        # Buscar produto no contexto anterior
        contexto_banco = _buscar_contexto_do_banco(sessao_id)
        produtos_contexto = contexto_banco.get("contexto_estruturado", {}).get("produtos", [])
        
        produto_encontrado = None
        for produto in produtos_contexto:
            if produto.get("id") == item_id:
                produto_encontrado = produto
                break
        
        if not produto_encontrado:
            return {"erro": f"ID {item_id} não encontrado na busca anterior."}
        
        # Salvar produto selecionado e pedir quantidade
        produto_selecionado = {
            "item_id": item_id,
            "produto_info": produto_encontrado,
            "aguardando": "quantidade"
        }
        
        _salvar_contexto_no_banco(
            sessao_id,
            {"produto_selecionado": produto_selecionado},
            f"selecionou ID {item_id}",
            "aguardando quantidade"
        )
        
        descricao = produto_encontrado.get("descricao", "Produto")
        preco = produto_encontrado.get("preco", 0)
        
        mensagem = f"Você escolheu:\\n{descricao}\\nR$ {preco:.2f}\\n\\nQuantas unidades você quer?"
        
        return {
            "mensagem": mensagem,
            "tipo": "pergunta_quantidade",
            "produto_selecionado": produto_selecionado
        }
        
    except ValueError:
        return {"erro": "ID inválido."}
    except Exception as e:
        return {"erro": f"Erro ao processar seleção: {str(e)}"}

def _processar_selecao_descricao_sem_quantidade(descricao: str, sessao_id: str) -> dict:
    """Processa seleção por descrição quando usuário não informou quantidade"""
    try:
        # Buscar produtos no contexto
        contexto_banco = _buscar_contexto_do_banco(sessao_id)
        produtos_contexto = contexto_banco.get("contexto_estruturado", {}).get("produtos", [])
        
        # Procurar produtos que contenham a descrição
        produtos_compatíveis = []
        descricao_lower = descricao.lower()
        
        for produto in produtos_contexto:
            produto_desc = produto.get("descricao", "").lower()
            if descricao_lower in produto_desc or any(word in produto_desc for word in descricao_lower.split()):
                produtos_compatíveis.append(produto)
        
        if not produtos_compatíveis:
            return {"erro": f"Não encontrei '{descricao}' nos produtos mostrados anteriormente."}
        
        if len(produtos_compatíveis) == 1:
            # Única opção - adicionar direto com quantidade 1
            produto = produtos_compatíveis[0]
            
            params_api = {
                "endpoint": "/carrinhos/{sessao_id}/itens",
                "method": "POST", 
                "body": {
                    "item_id": produto["item_id"],
                    "quantidade": 1,
                    "codfilial": 2
                }
            }
            
            resultado = _executar_api_call(params_api, sessao_id)
            
            if "erro" not in resultado:
                mensagem_sucesso = f"Adicionei 1 unidade de:\\n{produto.get('descricao', 'Produto')}\\nR$ {produto.get('preco', 0):.2f}"
                return {
                    "mensagem": mensagem_sucesso,
                    "tipo": "item_adicionado_auto"
                }
            else:
                return resultado
        else:
            # Múltiplas opções - mostrar para escolher
            opcoes = []
            for i, produto in enumerate(produtos_compatíveis):
                opcoes.append(f"ID: {produto['item_id']} - {produto.get('descricao', 'N/A')} - R$ {produto.get('preco', 0):.2f}")
            
            mensagem = f"Encontrei {len(produtos_compatíveis)} opções para '{descricao}':\\n\\n" + "\\n".join(opcoes) + "\\n\\nDigite o ID específico que você quer."
            
            return {
                "mensagem": mensagem,
                "tipo": "multiplas_opcoes"
            }
        
    except Exception as e:
        return {"erro": f"Erro ao processar descrição: {str(e)}"}

def _processar_adicao_descricao_com_quantidade(quantidade: int, descricao: str, sessao_id: str) -> dict:
    """Processa adição por descrição com quantidade específica"""
    try:
        # Buscar produtos no contexto
        contexto_banco = _buscar_contexto_do_banco(sessao_id)
        produtos_contexto = contexto_banco.get("contexto_estruturado", {}).get("produtos", [])
        
        # Procurar produto que contenha a descrição
        produto_encontrado = None
        descricao_lower = descricao.lower()
        
        for produto in produtos_contexto:
            produto_desc = produto.get("descricao", "").lower()
            if descricao_lower in produto_desc:
                produto_encontrado = produto
                break
        
        if not produto_encontrado:
            return {"erro": f"Não encontrei '{descricao}' nos produtos anteriores."}
        
        # Adicionar ao carrinho
        params_api = {
            "endpoint": "/carrinhos/{sessao_id}/itens",
            "method": "POST",
            "body": {
                "item_id": produto_encontrado["item_id"], 
                "quantidade": quantidade,
                "codfilial": 2
            }
        }
        
        resultado = _executar_api_call(params_api, sessao_id)
        
        if "erro" not in resultado:
            preco_unitario = produto_encontrado.get("preco", 0)
            total = preco_unitario * quantidade
            
            mensagem_sucesso = f"Adicionei {quantidade} unidades de:\\n{produto_encontrado.get('descricao', 'Produto')}\\n\\nValor: {quantidade} × R$ {preco_unitario:.2f} = R$ {total:.2f}"
            
            return {
                "mensagem": mensagem_sucesso,
                "tipo": "item_adicionado_com_descricao"
            }
        else:
            return resultado
        
    except Exception as e:
        return {"erro": f"Erro ao processar adição: {str(e)}"}
    
def _processar_selecao_produto(mensagem: str, sessao_id: str) -> dict:
    """
    Processa seleção de produto por ID ou descrição
    Fluxo: Usuário viu lista → digita ID → sistema pergunta quantidade
    """
    try:
        # Buscar contexto da sessão anterior
        contexto_banco = _buscar_contexto_do_banco(sessao_id)
        produtos_contexto = contexto_banco.get("contexto_estruturado", {}).get("produtos", [])
        
        if not produtos_contexto:
            return {"erro": "Nenhum produto foi mostrado anteriormente. Faça uma busca primeiro."}
        
        print(f"   🔍 Processando seleção: '{mensagem}' com {len(produtos_contexto)} produtos no contexto")
        
        # Usar prompt seletor para processar a seleção
        try:
            p_seletor = obter_prompt_por_nome(nome="prompt_seletor_produto", espaco="autonomo", versao=1)
            exemplos_seletor = listar_exemplos_prompt(p_seletor["id"])
            
            contexto_input = f"""mensagem_usuario: "{mensagem}"
produtos_contexto: {json.dumps(produtos_contexto, ensure_ascii=False)}"""
            
            resultado_selecao = completar_para_json(
                sistema=p_seletor["template"],
                entrada_usuario=contexto_input,
                exemplos=exemplos_seletor
            )
            
            print(f"   ✅ Seleção processada: {resultado_selecao.get('acao', 'N/A')}")
            
            if resultado_selecao.get("acao") == "perguntar_quantidade":
                # Salvar produto selecionado no contexto da sessão
                item_selecionado = {
                    "item_id": resultado_selecao.get("item_id"),
                    "produto_info": resultado_selecao.get("produto_info", {}),
                    "aguardando": "quantidade"
                }
                
                _salvar_contexto_no_banco(
                    sessao_id, 
                    {"produto_selecionado": item_selecionado},
                    mensagem,
                    resultado_selecao.get("mensagem", "")
                )
                
                return {
                    "mensagem": resultado_selecao.get("mensagem"),
                    "tipo": "pergunta_quantidade",
                    "produto_selecionado": item_selecionado
                }
            
            elif resultado_selecao.get("acao") == "id_nao_encontrado":
                return {
                    "mensagem": resultado_selecao.get("mensagem"),
                    "tipo": "erro_selecao"
                }
            
            else:
                return {"erro": "Não consegui processar sua seleção. Tente novamente."}
                
        except Exception as e:
            print(f"   ❌ Erro no prompt seletor: {e}")
            return {"erro": f"Erro ao processar seleção: {str(e)}"}
        
    except Exception as e:
        print(f"   ❌ Erro geral na seleção: {e}")
        return {"erro": f"Erro no processamento: {str(e)}"}

def _processar_quantidade_produto(mensagem: str, sessao_id: str) -> dict:
    """
    Processa quantidade após seleção de produto
    Fluxo: Usuário selecionou ID → digitou quantidade → adiciona ao carrinho
    """
    try:
        # Buscar produto selecionado anteriormente
        contexto_banco = _buscar_contexto_do_banco(sessao_id)
        produto_selecionado = contexto_banco.get("contexto_estruturado", {}).get("produto_selecionado", {})
        
        if not produto_selecionado or produto_selecionado.get("aguardando") != "quantidade":
            return {"erro": "Nenhum produto foi selecionado anteriormente."}
        
        # Extrair quantidade da mensagem
        import re
        quantidade_match = re.search(r'(\d+)', mensagem)
        
        if not quantidade_match:
            return {
                "mensagem": "Por favor, informe um número válido. Exemplo: '2' ou '5 unidades'",
                "tipo": "erro_quantidade"
            }
        
        quantidade = int(quantidade_match.group(1))
        item_id = produto_selecionado.get("item_id")
        produto_info = produto_selecionado.get("produto_info", {})
        
        print(f"   🛒 Adicionando {quantidade} unidades do ID {item_id}")
        
        # Adicionar ao carrinho
        params_api = {
            "endpoint": "/carrinhos/{sessao_id}/itens",
            "method": "POST",
            "body": {
                "item_id": item_id,
                "quantidade": quantidade,
                "codfilial": 2
            }
        }
        
        resultado_adicao = _executar_api_call(params_api, sessao_id)
        
        if "erro" not in resultado_adicao:
            # Limpar seleção do contexto
            _salvar_contexto_no_banco(
                sessao_id,
                {"produto_selecionado": None},
                mensagem,
                f"Adicionado {quantidade} unidades de {produto_info.get('descricao', 'produto')}"
            )
            
            # Personalizar mensagem de sucesso
            preco_unitario = produto_info.get("preco", 0)
            total_item = preco_unitario * quantidade
            
            mensagem_sucesso = f"Perfeito! ✅\\n\\nAdicionei {quantidade} unidades de:\\n{produto_info.get('descricao', 'Produto')}\\n\\n💰 Valor: {quantidade} × R$ {preco_unitario:.2f} = R$ {total_item:.2f}\\n\\nQuer adicionar mais produtos ou ver seu carrinho?"
            
            return {
                "mensagem": mensagem_sucesso,
                "tipo": "item_adicionado",
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


# ===== FUNÇÕES AUXILIARES ORIGINAIS =====

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
    """Executa a requisição HTTP"""
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
    print("      🔧 Executando reparo automático...")
    tempo_reparo = time.time()
    
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
        
        resultado = _executar_api_call(params_corrigidos, sessao_id)
        
        tempo_reparo_fim = time.time()
        print(f"      ⏱️ Reparo automático: {tempo_reparo_fim - tempo_reparo:.2f}s")
        return resultado
        
    except Exception as e:
        tempo_reparo_fim = time.time()
        print(f"      ❌ Falha reparo ({tempo_reparo_fim - tempo_reparo:.2f}s): {e}")
        return {"erro": f"Reparo automático falhou: {str(e)}. Erro original: {erro_response.get('error')}"}
    
def _salvar_contexto_no_banco(sessao_id: str, contexto_estruturado: dict, mensagem_original: str, resposta_apresentada: str):
    """Salva contexto no banco"""
    try:
        payload = {
            "tipo_contexto": "busca_numerada",
            "contexto_estruturado": contexto_estruturado,
            "mensagem_original": mensagem_original,
            "resposta_apresentada": resposta_apresentada
        }
        
        response = httpx.post(f"{API_NEGOCIO_URL}/contexto/{sessao_id}", json=payload, timeout=10.0)
        
        if response.is_success:
            print(f"   ✅ Contexto salvo para sessão {sessao_id}")
        else:
            print(f"   ❌ Erro ao salvar contexto: {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Erro ao salvar contexto: {e}")

def _buscar_contexto_do_banco(sessao_id: str) -> dict:
    """Busca contexto do banco"""
    try:
        response = httpx.get(f"{API_NEGOCIO_URL}/contexto/{sessao_id}", timeout=10.0)
        
        if response.is_success:
            contexto = response.json()
            print(f"   ✅ Contexto recuperado para sessão {sessao_id}")
            return contexto
        else:
            print(f"   ℹ️ Nenhum contexto encontrado para sessão {sessao_id}")
            return {"contexto_estruturado": {}}
            
    except Exception as e:
        print(f"   ❌ Erro ao buscar contexto: {e}")
        return {"contexto_estruturado": {}}