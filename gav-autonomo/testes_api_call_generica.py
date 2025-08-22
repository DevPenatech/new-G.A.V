# Cenários de teste para a ferramenta genérica API Call
# Execute estes testes para validar se a implementação está funcionando

import requests
import json

BASE_URL = "http://localhost:8000"

def testar_cenario(descricao: str, mensagem: str, sessao_id: str = "test123"):
    """Testa um cenário específico e mostra o resultado."""
    print(f"\n{'='*60}")
    print(f"TESTE: {descricao}")
    print(f"Mensagem: '{mensagem}'")
    print(f"Sessão: {sessao_id}")
    print(f"{'='*60}")
    
    try:
        response = requests.post(
            f"{BASE_URL}/chat",
            json={"texto": mensagem, "sessao_id": sessao_id},
            timeout=30
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Resposta: {json.dumps(result, indent=2, ensure_ascii=False)}")
            
            # Validações específicas por tipo de teste
            if "nescau" in mensagem.lower():
                assert "resultados" in result, "Busca deve retornar 'resultados'"
                print("✅ Busca executada corretamente")
                
            elif "carrinho" in mensagem.lower() and "ver" in mensagem.lower():
                assert "itens" in result or "valor_total" in result, "Ver carrinho deve retornar estrutura de carrinho"
                print("✅ Ver carrinho executado corretamente")
                
            elif "adicione" in mensagem.lower() or "codigo" in mensagem.lower():
                assert "status" in result or "carrinho_id" in result, "Adicionar deve retornar confirmação"
                print("✅ Adicionar ao carrinho executado corretamente")
                
            elif any(palavra in mensagem.lower() for palavra in ["oi", "olá", "eae"]):
                assert "mensagem" in result, "Chitchat deve retornar mensagem conversacional"
                print("✅ Conversa tratada corretamente")
        else:
            print(f"❌ Erro HTTP: {response.text}")
            
    except Exception as e:
        print(f"❌ Erro na requisição: {e}")

def executar_suite_testes():
    """Executa todos os cenários de teste."""
    print("🚀 INICIANDO SUITE DE TESTES - API CALL GENÉRICA")
    
    # Cenário 1: Busca simples
    testar_cenario(
        "Busca de produto com ordenação por preço",
        "eae, quero nescau baratinho"
    )
    
    # Cenário 2: Adição direta por código
    testar_cenario(
        "Adição direta por código/SKU",
        "adicione 2 caixas do codigo 639330"
    )
    
    # Cenário 3: Ver carrinho
    testar_cenario(
        "Visualizar carrinho",
        "ver meu carrinho"
    )
    
    # Cenário 4: Busca sem ordenação
    testar_cenario(
        "Busca simples sem ordenação",
        "quero café pilão"
    )
    
    # Cenário 5: Conversa informal
    testar_cenario(
        "Conversa sem intenção de compra",
        "oi, tudo bem?"
    )
    
    # Cenário 6: Teste de robustez - números por extenso
    testar_cenario(
        "Números por extenso",
        "adicione três unidades do sku 123456"
    )
    
    # Cenário 7: Teste de reparo automático (payload incorreto)
    testar_cenario(
        "Teste de reparo - ordenação inválida",
        "quero nescau bem barato mesmo"
    )
    
    print(f"\n{'='*60}")
    print("🏁 SUITE DE TESTES CONCLUÍDA")
    print(f"{'='*60}")

# Cenários de validação específicos para debugging
def validar_decisoes_llm():
    """Valida se o LLM está tomando as decisões corretas."""
    
    cenarios_esperados = [
        {
            "input": "eae, quero nescau baratinho",
            "expected_endpoint": "/produtos/busca",
            "expected_method": "POST",
            "expected_body_keys": ["query", "ordenar_por", "codfilial"]
        },
        {
            "input": "adicione 2 caixas do codigo 639330", 
            "expected_endpoint": "/carrinhos/{sessao_id}/itens",
            "expected_method": "POST",
            "expected_body_keys": ["item_id", "quantidade", "codfilial"]
        },
        {
            "input": "ver meu carrinho",
            "expected_endpoint": "/carrinhos/{sessao_id}",
            "expected_method": "GET",
            "expected_body_keys": []
        }
    ]
    
    print("\n🔍 VALIDANDO DECISÕES DO LLM...")
    
    for i, cenario in enumerate(cenarios_esperados, 1):
        print(f"\nCenário {i}: {cenario['input']}")
        # Aqui você poderia fazer uma chamada direto ao LLM para verificar a decisão
        # sem executar a API call completa
        print(f"Esperado: {cenario['expected_method']} {cenario['expected_endpoint']}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--validate-llm":
        validar_decisoes_llm()
    else:
        executar_suite_testes()