# /gav-orquestrador/app/servicos.py

import httpx
import json
import re
from .config import settings
from .esquemas import ToolCall, MensagemChat, Feedback
from fastapi import HTTPException
from .servico_carrinho import ver_carrinho as ver_carrinho_servico

_session_cache = {}
_prompt_cache = {}
_unit_alias_cache = None

async def _get_prompt_template(nome_prompt: str) -> str:
    if nome_prompt in _prompt_cache: return _prompt_cache[nome_prompt]
    url = f"{settings.API_NEGOCIO_URL}/prompts/{nome_prompt}"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            template = response.json()["template"]
            _prompt_cache[nome_prompt] = template
            return template
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail=f"Não foi possível buscar o prompt '{nome_prompt}'.")

async def chamar_ollama(texto_usuario: str, prompt_sistema: str) -> ToolCall:
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

async def orquestrar_chat(mensagem: MensagemChat):
    sessao_id = mensagem.sessao_id
    tool_call_a_executar: ToolCall
    categoria_parsed = None

    regex_carrinho = r"\b(carrinh[oa]s?|ver carrinho|meu carrinho|mostrar carrinho)\b"
    if re.search(regex_carrinho, mensagem.texto, re.IGNORECASE):
        tool_call_a_executar = ToolCall(tool_name="ver_carrinho", parameters={})
        categoria_parsed = "ver_carrinho"
    elif sessao_id in _session_cache and _session_cache[sessao_id].get('state') == 'aguardando_escolha_item':
        aliases = await _get_unit_aliases()
        contexto_salvo = _session_cache[sessao_id]['data']
        tool_call_a_executar = _extrair_escolha_do_contexto(mensagem.texto, contexto_salvo, aliases)
    else:
        prompt_mestre = await _get_prompt_template("prompt_mestre")
        prompt_a_usar = prompt_mestre.format(contexto_da_conversa="")
        tool_call_a_executar = await chamar_ollama(mensagem.texto, prompt_a_usar)
        
    rota_escolhida = tool_call_a_executar.tool_name
    async with httpx.AsyncClient() as client:
        log_payload = {
            "sessao_id": mensagem.sessao_id,
            "mensagem_usuario": mensagem.texto,
            "resposta_json": tool_call_a_executar.model_dump(),
            "categoria_parsed": categoria_parsed,
            "rota_escolhida": rota_escolhida,
        }
        await client.post(f"{settings.API_NEGOCIO_URL}/logs/interacao", json=log_payload)

    resposta_final = await executar_ferramenta(tool_call_a_executar, mensagem)
    return resposta_final

async def executar_ferramenta(tool_call: ToolCall, mensagem: MensagemChat):
    """Executa a ferramenta decidida pelo LLM e gerencia o estado da memória."""
    sessao_id = mensagem.sessao_id
    aliases = {"exibir_carrinho": "ver_carrinho", "mostrar_carrinho": "ver_carrinho"}
    if tool_call.tool_name in aliases:
        tool_call.tool_name = aliases[tool_call.tool_name]

    # Se a ação for conclusiva (adicionar item, ver carrinho), limpa a memória para a próxima conversa.
    if tool_call.tool_name in ["adicionar_item_carrinho", "ver_carrinho"]:
        _session_cache.pop(sessao_id, None)

    if tool_call.tool_name == "ver_carrinho":
        return await ver_carrinho_servico(sessao_id)

    async with httpx.AsyncClient(timeout=30.0) as client:
        if tool_call.tool_name == "buscar_produtos":
            url_busca = f"{settings.API_NEGOCIO_URL}/produtos/busca"
            
            # Montagem segura do payload para a API
            payload = {
                "query": tool_call.parameters.get("query", ""),
                "codfilial": 2, 
                "limit": 10,
                "ordenar_por": tool_call.parameters.get("ordenar_por", "relevancia")
            }
            
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

        elif tool_call.tool_name == "handle_chitchat":
            return {"resposta": tool_call.parameters.get("mensagem")}

    raise HTTPException(status_code=400, detail=f"Ferramenta '{tool_call.tool_name}' não implementada.")

async def salvar_feedback(feedback: Feedback):
    async with httpx.AsyncClient() as client:
        response = await client.patch(f"{settings.API_NEGOCIO_URL}/logs/feedback", json=feedback.model_dump())
        response.raise_for_status()
    return {"status": "feedback registrado com sucesso"}
