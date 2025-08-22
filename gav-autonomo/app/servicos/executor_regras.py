# arquivo: servicos/executor_regras.py

from app.adaptadores.cliente_negocio import obter_prompt_do_banco
from app.adaptadores.interface_llm import completar_para_json
from app.validadores.modelos import validar_json_contra_schema
import yaml

def executar_regras_do_manifesto(mensagem: str) -> dict:
    with open("app/config/model_manifest.yml", encoding="utf-8") as f:
        manifesto = yaml.safe_load(f)
    for regra in manifesto["regras"]:
        if regra["action"] == "decisao_llm":
            prompt = obter_prompt_do_banco(
                nome=regra["prompt"],
                espaco=regra["espaco_prompt"],
                versao=regra["versao_prompt"]
            )
            resposta = completar_para_json(
                sistema=prompt["template"],
                entrada_usuario=mensagem,
                exemplos=prompt.get("exemplos", []),
                caminho_schema=regra["schema"],
                modelo=manifesto["defaults"]["modelo"]
            )
            validar_json_contra_schema(resposta, regra["schema"])
            return resposta
    return {"erro": "Nenhuma regra válida encontrada."}
