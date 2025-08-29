# gav-autonomo/scripts/debug_contexto_salvamento.py
"""
Debug: Por que o contexto não está sendo salvo no banco
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import httpx
import json

def testar_salvamento_contexto():
    """Testa se contexto está sendo salvo após busca"""
    print("🔍 TESTANDO SALVAMENTO DE CONTEXTO")
    print("=" * 40)
    
    sessao_teste = "debug_contexto_salvamento"
    
    try:
        # 1. Fazer busca que deveria salvar contexto
        print("1. Fazendo busca...")
        response = httpx.post(
            "http://localhost:8000/chat",
            json={"texto": "quero nescau", "sessao_id": sessao_teste},
            timeout=60.0
        )
        
        if response.status_code == 200:
            resultado = response.json()
            print("✅ Busca realizada")
            
            # Verificar se tem contexto_estruturado na resposta
            contexto = resultado.get("contexto_estruturado", {})
            produtos = contexto.get("produtos", [])
            
            print(f"📊 Produtos no contexto da resposta: {len(produtos)}")
            
            if produtos:
                print("Primeiros 3 produtos:")
                for i, produto in enumerate(produtos[:3]):
                    print(f"  {i+1}. ID: {produto.get('item_id')} - {produto.get('descricao', 'N/A')[:50]}")
            else:
                print("❌ Nenhum produto no contexto da resposta!")
                return
            
        else:
            print(f"❌ Erro na busca: {response.status_code}")
            return
        
        # 2. Verificar se foi salvo no banco
        print("\n2. Verificando se salvou no banco...")
        
        response_contexto = httpx.get(
            f"http://api_negocio:8001/contexto/{sessao_teste}",
            timeout=60.0
        )
        
        if response_contexto.status_code == 200:
            contexto_banco = response_contexto.json()
            print("✅ Contexto encontrado no banco")
            
            produtos_banco = contexto_banco.get("contexto_estruturado", {}).get("produtos", [])
            print(f"📊 Produtos salvos no banco: {len(produtos_banco)}")
            
            if produtos_banco:
                print("Primeiros 3 produtos do banco:")
                for i, produto in enumerate(produtos_banco[:3]):
                    print(f"  {i+1}. ID: {produto.get('item_id')} - {produto.get('descricao', 'N/A')[:50]}")
            else:
                print("❌ Produtos não foram salvos no banco!")
                
        elif response_contexto.status_code == 404:
            print("❌ Contexto NÃO foi salvo no banco!")
            print("🔍 Problema: Sistema não está salvando contexto")
        else:
            print(f"❌ Erro ao buscar contexto: {response_contexto.status_code}")
        
        # 3. Tentar seleção para confirmar problema
        print("\n3. Testando seleção de ID...")
        
        response_selecao = httpx.post(
            "http://localhost:8000/chat", 
            json={"texto": "18135", "sessao_id": sessao_teste},
            timeout=60.0
        )
        
        if response_selecao.status_code == 200:
            resultado_selecao = response_selecao.json()
            
            if "erro" in resultado_selecao:
                print(f"❌ Erro esperado: {resultado_selecao['erro']}")
                print("🔍 Confirmado: Contexto não está disponível para seleção")
            else:
                print("✅ Seleção funcionou (inesperado)")
        else:
            print(f"❌ Erro na seleção: {response_selecao.status_code}")
            
    except Exception as e:
        print(f"💥 Erro no teste: {str(e)}")

if __name__ == "__main__":
    testar_salvamento_contexto()