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

async def buscar_manifesto_completo() -> list[dict]:
    """
    Busca todos os prompts ativos e seus respectivos exemplos da api-negocio.
    Esta função é chamada apenas na inicialização para popular o cache.
    """
    url_prompts = f"{API_NEGOCIO_URL}/admin/prompts"
    
    async with httpx.AsyncClient() as client:
        # 1. Buscar todos os prompts
        print(f"Buscando todos os prompts de {url_prompts}...")
        resp_prompts = await client.get(url_prompts, params={"limit": 500}, timeout=30.0)
        resp_prompts.raise_for_status()
        prompts = resp_prompts.json()
        print(f"Encontrados {len(prompts)} prompts.")

        # 2. Para cada prompt, buscar seus exemplos em paralelo
        tarefas_exemplos = []
        for p in prompts:
            if p.get("ativo"):
                url_exemplos = f"{API_NEGOCIO_URL}/admin/prompts/{p['id']}/exemplos/ativos"
                tarefas_exemplos.append(client.get(url_exemplos, timeout=10.0))

        if not tarefas_exemplos:
            return []

        print(f"Buscando exemplos para {len(tarefas_exemplos)} prompts ativos...")
        respostas_exemplos = await asyncio.gather(*tarefas_exemplos, return_exceptions=True)

        # 3. Combinar os resultados
        manifesto_final = []
        prompts_ativos = [p for p in prompts if p.get("ativo")]

        for i, p in enumerate(prompts_ativos):
            resposta = respostas_exemplos[i]
            if isinstance(resposta, httpx.Response) and resposta.status_code == 200:
                p['examples'] = resposta.json()
            else:
                p['examples'] = [] # Garante que a chave 'examples' sempre exista
            manifesto_final.append(p)
            
    return manifesto_final