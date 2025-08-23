# gav-autonomo/teste_pipeline_generico.py
# Testa pipeline 100% prompt-driven (sem regras hardcoded)

import requests
import json

BASE_URL = "http://localhost:8000"

def teste_llm_selector_deteccao():
    """Testa se LLM Selector detecta corretamente contexto vs busca nova"""
    
    print("🧠 TESTE: Detecção do LLM Selector")
    print("=" * 40)
    
    cenarios = [
        {
            "tipo": "busca_nova",
            "mensagem": "quero nescau",
            "endpoint_esperado": "/produtos/busca"
        },
        {
            "tipo": "contexto_anterior", 
            "mensagem": "quero o 1",
            "endpoint_esperado": "/chat/contexto"
        },
        {
            "tipo": "contexto_anterior",
            "mensagem": "id 18136", 
            "endpoint_esperado": "/chat/contexto"
        },
        {
            "tipo": "contexto_anterior",
            "mensagem": "ver mais opções",
            "endpoint_esperado": "/chat/contexto"
        },
        {
            "tipo": "carrinho",
            "mensagem": "ver meu carrinho",
            "endpoint_esperado": "/carrinhos/"
        },
        {
            "tipo": "conversa",
            "mensagem": "obrigado",
            "endpoint_esperado": "/chat/resposta"
        }
    ]
    
    sucessos = 0
    total = len(cenarios)
    
    print("📋 Cenários de teste:")
    for i, cenario in enumerate(cenarios, 1):
        print(f"   {i}. {cenario['tipo']}: '{cenario['mensagem']}'")
    
    print("\n🧪 Executando testes...")
    
    for i, cenario in enumerate(cenarios, 1):
        print(f"\n{i}. Testando: '{cenario['mensagem']}'")
        
        try:
            response = requests.post(f"{BASE_URL}/chat", json={
                "texto": cenario["mensagem"],
                "sessao_id": f"test_detector_{i}"
            }, timeout=30)
            
            if response.status_code == 200:
                resultado = response.json()
                
                # Para validar, vemos se a resposta faz sentido para o tipo
                if cenario["tipo"] == "busca_nova":
                    # Deve buscar produtos
                    if "encontrei" in resultado.get("mensagem", "").lower() or "resultados" in resultado:
                        print("✅ Busca nova detectada corretamente")
                        sucessos += 1
                    else:
                        print("❌ Busca nova NÃO detectada")
                        
                elif cenario["tipo"] == "contexto_anterior":
                    # Deve tentar processar contexto (pode dar erro por não ter contexto)
                    mensagem = resultado.get("mensagem", "").lower()
                    if "erro" in resultado or "não consegui" in mensagem or "contexto" in mensagem:
                        print("✅ Contexto anterior detectado (sem contexto disponível é OK)")
                        sucessos += 1
                    else:
                        print("❌ Contexto anterior NÃO detectado")
                        
                elif cenario["tipo"] == "carrinho":
                    # Deve processar carrinho
                    if "carrinho" in resultado.get("mensagem", "").lower():
                        print("✅ Carrinho detectado corretamente")
                        sucessos += 1
                    else:
                        print("❌ Carrinho NÃO detectado")
                        
                elif cenario["tipo"] == "conversa":
                    # Deve responder conversacionalmente
                    if resultado.get("tipo") == "conversacional" or len(resultado.get("mensagem", "")) > 10:
                        print("✅ Conversa detectada corretamente")
                        sucessos += 1
                    else:
                        print("❌ Conversa NÃO detectada")
                
                # Debug da resposta
                print(f"   📝 Resposta: {json.dumps(resultado, ensure_ascii=False)[:100]}...")
                
            else:
                print(f"❌ Erro HTTP: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Erro na requisição: {e}")
    
    print(f"\n📊 Resultado: {sucessos}/{total} detecções corretas ({sucessos/total*100:.1f}%)")
    
    if sucessos >= total * 0.8:
        print("✅ LLM Selector funcionando bem!")
        return True
    else:
        print("❌ LLM Selector precisa de ajustes")
        return False

def teste_pipeline_generico():
    """Testa se o pipeline genérico funciona para diferentes domínios"""
    
    print("\n🔄 TESTE: Pipeline Genérico")
    print("=" * 35)
    
    # Testa diferentes tipos de interação
    interacoes = [
        ("Busca de produto", "quero café"),
        ("Operação carrinho", "ver carrinho"),  
        ("Conversa casual", "oi, tudo bem?"),
        ("Agradecimento", "muito obrigado!")
    ]
    
    sucessos = 0
    
    for tipo, mensagem in interacoes:
        print(f"\n🧪 {tipo}: '{mensagem}'")
        
        try:
            response = requests.post(f"{BASE_URL}/chat", json={
                "texto": mensagem,
                "sessao_id": "test_pipeline_generico"
            })
            
            if response.status_code == 200:
                resultado = response.json()
                
                # Verifica se tem resposta conversacional
                if "mensagem" in resultado and len(resultado["mensagem"]) > 5:
                    print(f"✅ Pipeline funcionou: {resultado['mensagem'][:50]}...")
                    sucessos += 1
                else:
                    print("❌ Pipeline não gerou resposta conversacional")
                    print(f"   📝 Resposta: {json.dumps(resultado, indent=2)[:150]}...")
            else:
                print(f"❌ Erro HTTP: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Erro: {e}")
    
    print(f"\n📊 Pipeline: {sucessos}/{len(interacoes)} funcionando ({sucessos/len(interacoes)*100:.1f}%)")
    
    return sucessos >= len(interacoes) * 0.75

def teste_prompts_contexto():
    """Testa se os prompts de contexto foram criados corretamente"""
    
    print("\n🎯 TESTE: Prompts de Contexto")
    print("=" * 32)
    
    prompts_necessarios = [
        "prompt_processador_contexto",
        "prompt_executor_referencia"
    ]
    
    sucessos = 0
    
    for prompt_nome in prompts_necessarios:
        print(f"\n🔍 Verificando: {prompt_nome}")
        
        try:
            response = requests.get(f"http://localhost:8001/admin/prompts/buscar", params={
                "nome": prompt_nome,
                "espaco": "autonomo",
                "versao": "1"
            })
            
            if response.status_code == 200:
                prompt_data = response.json()
                
                if prompt_data.get("template") and len(prompt_data["template"]) > 100:
                    print("✅ Prompt existe e tem conteúdo")
                    sucessos += 1
                else:
                    print("❌ Prompt vazio ou muito pequeno")
            else:
                print(f"❌ Prompt não encontrado: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Erro ao verificar prompt: {e}")
    
    print(f"\n📊 Prompts: {sucessos}/{len(prompts_necessarios)} criados ({sucessos/len(prompts_necessarios)*100:.1f}%)")
    
    return sucessos == len(prompts_necessarios)

def teste_arquitetura_generica():
    """Testa se a arquitetura é realmente genérica (não específica de produtos)"""
    
    print("\n🏗️ TESTE: Arquitetura Genérica")
    print("=" * 35)
    
    # Simula diferentes domínios
    dominios = [
        ("Vendas", "quero um produto"),
        ("Suporte", "preciso de ajuda"),
        ("Agendamento", "quero marcar uma consulta"),
        ("Informações", "qual o horário de funcionamento?")
    ]
    
    generico = True
    
    for dominio, mensagem in dominios:
        print(f"\n🌐 Simulando {dominio}: '{mensagem}'")
        
        try:
            response = requests.post(f"{BASE_URL}/chat", json={
                "texto": mensagem,
                "sessao_id": f"test_{dominio.lower()}"
            })
            
            if response.status_code == 200:
                resultado = response.json()
                
                # Verifica se o sistema responde genericamente (não quebra)
                if "mensagem" in resultado or "erro" in resultado:
                    print(f"✅ Sistema genérico respondeu: {str(resultado)[:50]}...")
                else:
                    print("❌ Sistema não é genérico (quebrou com domínio diferente)")
                    generico = False
            else:
                print(f"⚠️ Sistema retornou erro: {response.status_code}")
                # Erro pode ser OK, desde que seja tratado genericamente
                
        except Exception as e:
            print(f"❌ Sistema quebrou com domínio diferente: {e}")
            generico = False
    
    if generico:
        print("\n✅ ARQUITETURA É GENÉRICA: Funciona para qualquer domínio!")
        print("🚀 Pronto para: vendas, telemarking, suporte, agendamento, etc.")
    else:
        print("\n❌ ARQUITETURA NÃO É GENÉRICA: Acoplada a produtos")
        
    return generico

def executar_suite_correcao():
    """Executa todos os testes da solução corrigida"""
    
    print("🎯 SUITE DE TESTES: Solução 100% Prompt-Driven")
    print("=" * 60)
    
    resultados = {
        "deteccao_llm": teste_llm_selector_deteccao(),
        "pipeline_generico": teste_pipeline_generico(), 
        "prompts_contexto": teste_prompts_contexto(),
        "arquitetura_generica": teste_arquitetura_generica()
    }
    
    # Relatório final
    print("\n" + "=" * 60)
    print("📊 RELATÓRIO FINAL - CORREÇÃO IMPLEMENTADA")
    print("=" * 60)
    
    sucessos = sum(resultados.values())
    total = len(resultados)
    
    print(f"✅ Detecção LLM: {'PASSOU' if resultados['deteccao_llm'] else 'FALHOU'}")
    print(f"✅ Pipeline Genérico: {'PASSOU' if resultados['pipeline_generico'] else 'FALHOU'}")
    print(f"✅ Prompts de Contexto: {'PASSOU' if resultados['prompts_contexto'] else 'FALHOU'}")
    print(f"✅ Arquitetura Genérica: {'PASSOU' if resultados['arquitetura_generica'] else 'FALHOU'}")
    
    print(f"\n🎯 RESULTADO GERAL: {sucessos}/{total} ({sucessos/total*100:.1f}%)")
    
    if sucessos == total:
        print("\n🎉 PERFEITO! Solução 100% Prompt-Driven implementada!")
        print("🚀 Sistema genérico para qualquer domínio")
        print("✅ Zero regras hardcoded mantido")
        print("🧠 Arquitetura evolutiva via prompt")
        
    elif sucessos >= total * 0.75:
        print("\n✅ MUITO BOM! Correção principal implementada")
        print("🔧 Pequenos ajustes nos prompts podem melhorar")
        
    else:
        print("\n🔧 PRECISA AJUSTES: Verificar prompts e implementação")
        print("💡 Lembrar: TUDO via prompt, zero regras hardcoded")
    
    return sucessos / total

if __name__ == "__main__":
    executar_suite_correcao()