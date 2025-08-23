# gav-autonomo/teste_correcoes_especificas.py
# Testa especificamente os problemas identificados no log

import requests
import json
import time

BASE_URL = "http://localhost:8000"

def teste_problema_1_deteccao_contexto():
    """Testa se LLM Selector detecta contexto COM produtos mostrados anteriormente"""
    
    print("🔍 TESTE PROBLEMA 1: Detecção de Contexto com Busca Anterior")
    print("=" * 60)
    print("📝 Estratégia: Buscar 'nescau' primeiro, depois testar seleções")
    print("   🍫 Nescau tem múltiplas opções: lata 200g, 370g, sachê, etc.")
    
    # Casos de seleção que devem funcionar COM contexto anterior de nescau
    casos_selecao = [
        ("quero o 1", "seleção por número (primeiro nescau)"),
        ("o primeiro", "seleção por posição (primeiro nescau)"), 
        ("ver mais opções", "expansão de resultados (mais nescaus)"),
        ("a lata pequena", "seleção por característica (nescau 200g)")
    ]
    
    sucessos = 0
    total = len(casos_selecao)
    
    for i, (caso, tipo) in enumerate(casos_selecao, 1):
        print(f"\n{i}. Testando {tipo}: '{caso}'")
        
        sessao_teste = f"test_contexto_real_{i}"
        
        try:
            # ETAPA 1: Primeiro fazer busca para ter contexto
            print(f"   🔍 Fazendo busca inicial...")
            response1 = requests.post(f"{BASE_URL}/chat", json={
                "texto": "quero nescau",
                "sessao_id": sessao_teste
            }, timeout=300)
            
            if response1.status_code == 200:
                resultado1 = response1.json()
                mensagem1 = resultado1.get("mensagem", "")
                
                # Verifica se busca retornou produtos numerados
                if "1️⃣" in mensagem1:
                    print(f"   ✅ Busca inicial OK com produtos numerados")
                    
                    # ETAPA 2: Agora testar seleção na MESMA sessão  
                    time.sleep(0.5)  # Pequena pausa
                    print(f"   🎯 Testando seleção na mesma sessão...")
                    
                    response2 = requests.post(f"{BASE_URL}/chat", json={
                        "texto": caso,
                        "sessao_id": sessao_teste  # MESMA sessão!
                    }, timeout=300)
                    
                    if response2.status_code == 200:
                        resultado2 = response2.json()
                        mensagem2 = resultado2.get("mensagem", "").lower()
                        
                        # Verifica se processou seleção corretamente
                        if caso == "ver mais opções":
                            # Para "ver mais" esperamos mais produtos
                            if "mais" in mensagem2 or "opções" in mensagem2 or "4️⃣" in resultado2.get("mensagem", ""):
                                print("   ✅ Expansão de resultados funcionou")
                                sucessos += 1
                            else:
                                print("   ❌ Expansão não funcionou")
                                print(f"      📝 Resposta: {mensagem2[:100]}...")
                        else:
                            # Para seleções esperamos adição ao carrinho
                            if "adicionado" in mensagem2 or "carrinho" in mensagem2:
                                print("   ✅ Seleção funcionou - produto adicionado!")
                                sucessos += 1
                            else:
                                print("   ❌ Seleção não resultou em adição")
                                print(f"      📝 Resposta: {mensagem2[:100]}...")
                    else:
                        print(f"   ❌ Erro na seleção: {response2.status_code}")
                else:
                    print(f"   ❌ Busca inicial não retornou produtos numerados")
                    print(f"      📝 Resposta: {mensagem1[:150]}...")
            else:
                print(f"   ❌ Erro na busca inicial: {response1.status_code}")
                
        except Exception as e:
            print(f"   ❌ Erro: {e}")
    
    print(f"\n📊 Seleção com Contexto: {sucessos}/{total} ({sucessos/total*100:.1f}%)")
    
    if sucessos >= total * 0.75:
        print("✅ PROBLEMA 1 RESOLVIDO: Seleção com contexto funcionando!")
        return True
    else:
        print("❌ PROBLEMA 1 PERSISTE: Fluxo de seleção não funciona")
        return False

def teste_problema_2_numeracao_produtos():
    """Testa se produtos agora aparecem numerados para seleção"""
    
    print("\n🔢 TESTE PROBLEMA 2: Numeração de Produtos")
    print("=" * 45)
    
    produtos_teste = [
        "nescau",
        "café", 
        "chocolate",
        "detergente"
    ]
    
    sucessos = 0
    total = len(produtos_teste)
    
    for i, produto in enumerate(produtos_teste, 1):
        print(f"\n{i}. Testando busca: '{produto}'")
        
        try:
            response = requests.post(f"{BASE_URL}/chat", json={
                "texto": f"quero {produto}",
                "sessao_id": f"test_numeracao_{i}"
            }, timeout=300)
            
            if response.status_code == 200:
                resultado = response.json()
                mensagem = resultado.get("mensagem", "")
                
                # Verifica se tem numeração
                tem_numeracao = "1️⃣" in mensagem and "2️⃣" in mensagem
                tem_ids = "(ID:" in mensagem
                tem_call_to_action = "digite o número" in mensagem.lower() or "qual te interessou" in mensagem.lower()
                
                if tem_numeracao and tem_ids and tem_call_to_action:
                    print("✅ Produtos numerados corretamente")
                    print(f"   📝 Exemplo: {mensagem[:150]}...")
                    sucessos += 1
                else:
                    print("❌ Produtos NÃO numerados adequadamente")
                    print(f"   📝 Numeração: {'✅' if tem_numeracao else '❌'}")
                    print(f"   📝 IDs: {'✅' if tem_ids else '❌'}")  
                    print(f"   📝 Call-to-action: {'✅' if tem_call_to_action else '❌'}")
                    print(f"   📝 Resposta: {mensagem[:200]}...")
                    
            else:
                print(f"❌ Erro HTTP: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Erro: {e}")
    
    print(f"\n📊 Numeração de Produtos: {sucessos}/{total} ({sucessos/total*100:.1f}%)")
    
    if sucessos >= total * 0.8:
        print("✅ PROBLEMA 2 RESOLVIDO: Produtos aparecem numerados!")
        return True
    else:
        print("❌ PROBLEMA 2 PERSISTE: Template de apresentação precisa ajuste")
        return False

def teste_contexto_sem_busca_anterior():
    """Testa se sistema trata adequadamente referências SEM contexto anterior"""
    
    print("\n❓ TESTE ADICIONAL: Referências sem Contexto Anterior")
    print("=" * 55)
    
    # Estes casos DEVEM dar erro ou resposta educativa
    casos_sem_contexto = [
        "quero o 1",
        "id 18136", 
        "ver mais opções",
        "o primeiro"
    ]
    
    sucessos = 0
    total = len(casos_sem_contexto)
    
    print("📝 Testando referências em sessões limpas (sem busca anterior)...")
    
    for i, caso in enumerate(casos_sem_contexto, 1):
        print(f"\n{i}. Testando: '{caso}' (sem contexto)")
        
        try:
            response = requests.post(f"{BASE_URL}/chat", json={
                "texto": caso,
                "sessao_id": f"test_sem_contexto_{i}"  # Sessão nova/limpa
            }, timeout=300)
            
            if response.status_code == 200:
                resultado = response.json()
                mensagem = resultado.get("mensagem", "").lower()
                
                # Verifica se tratou adequadamente a falta de contexto
                tratou_adequadamente = any(indicador in mensagem for indicador in [
                    "não consegui identificar",
                    "não encontrei",
                    "qual item",
                    "pode dar mais detalhes",
                    "não entendi qual",
                    "contexto"
                ])
                
                if tratou_adequadamente:
                    print("   ✅ Tratou adequadamente falta de contexto")
                    sucessos += 1
                else:
                    print("   ❌ Não tratou falta de contexto adequadamente")
                    print(f"      📝 Resposta: {mensagem[:100]}...")
                    
            else:
                print(f"   ❌ Erro HTTP: {response.status_code}")
                
        except Exception as e:
            print(f"   ❌ Erro: {e}")
    
    print(f"\n📊 Tratamento sem Contexto: {sucessos}/{total} ({sucessos/total*100:.1f}%)")
    
    if sucessos >= total * 0.75:
        print("✅ Sistema trata bem referências sem contexto!")
        return True
    else:
        print("❌ Sistema não trata bem falta de contexto")
        return False
    """Testa o fluxo completo: busca numerada → seleção → carrinho"""
    
    print("\n🔄 TESTE: Fluxo Completo Corrigido")
    print("=" * 40)
    
    sessao_teste = f"test_fluxo_completo_{int(time.time())}"
    
    # Etapa 1: Busca deve retornar produtos numerados
    print("1️⃣ Busca inicial...")
    response1 = requests.post(f"{BASE_URL}/chat", json={
        "texto": "quero nescau",
        "sessao_id": sessao_teste
    })
    
    if response1.status_code == 200:
        resultado1 = response1.json()
        mensagem1 = resultado1.get("mensagem", "")
        
        if "1️⃣" in mensagem1:
            print("✅ Produtos numerados encontrados")
            
            # Etapa 2: Tentar seleção por número  
            print("2️⃣ Tentando seleção...")
            time.sleep(1)  # Pequena pausa
            
            response2 = requests.post(f"{BASE_URL}/chat", json={
                "texto": "quero o 1",
                "sessao_id": sessao_teste
            })
            
            if response2.status_code == 200:
                resultado2 = response2.json()
                mensagem2 = resultado2.get("mensagem", "").lower()
                
                if "adicionado" in mensagem2 or "carrinho" in mensagem2:
                    print("✅ Seleção funcionou - item adicionado!")
                    
                    # Etapa 3: Verificar carrinho
                    print("3️⃣ Verificando carrinho...")
                    time.sleep(1)
                    
                    response3 = requests.post(f"{BASE_URL}/chat", json={
                        "texto": "ver meu carrinho", 
                        "sessao_id": sessao_teste
                    })
                    
                    if response3.status_code == 200:
                        resultado3 = response3.json()
                        mensagem3 = resultado3.get("mensagem", "").lower()
                        
                        if "nescau" in mensagem3 and "r$" in mensagem3:
                            print("✅ FLUXO COMPLETO FUNCIONANDO!")
                            print(f"   📝 Carrinho: {resultado3.get('mensagem', '')[:100]}...")
                            return True
                        else:
                            print("❌ Carrinho não mostra item adicionado")
                    else:
                        print(f"❌ Erro ao verificar carrinho: {response3.status_code}")
                else:
                    print("❌ Seleção não funcionou")
                    print(f"   📝 Resposta: {mensagem2[:150]}...")
            else:
                print(f"❌ Erro na seleção: {response2.status_code}")
        else:
            print("❌ Produtos não numerados na busca")
            print(f"   📝 Resposta: {mensagem1[:200]}...")
    else:
        print(f"❌ Erro na busca: {response1.status_code}")
    
    return False

def teste_fluxo_completo_corrigido():
    """Testa o fluxo completo: busca numerada → seleção → carrinho"""
    
    print("\n🔄 TESTE: Fluxo Completo Corrigido")
    print("=" * 40)
    
    sessao_teste = f"test_fluxo_completo_{int(time.time())}"
    
    # Etapa 1: Busca deve retornar produtos numerados
    print("1️⃣ Busca inicial...")
    response1 = requests.post(f"{BASE_URL}/chat", json={
        "texto": "quero nescau",
        "sessao_id": sessao_teste
    })
    
    if response1.status_code == 200:
        resultado1 = response1.json()
        mensagem1 = resultado1.get("mensagem", "")
        
        if "1️⃣" in mensagem1:
            print("✅ Produtos numerados encontrados")
            
            # Etapa 2: Tentar seleção por número  
            print("2️⃣ Tentando seleção...")
            time.sleep(1)  # Pequena pausa
            
            response2 = requests.post(f"{BASE_URL}/chat", json={
                "texto": "quero o 1",
                "sessao_id": sessao_teste
            })
            
            if response2.status_code == 200:
                resultado2 = response2.json()
                mensagem2 = resultado2.get("mensagem", "").lower()
                
                if "adicionado" in mensagem2 or "carrinho" in mensagem2:
                    print("✅ Seleção funcionou - item adicionado!")
                    
                    # Etapa 3: Verificar carrinho
                    print("3️⃣ Verificando carrinho...")
                    time.sleep(1)
                    
                    response3 = requests.post(f"{BASE_URL}/chat", json={
                        "texto": "ver meu carrinho", 
                        "sessao_id": sessao_teste
                    })
                    
                    if response3.status_code == 200:
                        resultado3 = response3.json()
                        mensagem3 = resultado3.get("mensagem", "").lower()
                        
                        if "nescau" in mensagem3 and "r$" in mensagem3:
                            print("✅ FLUXO COMPLETO FUNCIONANDO!")
                            print(f"   📝 Carrinho: {resultado3.get('mensagem', '')[:100]}...")
                            return True
                        else:
                            print("❌ Carrinho não mostra item adicionado")
                    else:
                        print(f"❌ Erro ao verificar carrinho: {response3.status_code}")
                else:
                    print("❌ Seleção não funcionou")
                    print(f"   📝 Resposta: {mensagem2[:150]}...")
            else:
                print(f"❌ Erro na seleção: {response2.status_code}")
        else:
            print("❌ Produtos não numerados na busca")
            print(f"   📝 Resposta: {mensagem1[:200]}...")
    else:
        print(f"❌ Erro na busca: {response1.status_code}")
    
    return False

def executar_testes_correcoes():
    """Executa todos os testes das correções específicas"""
    
    print("🔧 TESTES DAS CORREÇÕES ESPECÍFICAS")
    print("=" * 50)
    
    resultados = {}
    
    # Teste os problemas específicos identificados
    resultados["selecao_com_contexto"] = teste_problema_1_deteccao_contexto()
    resultados["numeracao_produtos"] = teste_problema_2_numeracao_produtos()
    resultados["tratamento_sem_contexto"] = teste_contexto_sem_busca_anterior()
    resultados["fluxo_completo"] = teste_fluxo_completo_corrigido()
    
    # Relatório final
    print("\n" + "=" * 50)
    print("📊 RELATÓRIO FINAL - CORREÇÕES")
    print("=" * 50)
    
    sucessos = sum(resultados.values())
    total = len(resultados)
    
    print(f"✅ Seleção com Contexto: {'FUNCIONANDO' if resultados['selecao_com_contexto'] else 'PROBLEMA'}")
    print(f"✅ Numeração de Produtos: {'FUNCIONANDO' if resultados['numeracao_produtos'] else 'PROBLEMA'}")
    print(f"✅ Tratamento sem Contexto: {'FUNCIONANDO' if resultados['tratamento_sem_contexto'] else 'PROBLEMA'}")
    print(f"✅ Fluxo Completo: {'FUNCIONANDO' if resultados['fluxo_completo'] else 'PROBLEMA'}")
    
    print(f"\n🎯 CORREÇÕES: {sucessos}/{total} aspectos funcionando ({sucessos/total*100:.1f}%)")
    
    if sucessos == total:
        print("\n🎉 SISTEMA DE SELEÇÃO 100% FUNCIONANDO!")
        print("🚀 Fluxo completo: busca → produtos numerados → seleção → carrinho")
        print("✅ Tratamento adequado de casos edge")
        
    elif sucessos >= total * 0.75:
        print("\n✅ SISTEMA MAJORITARIAMENTE FUNCIONANDO!")
        print("🔧 Pequenos ajustes podem melhorar os casos edge")
        
    else:
        print("\n🔧 SISTEMA AINDA PRECISA TRABALHO")
        print("💡 Verificar se SQLs foram executados corretamente")
        print("🔍 Checar logs do LLM para debugging")
    
    return sucessos / total

if __name__ == "__main__":
    executar_testes_correcoes()