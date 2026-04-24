# Setup local de desenvolvimento

Este guia descreve o caminho recomendado para trabalhar no Redisus/HEAL+ como repositório de software, não apenas como experimento local.

## Requisitos

- Python 3.11+
- Node.js 20+
- npm 10+
- Git
- Ambiente virtual Python local

Dependências pesadas de ML, GPU, modelos e datasets não são necessárias para a trilha de CI/smoke. Elas devem ser instaladas apenas quando a tarefa envolver treinamento, inferência local completa ou validação de modelos.

## Backend/API

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-ci.txt
python -m apps.api.app
```

O backend oficial fica em `apps/api`. O módulo `backend` existe como compatibilidade e não deve receber novas features sem justificativa.

## Frontend

```powershell
cd web\redisus-frontend
npm ci
npm run lint
npx tsc --noEmit
npm run build
npm run dev
```

Use `.env.example` e `.env.backend.example` como contrato de configuração. Nunca versione `.env`, credenciais Firebase, service accounts ou tokens.

## Toolchain

Com `make` disponível:

```powershell
make install-ci
make lint
make format-check
make test-smoke
make coverage
make web-lint
make web-typecheck
make web-build
```

Sem `make`, execute os mesmos comandos diretamente com `python -m ruff`, `python -m pytest` e `npm`.

## Artefatos locais

Datasets, checkpoints, bancos locais, runs de treino e imagens temporárias devem ficar no disco local ou em storage externo. O Git deve conter apenas código, documentação, manifests, model cards, dataset cards e amostras sintéticas pequenas.
