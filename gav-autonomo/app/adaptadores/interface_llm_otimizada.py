# gav-autonomo/app/adaptadores/interface_llm_otimizada.py
"""
Cliente LLM Otimizado com:
- Pool de conexões persistentes
- Timeout reduzido e streaming
- Paralelização de múltiplas chamadas
- Fallback inteligente
"""

import asyncio
import httpx
import json
import time
from typing import Optional, List, Dict
from dataclasses import dataclass
from app.config.settings import config

@dataclass
class LLMRequest:
    sistema: str
    entrada_usuario: str
    exemplos: List[dict]
    modelo: Optional[str] = None
    timeout: float = 15.0  # Reduzido de 60s para 15s

class ClienteLLMOtimizado:
    def __init__(self):
        # Pool de conexões persistente
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            http2=True  # HTTP/2 para melhor performance
        )
        self.ollama_url = config.OLLAMA_HOST.rstrip("/")
        self.modelo_padrao = config.OLLAMA_MODEL_NAME
        
        # Cache de prompts compilados (evita reprocessamento)
        self.prompts_compilados = {}
    
    def _compilar_prompt(self, request: LLMRequest) -> str:
        """Compila prompt uma vez e cacheia"""
        cache_key = hash(f"{request.sistema}{len(request.exemplos)}")
        
        if cache_key in self.prompts_compilados:
            template = self.prompts_compilados[cache_key]
            return template.replace("{ENTRADA_USUARIO}", request.entrada_usuario)
        
        # Monta template otimizado
        partes = [request.sistema.strip()]
        
        # Exemplos compactos (só os essenciais)
        for i, ex in enumerate(request.exemplos[:3]):  # Limita a 3 exemplos para velocidade
            partes.append(f"Exemplo {i+1}:")
            partes.append(f"Input: {ex.get('exemplo_input', '')}")
            partes.append(f"Output: {ex.get('exemplo_output_json', '')}")
        
        partes.append("Entrada atual: {ENTRADA_USUARIO}")
        
        template = "\n\n".join(partes)
        self.prompts_compilados[cache_key] = template
        
        return template.replace("{ENTRADA_USUARIO}", request.entrada_usuario)
    
    async def completar_para_json_async(self, request: LLMRequest) -> dict:
        """Versão assíncrona otimizada"""
        prompt_texto = self._compilar_prompt(request)
        
        payload = {
            "model": request.modelo or self.modelo_padrao,
            "prompt": prompt_texto,
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.1,
                "top_p": 0.9,
                "num_predict": 1000,  # Limita tokens para velocidade
                "stop": ["\n\n", "```"]  # Para mais cedo quando possível
            }
        }
        
        try:
            resp = await self.client.post(
                f"{self.ollama_url}/api/generate",
                json=payload,
                timeout=request.timeout
            )
            
            resp.raise_for_status()
            data = resp.json()
            
            conteudo = data.get("response") or data.get("output") or ""
            
            # Parse JSON otimizado
            try:
                # Remove possíveis caracteres extras
                conteudo_limpo = conteudo.strip()
                if conteudo_limpo.startswith("```json"):
                    conteudo_limpo = conteudo_limpo[7:]
                if conteudo_limpo.endswith("```"):
                    conteudo_limpo = conteudo_limpo[:-3]
                
                return json.loads(conteudo_limpo.strip())
            
            except json.JSONDecodeError as e:
                print(f"⚠️ JSON inválido do LLM: {conteudo[:200]}...")
                # Fallback: tenta extrair JSON do meio da resposta
                import re
                json_match = re.search(r'\{.*\}', conteudo, re.DOTALL)
                if json_match:
                    try:
                        return json.loads(json_match.group())
                    except:
                        pass
                
                # Último recurso: resposta estruturada mínima
                return {"erro": "json_parse_failed", "conteudo_original": conteudo}
        
        except asyncio.TimeoutError:
            return {"erro": "llm_timeout", "detalhes": f"Timeout após {request.timeout}s"}
        except Exception as e:
            return {"erro": "llm_error", "detalhes": str(e)}
    
    async def processar_multiplas_chamadas(self, requests: List[LLMRequest]) -> List[dict]:
        """Processa múltiplas chamadas LLM em paralelo"""
        tasks = [self.completar_para_json_async(req) for req in requests]
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    def completar_para_json_sync(self, sistema: str, entrada_usuario: str, 
                                exemplos: List[dict] = None, modelo: str = None) -> dict:
        """Wrapper síncrono para compatibilidade"""
        request = LLMRequest(
            sistema=sistema,
            entrada_usuario=entrada_usuario,
            exemplos=exemplos or [],
            modelo=modelo
        )
        
        loop = None
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self.completar_para_json_async(request))
    
    async def close(self):
        """Fecha conexões limpamente"""
        await self.client.aclose()

# Instância global
cliente_llm = ClienteLLMOtimizado()

# Wrapper para compatibilidade com código existente
def completar_para_json(sistema: str, entrada_usuario: str, exemplos: list = None, modelo: str = None) -> dict:
    return cliente_llm.completar_para_json_sync(sistema, entrada_usuario, exemplos, modelo)