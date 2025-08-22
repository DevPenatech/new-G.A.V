# gav-autonomo/teste_pipeline_fase5a.py
# Script para testar o pipeline de apresentação da Fase 5a

import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"

def testar_pipeline_apresentacao():
    """Testa o pipeline completo: LLM Selector → API → LLM Apresentador → Conversa"""
    
    print("🚀 TESTANDO PIPELINE DE APRESENTAÇÃO - FASE 5A")
    print("=" * 60)
    
    cenarios_teste = [
        {
            "nome": "Busca com Apresentação - Nescau Barato",
            "mensagem": "quero nescau baratinho",
            "esperado": {
                "tipo_resposta": "apresentacao_busca",
                "deve_conter": ["encontrei", "nescau", "R$", "carrinho"],
                "formato": "conversacional"
            }
        },
        {
            "nome": "Busca com Apresentação - Café",
            "mensagem": "tem café pilão?",
            "esperado": {
                "tipo_resposta": "apresentacao_busca", 
                "deve_conter": ["café", "opções", "R$"],
                "formato": "conversacional"
            }
        },
        {
            "nome": "Operação Carrinho - Visualizar",
            "mensagem": "ver meu carrinho",
            "esperado": {
                "tipo_resposta": "apresentacao_carrinho",
                "deve_conter": ["carrinho", "total", "R$"],
                "formato": "conversacional"
            }
        },
        {
            "nome": "Conversa Direta - Cumprimento",
            "mensagem": "oi, tudo bem?",
            "esperado": {
                "tipo_resposta": "conversacional",
                "deve_conter": ["olá", "ajudar"],
                "formato": "conversacional"
            }
        },
        {
            "nome": "Busca Sem Resultados",
            "mensagem": "quero chocolate importado da suíça",
            "esperado": {
                "tipo_resposta": "apresentacao_busca",
                "deve_conter": ["não encontrei", "opções", "chocolate"],
                "formato": "conversacional"
            }
        }
    ]
    
    resultados = []
    
    for i, cenario in enumerate(cenarios_teste, 1):
        print(f"\n{i}. {cenario['nome']}")
        print("-" * 40)
        print(f"📝 Mensagem: '{cenario['mensagem']}'")
        
        try:
            # Executa teste
            response = requests.post(
                f"{BASE_URL}/chat",
                json={
                    "texto": cenario["mensagem"], 
                    "sessao_id": f"test_pipeline_{datetime.now().strftime('%H%M%S')}"
                },
                timeout=30
            )
            
            if response.status_code == 200:
                resultado = response.json()
                
                # Analisa resultado
                analise = analisar_resposta_conversacional(resultado, cenario["esperado"])
                resultados.append({
                    "cenario": cenario["nome"],
                    "sucesso": analise["sucesso"],
                    "detalhes": analise
                })
                
                # Mostra resultado
                print(f"✅ Status: {response.status_code}")
                print(f"🤖 Resposta: {json.dumps(resultado, indent=2, ensure_ascii=False)}")
                print(f"📊 Análise: {analise['status']}")
                
                if not analise["sucesso"]:
                    print(f"❌ Problemas: {', '.join(analise['problemas'])}")
                
            else:
                print(f"❌ Erro HTTP: {response.status_code}")
                print(f"   {response.text}")
                resultados.append({
                    "cenario": cenario["nome"],
                    "sucesso": False,
                    "detalhes": {"erro": f"HTTP {response.status_code}"}
                })
                
        except Exception as e:
            print(f"❌ Erro na requisição: {e}")
            resultados.append({
                "cenario": cenario["nome"],
                "sucesso": False,
                "detalhes": {"erro": str(e)}
            })
    
    # Relatório final
    print("\n" + "=" * 60)
    print("📊 RELATÓRIO FINAL - PIPELINE DE APRESENTAÇÃO")
    print("=" * 60)
    
    sucessos = len([r for r in resultados if r["sucesso"]])
    total = len(resultados)
    
    print(f"✅ Sucessos: {sucessos}/{total} ({sucessos/total*100:.1f}%)")
    
    if sucessos < total:
        print(f"❌ Falhas:")
        for r in resultados:
            if not r["sucesso"]:
                print(f"   • {r['cenario']}: {r['detalhes'].get('erro', 'Análise falhou')}")
    
    # Recomendações
    print(f"\n🎯 PRÓXIMOS PASSOS:")
    if sucessos == total:
        print("   • ✅ Pipeline funcionando! Avançar para Fase 5a.2")
        print("   • 🎨 Adicionar formatação rica e emojis contextuais")
        print("   • 💡 Implementar sugestões inteligentes")
    else:
        print("   • 🔧 Ajustar prompts que falharam")
        print("   • 🐛 Verificar logs do LLM para debugging")
        print("   • 🧪 Adicionar mais exemplos aos prompts")

def analisar_resposta_conversacional(resultado: dict, esperado: dict) -> dict:
    """Analisa se a resposta está no formato conversacional esperado."""
    
    problemas = []
    
    # Verifica se tem mensagem conversacional
    if "mensagem" not in resultado:
        problemas.append("Sem campo 'mensagem' conversacional")
    
    # Verifica se contém palavras-chave esperadas
    mensagem = resultado.get("mensagem", "").lower()
    for palavra in esperado.get("deve_conter", []):
        if palavra.lower() not in mensagem:
            problemas.append(f"Não contém '{palavra}'")
    
    # Verifica formato conversacional vs JSON técnico
    if resultado.get("resultados") and not resultado.get("mensagem"):
        problemas.append("Retornou JSON técnico em vez de conversa")
    
    # Verifica se tem dados originais (para debugging)
    if "dados_originais" in resultado and not resultado.get("mensagem"):
        problemas.append("Pipeline de apresentação não funcionou")
    
    sucesso = len(problemas) == 0
    
    return {
        "sucesso": sucesso,
        "problemas": problemas,
        "status": "✅ APRESENTAÇÃO OK" if sucesso else "❌ APRESENTAÇÃO FALHOU",
        "tem_mensagem": "mensagem" in resultado,
        "eh_conversacional": bool(resultado.get("mensagem")) and not bool(resultado.get("resultados")),
        "formato_detectado": _detectar_formato_resposta(resultado)
    }

def _detectar_formato_resposta(resultado: dict) -> str:
    """Detecta o formato da resposta para análise."""
    
    if resultado.get("mensagem") and not resultado.get("resultados"):
        return "conversacional"
    elif resultado.get("resultados"):
        return "json_tecnico"
    elif resultado.get("erro"):
        return "erro"
    else:
        return "indefinido"

def testar_componentes_individuais():
    """Testa componentes específicos do pipeline."""
    
    print("\n🔍 TESTANDO COMPONENTES INDIVIDUAIS")
    print("=" * 40)
    
    # Teste 1: Verificar se novos prompts existem
    try:
        response = requests.get(f"http://localhost:8001/admin/prompts/buscar", params={
            "nome": "prompt_apresentador_busca",
            "espaco": "autonomo", 
            "versao": "1"
        })
        if response.status_code == 200:
            print("✅ Prompt apresentador_busca encontrado")
        else:
            print("❌ Prompt apresentador_busca NÃO encontrado")
    except:
        print("❌ Erro ao verificar prompts")
    
    # Teste 2: Verificar schema híbrido
    # (Este teste seria feito no próprio executor)
    print("✅ Schema híbrido: verificar manualmente no executor")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--componentes":
        testar_componentes_individuais()
    else:
        testar_pipeline_apresentacao()