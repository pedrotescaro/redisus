# Backlog GSD: APIs + Heal Analyzer

## Framework GET SHIT DONE

Para este projeto, o formato `GET SHIT DONE` será usado assim:

- `P0`: remover bloqueios reais de arquitetura, runtime e contrato.
- `P1`: consolidar caminhos oficiais, testes e manutenção.
- `P2`: melhorar escala, observabilidade e experiência operacional.

Cada ticket abaixo já vem em formato de execução:

- objetivo claro;
- arquivos prováveis;
- checklist de implementação;
- definição de pronto;
- validação sugerida.

## Meta do ciclo

Fechar um caminho oficial, testável e previsível para análise clínica de feridas, com:

- backend sem dependência de UI desktop;
- contrato de análise consistente;
- menos duplicação entre API, workflow e analyzer;
- cobertura mínima sobre os fluxos críticos.

## Ordem GSD recomendada

1. Fechar `P0` antes de qualquer feature nova.
2. Executar `P1` em paralelo por fatias pequenas.
3. Só puxar `P2` quando o fluxo principal estiver estável.

## P0

### GSD-P0-01 — Unificar a rota `/api/v1/analyze` com o workflow oficial

**Objetivo**

Fazer a rota de integração parar de montar resultado clínico por caminho próprio e passar a usar o mesmo fluxo oficial da plataforma.

**Arquivos prováveis**

- `apps/api/routes/integration.py`
- `packages/clinical_domain/workflow.py`
- `packages/clinical_domain/models.py`

**Checklist**

- criar adaptador da rota para o workflow oficial;
- eliminar montagem manual redundante de payload;
- garantir contrato versionado consistente entre integração e fluxo clínico;
- manter compatibilidade de campos públicos já usados pelo frontend.

**Definição de pronto**

- `/api/v1/analyze` usa o mesmo pipeline de resultado clínico do fluxo principal;
- `contract_version` e `model_version` passam a ter origem única;
- não existe duplicação relevante de regra de interpretação na rota.

**Validação sugerida**

- smoke test da rota com upload válido;
- comparação de payload com resultado do workflow oficial;
- teste automatizado de contrato.

### GSD-P0-02 — Formalizar contrato único de `analysis result`

**Objetivo**

Parar de trafegar dicionários ad hoc para análise clínica e usar modelos de contrato explícitos.

**Arquivos prováveis**

- `packages/clinical_domain/models.py`
- `packages/clinical_domain/workflow.py`
- `apps/api/routes/integration.py`
- `src/processing/clinical_wound_analyzer_core.py`

**Checklist**

- definir modelo canônico para resultado clínico;
- mapear campos de borda, tecidos, score, risco, metadados e fallback;
- criar serialização única para API;
- documentar os campos obrigatórios e opcionais.

**Definição de pronto**

- backend e integração retornam estrutura equivalente;
- mudanças futuras de contrato passam por um único modelo;
- erros de campo divergente deixam de depender de inspeção manual.

**Validação sugerida**

- testes de serialização;
- teste de contrato para rota oficial e integração;
- revisão do payload com exemplos reais.

### GSD-P0-03 — Blindar fallback de modelos opcionais

**Objetivo**

Garantir que ausência de `torch`, `transformers`, `firebase_admin` ou outros módulos opcionais não quebre o fluxo principal.

**Arquivos prováveis**

- `src/processing/clinical_wound_analyzer_core.py`
- `apps/api/routes/integration.py`
- `apps/api/app.py`

**Checklist**

- padronizar flags de disponibilidade;
- padronizar motivo de fallback por componente;
- remover `except` silencioso que esconde indisponibilidade crítica;
- distinguir claramente `degraded mode` de erro fatal.

**Definição de pronto**

- o backend responde com previsibilidade em ambiente parcial;
- fallback fica explícito em log e/ou metadata;
- ausência de dependência opcional não derruba a API.

**Validação sugerida**

- smoke em ambiente sem `torch`;
- smoke em ambiente sem `firebase_admin`;
- teste automatizado cobrindo modo degradado.

## P1

### GSD-P1-01 — Separar o desktop em módulos dedicados

**Objetivo**

Continuar a desmontagem do monólito desktop e deixar `heal_analyzer.py` como entrypoint fino.

**Arquivos prováveis**

- `heal_analyzer.py`
- `apps/desktop/`

**Checklist**

- mover `AnalysisThread` para módulo desktop próprio;
- mover webcam e realtime para módulo próprio;
- mover helpers visuais para utilitário de UI;
- reduzir `heal_analyzer.py` a composição de tela e bootstrap.

**Definição de pronto**

- `heal_analyzer.py` deixa de concentrar classes grandes de runtime;
- desktop fica legível por camada;
- o core continua totalmente headless.

**Validação sugerida**

- `py_compile` dos módulos novos;
- import do entrypoint desktop;
- teste manual do desktop em máquina com `PyQt6`.

### GSD-P1-02 — Cobrir o core headless com regressão mínima

**Objetivo**

Ter segurança automática sobre o que hoje é mais crítico: import, analyze, fallback e erros de entrada.

**Arquivos prováveis**

- `tests/test_clinical_wound_analyzer_core.py`
- `tests/test_integration_analyze_route.py`
- `tests/conftest.py`

**Checklist**

- adicionar caso válido sintético;
- adicionar caso vazio/malformado;
- adicionar caso sem dependência opcional;
- adicionar caso de rota com upload inválido;
- validar chaves mínimas do contrato.

**Definição de pronto**

- cobertura mínima dos fluxos principais do core;
- rota de integração protegida contra regressão básica;
- falhas quebram cedo no CI.

**Validação sugerida**

- `pytest` dos testes novos;
- smoke do upload na rota de integração.

### GSD-P1-03 — Padronizar erros e observabilidade da API

**Objetivo**

Tornar falhas de análise legíveis, debuggáveis e rastreáveis em ambiente real.

**Arquivos prováveis**

- `apps/api/app.py`
- `apps/api/routes/integration.py`
- `packages/shared/`

**Checklist**

- incluir `request_id` em respostas de erro;
- classificar erros por categoria;
- logar duração e etapa falha;
- registrar modelo, fallback e modo de execução;
- remover `traceback.print_exc()` do caminho normal.

**Definição de pronto**

- erro operacional chega com contexto mínimo útil;
- logs permitem rastrear análise ponta a ponta;
- a equipe consegue diferenciar bug, input ruim e indisponibilidade externa.

**Validação sugerida**

- simular upload inválido;
- simular analyzer indisponível;
- inspecionar logs gerados.

### GSD-P1-04 — Separar dependências por perfil de execução

**Objetivo**

Parar de tratar backend, desktop e ML pesado como se fossem o mesmo ambiente.

**Arquivos prováveis**

- `requirements.txt`
- novos arquivos `requirements-api.txt`, `requirements-desktop.txt`, `requirements-ml.txt`
- `README.md`

**Checklist**

- definir pacote mínimo para API;
- definir extras de desktop;
- definir extras de treino/ML pesado;
- atualizar instruções de instalação.

**Definição de pronto**

- uma máquina de API não precisa instalar stack desktop;
- uma máquina desktop não precisa carregar tudo de treino;
- onboarding local fica mais previsível.

**Validação sugerida**

- criar ambiente mínimo de API;
- validar boot do backend;
- validar import do core headless.

## P2

### GSD-P2-01 — Instrumentar tempos por etapa do analyzer

**Objetivo**

Descobrir onde o pipeline realmente gasta tempo e onde vale otimizar.

**Arquivos prováveis**

- `src/processing/clinical_wound_analyzer_core.py`
- `packages/clinical_domain/workflow.py`

**Checklist**

- medir preprocessamento, detecção, ROI, segmentação, classificação e montagem;
- retornar ou logar breakdown por etapa;
- registrar quando um bloco foi pulado por indisponibilidade.

**Definição de pronto**

- existe visibilidade de latência por estágio;
- tuning futuro deixa de ser “no escuro”.

**Validação sugerida**

- executar análise com log detalhado;
- revisar breakdown de tempo em ao menos 3 imagens.

### GSD-P2-02 — Criar catálogo de modos de execução

**Objetivo**

Deixar explícito o que é `official`, `fallback`, `desktop`, `experimental` e `degraded`.

**Arquivos prováveis**

- `docs/architecture/system-architecture.md`
- `README.md`
- `packages/clinical_domain/workflow.py`
- `src/processing/clinical_wound_analyzer_core.py`

**Checklist**

- nomear modos de execução;
- mapear qual modelo/serviço roda em cada modo;
- expor isso no payload ou metadata;
- documentar os limites clínicos de cada modo.

**Definição de pronto**

- produto e engenharia falam a mesma língua sobre o runtime;
- demos e testes deixam claro quando o sistema está em fallback.

**Validação sugerida**

- revisar docs e respostas da API;
- conferir consistência entre código e documentação.

### GSD-P2-03 — Preparar fila assíncrona única para análise

**Objetivo**

Levar a integração para o mesmo padrão de job assíncrono e observável do fluxo clínico.

**Arquivos prováveis**

- `apps/api/routes/integration.py`
- `src/dashboard/clinical_api.py`
- `packages/clinical_domain/workflow.py`

**Checklist**

- decidir se a integração vira job ou delega para job já existente;
- padronizar status, polling e payload final;
- revisar persistência de histórico e auditoria.

**Definição de pronto**

- análise síncrona deixa de ser gargalo do backend;
- fila de análise fica mais escalável e rastreável.

**Validação sugerida**

- criar job;
- consultar status;
- validar payload final concluído.

## Sprint sugerida

### Sprint 1

- `GSD-P0-01`
- `GSD-P0-02`
- `GSD-P0-03`

### Sprint 2

- `GSD-P1-01`
- `GSD-P1-02`
- `GSD-P1-03`

### Sprint 3

- `GSD-P1-04`
- `GSD-P2-01`
- `GSD-P2-02`

### Sprint 4

- `GSD-P2-03`

## Regra de execução

Nenhum ticket `P1` ou `P2` deve abrir nova feature de produto se:

- existir duplicação de contrato entre integração e workflow;
- o backend depender de comportamento implícito de fallback;
- a rota `/api/v1/analyze` continuar sem cobertura mínima.

## Primeiros 3 tickets para puxar agora

1. `GSD-P0-01 — Unificar a rota /api/v1/analyze com o workflow oficial`
2. `GSD-P0-02 — Formalizar contrato único de analysis result`
3. `GSD-P1-02 — Cobrir o core headless com regressão mínima`
