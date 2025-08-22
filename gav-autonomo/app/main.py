from fastapi import FastAPI
from pydantic import BaseModel
from app.servicos.executor_regras import executar_regras_do_manifesto

app = FastAPI()

@app.get("/ping")
async def ping():
    return {"status": "ok"}

class EntradaChat(BaseModel):
    texto: str
    sessao_id: str

@app.post("/chat")
async def receber_mensagem(body: EntradaChat):
    saida = executar_regras_do_manifesto(body.model_dump())
    return saida