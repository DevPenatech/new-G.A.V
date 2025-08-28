#!/usr/bin/env python3
# gav-autonomo/scripts/teste_simples_quantidade.py
"""
🧪 TESTE SIMPLES DO FLUXO DE QUANTIDADE
Testa via HTTP sem imports complexos
"""

import requests
import json
import time

def teste_fluxo_quantidade():
    """Teste do fluxo: busca → seleção → quantidade → verificação"""
    
    GAV_URL = "http://localhost:8000"
    API_URL = "http://localhost:8001"
    SESSAO = "teste_simples_quantidade"
    
    print("🧪 TESTE SIMPLES - FLUXO DE QUANTIDADE")
    print("=" * 45)
    print(f"🔑 Sessão: {SESSAO}")
    print()
    
    try:
        # ETAPA 1: Buscar produtos
        print("📋 ETAPA 1: Buscando produtos...")
        response1 = requests.post(f"{GAV_URL}/chat", 
            json={"texto": "buscar nescau", "sessao_id": SESSAO},
            timeout=30
        )
        
        if response1.status_code != 200:
            print(f"❌ Erro na busca: {response1.status_code}")
            return False
        
        resultado1 = response1.json()
        
        # Extrair ID do produto
        contexto = resultado1.get("contexto_estruturado", {})
        produtos = contexto.get("produtos", [])
        
        if not produtos:
            print("❌ Nenhum produto encontrado")
            print(f"Resposta: {json.dumps(resultado1, indent=2)}")
            return False
        
        primeiro_produto = produtos[0]
        item_id = primeiro_produto.get("item_id")
        nome_produto = primeiro_produto.get("descricao", "N/A")
        
        print(f"✅ Produtos encontrados: {len(produtos)}")
        print(f"🎯 Produto teste: ID {item_id} - {nome_produto[:40]}...")
        
        time.sleep(1)
        
        # ETAPA 2: Selecionar produto
        print(f"\n🎯 ETAPA 2: Selecionando produto ID {item_id}...")
        response2 = requests.post(f"{GAV_URL}/chat",
            json={"texto": str(item_id), "sessao_id": SESSAO},
            timeout=30
        )
        
        if response2.status_code != 200:
            print(f"❌ Erro na seleção: {response2.status_code}")
            return False
        
        resultado2 = response2.json()
        mensagem2 = resultado2.get("mensagem", "")
        
        print(f"💬 Resposta: {mensagem2[:100]}...")
        
        # Verificar se perguntou quantidade
        if "quantas" in mensagem2.lower() or "quantidade" in mensagem2.lower():
            print("✅ Sistema perguntou quantidade corretamente")
        else:
            print("❌ Sistema NÃO perguntou quantidade")
            print(f"Resposta completa: {mensagem2}")
            return False
        
        # Verificar contexto no banco
        try:
            response_ctx = requests.get(f"{API_URL}/contexto/{SESSAO}", timeout=10)
            if response_ctx.status_code == 200:
                contexto_banco = response_ctx.json()
                tipo_contexto = contexto_banco.get("tipo_contexto", "N/A")
                print(f"✅ Contexto no banco: {tipo_contexto}")
            else:
                print(f"⚠️ Contexto não encontrado no banco: {response_ctx.status_code}")
        except:
            print("⚠️ Não conseguiu verificar contexto no banco")
        
        time.sleep(1)
        
        # ETAPA 3: Informar quantidade
        print(f"\n🔢 ETAPA 3: Informando quantidade (3 unidades)...")
        response3 = requests.post(f"{GAV_URL}/chat",
            json={"texto": "3", "sessao_id": SESSAO},
            timeout=30
        )
        
        if response3.status_code != 200:
            print(f"❌ Erro na quantidade: {response3.status_code}")
            return False
        
        resultado3 = response3.json()
        mensagem3 = resultado3.get("mensagem", "")
        
        print(f"💬 Resposta: {mensagem3[:150]}...")
        
        # Verificar se adicionou
        palavras_sucesso = ["adicionei", "adicionado", "carrinho", "sucesso", "perfeito"]
        if any(palavra in mensagem3.lower() for palavra in palavras_sucesso):
            print("✅ Item foi adicionado ao carrinho!")
        else:
            print("❌ Item NÃO foi adicionado")
            print(f"Resposta completa: {mensagem3}")
            return False
        
        time.sleep(1)
        
        # ETAPA 4: Verificar carrinho
        print(f"\n🛒 ETAPA 4: Verificando carrinho...")
        response4 = requests.post(f"{GAV_URL}/chat",
            json={"texto": "ver carrinho", "sessao_id": SESSAO},
            timeout=30
        )
        
        if response4.status_code != 200:
            print(f"❌ Erro ao ver carrinho: {response4.status_code}")
            return False
        
        resultado4 = response4.json()
        dados_carrinho = resultado4.get("dados_originais", {})
        itens_carrinho = dados_carrinho.get("itens", [])
        
        print(f"✅ Itens no carrinho: {len(itens_carrinho)}")
        
        if itens_carrinho:
            primeiro_item = itens_carrinho[0]
            qtd_carrinho = primeiro_item.get("quantidade", 0)
            nome_carrinho = primeiro_item.get("descricao_produto", "N/A")
            
            print(f"✅ Item: {qtd_carrinho}x {nome_carrinho[:40]}...")
            
            if qtd_carrinho == 3:
                print("✅ Quantidade correta no carrinho!")
                print("\n🎉 TESTE COMPLETO: SUCESSO!")
                print("✅ Fluxo de quantidade está funcionando!")
                return True
            else:
                print(f"❌ Quantidade errada: esperado 3, encontrado {qtd_carrinho}")
                return False
        else:
            print("❌ Carrinho vazio - item não foi adicionado")
            return False
    
    except requests.exceptions.RequestException as e:
        print(f"💥 Erro de conexão: {e}")
        return False
    except Exception as e:
        print(f"💥 Erro: {e}")
        return False

if __name__ == "__main__":
    sucesso = teste_fluxo_quantidade()
    exit(0 if sucesso else 1)