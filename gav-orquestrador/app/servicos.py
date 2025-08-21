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

_session_cache = {}
_prompt_cache = {}
_unit_alias_cache = None

_modelfile_content = None # Variável global para o modelfile

def _carregar_modelfile():
    """Carrega o conteúdo do Modelfile para a memória."""
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

# Carrega o modelfile na inicialização do módulo
_carregar_modelfile()

def _carregar_modelfile():
    """Carrega o conteúdo do Modelfile para a memória."""
    global _modelfile_content
    if _modelfile_content is None:
        try:
            modelfile_path = Path(__file__).parent.parent / "gav_modelfile.md"
            with open(modelfile_path, "r", encoding="utf-8") as f:
                _modelfile_content = f.read()
            print("INFO: Modelfile carregado com sucesso.")
        except FileNotFoundError:
            print("WARN: gav_modelfile.md não encontrado. Usando um system prompt padrão.")
            _modelfile_content = "Você é um assistente prestativo."
    return _modelfile_content

# Carrega o modelfile na inicialização do módulo
_carregar_modelfile()

async def _get_prompt_template(nome_prompt: str) -> str:
    if nome_prompt in _prompt_cache: return _prompt_cache[nome_prompt]
    url = f"{settings.API_NEGOCIO_URL}/prompts/{nome_prompt}"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            if response.status_code != 200:
                 raise HTTPException(status_code=response.status_code, detail=f"Erro ao buscar prompt '{nome_prompt}': {response.text}")
            
            # Agora o endpoint retorna um objeto com template e exemplos
            prompt_data = response.json()
            _prompt_cache[nome_prompt] = prompt_data
            return prompt_data
    except httpx.RequestError:
        # Retorna um objeto padrão em caso de falha de conexão
        return {"template": "Você é um assistente prestativo. Responda em JSON.", "exemplos": []}
     
async def chamar_ollama(texto_usuario: str, prompt_sistema: str) -> ToolCall:
    """Chama o LLM esperando especificamente um JSON no formato ToolCall."""
    url_ollama = f"{settings.OLLAMA_HOST}/api/chat"
    

    # Se prompt_sistema for um dict (vindo do _get_prompt_template), formata com exemplos
    if isinstance(prompt_sistema, dict):
        template = prompt_sistema.get("template", "")
        exemplos = prompt_sistema.get("exemplos", [])
        
        exemplos_formatados = []
        for ex in exemplos:
            exemplos_formatados.append(f"Exemplo de Input do Usuário: \"{ex['exemplo_input']}\"\nExemplo de Output JSON Esperado: {ex['exemplo_output_json']}")
        
        prompt_final = f"{template}\n\n--- EXEMPLOS DE USO ---\n" + "\n\n".join(exemplos_formatados)
    else: # Mantém compatibilidade caso um prompt simples seja passado
        prompt_final = prompt_sistema
     
    # Combina o Modelfile com o prompt específico da tarefa
    prompt_combinado = f"{_modelfile_content}\n\n--- INSTRUÇÕES DA TAREFA ATUAL ---\n\n{prompt_final}"

    payload = { "model": settings.OLLAMA_MODEL_NAME, "temperature": 0.1, "messages": [{"role": "system", "content": prompt_combinado}, {"role": "user", "content": texto_usuario}], "format": "json", "stream": False }
      
    async with httpx.AsyncClient(timeout=180.0) as client:
        try:
            response = await client.post(url_ollama, json=payload)
            response.raise_for_status()
            resposta_str = response.json()["message"]["content"]
            try:
                # CORREÇÃO: Adiciona .strip() para remover quebras de linha
                # ou espaços no início/fim da resposta do LLM.
                # LOG DE DIAGNÓSTICO: Mostra a resposta bruta e a resposta limpa.
                print(f"DEBUG: Resposta bruta do LLM: >>>{resposta_str}<<<")
                resposta_limpa = resposta_str.strip()
                print(f"DEBUG: Resposta após .strip(): >>>{resposta_limpa}<<<")
                tool_call_data = json.loads(resposta_limpa)
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


    # --- INÍCIO DA CORREÇÃO ---
    # Adiciona a mesma lógica de tratamento de exemplos que a 'chamar_ollama' possui.
    if isinstance(prompt_sistema, dict):
        template = prompt_sistema.get("template", "")
        exemplos = prompt_sistema.get("exemplos", [])
        exemplos_formatados = []
        for ex in exemplos:
            exemplos_formatados.append(f"Exemplo de Input do Usuário: \"{ex['exemplo_input']}\"\nExemplo de Output JSON Esperado: {ex['exemplo_output_json']}")
        prompt_final = f"{template}\n\n--- EXEMPLOS DE USO ---\n" + "\n\n".join(exemplos_formatados)
    else:
        prompt_final = prompt_sistema

    prompt_combinado = f"{_modelfile_content}\n\n--- INSTRUÇÕES DA TAREFA ATUAL ---\n\n{prompt_final}"
    payload = {"model": settings.OLLAMA_MODEL_NAME, "temperature": 0.1, "messages": [{"role": "system", "content": prompt_combinado}, {"role": "user", "content": texto_usuario}], "format": "json", "stream": False}
    # --- FIM DA CORREÇÃO ---

    try:
         # Alterado para esperar TEXTO em vez de JSON para prompts de geração de resposta
        payload["format"] = "text" if "emitir_resposta" in prompt_final else "json"

        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(url_ollama, json=payload)
            response.raise_for_status()
            resposta_str = response.json()["message"]["content"]

            # Se a resposta esperada era texto, retorna a string diretamente
            if payload["format"] == "text":
                return resposta_str
            else: # Senão, tenta fazer o parse do JSON
                # CORREÇÃO: Adiciona .strip() aqui também por segurança.
                print("Retorno "+resposta_str.strip())
                return json.loads(resposta_str.strip())

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
    """
    [FUNÇÃO ATUALIZADA] Extrai a escolha do usuário de forma mais robusta,
    priorizando a extração de quantidade e depois identificando o item.
    """
    texto_lower = texto_usuario.lower().strip()
    quantidade_extraida = 1
    texto_sem_quantidade = texto_lower
    
    # 1. Tenta extrair a quantidade primeiro para evitar confundir com o código do produto
    mapa_palavras = {"uma": 1, "um": 1, "duas": 2, "dois": 2, "três": 3, "quatro": 4, "cinco": 5}
    for palavra, num in mapa_palavras.items():
        if f' {palavra} ' in f' {texto_lower} ':
            quantidade_extraida = num
            texto_sem_quantidade = texto_lower.replace(palavra, '')
            break # Para na primeira palavra numérica encontrada

    match_num = re.search(r'\b(\d{1,3})\b', texto_lower) # Procura números pequenos (até 3 dígitos)
    if match_num:
        numero = int(match_num.group(1))
        # Evita confundir com código do produto se for um número grande
        if numero < 1000:
            quantidade_extraida = numero
            texto_sem_quantidade = texto_lower.replace(match_num.group(0), '', 1)

    # 2. Agora, busca pelo item no texto que já não tem (potencialmente) a quantidade
    texto_para_busca = texto_sem_quantidade

    # Prioriza a busca por código do produto (número de 5+ dígitos)
    match_codprod = re.search(r'\b(\d{5,})\b', texto_para_busca)
    if match_codprod:
        codprod_escolhido = int(match_codprod.group(1))
        for produto in contexto_busca:
            if produto.get('codprod') == codprod_escolhido:
                # Pega o primeiro item (geralmente a unidade) deste produto
                if produto.get("itens"):
                    item_id_escolhido = produto["itens"][0]['id']
                    print(f"Escolha extraída por CÓDIGO DE PRODUTO: {codprod_escolhido} -> item {item_id_escolhido}, Quantidade: {quantidade_extraida}")
                    return ToolCall(tool_name="adicionar_item_carrinho", parameters={"item_id": item_id_escolhido, "quantidade": quantidade_extraida})

    print("Não foi possível extrair a escolha do usuário. Tratando como nova busca.")
    return None



def _preparar_contexto_para_ia(dados_api: dict) -> str:
    """
    [FUNÇÃO RESTAURADA E MELHORADA] Formata os dados da busca em um texto rico
        para o LLM, incluindo unidades, preços e códigos.
     """
    resultados = dados_api.get("resultados", [])
    if not resultados:
        return "Nenhum produto encontrado."

    fatos = []
    if dados_api.get("status_busca") == "fallback":
        fatos.append("[AVISO] Não encontrei a embalagem exata, mas achei o produto nestas outras opções:")

    # Limita a 5 itens para não exceder o contexto e focar nos mais relevantes.
    for produto in resultados[:4]: # Limita a 4 para não sobrecarregar
        desc = produto.get('descricaoweb') or produto.get('descricao', 'Produto sem descrição')
        codprod = produto.get('codprod', 'N/A')
        
        itens_str = []
        for item in produto.get("itens", []):
            unidade = item.get('unidade', '')
            preco = item.get('poferta') or item.get('pvenda')
            # Valida se o preço é um número válido e maior que zero.
            if isinstance(preco, (int, float)) and preco > 0:
                itens_str.append(f"{unidade}: R$ {preco:.2f}")

        if itens_str:
            fatos.append(f"- (cód {codprod}) {desc} — {' | '.join(itens_str)}")

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
    
    # ETAPA 1: O cérebro agora é o core_ia, que lê o manifesto
    tool_call_a_executar = await core_ia.rotear_e_decidir_acao(mensagem, correlation_id)
    print(f"INFO: correlation_id={correlation_id} id_sessao={sessao_id} llm_tool_name={tool_call_a_executar.tool_name}")
 
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
    # --- LOG DE DIAGNÓSTICO DEFINITIVO ---
    # Se esta mensagem não aparecer nos logs, o arquivo no contêiner não foi atualizado.
    print("--- EXECUTANDO A VERSÃO MAIS RECENTE DO CODIGO (servicos.py) ---")
    # ------------------------------------

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
            # O prompt_mestre agora faz a correção E a extração, então a chamada dupla foi removida.
            
            query = tool_call.parameters.get("query", "").strip()
            ordenar_por = tool_call.parameters.get("ordenar_por")

            print(f"INFO: correlation_id={correlation_id} id_sessao={sessao_id} query_extraida='{query}'")

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

            # --- CORREÇÃO DEFINITIVA DO BUG: Acessa o template aninhado e trabalha com uma cópia ---
            # 1. CORREÇÃO DO NOME DO PROMPT: Alterado de "prompt_sucesso_busca" para o nome correto do seu banco.
            prompt_data_original = await _get_prompt_template("prompt_gerar_resposta_busca")
 
            # 2. CORREÇÃO DA FORMATAÇÃO: Formata o template ANTES de passar para o LLM.
            # Garante que a estrutura (template + exemplos) seja mantida para a função `chamar_ollama`.
            prompt_para_llm = prompt_data_original.copy() # Cria uma cópia para não modificar o cache
            template_string = prompt_data_original.get("template", {}).get("template", "")
            
            # A variável no prompt é {contexto_busca}, conforme definimos anteriormente.
            prompt_para_llm["template"] = template_string.format(contexto_busca=contexto_fatos)
                                                     
            tool_call_resposta = await chamar_ollama(mensagem.texto, prompt_para_llm)
    
                                                     
            # [NOVA LÓGICA ROBUSTA] - Lida com a alucinação do LLM
            final_message = tool_call_resposta.parameters.get("mensagem")
            # Se o LLM não usou a chave "mensagem", mas usou "produtos"
            if not final_message and "produtos" in tool_call_resposta.parameters:
                produtos_formatados = tool_call_resposta.parameters["produtos"]
                # Junta a lista de produtos em uma única string de texto
                final_message = "\n".join(produtos_formatados)

            resposta_final_obj = {"resposta": final_message}
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