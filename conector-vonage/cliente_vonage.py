# SANDBOX-ONLY: WhatsApp via Vonage Messages Sandbox (Basic Auth).
# Sem PEM, sem Application ID, sem modos.
from __future__ import annotations
import os
from typing import Optional, Dict, Any
import httpx

VONAGE_API_KEY = (os.getenv("VONAGE_API_KEY") or "").strip()
VONAGE_API_SECRET = (os.getenv("VONAGE_API_SECRET") or "").strip()
SANDBOX_FROM = (os.getenv("VONAGE_SANDBOX_FROM") or "14157386102").strip()
SANDBOX_ENDPOINT = (os.getenv("VONAGE_SANDBOX_ENDPOINT") or "https://messages-sandbox.nexmo.com/v1/messages").strip()
TIMEOUT = int(os.getenv("VONAGE_TIMEOUT_SECONDS") or "30")

def _digits(s: Optional[str]) -> str:
    return "".join(ch for ch in (s or "") if ch.isdigit())

def _normalize_whatsapp_text(s: str) -> str:
    # converte texto "\n" literal em quebras reais
    s = s.replace("\\n", "\n")
    # remove escapes residuais comuns
    s = s.replace("\\t", "\t").replace('\\"', '"')
    # compacta espaços duplicados
    while "  " in s:
        s = s.replace("  ", " ")
    return s.strip()

def _validate_to(to: Optional[str]) -> str:
    n = _digits(to)
    if not n or not (10 <= len(n) <= 15):
        raise ValueError('Campo "to" ausente/inválido (use E.164 sem +).')
    return n

def _validate_text(text: Optional[str]) -> str:
    t = (text or "").strip()
    if not t:
        raise ValueError('Campo "text" ausente ou vazio.')
    return t

def _validate_from(f: Optional[str]) -> str:
    n = _digits(f or SANDBOX_FROM)
    if not n:
        raise ValueError("VONAGE_SANDBOX_FROM não configurado.")
    return n

async def send_text_whatsapp(to: str, text: str, from_override: Optional[str] = None) -> Dict[str, Any]:
    if not VONAGE_API_KEY or not VONAGE_API_SECRET:
        raise RuntimeError("Configure VONAGE_API_KEY e VONAGE_API_SECRET (sandbox).")

    to_num = _validate_to(to)
    txt = _validate_text(_normalize_whatsapp_text(text))
    frm = _validate_from(from_override)

    payload = {
        "from": frm,
        "to": to_num,
        "message_type": "text",
        "text": txt,
        "channel": "whatsapp",
    }

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        r = await client.post(
            SANDBOX_ENDPOINT,
            auth=(VONAGE_API_KEY, VONAGE_API_SECRET),
            json=payload,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
    if r.status_code >= 400:
        return {"ok": False, "status": r.status_code, "error": r.text}
    try:
        body = r.json()
    except Exception:
        body = {"raw": r.text}
    return {"ok": True, "to": to_num, "from": frm, "response": body}

def health() -> Dict[str, Any]:
    errs = []
    if not VONAGE_API_KEY: errs.append("VONAGE_API_KEY ausente")
    if not VONAGE_API_SECRET: errs.append("VONAGE_API_SECRET ausente")
    return {
        "ok": len(errs) == 0,
        "mode": "sandbox",
        "from": (SANDBOX_FROM[-4:] if SANDBOX_FROM else ""),
        "endpoint": SANDBOX_ENDPOINT,
        "errors": errs,
    }
