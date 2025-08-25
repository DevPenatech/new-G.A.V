-- /infra/banco_dados/schema.sql

-- Habilita extensões
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;

-- === CATÁLOGO DE PRODUTOS ===
CREATE TABLE produtos (
    id SERIAL PRIMARY KEY,
    codprod INTEGER UNIQUE NOT NULL,
    descricao TEXT,
    descricaoweb TEXT,
    departamento VARCHAR(100),
    categoria VARCHAR(100),
    marca VARCHAR(100)
);

CREATE TABLE produto_itens (
    id SERIAL PRIMARY KEY,
    produto_id INTEGER NOT NULL REFERENCES produtos(id) ON DELETE CASCADE,
    unidade VARCHAR(10) NOT NULL,
    qtunit INTEGER DEFAULT 1,
    UNIQUE(produto_id, unidade)
);

CREATE TABLE produto_precos (
    id SERIAL PRIMARY KEY,
    item_id INTEGER NOT NULL REFERENCES produto_itens(id) ON DELETE CASCADE,
    codfilial INTEGER NOT NULL,
    pvenda NUMERIC(10, 2),
    poferta NUMERIC(10, 2),
    atualizado_em TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(item_id, codfilial)
);

-- Tabela de Aliases de PRODUTO (para a Fase 3)
CREATE TABLE produto_aliases (
    id SERIAL PRIMARY KEY,
    produto_id INTEGER NOT NULL REFERENCES produtos(id) ON DELETE CASCADE,
    alias TEXT NOT NULL,
    ativo BOOLEAN DEFAULT TRUE,
    origem VARCHAR(50) DEFAULT 'manual' -- ('manual' ou 'automatico_sugerido')
);

-- === DICIONÁRIOS E ALIASES (NOVO) ===
CREATE TABLE unidade_aliases (
    id SERIAL PRIMARY KEY,
    unidade_principal VARCHAR(10) NOT NULL, -- ex: 'CX', 'UN', 'PK'
    alias VARCHAR(100) UNIQUE NOT NULL, -- ex: 'caixa', 'unidade', 'pack'
    ativo BOOLEAN DEFAULT TRUE
);
COMMENT ON TABLE unidade_aliases IS 'Dicionário de sinônimos para unidades de medida.';

-- Populando a tabela com os sinônimos que você forneceu
INSERT INTO unidade_aliases (unidade_principal, alias) VALUES
('CX', 'caixa'),
('UN', 'unidade'),
('FD', 'fardo'),
('PK', 'pack'),
('PC', 'pacote'),
('KG', 'kilo'),
('LT', 'lata'),
('DP', 'display'),
('CJ', 'conjunto'),
('SC', 'saco'),
('DZ', 'duzia');

-- === TRANSAÇÕES E VENDAS ===

CREATE TABLE carrinhos (
    id SERIAL PRIMARY KEY,
    sessao_id VARCHAR(255) UNIQUE NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'aberto',
    criado_em TIMESTAMPTZ DEFAULT NOW(),
    atualizado_em TIMESTAMPTZ DEFAULT NOW()
);
COMMENT ON TABLE carrinhos IS 'Representa o carrinho de compras de um usuário em uma sessão.';

CREATE TABLE carrinho_itens (
    id SERIAL PRIMARY KEY,
    carrinho_id INTEGER NOT NULL REFERENCES carrinhos(id) ON DELETE CASCADE,
    item_id INTEGER NOT NULL REFERENCES produto_itens(id),
    quantidade INTEGER NOT NULL CHECK (quantidade > 0),
    preco_unitario_registrado NUMERIC(10, 2),
    adicionado_em TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(carrinho_id, item_id)
);
COMMENT ON TABLE carrinho_itens IS 'Itens dentro de um carrinho de compras específico.';

CREATE TABLE pedidos (
    id SERIAL PRIMARY KEY,
    carrinho_id INTEGER UNIQUE REFERENCES carrinhos(id),
    cliente_id INTEGER,
    status VARCHAR(50) NOT NULL DEFAULT 'rascunho',
    valor_total NUMERIC(10, 2) NOT NULL,
    criado_em TIMESTAMPTZ DEFAULT NOW()
);
COMMENT ON TABLE pedidos IS 'Representa um orçamento ou pedido finalizado pelo cliente.';

CREATE TABLE pedido_itens (
    id SERIAL PRIMARY KEY,
    pedido_id INTEGER NOT NULL REFERENCES pedidos(id) ON DELETE CASCADE,
    item_id INTEGER NOT NULL REFERENCES produto_itens(id),
    quantidade INTEGER NOT NULL,
    preco_unitario NUMERIC(10, 2) NOT NULL,
    subtotal NUMERIC(10, 2) NOT NULL
);
COMMENT ON TABLE pedido_itens IS 'Snapshot dos itens no momento em que um pedido/orçamento é gerado.';

-- === LOGS E TREINAMENTO ===

CREATE TABLE interacao_log (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    sessao_id VARCHAR(255) NOT NULL,
    canal VARCHAR(50),
    mensagem_usuario TEXT,
    resposta_json JSONB,
    feedback_tipo VARCHAR(100),
    feedback_esperado JSONB,
    processado_para_treino BOOLEAN DEFAULT FALSE
);
COMMENT ON TABLE interacao_log IS 'Registra todas as interações e feedbacks para análise e re-treinamento.';

-- === GERENCIAMENTO DE IA (NOVO) ===

CREATE TABLE prompt_templates (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(100) NOT NULL, -- um nome único para identificar o prompt, ex: 'mestre', 'fallback_busca'
    template TEXT NOT NULL, -- O texto do prompt em si
    versao TEXT DEFAULT 'v1',
    espaco TEXT NOT NULL DEFAULT 'legacy',
    ativo BOOLEAN DEFAULT TRUE,
    criado_em TIMESTAMPTZ DEFAULT NOW(),
    atualizado_em TIMESTAMPTZ DEFAULT NOW()
);
ADD CONSTRAINT unica_por_espaco UNIQUE (espaco, nome, versao);
COMMENT ON TABLE prompt_templates IS 'Central de templates de prompt para o LLM.';

-- === GERENCIAMENTO DE IA (ADICIONAR NO FINAL DA SEÇÃO) ===

-- Tabela para armazenar exemplos para Few-Shot Prompting
CREATE TABLE prompt_exemplos (
    id SERIAL PRIMARY KEY,
    prompt_id INTEGER NOT NULL REFERENCES prompt_templates(id) ON DELETE CASCADE,
    exemplo_input TEXT NOT NULL,
    exemplo_output_json TEXT NOT NULL,
    ativo BOOLEAN DEFAULT TRUE,
    criado_em TIMESTAMPTZ DEFAULT NOW()
);
COMMENT ON TABLE prompt_exemplos IS 'Armazena pares de input/output para ensinar os prompts (Few-Shot).';

-- Populando com nossos prompts atuais
INSERT INTO prompt_templates (nome, template) VALUES 
('prompt_mestre', E'Você é G.A.V., um assistente de vendas e orquestrador de ferramentas. Sua única e exclusiva função é analisar a mensagem do usuário e retornar um JSON válido contendo o `tool_name` e os `parameters` da ferramenta mais apropriada a ser chamada.\n\nVocê NUNCA deve conversar com o usuário ou enviar qualquer texto que não seja o JSON final.\n\nAs ferramentas disponíveis são:\n- `buscar_produtos`: Usada para buscar produtos por texto.\n  - `query`: o termo de busca.\n  - `ordenar_por` (opcional): ''preco_asc'' para "barato", ''preco_desc'' para "caro".\n- `iniciar_adicao_item_carrinho`: Intenção de adicionar um item ao carrinho quando o ID não é fornecido.\n  - `nome_produto`: o nome do produto para buscar.\n  - `quantidade`: a quantidade desejada.\n- `adicionar_item_carrinho`: Adiciona um item específico ao carrinho usando seu ID.\n  - `item_id`: o ID numérico do item (SKU).\n  - `quantidade`: a quantidade desejada.\n- `ver_carrinho`: Usada para ver o conteúdo do carrinho. Sem parâmetros.\n\nAnalise a mensagem e retorne APENAS o JSON da ferramenta.'),

('prompt_fallback_busca', E'A busca original do usuário foi por ''{mensagem_usuario}''.\nNão encontramos uma correspondência exata para a unidade de medida solicitada.\nNo entanto, encontramos o produto com estas variações disponíveis: {contexto}.\nSua tarefa é informar ao usuário de forma clara e amigável que a unidade que ele pediu NÃO foi encontrada, mas que você encontrou o produto em outras embalagens.\nSeja fiel aos dados e apresente as opções disponíveis.\nSua resposta DEVE ser um JSON no formato: {{"tool_name": "handle_chitchat", "parameters": {{"mensagem": "SUA_RESPOSTA_AQUI"}}}}'),

('prompt_sucesso_busca', E'A busca do usuário foi por ''{mensagem_usuario}''.\nEncontramos os seguintes resultados que correspondem exatamente ao pedido: {contexto}.\nSua tarefa é apresentar estes resultados de forma amigável e clara para o usuário.\nSua resposta DEVE ser um JSON no formato: {{"tool_name": "handle_chitchat", "parameters": {{"mensagem": "SUA_RESPOSTA_AQUI"}}}}');


-- Criar tabela para contexto de sessões
CREATE TABLE IF NOT EXISTS contexto_sessoes (
    id SERIAL PRIMARY KEY,
    sessao_id VARCHAR(255) NOT NULL,
    tipo_contexto VARCHAR(100) NOT NULL,
    contexto_estruturado JSONB NOT NULL,
    mensagem_original TEXT,
    resposta_apresentada TEXT,
    criado_em TIMESTAMPTZ DEFAULT NOW(),
    atualizado_em TIMESTAMPTZ DEFAULT NOW(),
    ativo BOOLEAN DEFAULT TRUE
);

-- --- ÍNDICES DE PERFORMANCE ---

CREATE OR REPLACE FUNCTION public.unaccent_immutable(text)
 RETURNS text
 LANGUAGE sql
 IMMUTABLE PARALLEL SAFE STRICT
AS $function$
SELECT public.unaccent($1);
$function$;

-- Função para FTS com pesos
CREATE OR REPLACE FUNCTION public.produtos_fts_document(p_descricaoweb text, p_descricao text, p_marca text, p_categoria text, p_departamento text)
 RETURNS tsvector
 LANGUAGE plpgsql
 IMMUTABLE
AS $function$
BEGIN
    RETURN (
        setweight(to_tsvector('portuguese', public.unaccent_immutable(coalesce(p_descricaoweb, p_descricao, ''))), 'A') ||
        setweight(to_tsvector('portuguese', public.unaccent_immutable(coalesce(p_marca, ''))), 'B') ||
        setweight(to_tsvector('portuguese', public.unaccent_immutable(coalesce(p_categoria, ''))), 'C') ||
        setweight(to_tsvector('portuguese', public.unaccent_immutable(coalesce(p_departamento, ''))), 'D')
    );
END;
$function$;

-- Índice FTS, agora usando nossa função imutável
CREATE INDEX idx_produtos_busca_fts ON produtos USING GIN (public.produtos_fts_document(descricaoweb, descricao, marca, categoria, departamento));

-- Índice de Trigram, agora usando nossa função imutável
CREATE INDEX idx_produtos_descricao_trgm ON produtos USING gin (public.unaccent_immutable(descricao) gin_trgm_ops);

-- Índices B-Tree padrão para acelerar filtros e joins.
CREATE INDEX idx_produtos_marca ON produtos (marca);
CREATE INDEX idx_produto_itens_produto_id ON produto_itens (produto_id);
CREATE INDEX idx_produto_precos_item_id ON produto_precos (item_id);
CREATE INDEX idx_carrinho_itens_carrinho_id ON carrinho_itens (carrinho_id);
CREATE INDEX idx_pedidos_cliente_id ON pedidos (cliente_id);
CREATE INDEX idx_pedido_itens_pedido_id ON pedido_itens (pedido_id);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_contexto_sessoes_sessao_id ON contexto_sessoes (sessao_id);
CREATE INDEX IF NOT EXISTS idx_contexto_sessoes_ativo ON contexto_sessoes (ativo);
CREATE INDEX IF NOT EXISTS idx_contexto_sessoes_tipo ON contexto_sessoes (tipo_contexto);

-- Função para limpeza automática
CREATE OR REPLACE FUNCTION limpar_contextos_antigos()
RETURNS void AS $$
BEGIN
    WITH contextos_rankeados AS (
        SELECT id, 
               ROW_NUMBER() OVER (PARTITION BY sessao_id ORDER BY criado_em DESC) as rn
        FROM contexto_sessoes 
        WHERE ativo = TRUE
    )
    UPDATE contexto_sessoes 
    SET ativo = FALSE 
    WHERE id IN (
        SELECT id FROM contextos_rankeados WHERE rn > 3
    );
END;
$$ LANGUAGE plpgsql;
