# gav-autonomo/scripts/debug_apresentacao_llm.py
"""
Debug específico do LLM de apresentação
Testa isoladamente para identificar onde está falhando
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.adaptadores.cliente_negocio import obter_prompt_por_nome, listar_exemplos_prompt
from app.adaptadores.interface_llm import completar_para_json
import json
import time

def testar_apresentacao_llm():
    """Testa especificamente o LLM de apresentação"""
    print("🎨 TESTE ESPECÍFICO DO LLM DE APRESENTAÇÃO")
    print("=" * 50)
    
    # Dados reais que falharam
    dados_teste = {
        "query_original": "quero nescau",
        "resultados_json": {
            "resultados": [
                {
                    "id": 9089,
                    "codprod": 63930,
                    "descricao": "ACHOC.PO NESCAU LT. 1X200G",
                    "descricaoweb": "ACHOCOLATADO PÓ NESCAU LATA 200G",
                    "marca": "NESCAU",
                    "itens": [
                        {"id": 18135, "unidade": "LT", "qtunit": 1, "pvenda": 6.79, "poferta": 6.79},
                        {"id": 18136, "unidade": "CX", "qtunit": 24, "pvenda": 162.96, "poferta": 158.07}
                    ]
                }
            ],
            "status_busca": "sucesso"
        },
        "total_encontrados": 1
    }
    
    try:
        print("🔍 Buscando prompt de apresentação...")
        p_apresentador = obter_prompt_por_nome(
            nome="prompt_apresentador_busca", 
            espaco="autonomo", 
            versao=1
        )
        print(f"✅ Prompt encontrado - Tamanho: {len(p_apresentador['template'])} chars")
        
        exemplos_apresentador = listar_exemplos_prompt(p_apresentador["id"])
        print(f"✅ Exemplos encontrados: {len(exemplos_apresentador)}")
        
        # Montar contexto exatamente como no sistema real
        contexto_apresentacao = f"""query_original: "{dados_teste['query_original']}"
resultados_json: {json.dumps(dados_teste['resultados_json'], ensure_ascii=False)}
status_busca: "sucesso"
total_encontrados: {dados_teste['total_encontrados']}"""
        
        print(f"📝 Contexto montado - Tamanho: {len(contexto_apresentacao)} chars")
        print(f"📝 Primeiros 200 chars: {contexto_apresentacao[:200]}...")
        
        print("\n🤖 Executando LLM de apresentação...")
        inicio = time.time()
        
        # Testar com timeout menor para detectar problemas
        resposta_conversacional = completar_para_json(
            sistema=p_apresentador["template"],
            entrada_usuario=contexto_apresentacao,
            exemplos=exemplos_apresentador[:2]  # Limitar exemplos para evitar timeout
        )
        
        tempo_execucao = time.time() - inicio
        print(f"⏱️ Tempo execução: {tempo_execucao:.2f}s")
        
        print("\n✅ RESULTADO DO LLM:")
        print("=" * 30)
        print(f"Tipo resposta: {type(resposta_conversacional)}")
        print(f"Keys: {list(resposta_conversacional.keys()) if isinstance(resposta_conversacional, dict) else 'N/A'}")
        
        if isinstance(resposta_conversacional, dict):
            mensagem = resposta_conversacional.get("mensagem", "SEM MENSAGEM")
            print(f"Mensagem: {mensagem[:200]}{'...' if len(mensagem) > 200 else ''}")
            
            contexto = resposta_conversacional.get("contexto_estruturado", {})
            produtos = contexto.get("produtos", []) if isinstance(contexto, dict) else []
            print(f"Produtos no contexto: {len(produtos)}")
            
            if produtos:
                print("Primeiros 3 produtos:")
                for i, produto in enumerate(produtos[:3]):
                    print(f"  {i+1}. ID: {produto.get('item_id', 'N/A')} - {produto.get('descricao', 'N/A')[:50]}")
        
        print("\n📊 ANÁLISE:")
        if resposta_conversacional.get("mensagem", "") != "Ops, não consegui processar isso...":
            print("✅ LLM funcionou corretamente!")
        else:
            print("❌ LLM retornou mensagem de erro genérica")
            
        return resposta_conversacional
        
    except Exception as e:
        print(f"❌ ERRO NO TESTE: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def testar_com_dados_simples():
    """Teste com dados mais simples para comparar"""
    print("\n🧪 TESTE COM DADOS SIMPLES")
    print("=" * 30)
    
    dados_simples = {
        "query_original": "nescau",
        "resultados_json": {
            "resultados": [
                {
                    "id": 1,
                    "descricao": "NESCAU 200G",
                    "itens": [
                        {"id": 100, "pvenda": 6.79, "unidade": "UN", "qtunit": 1}
                    ]
                }
            ]
        }
    }
    
    contexto_simples = f"""query_original: "{dados_simples['query_original']}"
resultados_json: {json.dumps(dados_simples['resultados_json'], ensure_ascii=False)}
status_busca: "sucesso"
total_encontrados: 1"""
    
    try:
        p_apresentador = obter_prompt_por_nome(nome="prompt_apresentador_busca", espaco="autonomo", versao=1)
        exemplos_apresentador = listar_exemplos_prompt(p_apresentador["id"])
        
        inicio = time.time()
        resposta = completar_para_json(
            sistema=p_apresentador["template"],
            entrada_usuario=contexto_simples,
            exemplos=exemplos_apresentador[:1]  # Só 1 exemplo
        )
        tempo = time.time() - inicio
        
        print(f"⏱️ Tempo: {tempo:.2f}s")
        print(f"✅ Mensagem: {resposta.get('mensagem', 'SEM MENSAGEM')[:100]}...")
        
        return tempo < 30  # Considera sucesso se menos de 30s
        
    except Exception as e:
        print(f"❌ Erro: {str(e)}")
        return False

if __name__ == "__main__":
    # Teste principal
    resultado_complexo = testar_apresentacao_llm()
    
    # Teste simples para comparação
    sucesso_simples = testar_com_dados_simples()
    
    print(f"\n🏁 CONCLUSÃO:")
    print(f"Dados complexos: {'✅ OK' if resultado_complexo else '❌ FALHOU'}")
    print(f"Dados simples: {'✅ OK' if sucesso_simples else '❌ FALHOU'}")
    
    if not resultado_complexo and sucesso_simples:
        print("🔍 PROBLEMA: Volume de dados está causando timeout/falha")
        print("💡 SOLUÇÃO: Simplificar template ou reduzir dados enviados")
    elif not sucesso_simples:
        print("🔍 PROBLEMA: Template ou prompt está com erro")
        print("💡 SOLUÇÃO: Revisar template e exemplos")