#!/usr/bin/env python3
# gav-autonomo/scripts/debug_simples.py
"""
🔍 DEBUG SIMPLES - PROBLEMA 404
Versão ultra-simplificada para rodar no container
"""

def debug_problema_404():
    """Debug mínimo do problema"""
    
    print("🔍 DEBUG PROBLEMA 404")
    print("=" * 25)
    
    # Teste 1: Verificar imports
    print("1️⃣ Testando imports...")
    try:
        import sys
        import os
        
        # Adicionar paths
        sys.path.append('/app')
        sys.path.append('/app/gav-autonomo')
        
        # Testar import básico
        from app.servicos.executor_regras import _buscar_contexto_do_banco
        print("✅ Import _buscar_contexto_do_banco OK")
        
        from app.servicos.executor_regras import _detectar_selecao_produto
        print("✅ Import _detectar_selecao_produto OK")
        
    except Exception as e:
        print(f"❌ Erro de import: {e}")
        return
    
    # Teste 2: Detecção de seleção
    print("\n2️⃣ Testando detecção...")
    try:
        testes = ["1981", "18135", "buscar café"]
        
        for teste in testes:
            detectado = _detectar_selecao_produto(teste)
            print(f"   '{teste}' → {'SIM' if detectado else 'NÃO'}")
            
    except Exception as e:
        print(f"❌ Erro detecção: {e}")
    
    # Teste 3: Busca de contexto
    print("\n3️⃣ Testando busca contexto...")
    try:
        # Testar algumas sessões que podem existir
        sessoes = ["debug_interno", "teste_hash", "debug_selecao_404"]
        
        for sessao in sessoes:
            try:
                contexto = _buscar_contexto_do_banco(sessao)
                
                if contexto:
                    msg = contexto.get('mensagem_original', 'N/A')
                    produtos = contexto.get('contexto_estruturado', {}).get('produtos', [])
                    print(f"   ✅ '{sessao}': {msg} ({len(produtos)} produtos)")
                    
                    # Mostrar IDs disponíveis
                    if produtos:
                        ids = []
                        for p in produtos[:5]:  # Só os primeiros 5
                            item_id = p.get('item_id') or p.get('id')
                            if item_id:
                                ids.append(str(item_id))
                        print(f"      IDs: {', '.join(ids)}")
                else:
                    print(f"   ❌ '{sessao}': não encontrado")
                    
            except Exception as e:
                print(f"   ❌ '{sessao}': erro {e}")
                
    except Exception as e:
        print(f"❌ Erro busca contexto: {e}")
    
    # Teste 4: Hash (se existir)
    print("\n4️⃣ Testando hash...")
    try:
        from app.servicos.executor_regras import gerar_hash_query
        
        hash1 = gerar_hash_query("buscar nescau")
        hash2 = gerar_hash_query("quero nescau")
        
        print(f"   'buscar nescau' → {hash1[:8]}...")
        print(f"   'quero nescau' → {hash2[:8]}...")
        print(f"   Iguais? {'SIM' if hash1 == hash2 else 'NÃO'}")
        
    except Exception as e:
        print(f"❌ Hash não disponível: {e}")
    
    print("\n🏁 Debug concluído!")

def teste_rapido_interno():
    """Teste rápido das URLs internas"""
    
    print("\n🌐 TESTE URLS INTERNAS")
    print("=" * 25)
    
    try:
        import httpx
        
        # URLs internas do container
        urls = [
            "http://api_negocio:8001/healthcheck",
            "http://api_negocio:8001/contexto/teste123"
        ]
        
        for url in urls:
            try:
                resp = httpx.get(url, timeout=5.0)
                print(f"✅ {url}: {resp.status_code}")
            except Exception as e:
                print(f"❌ {url}: {str(e)[:50]}...")
                
    except Exception as e:
        print(f"❌ Erro teste URLs: {e}")

if __name__ == "__main__":
    debug_problema_404()
    teste_rapido_interno()
    
    print("\n💡 COMO EXECUTAR ESTE SCRIPT:")
    print("1. docker exec -it gav-autonomo bash")
    print("2. cd /app/gav-autonomo") 
    print("3. python scripts/debug_simples.py")