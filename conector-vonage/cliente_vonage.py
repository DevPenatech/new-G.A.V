# file: conector-vonage/cliente_vonage.py
"""
Cliente Vonage unificado (Sandbox & Produção) para envio de WhatsApp (Messages API).

- SANDBOX:
    * Endpoint: https://messages-sandbox.nexmo.com/v1/messages
    * Auth: Basic (API_KEY + API_SECRET)
    * FROM fixo do sandbox (ex.: 14157386102)
    * Apenas números verificados no painel do sandbox recebem mensagem.

- PRODUÇÃO:
    * Auth: JWT (application_id + private.key)
    * FROM deve ser o número WhatsApp Business APROVADO na MESMA Application
      do application_id.
    * Inbound (webhooks) funciona apenas em produção.

Variáveis de ambiente aceitas:

  VONAGE_MODE                = "sandbox" | "prod"           (default: "prod")
  VONAGE_API_KEY             = sua API key                  (sandbox ou fallback prod)
  VONAGE_API_SECRET          = seu API secret               (sandbox ou fallback prod)
  VONAGE_APPLICATION_ID      = application id (prod)
  VONAGE_PRIVATE_KEY_PATH    = caminho do private.key (prod; ex.: /run/secrets/vonage_private_key)
  VONAGE_WHATSAPP_NUMBER     = remetente WhatsApp PRODUÇÃO (somente dígitos; ex.: 55DDDNÚMERO)
  VONAGE_SANDBOX_FROM        = remetente SANDBOX (ex.: 14157386102)
  VONAGE_SANDBOX_ENDPOINT    = URL do sandbox (default oficial)
  VONAGE_TIMEOUT_SECONDS     = timeout HTTP (default 30)

Uso típico:

    from cliente_vonage import ClienteVonage

    cliente = ClienteVonage()  # lê env
    await cliente.send_text_whatsapp(to="+55SEUNUMERO", text="Olá!")

Observações:
- Este módulo retorna dicionários simples com {"ok": bool, ...} e lança
  ValueError para entradas inválidas.
- Para produção com SDK, o envio é feito em thread (to_thread.run_sync) para
  não bloquear o event loop.
"""

from __future__ import annotations

import os
import logging
from typing import Optional, Dict, Any

import httpx
from anyio import to_thread

# O SDK oficial usa Pydantic v1; garanta pydantic==1.10.x no ambiente
import vonage


logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)


DEFAULT_SANDBOX_ENDPOINT = "https://messages-sandbox.nexmo.com/v1/messages"


def _so_digitos(s: Optional[str]) -> str:
    return "".join(ch for ch in (s or "") if ch.isdigit())


def _ler_chave_privada(path: str) -> str:
    with open(path, "rb") as f:
        data = f.read()
    # Remove espaços e normaliza finais de linha que às vezes vêm do Windows
    return data.decode("utf-8").strip()


class ClienteVonage:
    def __init__(
        self,
        mode: Optional[str] = None,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        application_id: Optional[str] = None,
        private_key_path: Optional[str] = None,
        whatsapp_from_prod: Optional[str] = None,
        sandbox_from: Optional[str] = None,
        sandbox_endpoint: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
    ) -> None:
        # Config via parâmetros ou ENV
        self.mode = (mode or os.getenv("VONAGE_MODE") or "prod").lower()
        self.api_key = api_key or os.getenv("VONAGE_API_KEY") or ""
        self.api_secret = api_secret or os.getenv("VONAGE_API_SECRET") or ""
        self.application_id = application_id or os.getenv("VONAGE_APPLICATION_ID") or ""
        self.private_key_path = private_key_path or os.getenv("VONAGE_PRIVATE_KEY_PATH") or ""
        self.whatsapp_from_prod = whatsapp_from_prod or os.getenv("VONAGE_WHATSAPP_NUMBER") or ""
        self.sandbox_from = sandbox_from or os.getenv("VONAGE_SANDBOX_FROM") or "14157386102"
        self.sandbox_endpoint = sandbox_endpoint or os.getenv("VONAGE_SANDBOX_ENDPOINT") or DEFAULT_SANDBOX_ENDPOINT
        self.timeout_seconds = int(timeout_seconds or os.getenv("VONAGE_TIMEOUT_SECONDS") or 30)

        # Estado interno (preguiçoso)
        self._vonage_client: Optional[vonage.Client] = None
        self._private_key_contents: Optional[str] = None

        if self.mode not in ("sandbox", "prod"):
            raise ValueError('VONAGE_MODE deve ser "sandbox" ou "prod"')

        logger.info(
            "ClienteVonage inicializado: mode=%s, sandbox_endpoint=%s, app_id=%s",
            self.mode,
            self.sandbox_endpoint if self.mode == "sandbox" else "-",
            (self.application_id[:8] + "…") if self.application_id else "-",
        )

    # ----------------------- validações básicas -----------------------

    def _validar_from(self, override_from: Optional[str] = None) -> str:
        """
        Retorna o 'from' sanitizado (apenas dígitos) conforme modo.
        - sandbox: usa override ou VONAGE_SANDBOX_FROM
        - prod:    usa override ou VONAGE_WHATSAPP_NUMBER
        """
        if self.mode == "sandbox":
            numero = _so_digitos(override_from or self.sandbox_from)
            if not numero:
                raise ValueError("SANDBOX_FROM não configurado.")
            return numero

        # produção
        numero = _so_digitos(override_from or self.whatsapp_from_prod)
        if not numero:
            raise ValueError("VONAGE_WHATSAPP_NUMBER não configurado.")
        if not (10 <= len(numero) <= 15):
            raise ValueError(f"VONAGE_WHATSAPP_NUMBER inválido: {numero}")
        return numero

    @staticmethod
    def _validar_to(to: Optional[str]) -> str:
        numero = _so_digitos(to)
        if not numero:
            raise ValueError('Campo "to" ausente ou inválido.')
        if not (10 <= len(numero) <= 15):
            raise ValueError(f'Campo "to" inválido: {numero}')
        return numero

    @staticmethod
    def _validar_text(text: Optional[str]) -> str:
        text = (text or "").strip()
        if not text:
            raise ValueError('Campo "text" ausente ou vazio.')
        return text

    # ----------------------- inicialização do SDK (prod) -----------------------

    def _get_or_create_vonage_client(self) -> vonage.Client:
        if self._vonage_client is not None:
            return self._vonage_client

        if self.mode == "sandbox":
            # No sandbox não usamos o SDK para enviar
            raise RuntimeError("SDK não é usado em modo sandbox.")

        # Produção: prioridade ao JWT de Application
        if self.application_id and self.private_key_path and os.path.exists(self.private_key_path):
            try:
                if self._private_key_contents is None:
                    self._private_key_contents = _ler_chave_privada(self.private_key_path)
                self._vonage_client = vonage.Client(
                    application_id=self.application_id,
                    private_key=self._private_key_contents,
                )
                return self._vonage_client
            except Exception as e:
                logger.exception("Falha ao inicializar Vonage Client (JWT).")
                raise RuntimeError(f"Erro na chave privada/JWT: {e}") from e

        # Fallback: API key/secret (alguns recursos limitados)
        if self.api_key and self.api_secret:
            self._vonage_client = vonage.Client(key=self.api_key, secret=self.api_secret)
            return self._vonage_client

        raise RuntimeError(
            "Credenciais de produção ausentes: configure APPLICATION_ID + PRIVATE_KEY_PATH "
            "ou API_KEY + API_SECRET."
        )

    # ----------------------- envio -----------------------

    async def send_text_whatsapp(
        self,
        to: str,
        text: str,
        from_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Envia texto WhatsApp via Messages API (sandbox ou produção, conforme VONAGE_MODE).

        Returns:
            {"ok": True, "mode": "sandbox"|"prod", "to": "...", "from": "...", "response": <obj>}
        Raises:
            ValueError em parâmetros inválidos
            RuntimeError se credenciais/config estiverem incorretas
        """
        to_num = self._validar_to(to)
        text_ok = self._validar_text(text)
        from_num = self._validar_from(from_override)

        if self.mode == "sandbox":
            # Envio direto no endpoint do sandbox (Basic Auth)
            auth_key = self.api_key or ""
            auth_secret = self.api_secret or ""
            if not auth_key or not auth_secret:
                raise RuntimeError("API_KEY/API_SECRET são obrigatórios no sandbox.")

            payload = {
                "from": from_num,
                "to": to_num,
                "message_type": "text",
                "text": text_ok,
                "channel": "whatsapp",
            }

            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                r = await client.post(
                    self.sandbox_endpoint,
                    auth=(auth_key, auth_secret),
                    json=payload,
                    headers={"Content-Type": "application/json", "Accept": "application/json"},
                )
            if r.status_code >= 400:
                logger.warning("Sandbox 4xx/5xx: %s %s", r.status_code, r.text)
                return {
                    "ok": False,
                    "mode": "sandbox",
                    "to": to_num,
                    "from": from_num,
                    "status_code": r.status_code,
                    "error": r.text,
                }
            try:
                body = r.json()
            except Exception:
                body = {"raw": r.text}
            return {"ok": True, "mode": "sandbox", "to": to_num, "from": from_num, "response": body}

        # PRODUÇÃO (SDK + JWT)
        client = self._get_or_create_vonage_client()
        payload = {
            "channel": "whatsapp",
            "message_type": "text",
            "to": to_num,
            "from": from_num,
            "text": text_ok,
        }

        def _send_sync() -> Dict[str, Any]:
            try:
                # O SDK faz a chamada síncrona; rodamos em thread
                resp = client.messages.send_message(payload)  # type: ignore[attr-defined]
                # O SDK retorna None quando 2xx, e lança em 4xx/5xx; padronizamos:
                return {"ok": True, "response": resp}
            except vonage.errors.ClientError as e:  # 4xx da Vonage
                logger.warning("Vonage 4xx: %s", str(e))
                return {"ok": False, "error": str(e), "status": 422}
            except Exception as e:
                logger.exception("Erro inesperado no envio (prod).")
                return {"ok": False, "error": str(e), "status": 500}

        result = await to_thread.run_sync(_send_sync)
        result.update({"mode": "prod", "to": to_num, "from": from_num})
        return result

    # ----------------------- health -----------------------

    def health(self) -> Dict[str, Any]:
        """
        Retorna um snapshot simples de saúde/config (sem expor segredos).
        """
        try:
            from_mask = self._validar_from()[-4:]
        except Exception as e:
            from_mask = f"ERRO:{e}"

        data: Dict[str, Any] = {
            "ok": True,
            "mode": self.mode,
            "from": from_mask,
            "timeout": self.timeout_seconds,
        }
        if self.mode == "sandbox":
            data["sandbox_endpoint"] = self.sandbox_endpoint
            data["api_key_configured"] = bool(self.api_key)
        else:
            data["app_id_configured"] = bool(self.application_id)
            data["private_key_exists"] = bool(self.private_key_path and os.path.exists(self.private_key_path))
        return data


# CLI rápido para teste manual: python cliente_vonage.py 55DDDNUM "mensagem"
if __name__ == "__main__":
    import sys
    import asyncio

    if len(sys.argv) < 3:
        print("Uso: python cliente_vonage.py <to:55DDDNUMERO> <mensagem> [from_override]")
        raise SystemExit(2)

    to_arg = sys.argv[1]
    text_arg = sys.argv[2]
    from_arg = sys.argv[3] if len(sys.argv) > 3 else None

    async def _run():
        cliente = ClienteVonage()
        print("HEALTH:", cliente.health())
        resp = await cliente.send_text_whatsapp(to=to_arg, text=text_arg, from_override=from_arg)
        print("RESP:", resp)

    asyncio.run(_run())
