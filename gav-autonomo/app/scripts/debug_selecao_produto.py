#!/usr/bin/env python3
# gav-autonomo/scripts/debug_selecao_produto.py
"""
🔍 DEBUG - ERRO 404 NA SELEÇÃO DE PRODUTO
Identifica onde está falhando o fluxo de seleção
"""

import requests
import json
import time

def debug_problema_selecao():
    """Debug completo do problema de seleção"""
    
    GAV_URL = "http://localhost:8000"
    API_URL = "http://localhost:8001"
    SESSAO = "debug_selecao_404"
    
    print("🔍 DEBUG - ERRO 404 NA SELEÇÃO")
    print("=" * 40)
    print(f"🔑 Sessão: {SESSAO}")
    print()
    
    try:
        # PASSO 1: Fazer busca para ter contexto
        print("📋 PASSO 1: Fazendo busca para criar contexto...")
        resp_busca = requests.post(f"{GAV_URL}/chat", 
            json={"texto": "buscar coca cola", "sessao_id": SESSAO},
            timeout=45
        )
        
        if resp_busca.status_code != 200:
            print(f"❌ Erro na busca: {resp_busca.status_code}")
            return
        
        resultado_busca = resp_busca.json()
        
        # Extrair produtos da resposta
        contexto_resposta = resultado_busca.get("contexto_estruturado", {})
        produtos_resposta = contexto_resposta.get("produtos", [])
        
        print(f"✅ Busca OK - {len(produtos_resposta)} produtos na resposta")
        
        if produtos_resposta:
            print("📦 Produtos encontrados na resposta:")
            for produto in produtos_resposta:
                item_id = produto.get("item_id") or produto.get("id")
                descricao = produto.get("descricao", "N/A")[:40]
                preco = produto.get("preco", 0)
                print(f"   • ID: {item_id} - {descricao}... - R$ {preco}")
        
        time.sleep(1)
        
        # PASSO 2: Verificar contexto salvo no banco
        print(f"\n🔍 PASSO 2: Verificando contexto salvo no banco...")
        
        resp_contexto = requests.get(f"{API_URL}/contexto/{SESSAO}", timeout=10)
        
        if resp_contexto.status_code == 200:
            contexto_banco = resp_contexto.json()
            
            print("✅ Contexto encontrado no banco:")
            print(f"   • Tipo: {contexto_banco.get('tipo_contexto')}")
            print(f"   • Hash: {contexto_banco.get('hash_query', 'N/A')[:12]}...")
            print(f"   • Mensagem: {contexto_banco.get('mensagem_original')}")
            
            # Verificar produtos no contexto do banco
            contexto_estruturado_banco = contexto_banco.get("contexto_estruturado", {})
            produtos_banco = contexto_estruturado_banco.get("produtos", [])
            
            print(f"📦 Produtos salvos no banco: {len(produtos_banco)}")
            
            if produtos_banco:
                print("📋 Lista de produtos no banco:")
                for i, produto in enumerate(produtos_banco):
                    item_id = produto.get("item_id") or produto.get("id")
                    descricao = produto.get("descricao", "N/A")[:40]
                    print(f"   {i+1}. ID: {item_id} - {descricao}...")
                    
                # IDENTIFICAR ID PARA TESTE
                primeiro_id = produtos_banco[0].get("item_id") or produtos_banco[0].get("id")
                print(f"\n🎯 ID para teste: {primeiro_id}")
                
            else:
                print("❌ PROBLEMA: Nenhum produto salvo no banco!")
                print("💡 Contexto estruturado não tem produtos")
                return
                
        else:
            print(f"❌ Contexto não encontrado no banco: {resp_contexto.status_code}")
            print("💡 Sistema pode não estar salvando contexto")
            return
        
        time.sleep(1)
        
        # PASSO 3: Testar seleção com ID válido do banco
        id_teste = primeiro_id
        print(f"\n🎯 PASSO 3: Testando seleção com ID {id_teste}...")
        
        resp_selecao = requests.post(f"{GAV_URL}/chat", 
            json={"texto": str(id_teste), "sessao_id": SESSAO},
            timeout=30
        )
        
        print(f"📨 Status da seleção: {resp_selecao.status_code}")
        
        if resp_selecao.status_code == 200:
            resultado_selecao = resp_selecao.json()
            mensagem = resultado_selecao.get("mensagem", "")
            
            print("✅ Seleção funcionou!")
            print(f"💬 Mensagem: {mensagem[:100]}...")
            
            # Verificar se perguntou quantidade
            if "quantas" in mensagem.lower() or "quantidade" in mensagem.lower():
                print("✅ Sistema perguntou quantidade corretamente")
            else:
                print("⚠️ Sistema NÃO perguntou quantidade")
                
        else:
            print(f"❌ Erro na seleção: {resp_selecao.status_code}")
            
            try:
                erro_detalhes = resp_selecao.json()
                print(f"📄 Detalhes do erro:")
                print(json.dumps(erro_detalhes, indent=2))
            except:
                print(f"📄 Resposta do erro: {resp_selecao.text}")
        
        # PASSO 4: Testar com ID que causou problema originalmente
        print(f"\n🧪 PASSO 4: Testando com ID problemático (1981)...")
        
        resp_problema = requests.post(f"{GAV_URL}/chat",
            json={"texto": "1981", "sessao_id": SESSAO},
            timeout=30
        )
        
        print(f"📨 Status ID 1981: {resp_problema.status_code}")
        
        if resp_problema.status_code == 200:
            resultado_problema = resp_problema.json()
            print("⚠️ ID 1981 funcionou dessa vez")
            print(f"💬 Mensagem: {resultado_problema.get('mensagem', '')[:100]}...")
        else:
            print("❌ ID 1981 falhou novamente")
            try:
                erro_1981 = resp_problema.json()
                print("📄 Erro detalhado:")
                print(json.dumps(erro_1981, indent=2))
            except:
                print(f"📄 Resposta: {resp_problema.text}")
        
        # PASSO 5: Análise final
        print(f"\n📊 ANÁLISE FINAL:")
        
        # Verificar se ID 1981 estava nos produtos
        ids_no_contexto = []
        for produto in produtos_banco:
            item_id = produto.get("item_id") or produto.get("id")
            if item_id:
                ids_no_contexto.append(item_id)
        
        print(f"📋 IDs disponíveis no contexto: {ids_no_contexto}")
        
        if 1981 in ids_no_contexto:
            print("✅ ID 1981 ESTAVA no contexto - problema pode ser na detecção")
        else:
            print("❌ ID 1981 NÃO estava no contexto - por isso deu 404")
            print("💡 Usuário tentou selecionar ID que não existe na busca atual")
        
    except Exception as e:
        print(f"💥 Erro no debug: {e}")

def debug_deteccao_id():
    """Testa função de detecção de ID"""
    print("\n🧪 TESTE DA DETECÇÃO DE ID")
    print("-" * 25)
    
    import re
    
    def detectar_selecao_produto_local(texto: str) -> bool:
        """Simula função de detecção"""
        # ID sozinho (4-6 dígitos)
        if re.match(r'^\s*\d{4,6}\s*$', texto):
            return True
        
        # Padrões de seleção
        padroes = [
            r'\b(\d{4,6})\b',  # ID em qualquer lugar
            r'id\s*(\d{4,6})',  # "id 18135"
            r'quero\s*(\d{4,6})',  # "quero 18135"
            r'selecion\w*\s*(\d{4,6})'  # "selecionar 18135"
        ]
        
        for padrao in padroes:
            if re.search(padrao, texto.lower()):
                return True
        
        return False
    
    testes = ["1981", "18135", "quero 1981", "selecionar 18135", "buscar café", "ver carrinho"]
    
    for teste in testes:
        detectado = detectar_selecao_produto_local(teste)
        status = "✅" if detectado else "❌"
        print(f"{status} '{teste}' → {'DETECTADO' if detectado else 'NÃO detectado'}")

def verificar_logs_gav():
    """Verifica se há logs úteis no GAV"""
    print("\n📋 VERIFICAR LOGS DO GAV:")
    print("-" * 25)
    print("1. Olhar console do GAV durante seleção")
    print("2. Procurar por mensagens tipo:")
    print("   • '🔍 Verificando estado do contexto...'")
    print("   • '📋 Tipo contexto atual: busca_numerada_rica'")
    print("   • '🎯 Estado: Seleção de produto detectada'")
    print("   • Erros na recuperação do contexto")
    print("   • Logs da função _processar_selecao_produto_estado")

if __name__ == "__main__":
    # Debug completo
    debug_problema_selecao()
    
    # Teste de detecção
    debug_deteccao_id()
    
    # Dicas de verificação
    verificar_logs_gav()
    
    print(f"\n🏁 DEBUG CONCLUÍDO!")
    print("💡 Se ID não estava no contexto: usuário selecionou produto de busca anterior")
    print("💡 Se ID estava no contexto: problema na detecção ou recuperação")