# Versão alternativa: Teste com produtos diferentes para cada cenário
import requests
import json
import time

BASE_URL = "http://localhost:8000"



def teste_selecao_produtos_variados():
    """Testa seleção com produtos diferentes para cada cenário"""
    
    print("🛍️ TESTE: Seleção com Produtos Variados")
    print("=" * 45)
    
    # Cada cenário usa produto diferente
    cenarios_produto = [
        {
            "produto": "nescau",
            "busca": "quero nescau",
            "selecoes": [
                ("quero o 1", "primeiro nescau"),
                ("a lata pequena", "nescau 200g")
            ]
        },
        {
            "produto": "café", 
            "busca": "quero café pilão",
            "selecoes": [
                ("o primeiro", "primeiro café"),
                ("o de 250g", "café 250g")
            ]
        },
        {
            "produto": "detergente",
            "busca": "detergente",
            "selecoes": [
                ("quero o 2", "segundo detergente"),
                ("ver mais opções", "mais detergentes")
            ]
        }
    ]
    
    sucessos_totais = 0
    testes_totais = 0
    
    for cenario in cenarios_produto:
        print(f"\n🧪 Testando produto: {cenario['produto']}")
        print(f"   Busca: '{cenario['busca']}'")
        
        sessao_teste = f"test_{cenario['produto']}"
        
        # Busca inicial
        response1 = requests.post(f"{BASE_URL}/chat", json={
            "texto": cenario["busca"],
            "sessao_id": sessao_teste
        })
        
        if response1.status_code == 200:
            resultado1 = response1.json()
            
            if "1️⃣" in resultado1.get("mensagem", ""):
                print(f"   ✅ Busca OK: produtos numerados")
                
                # Testa cada seleção
                for selecao, descricao in cenario["selecoes"]:
                    print(f"   🎯 Testando: '{selecao}' ({descricao})")
                    
                    response2 = requests.post(f"{BASE_URL}/chat", json={
                        "texto": selecao,
                        "sessao_id": sessao_teste
                    })
                    
                    testes_totais += 1
                    
                    if response2.status_code == 200:
                        resultado2 = response2.json()
                        mensagem2 = resultado2.get("mensagem", "").lower()
                        
                        if "ver mais" in selecao:
                            sucesso = "mais" in mensagem2 or "opções" in mensagem2
                        else:
                            sucesso = "adicionado" in mensagem2 or "carrinho" in mensagem2
                        
                        if sucesso:
                            print(f"      ✅ Seleção funcionou")
                            sucessos_totais += 1
                        else:
                            print(f"      ❌ Seleção falhou")
                    else:
                        print(f"      ❌ Erro HTTP: {response2.status_code}")
            else:
                print(f"   ❌ Busca falhou: sem numeração")
        else:
            print(f"   ❌ Erro na busca: {response1.status_code}")
    
    print(f"\n📊 Total: {sucessos_totais}/{testes_totais} seleções funcionando")
    return sucessos_totais / testes_totais if testes_totais > 0 else 0

teste_selecao_produtos_variados()