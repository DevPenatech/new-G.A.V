#!/usr/bin/env python3
# gav-autonomo/scripts/teste_hash_query_sistema.py
"""
Teste do sistema de hash_query para deduplicação de contextos
"""

import requests
import time
from datetime import datetime

def teste_hash_query_completo():
    print("Teste Sistema Hash Query - Deduplicação de Contextos")
    print("=" * 55)
    
    GAV_URL = "http://localhost:8000"
    API_URL = "http://localhost:8001"
    SESSAO = "teste_hash_query"
    
    try:
        # FASE 1: Busca inicial
        print("1. Primeira busca: 'buscar nescau'")
        resp1 = requests.post(f"{GAV_URL}/chat", 
            json={"texto": "buscar nescau", "sessao_id": SESSAO},
            timeout=50
        )
        
        if resp1.status_code == 200:
            print("   Busca OK - contexto salvo")
        else:
            print(f"   Erro: {resp1.status_code}")
            return
        
        time.sleep(1)
        
        # FASE 2: Busca equivalente (deve deduplicar)
        print("2. Busca equivalente: 'quero nescau' (deve deduplicar)")
        resp2 = requests.post(f"{GAV_URL}/chat",
            json={"texto": "quero nescau", "sessao_id": SESSAO},
            timeout=50
        )
        
        if resp2.status_code == 200:
            print("   Busca OK - deve ter deduplicado contexto anterior")
        
        time.sleep(1)
        
        # FASE 3: Busca diferente
        print("3. Busca diferente: 'buscar café'")
        resp3 = requests.post(f"{GAV_URL}/chat",
            json={"texto": "buscar café", "sessao_id": SESSAO},
            timeout=50
        )
        
        if resp3.status_code == 200:
            print("   Busca OK - novo contexto salvo")
        
        time.sleep(1)
        
        # FASE 4: Verificar contextos no banco
        print("4. Verificando contextos no banco...")
        resp_contextos = requests.get(f"{API_URL}/admin/contextos/{SESSAO}/recentes",
            params={"limite": 10},
            timeout=50
        )
        
        if resp_contextos.status_code == 200:
            contextos = resp_contextos.json()
            print(f"   Total de contextos: {len(contextos)}")
            
            # Analisar contextos
            for i, ctx in enumerate(contextos):
                msg = ctx.get("mensagem_original", "N/A")
                hash_q = ctx.get("hash_query", "N/A")
                criado = ctx.get("criado_em", "N/A")
                
                print(f"   {i+1}. '{msg}' | Hash: {hash_q[:8]}... | {criado}")
            
            # Verificar deduplicação
            hashes = [ctx.get("hash_query") for ctx in contextos if ctx.get("hash_query")]
            hashes_unicos = set(hashes)
            
            print(f"   Hashes únicos: {len(hashes_unicos)} de {len(hashes)} total")
            
            if len(hashes_unicos) == len(hashes):
                print("   Deduplicação funcionando - sem hashes duplicados")
            else:
                print("   PROBLEMA: Hashes duplicados encontrados")
        
        else:
            print(f"   Erro ao verificar contextos: {resp_contextos.status_code}")
        
        # FASE 5: Teste de múltiplas buscas (limite de 5)
        print("5. Testando limite de contextos (máximo 5)...")
        
        buscas_teste = [
            "buscar arroz",
            "buscar feijão", 
            "buscar açúcar",
            "buscar sal",
            "buscar óleo",
            "buscar farinha",  # Esta deve remover as mais antigas
        ]
        
        for busca in buscas_teste:
            resp = requests.post(f"{GAV_URL}/chat",
                json={"texto": busca, "sessao_id": SESSAO},
                timeout=50
            )
            
            if resp.status_code == 200:
                print(f"   '{busca}' - OK")
            else:
                print(f"   '{busca}' - Erro: {resp.status_code}")
            
            time.sleep(0.5)  # Pausa menor entre buscas
        
        # FASE 6: Verificar limite aplicado
        print("6. Verificando se limite de 5 contextos foi aplicado...")
        resp_final = requests.get(f"{API_URL}/admin/contextos/{SESSAO}/recentes",
            params={"limite": 10},
            timeout=50
        )
        
        if resp_final.status_code == 200:
            contextos_final = resp_final.json()
            contextos_busca = [c for c in contextos_final if c.get("tipo_contexto") == "busca_numerada_rica"]
            
            print(f"   Contextos de busca ativos: {len(contextos_busca)}")
            
            if len(contextos_busca) <= 5:
                print("   Limite de contextos funcionando corretamente")
            else:
                print("   PROBLEMA: Mais de 5 contextos de busca ativos")
            
            # Mostrar contextos finais
            for ctx in contextos_busca:
                msg = ctx.get("mensagem_original", "N/A")
                criado = ctx.get("criado_em", "N/A")
                print(f"   - '{msg}' ({criado})")
        
        # FASE 7: Teste do comando histórico (futuro)
        print("7. [FUTURO] Teste comando 'histórico'...")
        print("   Implementar quando comando for adicionado")
        
        print("\nResumo do Teste:")
        print("- Deduplicação por hash: verificar logs")
        print("- Limite de contextos: verificar se <= 5")
        print("- Performance: contextos reutilizados")
        
    except Exception as e:
        print(f"Erro no teste: {e}")

def teste_hash_normalizacao():
    """Teste da normalização de hash"""
    print("\nTeste de Normalização Hash:")
    print("-" * 30)
    
    # Simulação dos hashes que seriam gerados
    import hashlib
    import re
    
    def gerar_hash_local(query):
        query_normalizada = query.lower().strip()
        query_normalizada = re.sub(r'\b(buscar|quero|procurar|encontrar|tem)\b', 'buscar', query_normalizada)
        query_normalizada = re.sub(r'\b(o|a|os|as|um|uma|de|da|do|para|por)\b', '', query_normalizada)
        query_normalizada = re.sub(r'\s+', ' ', query_normalizada).strip()
        return hashlib.md5(query_normalizada.encode('utf-8')).hexdigest()
    
    queries_teste = [
        "buscar nescau",
        "quero nescau",
        "procurar nescau",
        "  buscar   nescau  ",
        "BUSCAR NESCAU",
        "buscar o nescau",
        "buscar café",
        "quero café"
    ]
    
    hashes = {}
    for query in queries_teste:
        hash_result = gerar_hash_local(query)
        if hash_result in hashes:
            hashes[hash_result].append(query)
        else:
            hashes[hash_result] = [query]
    
    print("Grupos de queries com mesmo hash:")
    for hash_val, queries in hashes.items():
        if len(queries) > 1:
            print(f"Hash {hash_val[:8]}...: {queries}")
        else:
            print(f"Hash {hash_val[:8]}...: {queries[0]}")

if __name__ == "__main__":
    # Primeiro testa normalização
    teste_hash_normalizacao()
    
    print("\n" + "="*60 + "\n")
    
    # Depois testa sistema completo
    teste_hash_query_completo()