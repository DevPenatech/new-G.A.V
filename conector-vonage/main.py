# topo do arquivo
import os, time, hashlib, httpx
from typing import Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from cliente_vonage import send_text_whatsapp, health as sandbox_health

CHAT_URL = os.getenv("CHAT_URL", "http://gav_autonomo:8000/chat").strip()
TIMEOUT_CHAT = int(os.getenv("CHAT_TIMEOUT_SECONDS") or "60")
SANDBOX_FROM = "".join(ch for ch in (os.getenv("VONAGE_SANDBOX_FROM") or "") if ch.isdigit())

# memoria de curto prazo para idempotência (5 min)
_RECENT: dict[str, float] = {}
_TTL = 300.0  # segundos

def _digits(s: Optional[str]) -> str:
    return "".join(ch for ch in (s or "") if ch.isdigit())

def _gc_recent(now: float):
    # limpa chaves antigas
    dead = [k for k, t in _RECENT.items() if now - t > _TTL]
    for k in dead:
        _RECENT.pop(k, None)

def _mk_id(message_uuid: Optional[str], numero: str, texto: str, ts: Optional[str]) -> str:
    if message_uuid:
        return f"uuid:{message_uuid}"
    h = hashlib.sha1(f"{numero}|{texto}|{ts or ''}".encode("utf-8")).hexdigest()
    return f"hash:{h}"

async def _call_chat(texto: str, sessao_id: str) -> str:
    payload = {"texto": texto, "sessao_id": sessao_id}
    async with httpx.AsyncClient(timeout=TIMEOUT_CHAT) as client:
        r = await client.post(CHAT_URL, json=payload)
        r.raise_for_status()
        try:
            data = r.json()
        except Exception:
            data = {}
    return str(data.get("mensagem") or "") or "(sem resposta do /chat)"

def _extract_inbound(body: dict) -> tuple[str, str, Optional[str], Optional[str]]:
    """
    Retorna (numero, texto, message_uuid, timestamp)
    Suporta formato simples e Messages API.
    """
    # formato simples {from: "55...", text: "..."}
    if "text" in body and isinstance(body.get("from"), (str, int)):
        numero = _digits(str(body.get("from")))
        texto = str(body.get("text") or "")
        message_uuid = body.get("message_uuid") or body.get("id")
        ts = body.get("timestamp") or body.get("time")
        return numero, texto, message_uuid, ts

    # Messages API
    numero = _digits(((body.get("from") or {}).get("number") or ""))
    content = ((body.get("message") or {}).get("content") or {})
    texto = content.get("text") if content.get("type") == "text" else ""
    message_uuid = body.get("message_uuid") or body.get("uuid") or body.get("id")
    ts = body.get("timestamp") or body.get("received_time") or body.get("time")
    return numero, str(texto or ""), message_uuid, ts

app = FastAPI(title="conector-vonage-sandbox")

@app.get("/healthz")
async def healthz():
    h = sandbox_health()
    h["chat_url"] = CHAT_URL
    h["dedupe_size"] = len(_RECENT)
    return h

@app.post("/webhooks/inbound")
async def inbound_vonage(request: Request):
    body = await request.json()
    numero, texto, message_uuid, ts = _extract_inbound(body)

    # ignora eco (mensagens vindas do próprio remetente sandbox)
    if SANDBOX_FROM and numero == SANDBOX_FROM:
        return JSONResponse({"ok": True, "ignored": "self-message"})

    # idempotência
    now = time.time()
    _gc_recent(now)
    msg_id = _mk_id(message_uuid, numero, texto, ts)
    if msg_id in _RECENT:
        return JSONResponse({"ok": True, "ignored": "duplicate"})
    _RECENT[msg_id] = now

    # processa
    if not numero:
        return JSONResponse({"ok": True, "warn": "sem numero remetente"}, status_code=200)

    resposta = await _call_chat(texto, numero)
    envio = await send_text_whatsapp(to=numero, text=resposta)
    if not envio.get("ok"):
        raise HTTPException(status_code=envio.get("status", 400), detail=envio)
    return JSONResponse({"ok": True})

# mantém também o /inbound manual para testes locais
@app.post("/inbound")
async def inbound_local(payload: dict):
    numero, texto, message_uuid, ts = _extract_inbound(payload)

    if SANDBOX_FROM and numero == SANDBOX_FROM:
        return {"ok": True, "ignored": "self-message"}

    now = time.time(); _gc_recent(now)
    msg_id = _mk_id(message_uuid, numero, texto, ts)
    if msg_id in _RECENT:
        return {"ok": True, "ignored": "duplicate"}
    _RECENT[msg_id] = now

    if not numero:
        raise HTTPException(status_code=400, detail='Informe "from" (E.164 sem +).')

    resposta = await _call_chat(texto, numero)
    envio = await send_text_whatsapp(to=numero, text=resposta)
    if not envio.get("ok"):
        raise HTTPException(status_code=envio.get("status", 400), detail=envio)
    return {"ok": True, "to": numero}

@app.post("/webhooks/status")
async def status_post(request: Request):
    try:
        _ = await request.json()
    except Exception:
        _ = None
    return JSONResponse({"ok": True})

@app.get("/webhooks/status")
async def status_get():
    return JSONResponse({"ok": True})
