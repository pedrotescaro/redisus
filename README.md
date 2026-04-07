# HEAL+ / REDISUS

Plataforma de apoio ao diagnóstico de feridas por imagem, organizada para pesquisa aplicada, demonstração técnica e evolução incremental para produção.

## Status Atual

- `apps/api/` é o backend oficial do projeto.
- `packages/` concentra a camada canônica de wrappers para domínio e inferência.
- `src/` continua hospedando o núcleo clínico e de inferência durante a transição.
- `web/redisus-frontend/` contém a interface Next.js do fluxo clínico.
- `backend/` agora funciona como shim de compatibilidade para o backend oficial.
- `models/`, `dataset/` e `runs/` guardam artefatos experimentais de ML ainda em consolidação.

O repositório foi reorganizado para priorizar quatro frentes:

1. `PT2`: requisitos, arquitetura real e contrato de dados.
2. `PT3`: protocolo de coleta, rastreabilidade e curadoria do dataset.
3. `PT4`: baseline honesto, catálogo de modelos e model cards.
4. `PT5`: jornada diagnóstica demonstrável e documentação de produto.

## Problema

A avaliação clínica de feridas crônicas ainda depende fortemente de inspeção visual subjetiva, documentação heterogênea e baixa padronização de captura. Isso dificulta rastreabilidade, comparação longitudinal e treinamento de modelos robustos.

## Solução

O HEAL+ / REDISUS organiza um fluxo de:

`captura/upload -> avaliação clínica -> inferência -> relatório -> histórico`

com foco em:

- análise de imagem de feridas;
- classificação etiológica e composição tecidual;
- geração de relatórios estruturados;
- preparação para interoperabilidade clínica.

## Estrutura Recomendada

```text
apps/                     entrypoints canônicos
packages/                 wrappers estáveis para domínio e inferência
backend/                  compatibilidade legada do backend
src/                      domínio clínico, análise e serviços centrais
web/redisus-frontend/     frontend Next.js
docs/                     arquitetura, dados, produto, pesquisa e compliance
artifacts/                legados e logs históricos organizados
ml/                       benchmark, registro e documentação de modelos
scripts/                  utilitários e rotinas de treinamento
tests/                    testes Python
```

## Documentos Principais

- Arquitetura atual: [docs/architecture/system-architecture.md](docs/architecture/system-architecture.md)
- Matriz de requisitos e entregas: [docs/requirements/requirements-matrix.md](docs/requirements/requirements-matrix.md)
- Dicionário de dados: [docs/data/data-dictionary.md](docs/data/data-dictionary.md)
- Protocolo de coleta: [docs/data/collection-protocol.md](docs/data/collection-protocol.md)
- Dataset card: [docs/data/dataset-card.md](docs/data/dataset-card.md)
- Baseline de modelos: [ml/benchmarks/baseline_report.md](ml/benchmarks/baseline_report.md)
- Model card principal: [ml/model_cards/wound_classifier_v3.md](ml/model_cards/wound_classifier_v3.md)
- Jornada do usuário: [docs/product/user-journey.md](docs/product/user-journey.md)
- Roteiro de demo: [docs/product/demo-script.md](docs/product/demo-script.md)
- Segurança: [SECURITY.md](SECURITY.md)
- Roadmap: [ROADMAP.md](ROADMAP.md)

## Execução Local

### 1. Backend clínico e domínio Python

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m apps.api.app
```

Observação: o repositório ainda mistura dependências pesadas de inferência, experimentação e backend. A próxima etapa recomendada é separar ambientes `dev`, `train` e `prod`.

### 2. Frontend

```powershell
cd web\redisus-frontend
copy .env.local.example .env.local
npm install
npm run dev
```

### 3. Variáveis de ambiente

Use o arquivo [`.env.example`](.env.example) como contrato central e mantenha arquivos reais fora do Git.

## Verdade Atual do Projeto

- Existe valor técnico real em `src/`, `tests/` e na experiência web.
- O pipeline de ML ainda está em modo experimental e precisa de benchmark consolidado.
- O repositório ainda não deve ser apresentado como sistema pronto para produção clínica.
- O foco atual é consolidar o módulo de diagnóstico e a evidência técnica de entrega.

## Legados Preservados

- README anterior: [docs/research/legacy-readme.md](docs/research/legacy-readme.md)
- Arquitetura anterior: [docs/architecture/platform-architecture-legacy.md](docs/architecture/platform-architecture-legacy.md)
- Guia de treino legado: [docs/research/training-guide.md](docs/research/training-guide.md)
- Backups e logs antigos: [artifacts/README.md](artifacts/README.md)

## Próximos Passos

- fechar um backend oficial para o fluxo clínico;
- consolidar o dataset com manifests e QA;
- publicar benchmark reproduzível;
- validar a jornada de demonstração de ponta a ponta;
- preparar CI/CD e hardening de segurança.
