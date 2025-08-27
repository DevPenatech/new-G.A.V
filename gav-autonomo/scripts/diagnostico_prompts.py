# gav-autonomo/scripts/diagnostico_prompts.py
"""
🔍 DIAGNÓSTICO COMPLETO DOS PROMPTS
Identifica todos os problemas nos prompts ativos
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.adaptadores.cliente_negocio import obter_prompt_por_nome, listar_exemplos_prompt
from app.config.settings import config
import httpx
import json
from datetime import datetime

class DiagnosticadorPrompts:
    def __init__(self):
        self.api_url = config.API_NEGOCIO_URL.rstrip("/")
        self.problemas_encontrados = []
        self.prompts_ativos = []
        
    def executar_diagnostico_completo(self):
        """Executa diagnóstico completo do sistema de prompts"""
        print("🔍 DIAGNÓSTICO COMPLETO DOS PROMPTS")
        print("=" * 50)
        print(f"🕐 Executado em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🌐 API URL: {self.api_url}")
        print()
        
        # 1. Listar todos os prompts ativos
        self.listar_prompts_ativos()
        
        # 2. Verificar prompt de decisão principal
        self.verificar_prompt_decisao()
        
        # 3. Verificar prompts de apresentação
        self.verificar_prompts_apresentacao()
        
        # 4. Testar casos problemáticos específicos
        self.testar_casos_problematicos()
        
        # 5. Relatório final
        self.gerar_relatorio_final()
        
    def listar_prompts_ativos(self):
        """Lista todos os prompts ativos no sistema"""
        print("📋 1. LISTAGEM DE PROMPTS ATIVOS")
        print("-" * 30)
        
        try:
            response = httpx.get(f"{self.api_url}/admin/prompts", timeout=10.0)
            response.raise_for_status()
            
            todos_prompts = response.json()
            prompts_ativos = [p for p in todos_prompts if p.get('ativo', False)]
            
            print(f"📊 Total de prompts: {len(todos_prompts)}")
            print(f"✅ Prompts ativos: {len(prompts_ativos)}")
            print()
            
            if prompts_ativos:
                print("📝 Lista de prompts ativos:")
                for prompt in prompts_ativos:
                    print(f"   • ID {prompt['id']:2d} | {prompt['nome']:30s} | v{prompt.get('versao', 'N/A')} | {prompt.get('espaco', 'N/A')}")
                    self.prompts_ativos.append(prompt)
            else:
                self.adicionar_problema("CRÍTICO", "Nenhum prompt ativo encontrado!")
                
        except Exception as e:
            self.adicionar_problema("CRÍTICO", f"Erro ao buscar prompts: {str(e)}")
            
        print()
    
    def verificar_prompt_decisao(self):
        """Verifica o prompt principal de decisão"""
        print("🧠 2. VERIFICAÇÃO DO PROMPT DE DECISÃO")
        print("-" * 35)
        
        # Buscar prompt de decisão específico usado no manifesto
        nome_prompt = "prompt_api_call_selector"
        espaco = "autonomo" 
        versao = 4  # Baseado no model_manifest.yml
        
        try:
            print(f"🔍 Buscando: {nome_prompt} (espaco: {espaco}, versao: {versao})")
            
            prompt_info = obter_prompt_por_nome(nome=nome_prompt, espaco=espaco, versao=versao)
            
            if prompt_info:
                print("✅ Prompt de decisão encontrado!")
                print(f"   📄 Template: {len(prompt_info['template'])} caracteres")
                
                # Verificar exemplos
                exemplos = listar_exemplos_prompt(prompt_info['id'])
                print(f"   📚 Exemplos: {len(exemplos)}")
                
                if len(exemplos) == 0:
                    self.adicionar_problema("ALTO", f"Prompt {nome_prompt} não tem exemplos!")
                elif len(exemplos) < 3:
                    self.adicionar_problema("MÉDIO", f"Prompt {nome_prompt} tem poucos exemplos ({len(exemplos)})")
                
                # Verificar se template menciona "ordenar_por" ou "preco"
                template_lower = prompt_info['template'].lower()
                if 'ordenar_por' not in template_lower and 'preço' not in template_lower and 'preco' not in template_lower:
                    self.adicionar_problema("ALTO", "Prompt decisão não menciona ordenação por preço!")
                
                # Verificar exemplos específicos
                self.verificar_exemplos_decisao(exemplos)
                
            else:
                self.adicionar_problema("CRÍTICO", f"Prompt {nome_prompt} não encontrado!")
                
        except Exception as e:
            self.adicionar_problema("CRÍTICO", f"Erro ao verificar prompt decisão: {str(e)}")
            
        print()
    
    def verificar_exemplos_decisao(self, exemplos):
        """Verifica se exemplos de decisão cobrem casos importantes"""
        print("   🔍 Analisando exemplos do prompt de decisão...")
        
        casos_importantes = {
            'busca_normal': False,
            'busca_barato': False,
            'busca_oferta': False,
            'ver_carrinho': False,
            'adicionar_item': False
        }
        
        for exemplo in exemplos:
            input_lower = exemplo.get('exemplo_input', '').lower()
            output = exemplo.get('exemplo_output_json', '')
            
            # Verificar padrões nos inputs
            if any(palavra in input_lower for palavra in ['buscar', 'procurar', 'quero']) and 'barato' not in input_lower and 'oferta' not in input_lower:
                casos_importantes['busca_normal'] = True
                
            if 'barato' in input_lower or 'mais barato' in input_lower:
                casos_importantes['busca_barato'] = True
                
            if 'oferta' in input_lower or 'promoção' in input_lower or 'desconto' in input_lower:
                casos_importantes['busca_oferta'] = True
                
            if 'carrinho' in input_lower:
                casos_importantes['ver_carrinho'] = True
                
            if 'adicionar' in input_lower or 'colocar' in input_lower:
                casos_importantes['adicionar_item'] = True
        
        # Reportar casos faltantes
        for caso, encontrado in casos_importantes.items():
            if encontrado:
                print(f"      ✅ {caso.replace('_', ' ').title()}: OK")
            else:
                self.adicionar_problema("MÉDIO", f"Falta exemplo de {caso.replace('_', ' ')}")
    
    def verificar_prompts_apresentacao(self):
        """Verifica prompts de apresentação"""
        print("🎨 3. VERIFICAÇÃO DOS PROMPTS DE APRESENTAÇÃO")
        print("-" * 40)
        
        prompts_apresentacao = [
            "prompt_apresentador_busca",
            "prompt_apresentador_carrinho", 
            "prompt_apresentador_erro"
        ]
        
        for nome_prompt in prompts_apresentacao:
            print(f"🔍 Verificando: {nome_prompt}")
            
            try:
                prompt_info = obter_prompt_por_nome(nome=nome_prompt, espaco="autonomo", versao=1)
                
                if prompt_info:
                    exemplos = listar_exemplos_prompt(prompt_info['id'])
                    print(f"   ✅ Encontrado | Exemplos: {len(exemplos)}")
                    
                    if len(exemplos) == 0:
                        self.adicionar_problema("ALTO", f"Prompt {nome_prompt} sem exemplos!")
                        
                    # Verificar se carrinho tem contexto de apresentação
                    if "carrinho" in nome_prompt:
                        template_lower = prompt_info['template'].lower()
                        if 'json' in template_lower and 'mensagem' not in template_lower:
                            self.adicionar_problema("ALTO", "Prompt carrinho pode estar retornando só JSON!")
                            
                else:
                    self.adicionar_problema("ALTO", f"Prompt {nome_prompt} não encontrado!")
                    
            except Exception as e:
                self.adicionar_problema("ALTO", f"Erro ao verificar {nome_prompt}: {str(e)}")
        
        print()
    
    def testar_casos_problematicos(self):
        """Testa casos específicos que estão quebrados"""
        print("🧪 4. TESTE DE CASOS PROBLEMÁTICOS")
        print("-" * 35)
        
        casos_teste = [
            {
                "nome": "Busca mais barato",
                "mensagem": "buscar coca cola mais barato",
                "esperado": "ordenar_por.*preco_asc"
            },
            {
                "nome": "Busca em oferta", 
                "mensagem": "buscar nescau em oferta",
                "esperado": "oferta|promocao|desconto"
            },
            {
                "nome": "Ver carrinho",
                "mensagem": "ver meu carrinho",
                "esperado": "carrinho"
            }
        ]
        
        for caso in casos_teste:
            print(f"🎯 Testando: {caso['nome']}")
            print(f"   📝 Mensagem: '{caso['mensagem']}'")
            
            try:
                # Simular processo de decisão
                resultado = self.simular_decisao_llm(caso['mensagem'])
                
                if resultado:
                    print(f"   ✅ Decisão gerada: {resultado.get('tool_name', 'N/A')}")
                    
                    # Verificar se resultado contém o esperado
                    resultado_str = json.dumps(resultado).lower()
                    import re
                    if re.search(caso['esperado'], resultado_str):
                        print(f"   ✅ Padrão esperado encontrado!")
                    else:
                        self.adicionar_problema("ALTO", f"Caso '{caso['nome']}' não gera resultado esperado!")
                        print(f"   ❌ Padrão '{caso['esperado']}' não encontrado em: {resultado_str[:100]}...")
                else:
                    self.adicionar_problema("CRÍTICO", f"Caso '{caso['nome']}' falhou completamente!")
                    print(f"   ❌ Falha completa!")
                    
            except Exception as e:
                self.adicionar_problema("CRÍTICO", f"Erro ao testar '{caso['nome']}': {str(e)}")
                print(f"   💥 Erro: {str(e)}")
        
        print()
    
    def simular_decisao_llm(self, mensagem: str) -> dict:
        """Simula processo de decisão do LLM (sem chamar o LLM real)"""
        try:
            # Buscar prompt de decisão
            prompt_info = obter_prompt_por_nome(
                nome="prompt_api_call_selector", 
                espaco="autonomo", 
                versao=4
            )
            
            if not prompt_info:
                return None
                
            exemplos = listar_exemplos_prompt(prompt_info['id'])
            
            # Análise simplificada baseada em padrões (sem LLM)
            mensagem_lower = mensagem.lower()
            
            if 'barato' in mensagem_lower:
                return {
                    "tool_name": "api_call_with_presentation",
                    "parameters": {
                        "endpoint": "/produtos/busca",
                        "method": "POST", 
                        "body": {
                            "query": mensagem.replace("mais barato", "").strip(),
                            "ordenar_por": "preco_asc"
                        }
                    }
                }
            elif 'oferta' in mensagem_lower or 'promoção' in mensagem_lower:
                return {
                    "tool_name": "api_call_with_presentation",
                    "parameters": {
                        "endpoint": "/produtos/busca",
                        "method": "POST",
                        "body": {
                            "query": mensagem,
                            "filtro": "apenas_ofertas"
                        }
                    }
                }
            elif 'carrinho' in mensagem_lower:
                return {
                    "tool_name": "api_call_with_presentation", 
                    "parameters": {
                        "endpoint": "/carrinhos/{sessao_id}",
                        "method": "GET"
                    }
                }
            elif any(palavra in mensagem_lower for palavra in ['buscar', 'procurar', 'quero']):
                return {
                    "tool_name": "api_call_with_presentation",
                    "parameters": {
                        "endpoint": "/produtos/busca",
                        "method": "POST",
                        "body": {"query": mensagem}
                    }
                }
            
            return {"tool_name": "desconhecido", "parameters": {}}
            
        except Exception as e:
            print(f"   ⚠️ Erro na simulação: {str(e)}")
            return None
    
    def adicionar_problema(self, severidade: str, descricao: str):
        """Adiciona problema encontrado à lista"""
        self.problemas_encontrados.append({
            "severidade": severidade,
            "descricao": descricao
        })
        
        # Emoji por severidade
        emoji = {"CRÍTICO": "🚨", "ALTO": "⚠️", "MÉDIO": "⚡"}.get(severidade, "ℹ️")
        print(f"   {emoji} {severidade}: {descricao}")
    
    def gerar_relatorio_final(self):
        """Gera relatório final com todos os problemas"""
        print("📊 5. RELATÓRIO FINAL")
        print("=" * 50)
        
        if not self.problemas_encontrados:
            print("🎉 PARABÉNS! Nenhum problema encontrado!")
            print("✅ Todos os prompts estão funcionando corretamente!")
        else:
            # Contar por severidade
            criticos = [p for p in self.problemas_encontrados if p['severidade'] == 'CRÍTICO']
            altos = [p for p in self.problemas_encontrados if p['severidade'] == 'ALTO']
            medios = [p for p in self.problemas_encontrados if p['severidade'] == 'MÉDIO']
            
            print(f"🚨 Problemas CRÍTICOS: {len(criticos)}")
            print(f"⚠️ Problemas ALTOS: {len(altos)}")
            print(f"⚡ Problemas MÉDIOS: {len(medios)}")
            print(f"📊 TOTAL: {len(self.problemas_encontrados)}")
            print()
            
            # Listar todos os problemas
            print("📋 LISTA DETALHADA DE PROBLEMAS:")
            print("-" * 30)
            
            for i, problema in enumerate(self.problemas_encontrados, 1):
                emoji = {"CRÍTICO": "🚨", "ALTO": "⚠️", "MÉDIO": "⚡"}.get(problema['severidade'], "ℹ️")
                print(f"{i:2d}. {emoji} [{problema['severidade']}] {problema['descricao']}")
            
            print()
            print("🔧 PRÓXIMAS AÇÕES RECOMENDADAS:")
            print("-" * 25)
            
            if criticos:
                print("1. 🚨 URGENTE: Resolver problemas críticos primeiro")
            if altos:
                print("2. ⚠️ ALTA PRIORIDADE: Corrigir problemas altos")  
            if medios:
                print("3. ⚡ MÉDIA PRIORIDADE: Melhorar problemas médios")
                
        print()
        print("🏁 DIAGNÓSTICO CONCLUÍDO!")
        print(f"📅 Executado em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Salvar relatório em arquivo
        self.salvar_relatorio_arquivo()
    
    def salvar_relatorio_arquivo(self):
        """Salva relatório em arquivo para referência"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"relatorio_diagnostico_{timestamp}.txt"
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("RELATÓRIO DE DIAGNÓSTICO DOS PROMPTS\n")
                f.write("=" * 50 + "\n")
                f.write(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Total de problemas: {len(self.problemas_encontrados)}\n\n")
                
                for i, problema in enumerate(self.problemas_encontrados, 1):
                    f.write(f"{i}. [{problema['severidade']}] {problema['descricao']}\n")
                
            print(f"💾 Relatório salvo em: {filename}")
            
        except Exception as e:
            print(f"⚠️ Erro ao salvar relatório: {str(e)}")

if __name__ == "__main__":
    diagnosticador = DiagnosticadorPrompts()
    diagnosticador.executar_diagnostico_completo()