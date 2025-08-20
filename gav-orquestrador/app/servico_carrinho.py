# gav-orquestrador/app/servico_carrinho.py

import httpx
from fastapi import HTTPException
from .config import settings


def _formata_valor(valor: float) -> str:
    return f"{valor:.2f}".replace('.', ',')

async def ver_carrinho(sessao_id: str) -> dict:
    url_base = f"{settings.API_NEGOCIO_URL}/carrinhos/{sessao_id}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(url_base)
            resp.raise_for_status()
            dados = resp.json()
            itens = dados.get("itens", []) if isinstance(dados, dict) else dados
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                resp = await client.get(f"{url_base}/itens")
                resp.raise_for_status()
                dados = resp.json()
                if isinstance(dados, dict):
                    itens = dados.get("itens", [])
                else:
                    itens = dados
            else:
                raise HTTPException(status_code=exc.response.status_code, detail="Erro ao buscar carrinho")
    if not itens:
        return {"resposta": "Seu carrinho está vazio."}
    linhas = []
    total_geral = 0.0
    for item in itens:
        nome = item.get("nome") or item.get("descricao") or "Item"
        quantidade = item.get("quantidade", 0)
        total_item = item.get("total")
        if total_item is None:
            pvenda = item.get("pvenda") or 0
            total_item = pvenda * quantidade
        total_geral += total_item
        linhas.append(f"{quantidade}x {nome} — R$ {_formata_valor(total_item)}")
    linhas.append(f"Total: R$ {_formata_valor(total_geral)}")
    return {"resposta": "\n".join(linhas)}

