# gav-autonomo/scripts/teste_casos_reais.py
"""
🧪 TESTE DE CASOS REAIS COM LLM
Testa os casos problemáticos com o LLM real para ver onde está falhando
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import httpx
import json
import time
from datetime import datetime
from app.config.settings import config

class TestadorCasosReais:
    def __init__(self):
        self.api_url = config.API_NEGOCIO_URL.rstrip("/")
        self.gav_url = "http://localhost:8000"  # GAV autônomo
        self.casos_teste = [
            {
                "nome": "Busca Normal",
                "mensagem": "buscar coca cola",
                "sessao": "teste_normal",
                "esperado": "lista de produtos coca cola"
            },
            {
                "nome": "Busca Mais Barato", 
                "mensagem": "buscar coca cola mais barato",
                "sessao": "teste_barato",
                "esperado": "produtos ordenados por preço"
            },
            {
                "nome": "Busca Oferta",
                "mensagem": "buscar nescau em oferta", 
                "sessao": "teste_oferta",
                "esperado": "produtos em promoção"
            },
            {
                "nome": "Ver Carrinho Vazio",
                "mensagem": "ver meu carrinho",
                "sessao": "teste_carrinho_vazio", 
                "esperado": "mensagem carrinho vazio"
            },
            {
                "nome": "Adicionar Item",
                "mensagem": "adicionar ID 18135 ao carrinho",
                "sessao": "teste_adicionar",
                "esperado": "confirmação item adicionado"
            },
            {
                "nome": "Ver Carrinho Com Item",
                "mensagem": "ver carrinho",
                "sessao": "teste_carrinho_cheio",
                "esperado": "lista de itens no carrinho"
            }
        ]
        
    def executar_testes_completos(self):
        """Executa todos os testes com LLM real"""
        print("🧪 TESTE DE CASOS REAIS COM LLM")
        print("=" * 50)
        print(f"🕐 Executado em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🤖 GAV URL: {self.gav_url}")
        print()
        
        resultados = []
        
        for i, caso in enumerate(self.casos_teste, 1):
            print(f"🎯 TESTE {i}/{len(self.casos_teste)}: {caso['nome']}")
            print(f"   📝 Mensagem: '{caso['mensagem']}'")
            print(f"   🔑 Sessão: {caso['sessao']}")
            print(f"   🎯 Esperado: {caso['esperado']}")
            
            resultado = self.executar_caso_teste(caso)
            resultados.append(resultado)
            
            print()
            time.sleep(1)  # Pausa entre testes
        
        # Relatório final
        self.gerar_relatorio_testes(resultados)
        
    def executar_caso_teste(self, caso):
        """Executa um caso de teste específico"""
        inicio = time.time()
        
        try:
            # Fazer requisição real para o GAV
            payload = {
                "texto": caso["mensagem"],
                "sessao_id": caso["sessao"]
            }
            
            print(f"   🚀 Enviando para GAV...")
            
            response = httpx.post(
                f"{self.gav_url}/chat",
                json=payload,
                timeout=30.0
            )
            
            tempo_total = time.time() - inicio
            
            if response.status_code == 200:
                resultado_json = response.json()
                
                # Analisar resposta
                analise = self.analisar_resposta(caso, resultado_json)
                
                print(f"   ✅ Sucesso ({tempo_total:.2f}s)")
                print(f"   📊 Análise: {analise['status']}")
                print(f"   💬 Mensagem: {analise['mensagem'][:100]}{'...' if len(analise['mensagem']) > 100 else ''}")
                
                if analise['debug_timing']:
                    print(f"   ⏱️ Timing: {analise['debug_timing']}")
                
                return {
                    "caso": caso["nome"],
                    "status": "sucesso",
                    "tempo": tempo_total,
                    "analise": analise,
                    "resposta_completa": resultado_json
                }
                
            else:
                print(f"   ❌ Erro HTTP {response.status_code}")
                print(f"   📄 Resposta: {response.text[:200]}")
                
                return {
                    "caso": caso["nome"],
                    "status": "erro_http",
                    "erro": f"HTTP {response.status_code}",
                    "tempo": tempo_total
                }
                
        except httpx.TimeoutException:
            tempo_total = time.time() - inicio
            print(f"   ⏰ Timeout ({tempo_total:.2f}s)")
            
            return {
                "caso": caso["nome"], 
                "status": "timeout",
                "tempo": tempo_total
            }
            
        except Exception as e:
            tempo_total = time.time() - inicio
            print(f"   💥 Erro: {str(e)}")
            
            return {
                "caso": caso["nome"],
                "status": "erro",
                "erro": str(e),
                "tempo": tempo_total
            }
    
    def analisar_resposta(self, caso, resposta):
        """Analisa se a resposta está correta"""
        analise = {
            "status": "indefinido",
            "mensagem": "",
            "tem_dados": False,
            "debug_timing": None,
            "problemas": []
        }
        
        # Extrair mensagem da resposta
        mensagem = resposta.get("mensagem", "")
        dados_originais = resposta.get("dados_originais", {})
        debug_timing = resposta.get("_debug_timing", {})
        
        analise["mensagem"] = mensagem
        analise["debug_timing"] = debug_timing.get("tempo_total_segundos", "N/A")
        
        # Verificar se tem dados
        if dados_originais:
            analise["tem_dados"] = True
        
        # Análise específica por tipo de caso
        caso_nome = caso["nome"].lower()
        
        if "busca" in caso_nome:
            self.analisar_busca(caso, resposta, analise)
        elif "carrinho" in caso_nome:
            self.analisar_carrinho(caso, resposta, analise)
        elif "adicionar" in caso_nome:
            self.analisar_adicao(caso, resposta, analise)
        
        return analise
    
    def analisar_busca(self, caso, resposta, analise):
        """Analisa resposta de busca"""
        mensagem = resposta.get("mensagem", "").lower()
        dados = resposta.get("dados_originais", {})
        
        # Verificar se encontrou produtos
        resultados = dados.get("resultados", [])
        
        if not resultados:
            analise["status"] = "problema_sem_produtos"
            analise["problemas"].append("Nenhum produto encontrado")
            return
        
        # Busca normal
        if caso["nome"] == "Busca Normal":
            if "coca" in mensagem:
                analise["status"] = "ok"
            else:
                analise["status"] = "problema_apresentacao"
                analise["problemas"].append("Mensagem não menciona coca cola")
        
        # Busca mais barato
        elif "barato" in caso["nome"].lower():
            if "barato" in mensagem or "preço" in mensagem or "menor" in mensagem:
                analise["status"] = "ok"
                
                # Verificar se está realmente ordenado por preço
                precos = []
                for produto in resultados:
                    for item in produto.get("itens", []):
                        preco = item.get("pvenda") or item.get("poferta")
                        if preco and preco > 1:  # Ignorar preços R$ 1,00 (placeholder)
                            precos.append(float(preco))
                
                if len(precos) > 1:
                    ordenado_crescente = precos == sorted(precos)
                    if not ordenado_crescente:
                        analise["problemas"].append("Produtos não estão ordenados por preço crescente")
                
            else:
                analise["status"] = "problema_apresentacao" 
                analise["problemas"].append("Mensagem não menciona que é mais barato")
        
        # Busca oferta
        elif "oferta" in caso["nome"].lower():
            if "oferta" in mensagem or "promoção" in mensagem or "desconto" in mensagem:
                analise["status"] = "ok"
                
                # Verificar se há produtos com poferta diferente de pvenda
                tem_oferta = False
                for produto in resultados:
                    for item in produto.get("itens", []):
                        pvenda = item.get("pvenda")
                        poferta = item.get("poferta") 
                        if poferta and pvenda and poferta < pvenda:
                            tem_oferta = True
                            break
                
                if not tem_oferta:
                    analise["problemas"].append("Nenhum produto com preço de oferta encontrado")
            else:
                analise["status"] = "problema_apresentacao"
                analise["problemas"].append("Mensagem não menciona ofertas")
    
    def analisar_carrinho(self, caso, resposta, analise):
        """Analisa resposta de carrinho"""
        mensagem = resposta.get("mensagem", "").lower() 
        dados = resposta.get("dados_originais", {})
        
        itens = dados.get("itens", [])
        
        if "vazio" in caso["nome"].lower():
            if not itens:
                if "vazio" in mensagem or "nenhum" in mensagem or "não tem" in mensagem:
                    analise["status"] = "ok"
                else:
                    analise["status"] = "problema_apresentacao"
                    analise["problemas"].append("Mensagem não indica carrinho vazio claramente")
            else:
                analise["status"] = "problema_dados"
                analise["problemas"].append("Carrinho deveria estar vazio mas tem itens")
        
        elif "cheio" in caso["nome"].lower() or "item" in caso["nome"].lower():
            if itens:
                if any(word in mensagem for word in ["item", "produto", "carrinho", "total"]):
                    analise["status"] = "ok"
                else:
                    analise["status"] = "problema_apresentacao"
                    analise["problemas"].append("Mensagem não lista itens do carrinho")
            else:
                analise["status"] = "problema_dados"
                analise["problemas"].append("Carrinho deveria ter itens")
    
    def analisar_adicao(self, caso, resposta, analise):
        """Analisa resposta de adição ao carrinho"""
        mensagem = resposta.get("mensagem", "").lower()
        
        if "adicionado" in mensagem or "carrinho" in mensagem or "sucesso" in mensagem:
            analise["status"] = "ok"
        else:
            analise["status"] = "problema_apresentacao"
            analise["problemas"].append("Mensagem não confirma adição ao carrinho")
    
    def gerar_relatorio_testes(self, resultados):
        """Gera relatório final dos testes"""
        print("📊 RELATÓRIO FINAL DOS TESTES")
        print("=" * 50)
        
        sucessos = [r for r in resultados if r.get("status") == "sucesso"]
        erros = [r for r in resultados if r.get("status") != "sucesso"]
        
        print(f"✅ Testes bem-sucedidos: {len(sucessos)}/{len(resultados)}")
        print(f"❌ Testes com problema: {len(erros)}")
        
        if sucessos:
            print("\n✅ CASOS QUE FUNCIONARAM:")
            for resultado in sucessos:
                analise = resultado.get("analise", {})
                status_analise = analise.get("status", "?")
                tempo = resultado.get("tempo", 0)
                
                emoji = "✅" if status_analise == "ok" else "⚠️"
                print(f"   {emoji} {resultado['caso']}: {status_analise} ({tempo:.1f}s)")
                
                if analise.get("problemas"):
                    for problema in analise["problemas"]:
                        print(f"      ⚠️ {problema}")
        
        if erros:
            print("\n❌ CASOS COM PROBLEMAS:")
            for resultado in erros:
                print(f"   ❌ {resultado['caso']}: {resultado['status']}")
                if resultado.get("erro"):
                    print(f"      💥 {resultado['erro']}")
        
        # Análise de performance
        tempos = [r.get("tempo", 0) for r in sucessos]
        if tempos:
            tempo_medio = sum(tempos) / len(tempos)
            tempo_max = max(tempos)
            print(f"\n⏱️ PERFORMANCE:")
            print(f"   📊 Tempo médio: {tempo_medio:.2f}s")
            print(f"   📊 Tempo máximo: {tempo_max:.2f}s")
        
        print()
        print("🏁 TESTE COMPLETO FINALIZADO!")
        
        # Salvar resultados
        self.salvar_resultados_arquivo(resultados)
    
    def salvar_resultados_arquivo(self, resultados):
        """Salva resultados detalhados em arquivo"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"teste_casos_reais_{timestamp}.json"
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump({
                    "timestamp": datetime.now().isoformat(),
                    "total_testes": len(resultados),
                    "resultados": resultados
                }, f, ensure_ascii=False, indent=2)
            
            print(f"💾 Resultados salvos em: {filename}")
            
        except Exception as e:
            print(f"⚠️ Erro ao salvar: {str(e)}")

if __name__ == "__main__":
    testador = TestadorCasosReais()
    testador.executar_testes_completos()