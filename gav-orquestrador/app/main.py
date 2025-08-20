# gav-orquestrador/app/main.py

from fastapi import FastAPI, HTTPException
from . import servicos, esquemas

app = FastAPI(
    title="G.A.V. - Orquestrador de IA",
    version="1.0.0"
)

# ... (healthcheck continua o mesmo) ...
@app.get("/healthcheck", tags=["Monitoring"])
def health_check():
    return {"status": "ok", "service": "G.A.V. Orquestrador"}


@app.post("/chat", tags=["Chat"])
async def post_chat(mensagem: esquemas.MensagemChat):
    try:
        resultado_final = await servicos.orquestrar_chat(mensagem)
        return resultado_final
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/feedback/report", tags=["Feedback"])
async def post_feedback(feedback: esquemas.Feedback):
    try:
        resultado = await servicos.salvar_feedback(feedback)
        return resultado
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))