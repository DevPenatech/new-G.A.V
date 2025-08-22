import httpx
from app.config.settings import config

API_NEGOCIO_URL = config.API_NEGOCIO_URL

def obter_prompt_por_nome(nome: str, espaco: str = "autonomo", versao: int = 2) -> dict:
    url = f"{API_NEGOCIO_URL}/admin/prompts/buscar"
    r = httpx.get(url, params={"nome": nome, "espaco": espaco, "versao": versao}, timeout=10.0)
    r.raise_for_status()
    return r.json()

def listar_exemplos_prompt(prompt_id: int) -> list[dict]:
    url = f"{API_NEGOCIO_URL}/admin/prompts/{prompt_id}/exemplos/ativos"
    r = httpx.get(url, timeout=10.0)
    r.raise_for_status()
    return r.json()

def buscar_produtos(query: str, ordenar_por: str | None = None) -> dict:
    url = f"{API_NEGOCIO_URL}/produtos/busca"
    r = httpx.post(url, json={"query": query, "ordenar_por": ordenar_por}, timeout=15.0)
    r.raise_for_status()
    return r.json()

def adicionar_ao_carrinho(sessao_id: str, **payload) -> dict:
    url = f"{API_NEGOCIO_URL}/carrinhos/{sessao_id}/itens"
    r = httpx.post(url, json=payload, timeout=10.0)
    r.raise_for_status()
    return r.json()

def ver_carrinho(sessao_id: str) -> dict:
    url = f"{API_NEGOCIO_URL}/carrinhos/{sessao_id}"
    r = httpx.get(url, timeout=10.0)
    r.raise_for_status()
    return r.json()