#!/usr/bin/env python3
# debug_prompt.py - Ver resposta completa do LLM

import requests
import json
import time

def debug_prompt_resposta():
    """Ver se prompt está gerando contexto_estruturado"""
    
    sessao = f"DebugPrompt_{int(time.time())}"
    
    print("🔍 TESTE: Verificar resposta COMPLETA do sistema")
    
    r1 = requests.post("http://localhost:8000/chat", json={
        "texto": "quero nescau",
        "sessao_id": sessao
    })
    
    if r1.status_code == 200:
        resultado_completo = r1.json()
        
        print("📋 RESPOSTA COMPLETA:")
        print(json.dumps(resultado_completo, indent=2, ensure_ascii=False))
        
        print("\n🔍 ANÁLISE:")
        print(f"✅ Tem 'mensagem': {'mensagem' in resultado_completo}")
        print(f"✅ Tem 'dados_originais': {'dados_originais' in resultado_completo}")
        
        # Verificar se tem dados_originais estruturados que poderiam virar contexto
        dados_orig = resultado_completo.get("dados_originais", {})
        resultados = dados_orig.get("resultados", [])
        
        print(f"✅ Dados originais têm {len(resultados)} produtos")
        
        if resultados:
            primeiro_produto = resultados[0]
            itens = primeiro_produto.get("itens", [])
            print(f"✅ Primeiro produto tem {len(itens)} itens/variações")
            
            # Ver se tem item_id para mapear
            if itens:
                print(f"✅ Primeiro item_id: {itens[0].get('id')}")
    else:
        print(f"❌ Erro na busca: {r1.status_code}")

if __name__ == "__main__":
    debug_prompt_resposta()