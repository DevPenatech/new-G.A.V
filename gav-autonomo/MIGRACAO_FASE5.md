# 🚀 Guia de Implementação - Fase 5a: Pipeline de Apresentação

## ✅ **Checklist de Implementação**

### **1. Executar SQLs dos Novos Prompts** (5 min)
```bash
# Conecte ao banco e execute os prompts de apresentação
psql -h localhost -U gav_user -d gav_db -f prompts_apresentacao_fase5a.sql
```

**Verifica:**
- ✅ 3 novos prompts criados (busca, carrinho, erro)
- ✅ 8 exemplos adicionados
- ✅ Prompts ativos no banco

### **2. Substituir executor_regras.py** (2 min)
```bash
# Backup do código atual
cp gav-autonomo/app/servicos/executor_regras.py gav-autonomo/app/servicos/executor_regras_backup_fase4.py

# Aplicar nova versão com pipeline
cp executor_regras_fase5a.py gav-autonomo/app/servicos/executor_regras.py
```

**Verifica:**
- ✅ Nova função `_apresentar_resultado()` presente
- ✅ Pipeline para `api_call_with_presentation` implementado
- ✅ Fallback para JSON em caso de erro

### **3. Reiniciar Serviços** (1 min)
```bash
# Reinicia apenas o orquestrador
docker-compose restart gav_autonomo

# Verifica se subiu corretamente
docker logs gav_autonomo
```

**Verifica:**
- ✅ Serviço subiu sem erros
- ✅ Logs normais de inicialização

### **4. Teste Básico de Funcionamento** (5 min)
```bash
# Teste rápido via curl
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"texto": "quero nescau baratinho", "sessao_id": "test123"}'
```

**Resultado Esperado:**
```json
{
  "mensagem": "Encontrei o Nescau! 🍫\n\n🏆 MELHOR PREÇO: R$ 6,79\n   Nescau Lata 200g\n\nPerfeito para quem quer economizar! Quer adicionar ao carrinho?",
  "tipo": "apresentacao_busca"
}
```

### **5. Executar Suite Completa de Testes** (10 min)
```bash
cd gav-autonomo
python teste_pipeline_fase5a.py
```

**Meta de Sucesso:** 80%+ dos testes passando

---

## 🔍 **Validação do Pipeline**

### **Fluxo Esperado:**

1. **Usuário:** "quero nescau baratinho"
2. **LLM Selector:** Decide `api_call_with_presentation`
3. **API Call:** `POST /produtos/busca` → JSON com produtos
4. **LLM Apresentador:** JSON → conversa amigável
5. **Resposta:** "Encontrei o Nescau! 🍫..."

### **Pontos de Verificação:**

- ✅ **Decisão Correta:** Busca → `api_call_with_presentation`
- ✅ **API Funcionando:** Retorna produtos válidos
- ✅ **Apresentação Ativa:** JSON vira conversa natural
- ✅ **Fallback Seguro:** Em caso de erro, retorna JSON

---

## 🐛 **Troubleshooting**

### **Problema: "Prompt não encontrado"**
```bash
# Verifica se prompts estão no banco
psql -h localhost -U gav_user -d gav_db -c "
SELECT nome, versao, espaco, ativo 
FROM prompt_templates 
WHERE nome LIKE 'prompt_apresentador%';"
```

**Solução:** Re-executar SQLs dos prompts

### **Problema: "Retorna JSON em vez de conversa"**
**Possíveis Causas:**
- LLM Selector escolheu `api_call` em vez de `api_call_with_presentation`
- Erro na função `_apresentar_resultado()`
- Prompt de apresentação com problema

**Debug:**
```bash
# Verifica logs do orquestrador
docker logs -f gav_autonomo

# Procura por:
# "Pipeline de apresentação ativado"
# "Erro na apresentação"
```

### **Problema: "Conversas muito técnicas"**
**Solução:** Ajustar exemplos dos prompts de apresentação
```sql
-- Adicionar mais exemplos com tom descontraído
INSERT INTO prompt_exemplos (prompt_id, exemplo_input, exemplo_output_json)
SELECT id, 'novo_exemplo...', 'resposta_mais_amigavel...'
FROM prompt_templates WHERE nome='prompt_apresentador_busca';
```

### **Problema: "Timeout ou erro 500"**
**Possíveis Causas:**
- LLM sobrecarregado (duas chamadas por request)
- Ollama não respondendo
- API de negócio lenta

**Debug:**
```bash
# Verifica status dos serviços
docker-compose ps

# Testa API de negócio diretamente
curl http://localhost:8001/healthcheck

# Testa Ollama diretamente
curl http://localhost:11434/api/generate \
  -d '{"model": "llama3.1", "prompt": "teste", "stream": false}'
```

---

## 🎯 **Métricas de Sucesso**

### **Imediatas (hoje):**
- ✅ Busca de produtos retorna conversa em vez de JSON
- ✅ Carrinho apresentado de forma amigável
- ✅ Erros transformados em mensagens úteis
- ✅ 80%+ dos testes passando

### **Próximas 24h:**
- 🎨 Emojis contextuais funcionando
- 💰 Formatação de preços brasileiros
- 🏆 Destacamento de melhores ofertas
- 📊 Comparações inteligentes entre produtos

### **Próximos 3 dias:**
- 💡 Call-to-actions dinâmicos
- 🔄 Sugestões baseadas em contexto
- 🧠 Memória de preferências da sessão
- 📱 Preparação para WebChat (Fase 5b)

---

## 🚀 **Próximos Passos Após Sucesso**

### **Fase 5a.2 - Formatação Rica** (começar imediatamente)
1. Adicionar mais emojis contextuais nos prompts
2. Implementar formatação de preços mais rica
3. Adicionar comparações "melhor custo-benefício"

### **Fase 5a.3 - Sugestões Inteligentes** (2-3 dias)
1. Criar `prompt_sugestoes_complementares`
2. Implementar detecção de "combos" vantajosos
3. Adicionar recomendações baseadas no carrinho

### **Fase 5b - WebChat** (próxima semana)
1. Interface React para testar conversas
2. Histórico persistente de sessão
3. UX otimizada para demonstrações

---

## 📞 **Em Caso de Problemas**

1. **Verifique logs:** `docker logs -f gav_autonomo`
2. **Teste componentes:** APIs individuais funcionando?
3. **Rollback seguro:** Restaurar `executor_regras_backup_fase4.py`
4. **Iteração rápida:** Ajustar prompts sem redeploy

**🎯 Lembre-se: Tudo via prompt = evolução rápida e sem risco!**