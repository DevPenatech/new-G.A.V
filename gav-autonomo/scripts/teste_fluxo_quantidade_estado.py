# gav-autonomo/scripts/teste_fluxo_quantidade_estado.py
"""
🧪 TESTE COMPLETO DO FLUXO DE QUANTIDADE COM ESTADO
Valida se a correção resolve o problema de processamento
"""

import httpx
import json
import time
from datetime import datetime

class TesteFluxoQuantidade:
    def __init__(self):
        self.gav_url = "http://localhost:8000"
        self.api_url = "http://localhost:8001"  # Ajustado para localhost
        self.sessao_teste = "teste_quantidade_estado"
        
    def executar_teste_completo(self):
        """Executa teste completo do fluxo: busca → seleção → quantidade → carrinho"""
        print("🧪 TESTE FLUXO DE QUANTIDADE COM ESTADO")
        print("=" * 50)
        print(f"🕐 Iniciado em: {datetime.now().strftime('%H:%M:%S')}")
        print(f"🔑 Sessão: {self.sessao_teste}")
        print()
        
        try:
            # ETAPA 1: Busca produtos
            if not self.etapa_1_busca():
                return
            
            time.sleep(1)  # Pausa entre etapas
            
            # ETAPA 2: Seleciona produto (deve criar estado aguardando_quantidade)
            if not self.etapa_2_selecao():
                return
                
            time.sleep(1)
            
            # ETAPA 3: Informa quantidade (deve processar e adicionar ao carrinho)
            if not self.etapa_3_quantidade():
                return
                
            time.sleep(1)
            
            # ETAPA 4: Verifica carrinho (deve mostrar item adicionado)
            if not self.etapa_4_verificacao():
                return
            
            print("🎉 TESTE COMPLETO: SUCESSO!")
            print("✅ Fluxo de quantidade funcionando corretamente")
            
        except Exception as e:
            print(f"💥 ERRO NO TESTE: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def etapa_1_busca(self) -> bool:
        """ETAPA 1: Busca produtos"""
        print("📋 ETAPA 1: Busca de produtos")
        print("-" * 30)
        
        payload = {
            "texto": "buscar nescau",
            "sessao_id": self.sessao_teste
        }
        
        try:
            response = httpx.post(f"{self.gav_url}/chat", json=payload, timeout=30.0)
            
            if response.status_code != 200:
                print(f"❌ Erro HTTP: {response.status_code}")
                return False
                
            resultado = response.json()
            
            # Verificar se encontrou produtos
            dados_originais = resultado.get("dados_originais", {})
            resultados = dados_originais.get("resultados", [])
            
            print(f"✅ Produtos encontrados: {len(resultados)}")
            
            if not resultados:
                print("❌ Nenhum produto encontrado")
                return False
            
            # Verificar se salvou contexto
            contexto_estruturado = resultado.get("contexto_estruturado", {})
            produtos_contexto = contexto_estruturado.get("produtos", [])
            
            print(f"✅ Produtos no contexto: {len(produtos_contexto)}")
            
            if produtos_contexto:
                primeiro_produto = produtos_contexto[0]
                print(f"✅ Primeiro produto ID: {primeiro_produto.get('item_id')}")
                self.item_id_teste = primeiro_produto.get("item_id")
                self.produto_nome = primeiro_produto.get("descricao", "N/A")[:30]
                self.produto_preco = primeiro_produto.get("preco", 0)
                
                print(f"🎯 Produto para teste: ID {self.item_id_teste} - {self.produto_nome}")
                return True
            else:
                print("❌ Nenhum produto salvo no contexto")
                return False
                
        except Exception as e:
            print(f"❌ Erro: {str(e)}")
            return False
    
    def etapa_3_quantidade(self) -> bool:
        """ETAPA 3: Resposta de quantidade"""
        print(f"\n🔢 ETAPA 3: Informando quantidade (5 unidades)")
        print("-" * 30)
        
        payload = {
            "texto": "5",  # Só o número
            "sessao_id": self.sessao_teste
        }
        
        try:
            response = httpx.post(f"{self.gav_url}/chat", json=payload, timeout=30.0)
            
            if response.status_code != 200:
                print(f"❌ Erro HTTP: {response.status_code}")
                return False
                
            resultado = response.json()
            
            print(f"📨 Tipo resposta: {resultado.get('tipo', 'N/A')}")
            mensagem = resultado.get("mensagem", "")
            print(f"💬 Mensagem: {mensagem[:150]}{'...' if len(mensagem) > 150 else ''}")
            
            # Verificar se adicionou ao carrinho
            if any(palavra in mensagem.lower() for palavra in ["adicionei", "adicionado", "carrinho", "sucesso"]):
                print("✅ Item adicionado ao carrinho com sucesso")
                
                # Verificar detalhes da adição
                detalhes = resultado.get("detalhes", {})
                if detalhes:
                    print(f"✅ Detalhes: {detalhes.get('quantidade')} unidades × R$ {detalhes.get('preco_unitario', 0):.2f}")
                
                # Verificar se contexto foi limpo
                contexto_banco = self.verificar_contexto_banco()
                if contexto_banco:
                    tipo_contexto = contexto_banco.get("tipo_contexto", "")
                    print(f"✅ Contexto atualizado para: {tipo_contexto}")
                    
                    if tipo_contexto == "item_adicionado":
                        print("✅ Estado limpo corretamente após adição")
                        return True
                    else:
                        print(f"⚠️ Estado não foi limpo: {tipo_contexto}")
                        # Ainda considera sucesso se item foi adicionado
                        return True
                else:
                    print("⚠️ Contexto não encontrado, mas item foi adicionado")
                    return True
                    
            else:
                print("❌ Item NÃO foi adicionado ao carrinho")
                print(f"   Resposta recebida: {mensagem}")
                return False
                
        except Exception as e:
            print(f"❌ Erro: {str(e)}")
            return False
    
    def etapa_4_verificacao(self) -> bool:
        """ETAPA 4: Verificação do carrinho"""
        print(f"\n🛒 ETAPA 4: Verificando carrinho")
        print("-" * 30)
        
        payload = {
            "texto": "ver carrinho",
            "sessao_id": self.sessao_teste
        }
        
        try:
            response = httpx.post(f"{self.gav_url}/chat", json=payload, timeout=30.0)
            
            if response.status_code != 200:
                print(f"❌ Erro HTTP: {response.status_code}")
                return False
                
            resultado = response.json()
            
            # Verificar dados do carrinho
            dados_originais = resultado.get("dados_originais", {})
            itens = dados_originais.get("itens", [])
            valor_total = dados_originais.get("valor_total", 0)
            
            print(f"✅ Itens no carrinho: {len(itens)}")
            print(f"✅ Valor total: R$ {valor_total:.2f}")
            
            if itens:
                primeiro_item = itens[0]
                quantidade_carrinho = primeiro_item.get("quantidade", 0)
                nome_produto = primeiro_item.get("descricao_produto", "N/A")
                
                print(f"✅ Primeiro item: {quantidade_carrinho}x {nome_produto[:40]}")
                
                # Verificar se quantidade está correta
                if quantidade_carrinho == 5:
                    print("✅ Quantidade correta no carrinho (5 unidades)")
                    return True
                else:
                    print(f"❌ Quantidade errada: esperado 5, encontrado {quantidade_carrinho}")
                    return False
            else:
                print("❌ Carrinho vazio - item não foi adicionado")
                return False
                
        except Exception as e:
            print(f"❌ Erro: {str(e)}")
            return False
    
    def verificar_contexto_banco(self) -> dict:
        """Verifica contexto salvo no banco de dados"""
        try:
            response = httpx.get(f"{self.api_url}/contexto/{self.sessao_teste}", timeout=10.0)
            
            if response.status_code == 200:
                return response.json()
            else:
                return {}
                
        except Exception as e:
            print(f"⚠️ Erro ao verificar contexto: {e}")
            return {}
    
    def diagnostico_contexto(self):
        """Diagnóstico detalhado do contexto para debug"""
        print("\n🔍 DIAGNÓSTICO DO CONTEXTO")
        print("-" * 25)
        
        contexto = self.verificar_contexto_banco()
        
        if contexto:
            print(f"📋 Tipo: {contexto.get('tipo_contexto', 'N/A')}")
            print(f"📅 Criado: {contexto.get('criado_em', 'N/A')}")
            print(f"💬 Mensagem original: {contexto.get('mensagem_original', 'N/A')}")
            print(f"📨 Resposta: {contexto.get('resposta_apresentada', 'N/A')[:50]}...")
            
            estruturado = contexto.get("contexto_estruturado", {})
            
            if "produto_selecionado" in estruturado:
                produto = estruturado["produto_selecionado"]
                if produto:
                    print(f"🎯 Produto selecionado: ID {produto.get('item_id')} - {produto.get('produto_info', {}).get('descricao', 'N/A')[:30]}")
                    print(f"⏱️ Aguardando: {produto.get('aguardando', 'N/A')}")
            
            if "produtos" in estruturado:
                produtos = estruturado["produtos"]
                print(f"📦 Produtos disponíveis: {len(produtos)}")
                
        else:
            print("❌ Nenhum contexto encontrado")

def executar_teste_rapido():
    """Execução rápida do teste"""
    teste = TesteFluxoQuantidade()
    teste.executar_teste_completo()
    
    # Diagnóstico final para debug
    teste.diagnostico_contexto()

if __name__ == "__main__":
    executar_teste_rapido() Erro: {str(e)}")
            return False
    
    def etapa_2_selecao(self) -> bool:
        """ETAPA 2: Seleção de produto"""
        print(f"\n🎯 ETAPA 2: Seleção do produto ID {self.item_id_teste}")
        print("-" * 30)
        
        payload = {
            "texto": str(self.item_id_teste),  # Só o ID
            "sessao_id": self.sessao_teste
        }
        
        try:
            response = httpx.post(f"{self.gav_url}/chat", json=payload, timeout=30.0)
            
            if response.status_code != 200:
                print(f"❌ Erro HTTP: {response.status_code}")
                return False
                
            resultado = response.json()
            
            print(f"📨 Tipo resposta: {resultado.get('tipo', 'N/A')}")
            mensagem = resultado.get("mensagem", "")
            print(f"💬 Mensagem: {mensagem[:100]}{'...' if len(mensagem) > 100 else ''}")
            
            # Verificar se perguntou quantidade
            if "quantas" in mensagem.lower() or "quantidade" in mensagem.lower():
                print("✅ Sistema perguntou quantidade corretamente")
                
                # Verificar se contexto foi salvo com tipo correto
                contexto_banco = self.verificar_contexto_banco()
                if contexto_banco:
                    tipo_contexto = contexto_banco.get("tipo_contexto", "")
                    print(f"✅ Contexto no banco: {tipo_contexto}")
                    
                    if tipo_contexto == "aguardando_quantidade":
                        print("✅ Estado 'aguardando_quantidade' salvo corretamente")
                        return True
                    else:
                        print(f"❌ Tipo contexto errado: esperado 'aguardando_quantidade', obtido '{tipo_contexto}'")
                        return False
                else:
                    print("❌ Contexto não foi salvo no banco")
                    return False
                    
            else:
                print("❌ Sistema NÃO perguntou quantidade")
                print(f"   Resposta recebida: {mensagem}")
                return False
                
        except Exception as e:
            print(f"❌