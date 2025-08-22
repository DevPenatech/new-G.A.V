import httpx, json
from app.config.settings import config

OLLAMA_URL = config.OLLAMA_HOST.rstrip("/")
OLLAMA_MODEL = getattr(config, "OLLAMA_MODEL", "llama3.1:8b")

def _montar_prompt(sistema: str, entrada_usuario: str, exemplos: list[dict]) -> str:
    partes = [sistema.strip()]
    for ex in (exemplos or []):
        partes.append("Exemplo de entrada:\n" + (ex.get("exemplo_input") or "").strip())
        partes.append("Exemplo de saída (JSON):\n" + (ex.get("exemplo_output_json") or "").strip())
    partes.append("Entrada do usuário:\n" + (entrada_usuario or "").strip())
    return "\n\n".join(partes)

def completar_para_json(sistema: str, entrada_usuario: str, exemplos: list[dict] | None = None, modelo: str | None = None) -> dict:
    prompt_texto = _montar_prompt(sistema, entrada_usuario, exemplos or [])
    resp = httpx.post(
        f"{OLLAMA_URL}/api/generate",
        json={
            "model": modelo or OLLAMA_MODEL,
            "prompt": prompt_texto,
            "format": "json",     # força JSON
            "stream": False,
            "options": {"temperature": 0.1}
        },
        timeout=60.0
    )
    resp.raise_for_status()
    data = resp.json()
    conteudo = data.get("response") or data.get("output") or ""
    try:
        return json.loads(conteudo)
    except json.JSONDecodeError:
        raise ValueError("LLM não retornou JSON válido. Ajuste o template/exemplos.")