import httpx
from app.config.settings import config

API_NEGOCIO_URL = config.API_NEGOCIO_URL

def obter_prompt_do_banco(nome: str, espaco: str, versao: int) -> dict:
    resposta = httpx.get(
        f"{API_NEGOCIO_URL}/admin/prompts/{nome}",
        params={"espaco": espaco, "versao": versao},
        timeout=10
    )
    resposta.raise_for_status()
    return resposta.json()
