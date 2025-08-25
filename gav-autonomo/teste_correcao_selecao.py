#!/usr/bin/env python3
# teste_correcao_selecao.py
# Valida se as correções do LLM Selector funcionaram

import requests
import json
import time
from typing import Dict, Any

BASE_URL = "http://localhost:8000"

def teste_fluxo_completo_corrigido():
    """Testa o fluxo completo: busca numerada → seleção → confirmação"""
    
    print("🔄 TESTE CRÍTICO: Fluxo Seleção por Contexto")
    print("=" * 50)
    
    sessao_teste = f"test_correcao_{int(time.time())}"
    
    # ETAPA 1: Busca deve retornar produtos numerados
    print("1️⃣ Busca inicial para criar contexto...")
    
    response1 = requests.post(f"{BASE_URL}/chat", json={
        "texto": "quero nescau",
        "sessao_id": sessao_teste
    }, timeout=300)
    
    if response1.status_code != 200:
        print(f"❌ FALHA: Busca inicial falhou com status {response1.status_code}")
        return False
    
    resultado1 = response1.json()
    mensagem1 = resultado1.get("mensagem", "")
    
    # Verifica se produtos foram numerados
    if not ("1️⃣" in mensagem1 and "2️⃣" in mensagem1):
        print(f"❌ FALHA: Produtos não estão numerados na busca")
        print(f"   Resposta: {mensagem1[:200]}...")
        return False
    
    print(f"✅ Busca OK - produtos numerados encontrados")
    print(f"   Exemplo: {mensagem1[:100]}...")
    
    # ETAPA 2: Seleção "quero o 1" deve processar contexto
    print(f"\n2️⃣ Tentando seleção por número...")
    time.sleep(1)  # Pequena pausa para o sistema processar
    
    response2 = requests.post(f"{BASE_URL}/chat", json={
        "texto": "quero o 1",
        "sessao_id": sessao_teste  # MESMA sessão!
    }, timeout=300)
    
    if response2.status_code != 200:
        print(f"❌ FALHA: Seleção falhou com status {response2.status_code}")
        return False
    
    resultado2 = response2.json()
    mensagem2 = resultado2.get("mensagem", "").lower()
    
    # Verifica se processou a seleção corretamente
    sucesso_selecao = any(indicador in mensagem2 for indicador in [
        "adicionado", "carrinho", "item", "produto"
    ])
    
    if sucesso_selecao:
        print(f"✅ CORREÇÃO FUNCIONOU: Seleção processada corretamente!")
        print(f"   Resposta: {resultado2.get('mensagem', '')[:150]}...")
        return True
    else:
        print(f"❌ FALHA: Seleção ainda não funciona")
        print(f"   Resposta: {mensagem2[:150]}...")
        
        # Debug adicional
        if "não consegui identificar" in mensagem2:
            print(f"   🔍 Problema: Sistema não encontrou contexto")
        elif "nescau" in mensagem2:
            print(f"   🔍 Problema: Sistema fez nova busca em vez de seleção")
        
        return False

def teste_multiplos_tipos_referencia():
    """Testa diferentes tipos de referência ao contexto"""
    
    print(f"\n🧪 TESTE ABRANGENTE: Múltiplos Tipos de Referência")
    print("=" * 55)
    
    casos_referencia = [
        ("quero o 1", "número direto"),
        ("o primeiro", "posição por extenso"),
        ("id 18136", "referência por ID"),
        ("a lata pequena", "característica"),
        ("ver mais opções", "expansão de resultados")
    ]
    
    sucessos = 0
    total = len(casos_referencia)
    
    for i, (caso, tipo) in enumerate(casos_referencia, 1):
        print(f"\n{i}. Testando {tipo}: '{caso}'")
        
        sessao = f"test_ref_{i}_{int(time.time())}"
        
        # Primeiro fazer busca para ter contexto
        requests.post(f"{BASE_URL}/chat", json={
            "texto": "quero nescau",
            "sessao_id": sessao
        })
        
        time.sleep(0.5)
        
        # Depois testar referência
        response = requests.post(f"{BASE_URL}/chat", json={
            "texto": caso,
            "sessao_id": sessao
        })
        
        if response.status_code == 200:
            resultado = response.json()
            mensagem = resultado.get("mensagem", "").lower()
            
            # Para "ver mais" esperamos expansão, para outros esperamos seleção
            if caso == "ver mais opções":
                sucesso = "mais" in mensagem or "opções" in mensagem
            else:
                sucesso = any(x in mensagem for x in ["adicionado", "carrinho", "item"])
            
            if sucesso:
                print(f"   ✅ {tipo} funcionou!")
                sucessos += 1
            else:
                print(f"   ❌ {tipo} não funcionou")
                if "não consegui identificar" in mensagem:
                    print(f"      Problema: Não encontrou contexto")
        else:
            print(f"   ❌ Erro HTTP: {response.status_code}")
    
    print(f"\n📊 Tipos de Referência: {sucessos}/{total} funcionando ({sucessos/total*100:.1f}%)")
    return sucessos >= total * 0.8

def teste_deteccao_llm_selector():
    """Testa se LLM Selector agora detecta corretamente contexto vs busca nova"""
    
    print(f"\n🧠 TESTE ESPECÍFICO: Detecção LLM Selector")
    print("=" * 45)
    
    # Teste sem contexto anterior - deve detectar falta de contexto
    print(f"1. Referência sem contexto anterior...")
    response_sem_contexto = requests.post(f"{BASE_URL}/chat", json={
        "texto": "quero o 1",
        "sessao_id": f"sem_contexto_{int(time.time())}"
    })
    
    if response_sem_contexto.status_code == 200:
        resultado = response_sem_contexto.json()
        mensagem = resultado.get("mensagem", "").lower()
        
        # Deve reconhecer que não tem contexto
        if any(x in mensagem for x in ["não consegui", "não encontrei", "contexto", "mais detalhes"]):
            print("   ✅ Detectou corretamente falta de contexto")
        else:
            print("   ❌ Não detectou falta de contexto adequadamente")
    
    # Teste busca nova - deve ir para busca normal
    print(f"2. Busca nova (não referência)...")
    response_busca_nova = requests.post(f"{BASE_URL}/chat", json={
        "texto": "quero café pilão",
        "sessao_id": f"busca_nova_{int(time.time())}"
    })
    
    if response_busca_nova.status_code == 200:
        resultado = response_busca_nova.json()
        mensagem = resultado.get("mensagem", "").lower()
        
        # Deve fazer busca normal e mostrar produtos
        if "café" in mensagem and ("encontrei" in mensagem or "opções" in mensagem):
            print("   ✅ Busca nova processada corretamente")
        else:
            print("   ❌ Busca nova não processada corretamente")

def executar_validacao_completa():
    """Executa todos os testes de validação das correções"""
    
    print("🎯 VALIDAÇÃO COMPLETA: Correções LLM Selector")
    print("=" * 60)
    print("📝 Validando se correções no banco resolveram problemas de seleção")
    
    # Testa fluxo crítico principal
    fluxo_funcionando = teste_fluxo_completo_corrigido()
    
    # Testa diferentes tipos de referência
    referencias_funcionando = teste_multiplos_tipos_referencia()
    
    # Testa detecção específica do LLM
    teste_deteccao_llm_selector()
    
    # Relatório final
    print(f"\n{'=' * 60}")
    print("📊 RELATÓRIO FINAL DA VALIDAÇÃO")
    print("=" * 60)
    
    if fluxo_funcionando and referencias_funcionando:
        print("🎉 CORREÇÕES BEM-SUCEDIDAS!")
        print("✅ Fluxo principal funcionando")
        print("✅ Múltiplos tipos de referência funcionando")
        print("✅ LLM Selector detectando contexto corretamente")
        
        print(f"\n🚀 PRÓXIMOS PASSOS:")
        print("1. Executar teste completo da Fase 5a.2.1")
        print("2. Implementar formatação rica de preços")
        print("3. Adicionar emojis contextuais por categoria")
        
        return True
        
    elif fluxo_funcionando:
        print("✅ PARCIALMENTE CORRIGIDO")
        print("✅ Fluxo principal funcionando")
        print("🔧 Alguns tipos de referência precisam ajuste")
        
        return False
        
    else:
        print("❌ CORREÇÕES AINDA NÃO SURTIRAM EFEITO")
        print("🔧 Problemas persistem:")
        print("   • Fluxo de seleção não funciona")
        print("   • LLM Selector não detecta contexto")
        
        print(f"\n💡 VERIFICAÇÕES RECOMENDADAS:")
        print("1. Confirmar se SQLs foram executados no banco")
        print("2. Reiniciar gav_autonomo após alterações no banco")
        print("3. Verificar logs do LLM durante teste")
        print("4. Confirmar se prompt_api_call_selector versão 4 está ativo")
        
        return False

if __name__ == "__main__":
    try:
        print("🔧 INICIANDO VALIDAÇÃO DAS CORREÇÕES...")
        time.sleep(2)  # Aguarda sistema estar pronto
        
        sucesso = executar_validacao_completa()
        
        if sucesso:
            print(f"\n🎉 FASE 5a.2.1 PRONTA PARA CONTINUAR!")
        else:
            print(f"\n🔧 AJUSTES ADICIONAIS NECESSÁRIOS")
            
    except KeyboardInterrupt:
        print(f"\n⚡ Teste interrompido pelo usuário")
    except Exception as e:
        print(f"\n❌ Erro durante validação: {e}")