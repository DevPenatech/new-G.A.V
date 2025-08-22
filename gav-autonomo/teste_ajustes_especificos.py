# gav-autonomo/teste_ajustes_especificos.py
# Testa especificamente os problemas encontrados nos testes anteriores

import requests
import json

BASE_URL = "http://localhost:8000"

def testar_ajustes_especificos():
    """Foca nos problemas específicos encontrados"""
    
    print("🔧 TESTANDO AJUSTES ESPECÍFICOS - FASE 5A")
    print("=" * 50)
    
    # Teste 1: Ver carrinho deve usar api_call_with_presentation
    print("\n1. 🛒 TESTE: Ver Carrinho com Apresentação")
    print("-" * 30)
    
    response = requests.post(f"{BASE_URL}/chat", json={
        "texto": "ver meu carrinho", 
        "sessao_id": "test_ajuste_carrinho"
    })
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Status: {response.status_code}")
        
        # Verifica se tem campo mensagem (apresentação conversacional)
        if "mensagem" in result:
            print("✅ SUCESSO: Carrinho apresentado conversacionalmente")
            print(f"📝 Mensagem: {result['mensagem'][:100]}...")
        else:
            print("❌ FALHA: Ainda retornando JSON técnico")
            print(f"🔍 Resposta: {json.dumps(result, indent=2)[:200]}...")
    else:
        print(f"❌ Erro HTTP: {response.status_code}")
    
    # Teste 2: Busca sem resultados específicos
    print("\n2. 🔍 TESTE: Busca Produto Não Encontrado")
    print("-" * 30)
    
    response = requests.post(f"{BASE_URL}/chat", json={
        "texto": "quero caviar russo importado", 
        "sessao_id": "test_ajuste_busca"
    })
    
    if response.status_code == 200:
        result = response.json()
        mensagem = result.get("mensagem", "").lower()
        
        if "não encontrei" in mensagem or "não achei" in mensagem:
            print("✅ SUCESSO: Reconheceu que não encontrou exatamente")
        else:
            print("❌ FALHA: Não reconheceu busca sem resultado específico")
        
        print(f"📝 Resposta: {result.get('mensagem', 'Sem mensagem')[:150]}...")
    
    # Teste 3: Adicionar item ao carrinho deve ser apresentado
    print("\n3. ➕ TESTE: Adicionar Item com Apresentação")
    print("-" * 30)
    
    response = requests.post(f"{BASE_URL}/chat", json={
        "texto": "adicione 1 do codigo 18136", 
        "sessao_id": "test_ajuste_adicionar"
    })
    
    if response.status_code == 200:
        result = response.json()
        
        if "mensagem" in result and "adicionado" in result.get("mensagem", "").lower():
            print("✅ SUCESSO: Adição apresentada conversacionalmente")
        else:
            print("❌ FALHA: Adição não apresentada ou falhou")
        
        print(f"📝 Resposta: {json.dumps(result, indent=2)[:200]}...")
    
    # Teste 4: Conversa direta (deve continuar funcionando)
    print("\n4. 💬 TESTE: Conversa Direta")
    print("-" * 30)
    
    response = requests.post(f"{BASE_URL}/chat", json={
        "texto": "obrigado pela ajuda", 
        "sessao_id": "test_ajuste_conversa"
    })
    
    if response.status_code == 200:
        result = response.json()
        
        if "mensagem" in result:
            print("✅ SUCESSO: Conversa direta funcionando")
            print(f"📝 Resposta: {result['mensagem']}")
        else:
            print("❌ FALHA: Conversa direta quebrou")

def verificar_decisoes_llm():
    """Verifica se o LLM está tomando as decisões corretas"""
    
    print("\n🧠 ANÁLISE: Decisões do LLM Selector")
    print("=" * 40)
    
    cenarios = [
        ("ver meu carrinho", "api_call_with_presentation"),
        ("quero nescau", "api_call_with_presentation"), 
        ("adicione 2 do codigo 123", "api_call"),  # Este deve ser api_call mesmo
        ("oi, tudo bem?", "api_call")  # Conversa também api_call
    ]
    
    print("📋 Cenários esperados:")
    for input_text, expected_tool in cenarios:
        print(f"   '{input_text}' → {expected_tool}")
    
    print("\n💡 Para verificar: cheque logs do gav_autonomo durante os testes")
    print("   docker logs -f gav_autonomo | grep 'tool_name'")

if __name__ == "__main__":
    testar_ajustes_especificos()
    verificar_decisoes_llm()