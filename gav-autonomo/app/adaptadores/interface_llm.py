import httpx
import json
from jsonschema import validate, ValidationError
from app.config.settings import config

LLM_API_URL = config.OLLAMA_HOST  

def completar_para_json(sistema: str, entrada_usuario: str, exemplos: list, caminho_schema: str, modelo: str) -> dict:
    mensagens = [{"role": "system", "content": sistema}]
    
    for ex in exemplos:
        mensagens.append({"role": "user", "content": ex["exemplo_input"]})
        mensagens.append({"role": "assistant", "content": ex["exemplo_output_json"]})

    mensagens.append({"role": "user", "content": entrada_usuario})

    resposta = httpx.post(
        LLM_API_URL,
        json={"model": modelo, "messages": mensagens, "temperature": 0.2, "max_tokens": 500},
        timeout=30
    )
    resposta.raise_for_status()
    
    conteudo = resposta.json()["choices"][0]["message"]["content"]

    try:
        json_saida = json.loads(conteudo)
    except json.JSONDecodeError as e:
        raise ValueError(f"Resposta do LLM não é JSON válido: {e}")

    with open(caminho_schema, "r", encoding="utf-8") as f:
        schema = json.load(f)

    try:
        validate(instance=json_saida, schema=schema)
    except ValidationError as e:
        raise ValueError(f"JSON inválido conforme schema: {e}")

    return json_saida
