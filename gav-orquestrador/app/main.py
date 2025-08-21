# gav-orquestrador/app/main.py

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from . import servicos, esquemas

app = FastAPI(
    title="G.A.V. - Orquestrador de IA",
    version="1.0.0"
)

# 2. Adicione o bloco de configuração do CORS
origins = [
    "http://localhost",
    "http://localhost:3000", # Adicione a porta em que seu React está rodando, se for diferente
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Permite todos os métodos (GET, POST, OPTIONS, etc)
    allow_headers=["*"], # Permite todos os cabeçalhos
)

# ... (healthcheck continua o mesmo) ...
@app.get("/healthcheck", tags=["Monitoring"])
def health_check():
    return {"status": "ok", "service": "G.A.V. Orquestrador"}


@app.post("/chat", tags=["Chat (Legado)"])
async def post_chat(mensagem: esquemas.MensagemChat):
    try:
        resultado_final = await servicos.orquestrar_chat(mensagem)
        return resultado_final
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/webhook/webchat", response_model=esquemas.RespostaWebchat, tags=["Canais"])
async def webhook_webchat(mensagem: esquemas.MensagemChat):
    """
    Endpoint adaptador para o canal de Webchat.
    Recebe uma mensagem, orquestra a resposta e a formata para o cliente de webchat.
    """
    try:
        resultado_interno = await servicos.orquestrar_chat(mensagem)
        return esquemas.RespostaWebchat(
            conteudo_markdown=resultado_interno.get("resposta", ""),
            dados_da_busca=resultado_interno.get("dados_da_busca")
        )
    except Exception:
        # [NOVO BLOCO DE LOG] - Captura e loga a exceção completa com traceback
        # para sabermos exatamente onde e por que o erro está acontecendo.
        import traceback
        tb_str = traceback.format_exc()
        print(f"ERRO CRÍTICO NO ORQUESTRADOR: {tb_str}")
        # Mantém o erro 500, mas agora teremos o log completo para análise.
        # Em um cenário real, teríamos um tratamento de erro mais granular aqui.
        raise HTTPException(status_code=500, detail="Ocorreu um erro interno no orquestrador.")
 

@app.post("/webhook/whatsapp", response_model=esquemas.RespostaWhatsapp, tags=["Canais"])
async def webhook_whatsapp(mensagem: esquemas.MensagemWhatsapp):
    """
    Endpoint adaptador para o canal WhatsApp.
    Mapeia o ID do WhatsApp para a ID da sessão e formata a resposta como texto simples.
    """
    try:
        # Converte o schema do WhatsApp para o schema interno do chat
        mensagem_interna = esquemas.MensagemChat(
            sessao_id=mensagem.wa_id, # O ID do WhatsApp define a sessão
            texto=mensagem.texto
        )
        resultado_interno = await servicos.orquestrar_chat(mensagem_interna)
        return esquemas.RespostaWhatsapp(texto=resultado_interno.get("resposta", ""))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/feedback/report", tags=["Feedback"])
async def post_feedback(feedback: esquemas.Feedback):
    try:
        resultado = await servicos.salvar_feedback(feedback)
        return resultado
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))