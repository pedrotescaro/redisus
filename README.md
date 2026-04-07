# HEAL+ / REDISUS

Plataforma de apoio ao diagnóstico e acompanhamento longitudinal de feridas, com backend clínico em Python, frontend web em Next.js e pipeline de IA para imagem médica.

[![CI Python](https://github.com/pedrotescaro/redisus/actions/workflows/ci-python.yml/badge.svg)](https://github.com/pedrotescaro/redisus/actions/workflows/ci-python.yml)
[![CI Web](https://github.com/pedrotescaro/redisus/actions/workflows/ci-web.yml/badge.svg)](https://github.com/pedrotescaro/redisus/actions/workflows/ci-web.yml)
[![CodeQL](https://github.com/pedrotescaro/redisus/actions/workflows/codeql.yml/badge.svg)](https://github.com/pedrotescaro/redisus/actions/workflows/codeql.yml)
[![Secret Scan](https://github.com/pedrotescaro/redisus/actions/workflows/secret-scan.yml/badge.svg)](https://github.com/pedrotescaro/redisus/actions/workflows/secret-scan.yml)
[![License](https://img.shields.io/github/license/pedrotescaro/redisus)](LICENSE)

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.x-000000?logo=flask&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-14-000000?logo=next.js&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=0A0A0A)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript&logoColor=white)
![Firebase](https://img.shields.io/badge/Firebase-Auth%20%7C%20Firestore%20%7C%20Storage-FFCA28?logo=firebase&logoColor=black)
![PyTorch](https://img.shields.io/badge/PyTorch-2.x-EE4C2C?logo=pytorch&logoColor=white)
![OpenCV](https://img.shields.io/badge/OpenCV-4.x-5C3EE8?logo=opencv&logoColor=white)
![FHIR](https://img.shields.io/badge/HL7%20FHIR-R4-orange)
![SQLite](https://img.shields.io/badge/SQLite-Local%20DB-003B57?logo=sqlite&logoColor=white)

## Visão Geral

O HEAL+ / REDISUS organiza um fluxo clínico ponta a ponta para acompanhamento de pacientes com feridas:

`paciente -> lesão -> imagem -> IA -> avaliação -> evolução -> plano -> acompanhamento`

Hoje o repositório já entrega:

- cadastro e avaliação clínica;
- upload e validação real de imagens;
- inferência com contrato padronizado de saída;
- timeline clínica por lesão;
- geração de `care plan`, `follow-up` e alertas;
- RBAC backend-first com postura zero trust;
- dashboard com fila clínica decisória;
- base para interoperabilidade clínica e exportação FHIR.

## Problema

A avaliação de feridas crônicas ainda depende muito de inspeção visual subjetiva, documentação heterogênea e baixa padronização de captura. Isso dificulta:

- rastreabilidade longitudinal;
- comparação objetiva da evolução;
- priorização clínica;
- treinamento e validação de modelos robustos;
- interoperabilidade com fluxos assistenciais reais.

## O Que Este Repositório É Hoje

Este repositório é uma base técnica séria para produto clínico e pesquisa aplicada, mas ainda não deve ser apresentado como sistema clínico pronto para produção assistencial.

O estado atual é:

- backend oficial consolidado em [`apps/api/`](apps/api/);
- domínio clínico e serviços centrais ainda concentrados em [`src/`](src/);
- wrappers estáveis em [`packages/`](packages/);
- frontend web em [`web/redisus-frontend/`](web/redisus-frontend/);
- ML e artefatos experimentais ainda em consolidação em [`ml/`](ml/), [`models/`](models/), [`dataset/`](dataset/) e [`runs/`](runs/).

## Fluxo Clínico Principal

O fluxo principal que guia o produto hoje é:

1. registrar o paciente;
2. criar a lesão;
3. associar imagem clínica;
4. rodar análise de IA;
5. registrar avaliação clínica;
6. consolidar evolução na timeline;
7. gerar ou atualizar plano de cuidado;
8. agendar acompanhamento e alertar prioridades.

Essa é a trilha mais importante do projeto neste momento. Novas features devem ficar subordinadas a esse fluxo.

## Funcionalidades Atuais

### Backend Clínico

- API oficial Flask com factory em [`apps/api/app.py`](apps/api/app.py)
- validação de payloads no backend
- upload validado por conteúdo real
- modelo de domínio com `Patient`, `Lesion`, `ClinicalImage`, `Assessment`, `InferenceResult`, `CarePlan`, `FollowUp` e `Alert`
- persistência local em SQLite
- histórico de inferência e resultado padronizado
- exportação e contratos clínicos estruturados

### IA e Análise de Imagem

- pipeline de inferência clínica em Python
- saída padronizada com `contract_version`, `model_version` e `confidence`
- fallback para cenários sem modelo principal disponível
- suporte a experimentação com detecção, segmentação e classificação

### Gestão Clínica

- timeline clínica por lesão
- comparação temporal de evolução
- geração automática de `care plan`
- criação de `follow-up`
- alertas clínicos persistidos
- dashboard com fila decisória baseada em risco, piora, atraso e alertas

### Segurança e Governança

- backend não confia no frontend
- RBAC aplicado no backend
- perfis clínicos e pesquisador com restrições de escrita
- `.env.example` como contrato
- `firestore.rules` e `storage.rules`
- secret scanning, CodeQL, Dependabot e CI no GitHub Actions

## Tecnologias Usadas

### Backend e API

- Python
- Flask
- Flask-CORS
- Pydantic
- Loguru
- SQLite
- Requests
- Python-Dotenv

### IA, Visão Computacional e ML

- PyTorch
- TorchVision
- OpenCV
- NumPy
- Ultralytics YOLO
- segmentation-models-pytorch
- ONNX Runtime
- TensorFlow / tf2onnx
- Transformers
- OpenCLIP
- MediaPipe
- Pillow

### Frontend

- Next.js 14
- React 18
- TypeScript
- Tailwind CSS
- Firebase
- Lucide React
- jsPDF

### Interoperabilidade e Documentação Clínica

- HL7 FHIR R4 via `fhir.resources`
- contratos clínicos documentados
- dicionário de dados
- dataset card
- documentação de arquitetura e roadmap

### CI/CD e Qualidade

- GitHub Actions
- CodeQL
- Gitleaks
- Dependabot
- Pytest
- smoke tests de API e segurança

## Arquitetura Real do Repositório

```text
apps/
  api/                   backend oficial
  web/                   referência canônica em transição
  desktop/               camada desktop legada

packages/
  clinical_domain/       wrappers e contratos do domínio clínico
  ml_inference/          wrappers de inferência
  shared/                utilitários compartilhados

src/
  data/                  banco e persistência
  dashboard/             API clínica e dashboard
  diagnosis/             lógica diagnóstica
  processing/            processamento de imagem
  treatment/             apoio à conduta e cuidado

web/redisus-frontend/    frontend web em Next.js
docs/                    arquitetura, dados, produto, pesquisa e compliance
ml/                      benchmarks, model cards e relatórios
dataset/                 acervo e documentação de dados
tests/                   testes Python
artifacts/               legados, saídas e logs históricos
```

## Documentação Principal

- Arquitetura atual: [docs/architecture/system-architecture.md](docs/architecture/system-architecture.md)
- Matriz de requisitos: [docs/requirements/requirements-matrix.md](docs/requirements/requirements-matrix.md)
- Dicionário de dados: [docs/data/data-dictionary.md](docs/data/data-dictionary.md)
- Protocolo de coleta: [docs/data/collection-protocol.md](docs/data/collection-protocol.md)
- Dataset card: [docs/data/dataset-card.md](docs/data/dataset-card.md)
- Jornada do usuário: [docs/product/user-journey.md](docs/product/user-journey.md)
- Demo script: [docs/product/demo-script.md](docs/product/demo-script.md)
- Baseline de modelos: [ml/benchmarks/baseline_report.md](ml/benchmarks/baseline_report.md)
- Model card principal: [ml/model_cards/wound_classifier_v3.md](ml/model_cards/wound_classifier_v3.md)
- Segurança: [SECURITY.md](SECURITY.md)
- Roadmap: [ROADMAP.md](ROADMAP.md)
- Changelog: [CHANGELOG.md](CHANGELOG.md)

## Como Rodar Localmente

### 1. Backend oficial

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
copy .env.example .env
python -m apps.api.app
```

Backend oficial:

- app factory: [`apps/api/app.py`](apps/api/app.py)
- healthcheck: `GET /api/v1/health`

### 2. Frontend web

```powershell
cd web\redisus-frontend
copy .env.local.example .env.local
npm install
npm run dev
```

### 3. Variáveis de ambiente

Use [`.env.example`](.env.example) como contrato central. Não versione segredos reais.

## Testes e Verificação

### Python

```powershell
python -m pytest tests/test_clinical_api_contracts.py tests/test_api_security.py tests/test_clinical_dashboard.py -q
```

### Frontend

```powershell
cd web\redisus-frontend
npm run lint
npm run build
```

## Segurança

Itens já presentes no repositório:

- validação de autenticação e autorização no backend;
- RBAC com restrição de escrita clínica;
- validação de upload por conteúdo real;
- secret scan em CI;
- CodeQL;
- regras Firebase locais;
- arquivos de ambiente de exemplo.

Antes de produção real, ainda é necessário:

- aplicar `firestore.rules` no ambiente Firebase real;
- aplicar `storage.rules` no ambiente Firebase real;
- revisar permissões reais de acesso;
- ativar branch protection;
- fechar o processo de release.

## Licença

Este repositório está licenciado sob a [Apache License 2.0](LICENSE).

Pontos práticos da licença neste projeto:

- o código pode ser usado, modificado e redistribuído sob os termos da Apache-2.0;
- avisos de copyright e licença devem ser preservados;
- arquivos modificados devem indicar que houve alterações;
- a licença inclui concessão expressa de patentes dos contribuidores;
- a licença não concede direitos de marca sobre nomes, identidade visual ou logotipos.

Avisos adicionais do projeto estão em [NOTICE](NOTICE).

Importante:

- datasets, pesos de modelos, serviços externos e dependências de terceiros continuam sujeitos às suas próprias licenças e termos de uso;
- se a titularidade institucional do código mudar no futuro, o copyright e o `NOTICE` devem ser atualizados para refletir isso corretamente.

## Importante

- O projeto já roda e demonstra valor técnico real.
- O fluxo clínico principal está sendo fechado com prioridade máxima.
- A base ainda não representa produto clínico homologado.
- A camada de ML continua parcialmente experimental e precisa de benchmark consolidado.

## Legados Preservados

- README anterior: [docs/research/legacy-readme.md](docs/research/legacy-readme.md)
- Arquitetura anterior: [docs/architecture/platform-architecture-legacy.md](docs/architecture/platform-architecture-legacy.md)
- Guia de treino legado: [docs/research/training-guide.md](docs/research/training-guide.md)
- Artefatos antigos: [artifacts/README.md](artifacts/README.md)

## Próximos Passos

- fechar o fluxo principal clínico ponta a ponta com UX consistente;
- tornar a fila clínica acionável no dashboard;
- consolidar dataset, manifests e QA de coleta;
- fortalecer segurança de produção;
- evoluir interoperabilidade FHIR e integração SUS;
- transformar a base atual em acompanhamento longitudinal real de paciente.
