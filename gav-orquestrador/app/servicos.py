# /gav-orquestrador/app/servicos.py

import uuid
from . import core_ia
import httpx
import json
import re
from .config import settings
from .esquemas import ToolCall, MensagemChat, Feedback
from fastapi import HTTPException
from pathlib import Path

# --- Variáveis de Cache em Memória ---
_session_cache = {}
_prompt_cache = {}
_unit_alias_cache = None
_modelfile_content = None

# --- Funções de Inicialização e Cache ---

def _carregar_modelfile():
    """Carrega o conteúdo do Modelfile para a memória na inicialização."""
    global _modelfile_content
    if _modelfile_content is None:
        try:
            modelfile_path = Path(__file__).parent / "gav_modelfile.md"
            with open(modelfile_path, "r", encoding="utf-8") as f:
                _modelfile_content = f.read()
            print("INFO: Modelfile carregado com sucesso.")
        except FileNotFoundError:
            print("WARN: gav_modelfile.md não encontrado. Usando um system prompt padrão.")
            _modelfile_content = "Você é um assistente prestativo."
    return _modelfile_content

_carregar_modelfile() # Garante que o modelfile é carregado quando o módulo é importado

async def _get_prompt_template(nome_prompt: str) -> dict:
    """Busca um prompt da API de Negócio e o armazena em cache."""
    if nome_prompt in _prompt_cache:
        return _prompt_cache[nome_prompt]
    
    url = f"{settings.API_NEGOCIO_URL}/prompts/{nome_prompt}"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            prompt_data = response.json()
            _prompt_cache[nome_prompt] = prompt_data
            return prompt_data
    except httpx.RequestError:
        return {"template": {"template": "Você é um assistente prestativo.", "exemplos": []}}

# --- Lógica Central de IA ---

async def chamar_ollama(texto_usuario: str, prompt_sistema: dict | str, esperar_json: bool) -> dict | str:
    """
    Função central e única para chamar o LLM.
    Pode retornar um dicionário (se esperar_json=True) ou uma string de texto.
    """
    url_ollama = f"{settings.OLLAMA_HOST}/api/chat"
    
    prompt_final = prompt_sistema
    if isinstance(prompt_sistema, dict):
        template_obj = prompt_sistema.get("template", {})
        template = template_obj.get("template", "")
        exemplos = template_obj.get("exemplos", [])
        
        exemplos_formatados = "\n\n".join(
            [f"Exemplo de Input do Usuário: \"{ex['exemplo_input']}\"\nExemplo de Output JSON Esperado: {ex['exemplo_output_json']}" for ex in exemplos]
        )
        prompt_final = f"{template}\n\n--- EXEMPLOS DE USO ---\n{exemplos_formatados}"
     
    prompt_combinado = f"{_modelfile_content}\n\n--- INSTRUÇÕES DA TAREFA ATUAL ---\n\n{prompt_final}"
    payload = {
        "model": settings.OLLAMA_MODEL_NAME, "temperature": 0.1,
        "messages": [{"role": "system", "content": prompt_combinado}, {"role": "user", "content": texto_usuario}],
        "format": "json" if esperar_json else "text", "stream": False
    }
      
    async with httpx.AsyncClient(timeout=180.0) as client:
        try:
            response = await client.post(url_ollama, json=payload)
            response.raise_for_status()
            resposta_str = response.json()["message"]["content"]
            
            if esperar_json:
                try:
                    return json.loads(resposta_str)
                except json.JSONDecodeError:
                    print(f"ALERTA: LLM deveria retornar JSON mas retornou texto. Resposta: {resposta_str}")
                    return {"tool_name": "emitir_resposta", "parameters": {"mensagem": "Desculpe, tive um problema ao processar a resposta."}}
            else:
                return resposta_str

        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Timeout ao chamar o LLM.")
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Erro de conexão com o Ollama: {e}")

# --- Orquestração e Execução de Ferramentas ---

async def orquestrar_chat(mensagem: MensagemChat):
    """Orquestra a conversa, decidindo e executando a ação apropriada."""
    correlation_id = uuid.uuid4()
    print(f"INFO: correlation_id={correlation_id} id_sessao={mensagem.sessao_id} status=iniciado mensagem='{mensagem.texto}'")
    
    acao_dict = await core_ia.rotear_e_decidir_acao(mensagem, correlation_id)
    tool_call = ToolCall(**acao_dict)
    print(f"INFO: correlation_id={correlation_id} id_sessao={mensagem.sessao_id} llm_tool_name={tool_call.tool_name}")
 
    async with httpx.AsyncClient() as client:
        log_payload = {"sessao_id": mensagem.sessao_id, "mensagem_usuario": mensagem.texto, "resposta_json": tool_call.model_dump()}
        await client.post(f"{settings.API_NEGOCIO_URL}/logs/interacao", json=log_payload)

    resposta_final = await executar_ferramenta(tool_call, mensagem, correlation_id)
    print(f"INFO: correlation_id={correlation_id} id_sessao={mensagem.sessao_id} status=concluido")
    return resposta_final

async def executar_ferramenta(tool_call: ToolCall, mensagem: MensagemChat, correlation_id: uuid.UUID):
    """Executa a ferramenta decidida pelo LLM e retorna a resposta final para o usuário."""
    sessao_id = mensagem.sessao_id
    params_log = {k: v for k, v in tool_call.parameters.items() if k not in ["contexto"]}
    print(f"INFO: correlation_id={correlation_id} id_sessao={sessao_id} executando_ferramenta={tool_call.tool_name} parametros={params_log}")
     
    if tool_call.tool_name in ["adicionar_item_carrinho", "ver_carrinho"]:
        _session_cache.pop(sessao_id, None)
        
    async with httpx.AsyncClient(timeout=30.0) as client:
        if tool_call.tool_name == "buscar_produtos":
            query = tool_call.parameters.get("query", "").strip()
            if not query:
                return {"resposta": "Não entendi o que você quer procurar.", "dados_da_busca": []}

            payload = { "query": query, "codfilial": 2, "limit": 10 }
            if tool_call.parameters.get("ordenar_por") in ["preco_asc", "preco_desc"]:
                payload["ordenar_por"] = tool_call.parameters["ordenar_por"]
            
            response = await client.post(f"{settings.API_NEGOCIO_URL}/produtos/busca", json=payload)
            response.raise_for_status()
            dados_api = response.json()

            if not dados_api.get("resultados"):
                _session_cache.pop(sessao_id, None)
                return {"resposta": "Desculpe, não encontrei produtos para essa busca.", "dados_da_busca": []}

            if len(dados_api.get("resultados", [])) > 0 and len(dados_api["resultados"][0].get("itens", [])) > 1:
                 _session_cache[sessao_id] = {'state': 'aguardando_escolha_item', 'data': dados_api["resultados"]}
            else:
                _session_cache.pop(sessao_id, None)

            contexto_fatos = _preparar_contexto_para_ia(dados_api)
            prompt_data = await _get_prompt_template("prompt_sucesso_busca")
            
            template_string = prompt_data.get("template", {}).get("template", "Mostre os resultados: {contexto}")
            prompt_formatado = template_string.format(contexto=contexto_fatos, mensagem_usuario=mensagem.texto)
            
            mensagem_gerada = await chamar_ollama(mensagem.texto, prompt_formatado, esperar_json=False)

            return {"resposta": mensagem_gerada, "dados_da_busca": dados_api.get("resultados", [])}

        elif tool_call.tool_name == "adicionar_item_carrinho":
            payload = { "item_id": tool_call.parameters.get("item_id"), "quantidade": tool_call.parameters.get("quantidade", 1), "codfilial": 2 }
            await client.post(f"{settings.API_NEGOCIO_URL}/carrinhos/{sessao_id}/itens", json=payload)
            return {"resposta": "Item adicionado ao carrinho com sucesso!", "dados_da_busca": []}

        elif tool_call.tool_name == "ver_carrinho":
            response = await client.get(f"{settings.API_NEGOCIO_URL}/carrinhos/{sessao_id}")
            dados_carrinho = response.json() if response.status_code == 200 else {}
            return {"resposta": await formatar_resposta_carrinho(dados_carrinho), "dados_da_busca": []}
            
        elif tool_call.tool_name in ["handle_chitchat", "emitir_resposta"]:
            return {"resposta": tool_call.parameters.get("mensagem"), "dados_da_busca": []}

    raise HTTPException(status_code=400, detail=f"Ferramenta '{tool_call.tool_name}' não implementada.")

# --- Funções Auxiliares ---
def _preparar_contexto_para_ia(dados_api: dict) -> str:
    resultados = dados_api.get("resultados", [])
    if not resultados: return "Nenhum produto encontrado."
    fatos = []
    if dados_api.get("status_busca") == "fallback":
        fatos.append("Não encontrei a embalagem exata que você pediu, mas achei o produto nestas outras opções:")
    for produto in resultados[:3]:
        desc = produto.get("descricaoweb") or produto.get("descricao", "Produto sem descrição")
        fatos.append(f"\n**{desc}**")
        for item in produto.get("itens", []):
            if item.get("pvenda") is not None:
                preco = item.get("poferta") or item.get("pvenda")
                linha_item = f"- Item `{item['id']}`: {item['unidade']} com {item['qtunit']} und. - **R$ {preco:.2f}**"
                if item.get("poferta") and item.get("pvenda") and item.get("poferta") < item.get("pvenda"):
                    linha_item += " *(OFERTA!)*"
                fatos.append(linha_item)
    return "\n".join(fatos)

async def formatar_resposta_carrinho(dados_carrinho: dict) -> str:
    if not dados_carrinho or not dados_carrinho.get("itens"):
        return "Seu carrinho está vazio."
    linhas_itens = []
    for item in dados_carrinho["itens"]:
        linhas_itens.append(f"{item['quantidade']}x {item['descricao_produto']} — R$ {item['subtotal']:.2f}")
    resposta_formatada = "\n".join(linhas_itens)
    resposta_formatada += f"\n\n**Total:** R$ {dados_carrinho['valor_total']:.2f}"
    return resposta_formatada

async def salvar_feedback(feedback: Feedback):
    async with httpx.AsyncClient() as client:
        response = await client.patch(f"{settings.API_NEGOCIO_URL}/logs/feedback", json=feedback.model_dump())
        response.raise_for_status()
    return {"status": "feedback registrado com sucesso"}

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

def _extrair_escolha_do_contexto(texto_usuario: str, contexto_busca: list, aliases: dict) -> ToolCall | None:
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
    return None