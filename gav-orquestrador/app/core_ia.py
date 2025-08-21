# /gav-orquestrador/app/core_ia.py

import yaml
import re
from pathlib import Path
from .esquemas import ToolCall

MANIFEST_PATH = Path(__file__).parent.parent / "model_manifest.yml"
MANIFEST = None

def carregar_manifesto():
    """Carrega o manifesto YAML para a memória."""
    global MANIFEST
    if MANIFEST is None:
        print("INFO: Carregando o manifesto do modelo pela primeira vez...")
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            MANIFEST = yaml.safe_load(f)
        print("INFO: Manifesto do modelo carregado com sucesso.")
    return MANIFEST

async def rotear_e_decidir_acao(mensagem, correlation_id) -> ToolCall:
    """
    Processa a mensagem do usuário usando as regras do manifesto para decidir a próxima ação.
    """
    
    # Importação local para evitar o erro de importação circular
    from . import servicos

    manifesto = carregar_manifesto()
    estado_sessao = servicos._session_cache.get(mensagem.sessao_id, {})

    for regra in manifesto.get("roteamento", []):
        print(f"DEBUG: correlation_id={correlation_id} avaliando_regra='{regra['nome']}'")
        condicoes_satisfeitas = True
        for condicao in regra.get("condicoes", []):
            if condicao["tipo"] == "regex":
                if not re.search(condicao["padrao"], mensagem.texto, re.IGNORECASE):
                    condicoes_satisfeitas = False
                    break
            elif condicao["tipo"] == "estado_sessao":
                if estado_sessao.get("state") != condicao["estado"]:
                    condicoes_satisfeitas = False
                    break
        
        if condicoes_satisfeitas:
            print(f"INFO: correlation_id={correlation_id} id_sessao={mensagem.sessao_id} regra_ativada='{regra['nome']}'")
            acao = regra["acao"]
            
            # Ação direta de ferramenta (ex: ver carrinho)
            if "tool_name" in acao:
                return ToolCall(tool_name=acao["tool_name"], parameters=acao.get("parametros", {}))
            
            # Ação que depende de um handler customizado no código
            if "handler" in acao and acao["handler"] == "extrair_escolha_do_contexto":
                aliases = await servicos._get_unit_aliases()
                contexto_salvo = estado_sessao.get('data', [])
                resultado_extracao = servicos._extrair_escolha_do_contexto(mensagem.texto, contexto_salvo, aliases)
                if resultado_extracao: # Se a extração foi bem-sucedida, retorna a ação
                    return resultado_extracao
                # Se a extração falhou (retornou None), a condição não é satisfeita, e o loop continua para a próxima regra.
                else:
                    condicoes_satisfeitas = False

    # Se nenhuma regra de bypass foi ativada, executa a triagem padrão
    regra_triagem = manifesto["roteamento"][-1] # Assume que a última regra é a de triagem
    print(f"INFO: correlation_id={correlation_id} id_sessao={mensagem.sessao_id} regra_ativada='{regra_triagem['nome']}'")
    
    prompt_triagem = await servicos._get_prompt_template(regra_triagem["acao"]["prompt"])
    classificacao_json = await servicos._chamar_llm_para_json(mensagem.texto, prompt_triagem)
    categoria = classificacao_json.get("categoria", "conversa_fiada")
    print(f"INFO: correlation_id={correlation_id} id_sessao={mensagem.sessao_id} intencao_classificada={categoria}")

    # Mapeia a intenção classificada para a ação correspondente no manifesto
    for mapeamento in regra_triagem["acao"]["mapeamento_intencao"]:
        if categoria in mapeamento["intencao"]:
            acao_mapeada = mapeamento["acao"]
            if acao_mapeada["tipo"] == "extracao_parametros_llm":
                prompt_extracao = await servicos._get_prompt_template(acao_mapeada["prompt"])
                return await servicos.chamar_ollama(mensagem.texto, prompt_extracao)
            elif "tool_name" in acao_mapeada: # Ação direta de ferramenta (ex: saudação)
                return ToolCall(tool_name=acao_mapeada["tool_name"], parameters=acao_mapeada.get("parametros", {}))

    # Fallback final
    return ToolCall(tool_name="emitir_resposta", parameters={"mensagem": "Desculpe, não consegui processar sua solicitação."})