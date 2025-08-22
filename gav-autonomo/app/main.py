# arquivo: main.py

from fastapi import FastAPI, Request
from app.servicos.executor_regras import executar_regras_do_manifesto

app = FastAPI()

@app.get("/ping")
async def ping():
    return {"status": "ok"}

@app.post("/chat")
async def receber_mensagem(request: Request):
    dados = await request.json()
    mensagem = dados.get("mensagem", "")
    saida = executar_regras_do_manifesto(mensagem)
    return {"conteudo_markdown": "Tudo certo!", "dados_da_busca": saida}
