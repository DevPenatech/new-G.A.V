# Guia de Migração - Fase 4: API Call Genérica

## Visão Geral da Mudança

**ANTES (Fase 3)**: Orquestrador com regras hardcoded para cada tipo de ferramenta:
```python
if tool == "buscar_produtos":
    return buscar_produtos(query=params.get("query",""), ordenar_por=params.get("ordenar_por"))
elif tool == "adicionar_item_carrinho":
    payload = dict(params)
    for k in ("item_id","quantidade"):
        if isinstance(payload.get(k), str) and payload[k].isdigit():
            payload[k] = int(payload[k])
    return adicionar_ao_carrinho(sessao_id=mensagem["sessao_id"], **payload)
```

**DEPOIS (Fase 4)**: Orquestrador genérico que só executa chamadas HTTP:
```python
if decisao.get("tool_name") == "api_call":
    return _executar_api_call(decisao.get("parameters", {}), mensagem["sessao_id"])
```

## Passos de Migração

### 1. Executar SQLs dos Novos Prompts
```bash
# Conecte ao banco e execute os prompts da Fase 4
psql -h localhost -U gav_user -d gav_db -f prompts_api_call.sql
```

### 2. Salvar o Schema de Validação
```bash
# Salve o novo schema em gav-autonomo/app/validadores/esquemas/
cp api_call_decision.json gav-autonomo/app/validadores/esquemas/
```

### 3. Substituir o Executor de Regras
```bash
# Backup do código atual
cp gav-autonomo/app/servicos/executor_regras.py gav-autonomo/app/servicos/executor_regras_backup.py

# Aplicar nova versão
cp executor_regras_generico.py gav-autonomo/app/servicos/executor_regras.py
```

### 4. Atualizar o Manifesto
```bash
# Backup do manifesto atual
cp gav-autonomo/app/config/model_manifest.yml gav-autonomo/app/config/model_manifest_backup.yml

# Aplicar novo manifesto
cp model_manifest_generico.yml gav-autonomo/app/config/model_manifest.yml
```

### 5. Reiniciar os Serviços
```bash
docker-compose restart gav_autonomo
```

## Validação da Migração

### Teste 1: Funcionalidade Básica
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"texto": "quero nescau baratinho", "sessao_id": "test123"}'
```

**Resultado Esperado**: Busca de produtos com ordenação por preço.

### Teste 2: Robustez do Sistema
```bash
# Testa se o reparo automático funciona
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"texto": "adicione duas caixas do sku abc123", "sessao_id": "test123"}'
```

### Teste 3: Executar Suite Completa
```bash
cd gav-autonomo
python testes_api_call_generica.py
```

## Benefícios da Nova Arquitetura

### ✅ Evolução 100% via Prompt
- **Antes**: Adicionar nova ferramenta = modificar código Python
- **Depois**: Adicionar nova API = adicionar exemplos no prompt

### ✅ Ciclo de Reparo Automático
- **Antes**: Erro 422 quebrava o fluxo
- **Depois**: Sistema automaticamente corrige e retenta

### ✅ Zero Acoplamento
- **Antes**: Nomes hardcoded ("buscar_produtos", "ver_carrinho")
- **Depois**: Apenas "api_call" genérica

### ✅ Observabilidade Melhorada
- Logs incluem endpoint, método, body enviado
- Rastrea tentativas de reparo automático
- Facilita debugging de prompts

## Monitoramento Pós-Migração

### Logs a Observar
```bash
# Acompanhe os logs do orquestrador
docker logs -f gav_autonomo

# Procure por estas mensagens:
# ✅ "Executando API call: POST /produtos/busca"
# ✅ "Reparo automático aplicado com sucesso"
# ❌ "Decisão do LLM inválida"
# ❌ "Reparo automático falhou"
```

### Métricas de Sucesso
- **Taxa de decisões válidas**: > 95%
- **Taxa de sucesso de reparo**: > 80%
- **Latência média**: < 3 segundos
- **Erros 5xx**: = 0

## Troubleshooting

### Problema: "Decisão do LLM inválida"
**Causa**: Schema de validação muito restritivo ou prompt inconsistente
**Solução**: Revisar exemplos do prompt_api_call_selector

### Problema: "Reparo automático falhou"
**Causa**: Prompt de reparo não cobre o tipo de erro encontrado
**Solução**: Adicionar exemplo ao prompt_api_repair

### Problema: "Endpoint não reconhecido"
**Causa**: LLM inventou endpoint que não existe na API
**Solução**: Atualizar lista de endpoints no prompt

## Rollback (Se Necessário)

```bash
# 1. Restaurar código anterior
cp gav-autonomo/app/servicos/executor_regras_backup.py gav-autonomo/app/servicos/executor_regras.py

# 2. Restaurar manifesto anterior  
cp gav-autonomo/app/config/model_manifest_backup.yml gav-autonomo/app/config/model_manifest.yml

# 3. Reiniciar serviços
docker-compose restart gav_autonomo

# 4. Desativar novos prompts no banco
UPDATE prompt_templates SET ativo = FALSE 
WHERE nome IN ('prompt_api_call_selector', 'prompt_api_repair') 
AND espaco = 'autonomo';
```

## Próximos Passos (Fase 5)

### Expandir Cobertura de APIs
- Adicionar endpoints de relatórios
- Integrar APIs de terceiros (pagamento, logística)
- Suporte a chamadas assíncronas

### Melhorar Reparo Automático
- Detectar padrões de erro mais complexos
- Cache de correções bem-sucedidas  
- Feedback loop: erros humanos alimentam prompt

### Observabilidade Avançada
- Dashboard de decisões do LLM
- Alertas para queda na taxa de sucesso
- Análise de drift nos prompts