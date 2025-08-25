#!/usr/bin/env python3
# teste_após_correcao.py - Verificar se contexto agora é gerado

import requests
import json
import time

def teste_contexto_corrigido():
    """Testa se contexto_estruturado agora é gerado e salvo"""
    
    sessao = f"TesteCorrecao_{int(time.time())}"
    
    print("🔧 TESTE APÓS CORREÇÃO DO PROMPT")
    print("=" * 40)
    
    print("1️⃣ Busca: quero nescau")
    r1 = requests.post("http://localhost:8000/chat", json={
        "texto": "quero nescau",
        "sessao_id": sessao
    })
    
    if r1.status_code == 200:
        resultado = r1.json()
        print(f"✅ Status: {r1.status_code}")
        
        # Verificar se agora tem contexto_estruturado na resposta 
        print(f"📋 Campos na resposta: {list(resultado.keys())}")
        
        if "contexto_estruturado" in resultado:
            print("🎉 SUCESSO! Agora tem contexto_estruturado na resposta!")
            contexto = resultado["contexto_estruturado"]
            produtos = contexto.get("produtos", [])
            print(f"   📦 {len(produtos)} produtos no contexto")
            if produtos:
                primeiro = produtos[0]
                print(f"   📝 Exemplo: posição {primeiro.get('posicao')} → ID {primeiro.get('item_id')}")
        else:
            print("❌ AINDA sem contexto_estruturado na resposta")
            print(f"   🔍 Resposta: {json.dumps(resultado, indent=2)[:300]}...")
    
    time.sleep(2)
    
    print("\n2️⃣ Verificar se contexto foi salvo no banco")
    try:
        r_banco = requests.get(f"http://localhost:8001/contexto/{sessao}")
        print(f"✅ Status banco: {r_banco.status_code}")
        
        if r_banco.status_code == 200:
            print("🎉 CONTEXTO SALVO NO BANCO!")
            contexto_banco = r_banco.json()
            produtos_banco = contexto_banco.get("contexto_estruturado", {}).get("produtos", [])
            print(f"   📦 {len(produtos_banco)} produtos salvos no banco")
        else:
            print("❌ Contexto ainda não está sendo salvo")
    except Exception as e:
        print(f"❌ Erro ao verificar banco: {e}")
    
    print("\n3️⃣ Testar seleção: quero o 1")
    r2 = requests.post("http://localhost:8000/chat", json={
        "texto": "quero o 1", 
        "sessao_id": sessao
    })
    
    if r2.status_code == 200:
        resultado2 = r2.json()
        mensagem = resultado2.get("mensagem", "").lower()
        
        print(f"✅ Status: {r2.status_code}")
        print(f"📝 Resposta: {mensagem[:100]}...")
        
        if "adicionado" in mensagem or "carrinho" in mensagem:
            print("🎉 SELEÇÃO FUNCIONOU!")
        else:
            print("❌ Seleção ainda não funciona")

if __name__ == "__main__":
    teste_contexto_corrigido()