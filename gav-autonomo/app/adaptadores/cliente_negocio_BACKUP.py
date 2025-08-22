from app.config.settings import config
import httpx
from typing import Optional, Dict, Any

API_NEGOCIO_URL = config.API_NEGOCIO_URL.rstrip("/")

def chamar_api(endpoint: str, method: str = "POST",
               payload: Optional[Dict[str, Any]] = None,
               headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """
    Chamador genérico de APIs da api-negocio.
    endpoint: caminho (ex.: '/produtos/busca' ou 'carrinhos/{sessao_id}')
    method:   GET|POST|PUT|PATCH|DELETE
    payload:  params (GET) ou JSON (demais)
    """
    if not endpoint.startswith("/"):
        endpoint = "/" + endpoint
    url = f"{API_NEGOCIO_URL}{endpoint}"
    method = method.upper()
    try:
        if method == "GET":
            resp = httpx.get(url, params=payload or {}, headers=headers, timeout=30)
        else:
            resp = httpx.request(method, url, json=payload or {}, headers=headers, timeout=30)
        if resp.status_code >= 400:
            return {"erro": "api_call_failed", "status_code": resp.status_code,
                    "endpoint": endpoint, "body": _safe_text(resp)}
        return resp.json()
    except httpx.RequestError as e:
        return {"erro": "api_unreachable", "detalhe": str(e), "endpoint": endpoint}

def _safe_text(response: httpx.Response) -> str:
    try:
        return response.text[:2000]
    except Exception:
        return "<sem corpo>"
