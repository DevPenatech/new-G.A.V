#!/usr/bin/env python3
# debug_contexto.py - Verificar se contexto está sendo salvo

import requests
import json
import time

def debug_contexto():
    """Testa se contexto está sendo salvo e recuperado"""
    
    sessao = f"Debug_{int(time.time())}"
    
    print("1️⃣ Busca inicial: quero nescau")
    r1 = requests.post("http://localhost:8000/chat", json={
        "texto": "quero nescau",
        "sessao_id": sessao
    })
    print(f"Status busca: {r1.status_code}")
    
    time.sleep(2)
    
    print("\n2️⃣ VERIFICAR: Contexto foi salvo no banco?")
    try:
        r_contexto = requests.get(f"http://localhost:8001/contexto/{sessao}")
        print(f"Status contexto: {r_contexto.status_code}")
        
        if r_contexto.status_code == 200:
            contexto = r_contexto.json()
            produtos = contexto.get("contexto_estruturado", {}).get("produtos", [])
            print(f"✅ Contexto encontrado! {len(produtos)} produtos salvos")
            
            if produtos:
                primeiro = produtos[0]
                print(f"   📝 Primeiro produto: posição {primeiro.get('posicao')} → ID {primeiro.get('item_id')}")
            else:
                print("❌ Contexto salvo mas SEM produtos!")
        else:
            print("❌ Contexto NÃO foi salvo no banco!")
            
    except Exception as e:
        print(f"❌ Erro ao verificar contexto: {e}")
    
    print("\n3️⃣ Testar seleção: quero o 1")
    r2 = requests.post("http://localhost:8000/chat", json={
        "texto": "quero o 1",
        "sessao_id": sessao
    })
    print(f"Status seleção: {r2.status_code}")
    
    if r2.status_code == 200:
        resultado = r2.json()
        print(f"Resposta: {resultado.get('mensagem', '')[:100]}...")

if __name__ == "__main__":
    debug_contexto()