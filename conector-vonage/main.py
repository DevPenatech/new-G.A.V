# file: conector-vonage/main.py
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import os
import httpx

app = FastAPI(title="conector-vonage-sandbox")

VONAGE_API_KEY = os.getenv("VONAGE_API_KEY", "").strip()
VONAGE_API_SECRET = os.getenv("VONAGE_API_SECRET", "").strip()
SANDBOX_FROM = os.getenv("VONAGE_SANDBOX_FROM", "14157386102").strip()
SANDBOX_ENDPOINT = os.getenv("VONAGE_SANDBOX_ENDPOINT", "https://messages-sandbox.nexmo.com/v1/messages").strip()
TIMEOUT = int(os.getenv("VONAGE_TIMEOUT_SECONDS", "30"))

def so_digitos(s: str | None) -> str:
    return "".join(ch for ch in (s or "") if ch.isdigit())

@app.get("/healthz")
async def healthz():
    errors = []
    if not VONAGE_API_KEY:
        errors.append("VONAGE_API_KEY ausente")
    if not VONAGE_API_SECRET:
        errors.append("VONAGE_API_SECRET ausente")
    return {
        "ok": len(errors) == 0,
        "mode": "sandbox",
        "from": SANDBOX_FROM[-4:],
        "endpoint": SANDBOX_ENDPOINT,
        "errors": errors,
    }

@app.post("/send")
async def send(payload: dict):
    # payload: { "to": "55DDDNUMERO", "text": "mensagem" }
    to = so_digitos(payload.get("to"))
    text = (payload.get("text") or "").strip()

    if not VONAGE_API_KEY or not VONAGE_API_SECRET:
        raise HTTPException(status_code=500, detail="Configure VONAGE_API_KEY e VONAGE_API_SECRET (sandbox).")
    if not to or len(to) < 10 or len(to) > 15:
        raise HTTPException(status_code=400, detail='Campo "to" ausente ou inválido (use E.164 sem +).')
    if not text:
        raise HTTPException(status_code=400, detail='Campo "text" ausente ou vazio.')

    payload_out = {
        "from": so_digitos(SANDBOX_FROM),
        "to": to,
        "message_type": "text",
        "text": text,
        "channel": "whatsapp",
    }

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        r = await client.post(
            SANDBOX_ENDPOINT,
            auth=(VONAGE_API_KEY, VONAGE_API_SECRET),  # Basic Auth (sandbox)
            json=payload_out,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )

    if r.status_code >= 400:
        # devolve o erro do sandbox na lata (geralmente "número não verificado" ou credenciais inválidas)
        raise HTTPException(status_code=r.status_code, detail=r.text)

    try:
        body = r.json()
    except Exception:
        body = {"raw": r.text}

    return {"ok": True, "mode": "sandbox", "to": to, "from": payload_out["from"], "response": body}
