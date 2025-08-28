# gav-autonomo/app/servicos/hash_query_manager.py
"""
Gerenciador de Hash Query para deduplicação de contextos
"""

import hashlib
import re
import httpx
from typing import Optional, List, Dict
from app.config.settings import config

API_NEGOCIO_URL = config.API_NEGOCIO_URL.rstrip("/")

def gerar_hash_query(query: str) -> str:
    """
    Gera hash MD5 normalizado de uma query para deduplicação
    
    Normalização:
    - Remove espaços extras
    - Converte para minúsculo  
    - Padroniza verbos de busca
    """
    if not query:
        return ""
    
    # Normaliza texto
    query_normalizada = query.lower().strip()
    
    # Padroniza verbos de busca
    query_normalizada = re.sub(r'\b(buscar|quero|procurar|encontrar|tem)\b', 'buscar', query_normalizada)
    
    # Remove artigos e preposições
    query_normalizada = re.sub(r'\b(o|a|os|as|um|uma|de|da|do|para|por)\b', '', query_normalizada)
    
    # Remove espaços extras
    query_normalizada = re.sub(r'\s+', ' ', query_normalizada).strip()
    
    # Gera hash MD5
    return hashlib.md5(query_normalizada.encode('utf-8')).hexdigest()

def salvar_contexto_com_hash(sessao_id: str, contexto_estruturado: dict, 
                           mensagem_original: str, resposta_apresentada: str,
                           tipo: str = "busca_numerada_rica") -> bool:
    """
    Salva contexto com deduplicação por hash
    """
    try:
        # Gera hash da query
        hash_query = gerar_hash_query(mensagem_original)
        
        print(f"   📝 Hash gerado: {hash_query[:8]}... para '{mensagem_original}'")
        
        # 1. Primeiro deduplica contextos existentes
        deduplicar_contextos_existentes(sessao_id, hash_query, tipo)
        
        # 2. Salva novo contexto
        payload = {
            "tipo_contexto": tipo,
            "contexto_estruturado": contexto_estruturado,
            "mensagem_original": mensagem_original,
            "resposta_apresentada": resposta_apresentada,
            "hash_query": hash_query  # Novo campo
        }
        
        response = httpx.post(f"{API_NEGOCIO_URL}/contexto/{sessao_id}", json=payload, timeout=10.0)
        
        if response.is_success:
            print(f"   ✅ Contexto salvo com hash para sessão {sessao_id}")
            
            # 3. Limpa contextos antigos (mantém apenas 5 mais recentes)
            limpar_contextos_antigos(sessao_id, tipo)
            
            return True
        else:
            print(f"   ❌ Erro ao salvar contexto: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"   ❌ Erro ao salvar contexto com hash: {e}")
        return False

def deduplicar_contextos_existentes(sessao_id: str, hash_query: str, tipo_contexto: str):
    """
    Desativa contextos duplicados com mesmo hash, mantendo apenas o mais recente
    """
    try:
        # Chama função do banco para deduplicar
        response = httpx.post(
            f"{API_NEGOCIO_URL}/admin/contextos/deduplicar",
            json={
                "sessao_id": sessao_id,
                "hash_query": hash_query,
                "tipo_contexto": tipo_contexto
            },
            timeout=5.0
        )
        
        if response.is_success:
            data = response.json()
            removidos = data.get("contextos_removidos", 0)
            if removidos > 0:
                print(f"   🔄 Deduplicados {removidos} contextos duplicados")
        
    except Exception as e:
        print(f"   ⚠️ Erro na deduplicação: {e}")

def limpar_contextos_antigos(sessao_id: str, tipo_contexto: str, limite: int = 5):
    """
    Limpa contextos antigos, mantendo apenas os N mais recentes
    """
    try:
        response = httpx.post(
            f"{API_NEGOCIO_URL}/admin/contextos/limpar",
            json={
                "sessao_id": sessao_id,
                "tipo_contexto": tipo_contexto,
                "limite": limite
            },
            timeout=5.0
        )
        
        if response.is_success:
            data = response.json()
            removidos = data.get("contextos_removidos", 0)
            if removidos > 0:
                print(f"   🗑️ Removidos {removidos} contextos antigos")
        
    except Exception as e:
        print(f"   ⚠️ Erro na limpeza: {e}")

def listar_contextos_recentes(sessao_id: str, limite: int = 5) -> List[Dict]:
    """
    Lista contextos de busca mais recentes para navegação
    """
    try:
        response = httpx.get(
            f"{API_NEGOCIO_URL}/admin/contextos/{sessao_id}/recentes",
            params={"limite": limite, "tipo": "busca_numerada_rica"},
            timeout=10.0
        )
        
        if response.is_success:
            contextos = response.json()
            print(f"   📋 Encontrados {len(contextos)} contextos recentes")
            return contextos
        else:
            print(f"   ❌ Erro ao listar contextos: {response.status_code}")
            return []
            
    except Exception as e:
        print(f"   ❌ Erro ao buscar contextos recentes: {e}")
        return []

def buscar_contexto_por_hash(sessao_id: str, hash_query: str) -> Optional[Dict]:
    """
    Busca contexto específico por hash (para reutilização)
    """
    try:
        response = httpx.get(
            f"{API_NEGOCIO_URL}/admin/contextos/{sessao_id}/hash/{hash_query}",
            timeout=5.0
        )
        
        if response.is_success:
            contexto = response.json()
            print(f"   ✅ Contexto encontrado por hash: {hash_query[:8]}...")
            return contexto
        else:
            return None
            
    except Exception as e:
        print(f"   ⚠️ Erro ao buscar por hash: {e}")
        return None

def formatar_lista_contextos_recentes(contextos: List[Dict]) -> str:
    """
    Formata lista de contextos recentes para apresentação ao usuário
    """
    if not contextos:
        return "Nenhuma busca anterior encontrada."
    
    linhas = ["📋 Suas buscas recentes:", ""]
    
    for i, ctx in enumerate(contextos, 1):
        msg_original = ctx.get("mensagem_original", "Busca sem título")
        criado_em = ctx.get("criado_em", "")
        total_produtos = len(ctx.get("contexto_estruturado", {}).get("produtos", []))
        
        # Extrai data/hora
        if criado_em:
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(criado_em.replace('Z', '+00:00'))
                tempo = dt.strftime("%H:%M")
            except:
                tempo = "??:??"
        else:
            tempo = "??:??"
        
        linhas.append(f"{i}. '{msg_original}' - {total_produtos} produtos ({tempo})")
    
    linhas.extend(["", "💡 Para ver uma busca anterior, digite: 'busca 1' ou 'voltar para café'"])
    
    return "\n".join(linhas)

# === TESTES ===
def testar_hash_query():
    """Testa geração de hash para diferentes queries"""
    testes = [
        "buscar nescau",
        "quero nescau", 
        "procurar nescau",
        "buscar  nescau  ", # espaços extras
        "Buscar NESCAU",    # case diferente
        "buscar café",
        "buscar cafe",      # sem acento
    ]
    
    print("🧪 Teste de Hash Query:")
    for query in testes:
        hash_result = gerar_hash_query(query)
        print(f"   '{query}' → {hash_result[:12]}...")
    
    # Verifica se queries similares geram mesmo hash
    hash1 = gerar_hash_query("buscar nescau")
    hash2 = gerar_hash_query("quero nescau")
    hash3 = gerar_hash_query("  BUSCAR   NESCAU  ")
    
    if hash1 == hash2 == hash3:
        print("   ✅ Normalização funcionando - hashes iguais")
    else:
        print("   ❌ Problema na normalização - hashes diferentes")

if __name__ == "__main__":
    testar_hash_query()