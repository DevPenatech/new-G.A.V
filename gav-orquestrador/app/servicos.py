# /gav-orquestrador/app/servicos.py

import uuid
import httpx
import json
import re
from .config import settings
from .esquemas import ToolCall, MensagemChat, Feedback
from fastapi import HTTPException

_session_cache = {}
_prompt_cache = {}
_unit_alias_cache = None

async def _get_prompt_template(nome_prompt: str) -> str:
    if nome_prompt in _prompt_cache: return _prompt_cache[nome_prompt]
    url = f"{settings.API_NEGOCIO_URL}/prompts/{nome_prompt}"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            if response.status_code != 200:
                 raise HTTPException(status_code=response.status_code, detail=f"Erro ao buscar prompt '{nome_prompt}': {response.text}")
            template = response.json()["template"]
            _prompt_cache[nome_prompt] = template
            return template
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail=f"Não foi possível buscar o prompt '{nome_prompt}'.")

async def chamar_ollama(texto_usuario: str, prompt_sistema: str) -> ToolCall:
    """Chama o LLM esperando especificamente um JSON no formato ToolCall."""
    url_ollama = f"{settings.OLLAMA_HOST}/api/chat"
    payload = { "model": settings.OLLAMA_MODEL_NAME, "temperature": 0.1, "messages": [{"role": "system", "content": prompt_sistema}, {"role": "user", "content": texto_usuario}], "format": "json", "stream": False }
    
    async with httpx.AsyncClient(timeout=180.0) as client:
        try:
            response = await client.post(url_ollama, json=payload)
            response.raise_for_status()
            resposta_str = response.json()["message"]["content"]
            try:
                tool_call_data = json.loads(resposta_str)
                if "tool_name" in tool_call_data and "parameters" in tool_call_data:
                    return ToolCall(**tool_call_data)
                else: raise ValueError("JSON não tem a estrutura de ToolCall")
            except Exception as e:
                print(f"ALERTA: LLM retornou JSON inválido. Erro: {e}. Resposta: {resposta_str}")
                return ToolCall(tool_name="handle_chitchat", parameters={"mensagem": "Desculpe, não consegui processar sua solicitação."})
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Timeout ao chamar o LLM.")
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Erro de conexão com o Ollama: {e}")


async def _chamar_llm_para_json(texto_usuario: str, prompt_sistema: str) -> dict:
    """Função genérica para chamar o LLM e obter uma resposta JSON."""
    url_ollama = f"{settings.OLLAMA_HOST}/api/chat"
    payload = {"model": settings.OLLAMA_MODEL_NAME, "temperature": 0.1, "messages": [{"role": "system", "content": prompt_sistema}, {"role": "user", "content": texto_usuario}], "format": "json", "stream": False}
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(url_ollama, json=payload)
            response.raise_for_status()
            resposta_str = response.json()["message"]["content"]
            return json.loads(resposta_str)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Timeout ao chamar o LLM para classificação.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao processar resposta do LLM para classificação: {e}")
 
 
async def _get_unit_aliases() -> dict:
    global _unit_alias_cache
    if _unit_alias_cache is None:
        print("Buscando e cacheando aliases de unidade da API de Negócio...")
        url = f"{settings.API_NEGOCIO_URL}/unidades/aliases"
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            _unit_alias_cache = response.json()
    return _unit_alias_cache


def _extrair_escolha_do_contexto(texto_usuario: str, contexto_busca: list, aliases: dict) -> ToolCall:
    texto_lower = texto_usuario.lower()
    quantidade = 1
    match_num = re.search(r'\b(\d+)\b', texto_lower)
    if match_num:
        quantidade = int(match_num.group(1))
    else:
        mapa_palavras = {"uma": 1, "duas": 2, "três": 3, "quatro": 4, "cinco": 5}
        for palavra, num in mapa_palavras.items():
            if palavra in texto_lower:
                quantidade = num
                break
    
    match_id = re.search(r'item (\d+)\b', texto_lower)
    if match_id:
        item_id_escolhido = int(match_id.group(1))
        for produto in contexto_busca:
            for item in produto.get("itens", []):
                if item['id'] == item_id_escolhido:
                    print(f"Escolha extraída por ID: {item_id_escolhido}, Quantidade: {quantidade}")
                    return ToolCall(tool_name="adicionar_item_carrinho", parameters={"item_id": item_id_escolhido, "quantidade": quantidade})

    for produto in contexto_busca:
        for item in produto.get("itens", []):
            unidade_lower = item['unidade'].lower()
            if f" {unidade_lower} " in f" {texto_lower} ":
                 print(f"Escolha extraída por unidade: {unidade_lower} -> item {item['id']}, Quantidade: {quantidade}")
                 return ToolCall(tool_name="adicionar_item_carrinho", parameters={"item_id": item['id'], "quantidade": quantidade})
            for alias, unidade_principal in aliases.items():
                if unidade_principal.lower() == unidade_lower and alias in texto_lower:
                    print(f"Escolha extraída por alias: {alias} -> {unidade_principal} -> item {item['id']}, Quantidade: {quantidade}")
                    return ToolCall(tool_name="adicionar_item_carrinho", parameters={"item_id": item['id'], "quantidade": quantidade})
    
    print("Não foi possível extrair a escolha do usuário. Tratando como nova busca.")
    # BUG 2 - CORRIGIDO: Retorna uma ferramenta para fazer uma nova busca
    return ToolCall(tool_name="buscar_produtos", parameters={"query": texto_usuario})



def _preparar_contexto_para_ia(dados_api: dict) -> str:
    resultados = dados_api.get("resultados", [])
    if not resultados: return "Nenhum produto encontrado."
    fatos = []
    if dados_api.get("status_busca") == "fallback":
        fatos.append("[FALLBACK] A embalagem exata não foi encontrada, mas o produto existe nestas outras:")
    for produto in resultados[:3]:
        desc = produto.get("descricaoweb") or produto.get("descricao", "Produto sem descrição")
        fatos.append(f"\nProduto: {desc}")
        item_unidade, item_caixa = None, None
        for item in produto.get("itens", []):
            if item.get("unidade") in ["UN", "L", "KG"]: item_unidade = item
            if item.get("unidade") in ["CX", "PK", "PC", "FD"]: item_caixa = item
        if item_unidade and item_unidade.get("pvenda") is not None:
            preco_un = item_unidade.get("poferta") or item_unidade.get("pvenda")
            fatos.append(f"- Unidade custa R${preco_un:.2f}")
            if item_unidade.get("poferta") and item_unidade.get("pvenda") and item_unidade.get("poferta") < item_unidade.get("pvenda"):
                fatos.append("  - [PROMOÇÃO] Este item está em oferta!")
        if item_caixa and item_caixa.get("pvenda") is not None and item_caixa.get("qtunit", 0) > 0:
            preco_cx = item_caixa.get("poferta") or item_caixa.get("pvenda")
            preco_un_na_caixa = preco_cx / item_caixa["qtunit"]
            fatos.append(f"- Caixa com {item_caixa['qtunit']} custa R${preco_cx:.2f} (unidade sai por R${preco_un_na_caixa:.2f})")
            if item_caixa.get("poferta") and item_caixa.get("pvenda") and item_caixa.get("poferta") < item_caixa.get("pvenda"):
                fatos.append("  - [PROMOÇÃO] A caixa está em oferta!")
            if item_unidade and preco_un_na_caixa < (item_unidade.get("poferta") or item_unidade.get("pvenda", float('inf'))):
                fatos.append("  - [MELHOR CUSTO-BENEFÍCIO] Levar a caixa é mais barato por unidade!")
    return "\n".join(fatos)

async def formatar_resposta_carrinho(dados_carrinho: dict) -> str:
    if not dados_carrinho or not dados_carrinho.get("itens"):
        return "Seu carrinho está vazio."

    linhas_itens = []
    for item in dados_carrinho["itens"]:
        linhas_itens.append(
            f"{item['quantidade']}x {item['descricao_produto']} — R$ {item['subtotal']:.2f}"
        )
    
    resposta_formatada = "\n".join(linhas_itens)
    resposta_formatada += f"\n\n**Total:** R$ {dados_carrinho['valor_total']:.2f}"
    return resposta_formatada


async def orquestrar_chat(mensagem: MensagemChat):
    sessao_id = mensagem.sessao_id
    correlation_id = uuid.uuid4()
    print(f"INFO: correlation_id={correlation_id} id_sessao={sessao_id} status=iniciado mensagem='{mensagem.texto}'")
    tool_call_a_executar: ToolCall

    # TRANSITÓRIO: PR#1 - Curto-circuito para visualização de carrinho
    padrao_carrinho = re.compile(r'\b(carrinh[oa]s?|ver carrinho|meu carrinho|mostrar carrinho|exibir carrinho)\b', re.IGNORECASE)
    if padrao_carrinho.search(mensagem.texto):
        tool_call_a_executar = ToolCall(tool_name="ver_carrinho", parameters={})
    elif sessao_id in _session_cache and _session_cache[sessao_id].get('state') == 'aguardando_escolha_item':
        print(f"INFO: correlation_id={correlation_id} id_sessao={sessao_id} rota_escolhida=extrair_escolha_do_contexto fonte=memoria_de_sessao")
        aliases = await _get_unit_aliases()
        contexto_salvo = _session_cache[sessao_id]['data']
        tool_call_a_executar = _extrair_escolha_do_contexto(mensagem.texto, contexto_salvo, aliases)
    else:
         # Classificação da intenção via LLM
        prompt_triagem = await _get_prompt_template("prompt_triagem_intencao")
        classificacao_json = await _chamar_llm_para_json(mensagem.texto, prompt_triagem)
        categoria = classificacao_json.get("categoria", "conversa_fiada")
        print(f"INFO: correlation_id={correlation_id} id_sessao={sessao_id} intencao_classificada={categoria}")

        if categoria == "busca_produto":
            print(f"INFO: correlation_id={correlation_id} id_sessao={sessao_id} rota_escolhida=chamar_llm_para_ferramenta fonte=prompt_mestre")
            prompt_mestre = await _get_prompt_template("prompt_mestre")
            tool_call_a_executar = await chamar_ollama(mensagem.texto, prompt_mestre)
            print(f"INFO: correlation_id={correlation_id} id_sessao={sessao_id} llm_tool_name={tool_call_a_executar.tool_name}")
        elif categoria in ["saudacao", "conversa_fiada"]:
            tool_call_a_executar = ToolCall(tool_name="handle_chitchat", parameters={"mensagem": "Olá! Sou G.A.V., seu assistente de vendas. Como posso te ajudar a encontrar produtos hoje?"})
        else:
            # Fallback para qualquer outra categoria não tratada
            tool_call_a_executar = ToolCall(tool_name="handle_chitchat", parameters={"mensagem": "Desculpe, não entendi. Você pode tentar perguntar sobre um produto?"})
        
    # ETAPA 2: EXECUÇÃO DA FERRAMENTA E RESPOSTA
   
    async with httpx.AsyncClient() as client:
        log_payload = {
            "sessao_id": mensagem.sessao_id, "mensagem_usuario": mensagem.texto,
            # BUG 1 - CORRIGIDO: usa a variável correta
            "resposta_json": tool_call_a_executar.model_dump()
        }
        await client.post(f"{settings.API_NEGOCIO_URL}/logs/interacao", json=log_payload)

    resposta_final = await executar_ferramenta(tool_call_a_executar, mensagem, correlation_id)
    print(f"INFO: correlation_id={correlation_id} id_sessao={sessao_id} status=concluido")
    return resposta_final

async def executar_ferramenta(tool_call: ToolCall, mensagem: MensagemChat, correlation_id: uuid.UUID):
    """Executa a ferramenta decidida pelo LLM e gerencia o estado da memória."""
    sessao_id = mensagem.sessao_id
    
    # Oculta parâmetros potencialmente grandes ou sensíveis dos logs de execução
    params_log = {k: v for k, v in tool_call.parameters.items() if k not in ["contexto"]}
    print(f"INFO: correlation_id={correlation_id} id_sessao={sessao_id} executando_ferramenta={tool_call.tool_name} parametros={params_log}")
     
     
    # Se a ação for conclusiva (adicionar item, ver carrinho), limpa a memória para a próxima conversa.
    if tool_call.tool_name in ["adicionar_item_carrinho"]:
        _session_cache.pop(sessao_id, None)
        
    async with httpx.AsyncClient(timeout=30.0) as client:
        if tool_call.tool_name == "buscar_produtos":
            url_busca = f"{settings.API_NEGOCIO_URL}/produtos/busca"
            
            # PR#4: Bloco de validação e limpeza dos parâmetros do LLM
            query = tool_call.parameters.get("query", "").strip()
            ordenar_por = tool_call.parameters.get("ordenar_por")

            if not query:
                print(f"WARN: correlation_id={correlation_id} id_sessao={sessao_id} erro_validacao='Query do LLM estava vazia. Abortando busca.'")
                return {"resposta": "Não entendi o que você quer procurar. Pode tentar de novo, por favor?"}

            payload = {
                "query": query,
                "codfilial": 2, 
                "limit": 10
            }
            
            # Apenas adiciona 'ordenar_por' se for um valor válido, evitando a string vazia.
            if ordenar_por in ["preco_asc", "preco_desc"]:
                payload["ordenar_por"] = ordenar_por
            
            print(f"INFO: correlation_id={correlation_id} id_sessao={sessao_id} api_negocio_payload={payload}")

            url_busca = f"{settings.API_NEGOCIO_URL}/produtos/busca"
            response = await client.post(url_busca, json=payload)
            response.raise_for_status()
            dados_api = response.json()

            if not dados_api.get("resultados"):
                _session_cache.pop(sessao_id, None) # Limpa memória se a busca não achar nada
                return {"resposta": "Desculpe, não encontrei produtos para essa busca."}

            # Se a busca encontrou produtos com mais de uma variação, entra no estado de escolha
            # E se o usuário não especificou uma unidade na busca (evita entrar em modo de escolha desnecessariamente)
            if (len(dados_api.get("resultados", [])) > 0 and 
                len(dados_api["resultados"][0].get("itens", [])) > 1):
                 _session_cache[sessao_id] = {'state': 'aguardando_escolha_item', 'data': dados_api["resultados"]}
            else:
                _session_cache.pop(sessao_id, None) # Limpa se não precisar de escolha

            contexto_fatos = _preparar_contexto_para_ia(dados_api)
            prompt_template = await _get_prompt_template("prompt_gerar_resposta_busca")
            prompt_final = prompt_template.format(contexto=contexto_fatos, mensagem_usuario=mensagem.texto)
            
            tool_call_resposta = await chamar_ollama(mensagem.texto, prompt_final)
            
            resposta_final_obj = {"resposta": tool_call_resposta.parameters.get("mensagem")}
            resposta_final_obj["dados_da_busca"] = dados_api.get("resultados", [])
            return resposta_final_obj

        elif tool_call.tool_name == "adicionar_item_carrinho":
            url_add_item = f"{settings.API_NEGOCIO_URL}/carrinhos/{sessao_id}/itens"
            payload = {
                "item_id": tool_call.parameters.get("item_id"),
                "quantidade": tool_call.parameters.get("quantidade", 1),
                "codfilial": 2
            }
            response = await client.post(url_add_item, json=payload)
            response.raise_for_status()
            return {"resposta": "Item adicionado ao carrinho com sucesso!"}

        elif tool_call.tool_name == "ver_carrinho": # Mantido para o bypass
            url_ver_carrinho = f"{settings.API_NEGOCIO_URL}/carrinhos/{sessao_id}"
            response = await client.get(url_ver_carrinho)
            # Não precisa de raise_for_status, pois a API já trata 404 como "carrinho não encontrado" que resulta em vazio
            dados_carrinho = response.json() if response.status_code == 200 else {}
            return {"resposta": await formatar_resposta_carrinho(dados_carrinho)}
            
        # PR#5: Aceita tanto o nome antigo quanto o novo nome padronizado.
        elif tool_call.tool_name in ["handle_chitchat", "emitir_resposta"]:
            return {"resposta": tool_call.parameters.get("mensagem")}

    raise HTTPException(status_code=400, detail=f"Ferramenta '{tool_call.tool_name}' não implementada.")

async def salvar_feedback(feedback: Feedback):
    async with httpx.AsyncClient() as client:
        response = await client.patch(f"{settings.API_NEGOCIO_URL}/logs/feedback", json=feedback.model_dump())
        response.raise_for_status()
    return {"status": "feedback registrado com sucesso"}