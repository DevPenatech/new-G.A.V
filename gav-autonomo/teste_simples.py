#!/usr/bin/env python3
# teste_simples.py - Testa exatamente seu caso

import requests
import json
import time

def teste_seu_caso():
    """Testa: quero nescau → quero a 1 opcao com 4 unidades → meu carrinho"""
    
    sessao = f"MeuTeste_{int(time.time())}"
    
    print("1️⃣ Primeira requisição: quero nescau")
    r1 = requests.post("http://localhost:8000/chat", json={
        "texto": "quero nescau",
        "sessao_id": sessao
    })
    print(f"Status: {r1.status_code}")
    if r1.status_code == 200:
        result1 = r1.json()
        print(f"✅ Resposta: {result1.get('mensagem', '')[:100]}...")
    
    time.sleep(2)
    
    print("\n2️⃣ Segunda requisição: quero a 1 opcao com 4 unidades")
    r2 = requests.post("http://localhost:8000/chat", json={
        "texto": "quero a 1 opcao com 4 unidades",
        "sessao_id": sessao
    })
    print(f"Status: {r2.status_code}")
    if r2.status_code == 200:
        result2 = r2.json()
        print(f"✅ Resposta: {result2.get('mensagem', '')[:100]}...")
    
    time.sleep(2)
    
    print("\n3️⃣ Terceira requisição: meu carrinho")
    r3 = requests.post("http://localhost:8000/chat", json={
        "texto": "meu carrinho",
        "sessao_id": sessao
    })
    print(f"Status: {r3.status_code}")
    if r3.status_code == 200:
        result3 = r3.json()
        mensagem = result3.get('mensagem', '').lower()
        print(f"✅ Carrinho: {result3.get('mensagem', '')}")
        
        # VALIDAÇÃO: Tem Nescau?
        if "nescau" in mensagem:
            print("\n🎉 SUCESSO! Nescau está no carrinho (produto correto)")
        else:
            print("\n❌ FALHA! Nescau NÃO está no carrinho")

if __name__ == "__main__":
    print("🔧 TESTE SIMPLES DO SEU CASO")
    teste_seu_caso()