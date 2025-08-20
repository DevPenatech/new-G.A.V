# gav-orquestrador/app/servicos.py

import httpx
import json
from .config import settings
from .esquemas import ToolCall, MensagemChat, Feedback
from fastapi import HTTPException


# Cache em memória para os templates de prompt
_prompt_cache = {}


async def _get_prompt_template(nome_prompt: str) -> str:
    """Busca um template de prompt da api-negocio, com cache em memória."""
    if nome_prompt in _prompt_cache:
        return _prompt_cache[nome_prompt]
    
    url = f"{settings.API_NEGOCIO_URL}/prompts/{nome_prompt}"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            template = response.json()["template"]
            _prompt_cache[nome_prompt] = template # Salva no cache
            return template
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail=f"Não foi possível buscar o prompt '{nome_prompt}' da API de Negócio.")


async def chamar_ollama(texto_usuario: str, prompt_sistema: str) -> ToolCall:
    """
    Chama o LLM e usa um parser seguro para garantir que a resposta seja sempre válida.
    """
    url_ollama = f"{settings.OLLAMA_HOST}/api/chat"
    payload = {
        "model": settings.OLLAMA_MODEL_NAME,
        "temperature": 0.1, # Reduz a aleatoriedade para respostas mais consistentes
        "messages": [
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": texto_usuario}
        ],
        "format": "json", "stream": False
    }
    
    async with httpx.AsyncClient(timeout=180.0) as client:
        try:
            response = await client.post(url_ollama, json=payload)
            response.raise_for_status()
            resposta_str = response.json()["message"]["content"]
            
            # --- PARSER SEGURO ---
            # Tenta validar o JSON retornado. Se falhar, retorna uma ferramenta padrão.
            try:
                tool_call_data = json.loads(resposta_str)
                validated_tool_call = ToolCall(**tool_call_data)
                return validated_tool_call
            except (json.JSONDecodeError, TypeError):
                 # Se o LLM retornar algo que não é um JSON válido ou com a estrutura errada,
                 # nós não quebramos a aplicação. Assumimos uma ação padrão.
                print(f"ALERTA: LLM retornou JSON inválido. Resposta: {resposta_str}")
                return ToolCall(
                    tool_name="handle_chitchat",
                    parameters={"mensagem": "Desculpe, não consegui processar sua solicitação. Poderia tentar de outra forma?"}
                )

        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Timeout ao chamar o LLM.")
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Erro de conexão com o Ollama: {e}")


async def _gerar_resposta_final_com_llm(contexto: str, mensagem_usuario: str, prompt_template: str) -> dict:
    """Função auxiliar que agora aceita um template de prompt."""
    prompt_final = prompt_template.format(
        contexto=contexto,
        mensagem_usuario=mensagem_usuario
    )
    tool_call_resposta = await chamar_ollama(mensagem_usuario, prompt_final)
    return {"resposta": tool_call_resposta.parameters.get("mensagem")}

async def executar_ferramenta(tool_call: ToolCall, mensagem: MensagemChat):
    sessao_id = mensagem.sessao_id
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        if tool_call.tool_name == "buscar_produtos":
            url_busca = f"{settings.API_NEGOCIO_URL}/produtos/busca"
            ordenar_por = tool_call.parameters.get("ordenar_por")
            payload = {
                "query": tool_call.parameters.get("query", ""),
                "codfilial": 2,
                "ordenar_por": ordenar_por
            }
            if ordenar_por is None: del payload["ordenar_por"]
            response = await client.post(url_busca, json=payload)
            response.raise_for_status()
            dados_resposta = response.json()
        
            if not dados_resposta.get("resultados"):
                return {"resposta": "Desculpe, não encontrei nenhum produto para essa busca."}

            # --- AQUI ESTÁ A NOVA LÓGICA DE PROMPT ESPECÍFICO ---
            
            contexto_dados = json.dumps(dados_resposta['resultados'])
            resposta_final = {}

            if dados_resposta["status_busca"] == "fallback":
                prompt_template = """
                A busca original do usuário foi por '{mensagem_usuario}'.
                Não encontramos uma correspondência exata para a unidade de medida solicitada.
                No entanto, encontramos o produto com estas variações disponíveis: {contexto}.
                Sua tarefa é informar ao usuário de forma clara e amigável que a unidade que ele pediu NÃO foi encontrada,
                mas que você encontrou o produto em outras embalagens. Seja fiel aos dados e apresente as opções disponíveis.
                Sua resposta DEVE sempre ser um JSON no formato e sempre:
                {{\"tool_name\": \"handle_chitchat\", \"parameters\": {{\"mensagem\": \"SUA_RESPOSTA_AQUI\"}}}}
                """
                resposta_final = await _gerar_resposta_final_com_llm(contexto_dados, mensagem.texto, prompt_template)

            else: # sucesso
                prompt_template = """
                A busca do usuário foi por '{mensagem_usuario}'.
                Encontramos os seguintes resultados que correspondem exatamente ao pedido: {contexto}.
                Apresente estes resultados de forma amigável e clara para o usuário.
                Sua resposta DEVE sempre ser um JSON no formato:
                {{\"tool_name\": \"handle_chitchat\", \"parameters\": {{\"mensagem\": \"SUA_RESPOSTA_AQUI\"}}}}
                """
                resposta_final = await _gerar_resposta_final_com_llm(contexto_dados, mensagem.texto, prompt_template)
            
            resposta_final["dados_da_busca"] = dados_resposta["resultados"]
            return resposta_final

        if tool_call.tool_name == "iniciar_adicao_item_carrinho":
            nome_produto = tool_call.parameters.get("nome_produto")
            quantidade = tool_call.parameters.get("quantidade", 1)
            
            url_busca = f"{settings.API_NEGOCIO_URL}/produtos/busca"
            payload_busca = {"query": nome_produto, "codfilial": 2}
            response = await client.post(url_busca, json=payload_busca)
            response.raise_for_status()
            resultados_busca = response.json().get("resultados", [])

            if not resultados_busca:
                return {"resposta": f"Desculpe, não encontrei nenhum produto parecido com '{nome_produto}'."}
            
            primeiro_produto = resultados_busca[0]
            if len(primeiro_produto["itens"]) == 1:
                item_id = primeiro_produto["itens"][0]["id"]
                return await executar_ferramenta(
                    ToolCall(tool_name="adicionar_item_carrinho", parameters={"item_id": item_id, "quantidade": quantidade}),
                    mensagem 
                )
            elif len(primeiro_produto["itens"]) > 1:
                # --- AQUI ESTÁ A CORREÇÃO ---
                # O prompt antigo era muito aberto. Este novo prompt é explícito sobre o formato JSON.
                variacoes_texto = ", ".join([
                    f"{item['unidade']} com {item['qtunit']} un. (item {item['id']})" 
                    for item in primeiro_produto['itens']
                ])
                 
                prompt_esclarecimento = f"""
                O usuário quer adicionar o produto '{nome_produto}', mas ele tem múltiplas variações: {variacoes_texto}.
                Sua tarefa é formular uma pergunta de esclarecimento para o usuário.
                Sua resposta DEVE ser um JSON no seguinte formato exato:
                {{"tool_name": "handle_chitchat", "parameters": {{"mensagem": "SUA_PERGUNTA_AQUI"}}}}

                Exemplo de como sua resposta final deve se parecer:
                {{"tool_name": "handle_chitchat", "parameters": {{"mensagem": "Encontrei o {nome_produto}. Você prefere a variação Unidade (item X) ou Caixa (item Y)?"}}}}

                Agora, gere o JSON com a pergunta para o usuário.
                """
                
                tool_call_pergunta = await chamar_ollama(mensagem.texto, prompt_esclarecimento)
                return {"resposta": tool_call_pergunta.parameters.get("mensagem", "Encontrei múltiplas variações. Qual você deseja?")}
            else:
                return {"resposta": f"Encontrei o produto '{nome_produto}', mas parece não ter variações disponíveis no momento."}

        elif tool_call.tool_name == "adicionar_item_carrinho":
            url_add_item = f"{settings.API_NEGOCIO_URL}/carrinhos/{sessao_id}/itens"
            payload = {
                "item_id": tool_call.parameters.get("item_id"),
                "quantidade": tool_call.parameters.get("quantidade"),
                "codfilial": 2
            }
            response = await client.post(url_add_item, json=payload)
            response.raise_for_status()
            return {"resposta": "Item adicionado ao carrinho com sucesso!"}

        elif tool_call.tool_name == "ver_carrinho":
            url_ver_carrinho = f"{settings.API_NEGOCIO_URL}/carrinhos/{sessao_id}"
            response = await client.get(url_ver_carrinho)
            response.raise_for_status()
            return response.json()
            
        elif tool_call.tool_name == "handle_chitchat":
            return {"resposta": tool_call.parameters.get("mensagem", "Não entendi.")}
            
        else:
            raise HTTPException(status_code=400, detail=f"Ferramenta '{tool_call.tool_name}' desconhecida.")


async def orquestrar_chat(mensagem: MensagemChat):
    # CORREÇÃO PRINCIPAL APLICADA AQUI:
    # Carregamos o prompt mestre e o passamos para a função chamar_ollama
    prompt_sistema = await _get_prompt_template("prompt_mestre")
    tool_call = await chamar_ollama(mensagem.texto, prompt_sistema)
    
    async with httpx.AsyncClient() as client:
        log_payload = {
            "sessao_id": mensagem.sessao_id,
            "mensagem_usuario": mensagem.texto,
            "resposta_json": tool_call.model_dump()
        }
        await client.post(f"{settings.API_NEGOCIO_URL}/logs/interacao", json=log_payload)

    # Passamos o objeto 'mensagem' completo para a função executar_ferramenta
    resultado = await executar_ferramenta(tool_call, mensagem)
    return resultado

async def salvar_feedback(feedback: Feedback):
    async with httpx.AsyncClient() as client:
        response = await client.patch(f"{settings.API_NEGOCIO_URL}/logs/feedback", json=feedback.model_dump())
        response.raise_for_status()
    return {"status": "feedback registrado com sucesso"}