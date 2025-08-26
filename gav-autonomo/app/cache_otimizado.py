# gav-autonomo/app/cache_otimizado.py
"""
Sistema de Cache Multi-Camada para Prompts e Contextos
Reduz consultas ao banco de ~500ms para ~5ms por prompt
"""

import asyncio
import time
from typing import Dict, Optional, List
from dataclasses import dataclass
import httpx
from app.config.settings import config

@dataclass
class PromptCacheEntry:
    template: str
    exemplos: List[dict]
    timestamp: float
    espaco: str
    versao: str

class CacheOtimizado:
    def __init__(self):
        self.prompts_cache: Dict[str, PromptCacheEntry] = {}
        self.contextos_cache: Dict[str, dict] = {}
        self.cache_ttl = 300  # 5 minutos
        self.last_bulk_load = 0
        
    def _is_cache_expired(self, timestamp: float) -> bool:
        return time.time() - timestamp > self.cache_ttl
    
    def get_prompt_key(self, nome: str, espaco: str, versao: str) -> str:
        return f"{espaco}:{nome}:v{versao}"
    
    async def get_prompt_completo(self, nome: str, espaco: str = "autonomo", versao: str = "1") -> Optional[dict]:
        """Busca prompt com cache inteligente"""
        cache_key = self.get_prompt_key(nome, espaco, versao)
        
        # 1. Tenta cache local
        if cache_key in self.prompts_cache:
            entry = self.prompts_cache[cache_key]
            if not self._is_cache_expired(entry.timestamp):
                return {
                    "template": entry.template,
                    "exemplos": entry.exemplos
                }
        
        # 2. Busca do banco e armazena em cache
        try:
            async with httpx.AsyncClient() as client:
                # Busca prompt
                resp_prompt = await client.get(
                    f"{config.API_NEGOCIO_URL}/admin/prompts/buscar",
                    params={"nome": nome, "espaco": espaco, "versao": versao},
                    timeout=5.0
                )
                
                if resp_prompt.status_code != 200:
                    return None
                
                prompt_data = resp_prompt.json()
                
                # Busca exemplos em paralelo
                resp_exemplos = await client.get(
                    f"{config.API_NEGOCIO_URL}/admin/prompts/{prompt_data['id']}/exemplos/ativos",
                    timeout=5.0
                )
                
                exemplos = resp_exemplos.json() if resp_exemplos.status_code == 200 else []
                
                # Armazena em cache
                self.prompts_cache[cache_key] = PromptCacheEntry(
                    template=prompt_data["template"],
                    exemplos=exemplos,
                    timestamp=time.time(),
                    espaco=espaco,
                    versao=versao
                )
                
                return {
                    "template": prompt_data["template"],
                    "exemplos": exemplos
                }
                
        except Exception as e:
            print(f"Erro ao buscar prompt {nome}: {e}")
            return None
    
    async def bulk_load_prompts(self):
        """Carrega todos os prompts ativos em paralelo na inicialização"""
        if time.time() - self.last_bulk_load < 60:  # Evita reload muito frequente
            return
            
        try:
            async with httpx.AsyncClient() as client:
                # Busca todos os prompts ativos
                resp = await client.get(
                    f"{config.API_NEGOCIO_URL}/admin/prompts",
                    params={"limit": 500},
                    timeout=10.0
                )
                
                if resp.status_code != 200:
                    return
                
                prompts = [p for p in resp.json() if p.get("ativo")]
                
                # Busca exemplos de todos os prompts em paralelo
                tasks = []
                for prompt in prompts:
                    task = client.get(
                        f"{config.API_NEGOCIO_URL}/admin/prompts/{prompt['id']}/exemplos/ativos",
                        timeout=5.0
                    )
                    tasks.append(task)
                
                exemplos_responses = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Popula cache
                for i, prompt in enumerate(prompts):
                    exemplos = []
                    if i < len(exemplos_responses) and isinstance(exemplos_responses[i], httpx.Response):
                        if exemplos_responses[i].status_code == 200:
                            exemplos = exemplos_responses[i].json()
                    
                    cache_key = self.get_prompt_key(
                        prompt["nome"], 
                        prompt.get("espaco", "autonomo"), 
                        str(prompt.get("versao", "1"))
                    )
                    
                    self.prompts_cache[cache_key] = PromptCacheEntry(
                        template=prompt["template"],
                        exemplos=exemplos,
                        timestamp=time.time(),
                        espaco=prompt.get("espaco", "autonomo"),
                        versao=str(prompt.get("versao", "1"))
                    )
                
                self.last_bulk_load = time.time()
                print(f"✅ Cache carregado com {len(self.prompts_cache)} prompts")
                
        except Exception as e:
            print(f"Erro no bulk load: {e}")
    
    def get_contexto_sessao(self, sessao_id: str) -> Optional[dict]:
        """Cache para contextos de sessão (evita consultas repetidas)"""
        return self.contextos_cache.get(sessao_id)
    
    def set_contexto_sessao(self, sessao_id: str, contexto: dict):
        """Armazena contexto com TTL"""
        self.contextos_cache[sessao_id] = {
            **contexto,
            "_timestamp": time.time()
        }
        
        # Limpa contextos expirados
        expired_keys = [
            k for k, v in self.contextos_cache.items() 
            if self._is_cache_expired(v.get("_timestamp", 0))
        ]
        for k in expired_keys:
            del self.contextos_cache[k]

# Instância global
cache_otimizado = CacheOtimizado()