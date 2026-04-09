# Plano de Melhoria do Heal Analyzer

## Objetivo

Evoluir o `heal_analyzer.py` de um entrypoint desktop monolítico para uma camada de análise reutilizável, testável e segura para uso no backend oficial.

## Verificação Executada

Como não encontrei um recurso versionado ou skill disponível chamado `GET SHIT DONE`, a verificação foi feita de forma direta no código e no runtime:

- inspeção da arquitetura atual e das referências a `heal_analyzer.py`;
- leitura das rotas oficiais e do backend clínico;
- execução dos testes do pipeline de visão computacional;
- smoke test do fluxo clínico oficial;
- smoke test de importação do `ClinicalWoundAnalyzer`.

## Achados Principais

### 1. O `heal_analyzer.py` concentra responsabilidades demais

Hoje o arquivo tem 3.538 linhas e mistura:

- regras clínicas;
- processamento OpenCV;
- carga de modelos;
- threads de análise;
- webcam;
- interface PyQt6.

Isso dificulta testes, reuso e operação headless no backend.

### 2. A API oficial ainda depende do módulo legado desktop

A rota [`apps/api/routes/integration.py`](apps/api/routes/integration.py) importa `ClinicalWoundAnalyzer` diretamente de `heal_analyzer.py`.

### 3. O backend pode ficar sem análise por dependência de UI

No ambiente verificado, a importação falhou porque `PyQt6` não está instalado, enquanto `requirements.txt` deixa `PyQt6` comentado como opcional. Isso significa que a análise de backend pode falhar por um detalhe de interface desktop.

### 4. O fluxo clínico oficial já tem um caminho estável alternativo

O fluxo baseado em [`src/dashboard/clinical_dashboard.py`](src/dashboard/clinical_dashboard.py) e [`packages/clinical_domain/workflow.py`](packages/clinical_domain/workflow.py) funcionou em smoke test, retornando contrato `2026-04-07` com `model_version = fallback-clinical-v1`.

### 5. Existe cobertura boa para os blocos de CV, mas não para o entrypoint real da integração

Os testes do pipeline principal passaram:

- `tests/test_tissue_analyzer.py`
- `tests/test_wound_detector_cv.py`
- `tests/test_wound_classifier_cv.py`
- `tests/test_image_recognition.py`

Falta cobertura direta para:

- `ClinicalWoundAnalyzer`;
- rota `/api/v1/analyze` em `apps/api/routes/integration.py`;
- comportamento do backend sem `PyQt6`.

## Prioridades

### Prioridade 0: Remover o bloqueio de produção

1. Extrair um núcleo headless do analisador para `src/` ou `packages/`.
2. Fazer a rota de integração depender desse núcleo, não do arquivo desktop.
3. Garantir que `heal_analyzer.py` vire apenas wrapper/UI.

### Prioridade 1: Unificar o caminho oficial de análise

1. Definir qual contrato é canônico para análise clínica.
2. Alinhar `heal_analyzer.py`, `src/diagnosis/wound_analyzer.py` e `packages/clinical_domain/workflow.py`.
3. Eliminar duplicação de classificação, score e montagem de resposta.

### Prioridade 2: Aumentar segurança de mudança

1. Adicionar testes de importação headless.
2. Adicionar teste da rota `/api/v1/analyze`.
3. Adicionar smoke test de fallback quando modelos opcionais não estiverem disponíveis.

### Prioridade 3: Melhorar manutenção e performance

1. Isolar carregamento de modelos por feature flag.
2. Lazy-load dos modelos pesados.
3. Padronizar logging, tempos de inferência e motivos de fallback.

## Plano em Fases

## Fase 1: Estabilização estrutural

### Entregas

- criar `ClinicalWoundAnalyzerCore` sem dependência de PyQt6;
- mover dataclasses e lógica clínica reutilizável para módulo headless;
- adaptar `apps/api/routes/integration.py` para usar o core;
- manter a UI desktop consumindo o core por composição.

### Critério de aceite

- backend sobe e consegue instanciar o analisador sem `PyQt6`;
- `python -c "from heal_analyzer import ClinicalWoundAnalyzer"` deixa de ser requisito para a API;
- a rota `/api/v1/analyze` não quebra por falta de biblioteca de interface.

## Fase 2: Convergência do domínio de análise

### Entregas

- escolher um contrato único para resultado clínico;
- centralizar score, tecidos, bordas, área e metadados;
- criar adaptadores para desktop, API e workflow clínico.

### Critério de aceite

- desktop, integração e workflow retornam campos equivalentes;
- regras clínicas deixam de existir em mais de um lugar.

## Fase 3: Cobertura e regressão

### Entregas

- testes unitários do `ClinicalWoundAnalyzerCore`;
- testes de integração da rota `/api/v1/analyze`;
- casos sintéticos com granulação, esfacelo e necrose;
- teste explícito para ambiente sem dependências opcionais.

### Critério de aceite

- cobertura do core nova;
- rota oficial validada por teste automatizado;
- fallback documentado e testado.

## Fase 4: Qualidade operacional

### Entregas

- métricas de tempo por etapa;
- motivos estruturados de fallback;
- configuração por ambiente para desktop, backend e treino;
- documentação de operação e limites clínicos.

### Critério de aceite

- logs permitem saber qual pipeline rodou;
- operação local e CI usam configuração previsível;
- docs deixam claro o que é produção, fallback e experimento.

## Backlog Inicial Recomendado

1. Criar `src/processing/clinical_wound_analyzer_core.py` ou `packages/ml_inference/clinical_wound_analyzer.py`.
2. Mover `ClinicalReport`, `TissueClassification` e `BorderAnalysis` para o módulo headless.
3. Remover imports de PyQt6 do caminho de execução do backend.
4. Atualizar `apps/api/routes/integration.py` para importar apenas o módulo headless.
5. Criar `tests/test_clinical_wound_analyzer_core.py`.
6. Criar `tests/test_integration_analyze_route.py`.
7. Revisar `requirements.txt` para separar dependências de backend e desktop.

## Ordem Recomendada de Execução

1. desacoplar UI do core;
2. trocar a dependência da API;
3. criar testes do core;
4. criar testes da rota de integração;
5. alinhar contrato com o workflow clínico oficial;
6. só depois otimizar performance e expandir features.

## Resultado Esperado

Ao final, o projeto terá:

- um analisador reutilizável e headless;
- menos risco de quebra no backend;
- caminho oficial de análise mais claro;
- cobertura automática sobre o que hoje está mais frágil;
- base melhor para futuras melhorias clínicas e de produto.
