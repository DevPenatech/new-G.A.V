# arquivo: servicos/executor_regras.py
from app.adaptadores.cliente_negocio import (
    obter_prompt_por_nome, listar_exemplos_prompt,
    buscar_produtos, adicionar_ao_carrinho, ver_carrinho
)
from app.adaptadores.interface_llm import completar_para_json
from app.validadores.modelos import validar_json_contra_schema, carregar_schema
import yaml
import json

def executar_regras_do_manifesto(mensagem: dict) -> dict:
    """
    mensagem: {"texto": "...", "sessao_id": "..."}
    """
    with open("app/config/model_manifest.yml", encoding="utf-8") as f:
        manifesto = yaml.safe_load(f)
    for regra in manifesto["regras"]:
        if regra["action"] == "decisao_llm":
            
            p = obter_prompt_por_nome(nome=regra["prompt"], espaco=regra["espaco_prompt"], versao=regra["versao_prompt"])
            exemplos = listar_exemplos_prompt(p["id"])

            saida = completar_para_json(
                sistema=p["template"],
                entrada_usuario=mensagem["texto"],
                exemplos=exemplos,
                modelo=manifesto["defaults"].get("modelo")
            )

            schema = carregar_schema(regra["schema"])
            if not validar_json_contra_schema(saida, schema):
                return {"mensagem": "Não consegui entender sua intenção. Pode reformular?"}

            tool = (saida.get("tool_name") or "").strip()
            params = saida.get("parameters") or {}

            # Execução “burra”: orquestrador só chama a API correspondente
            if tool == "buscar_produtos":
                return buscar_produtos(query=params.get("query",""), ordenar_por=params.get("ordenar_por"))
            elif tool == "adicionar_item_carrinho":
                payload = dict(params)
                # coerção branda para inteiros comuns
                for k in ("item_id","quantidade"):
                    if isinstance(payload.get(k), str) and payload[k].isdigit():
                        payload[k] = int(payload[k])
                return adicionar_ao_carrinho(sessao_id=mensagem["sessao_id"], **payload)
            elif tool == "ver_carrinho":
                return ver_carrinho(sessao_id=mensagem["sessao_id"])
            elif tool == "iniciar_adicao_item_carrinho":
                # (Opcional) Fluxo em 2 etapas: buscar → prompt_extrair_escolha → adicionar
                # Para já: devolve a busca para o cliente (ou implemente o Passo 17 completo aqui)
                r = buscar_produtos(query=params.get("nome_produto",""), ordenar_por=None)
                return {"status":"precisa_confirmar","busca": r}
            else:
                # Fallback seguro
                return {"mensagem": params.get("mensagem", f"Ação não reconhecida: {tool}")}
    return {"erro": "Nenhuma regra válida encontrada."}
