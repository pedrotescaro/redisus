# Roadmap issues

Este documento transforma o plano tecnico do Redisus/Heal+ em uma fila de issues pequenas, auditaveis e priorizadas.
Use os labels definidos em `.github/labels.yml` como catalogo canonico para criar ou revisar as issues no GitHub.

## Ordem inicial de trabalho

| Ordem | Titulo | Prioridade | Tipo | Areas | Dependencias |
| --- | --- | --- | --- | --- | --- |
| 1 | [Criar issues e labels de governanca do roadmap](https://github.com/pedrotescaro/redisus/issues/26) | P0 | docs | docs, devops | nenhuma |
| 2 | [Adicionar Dependabot e endurecer CodeQL](https://github.com/pedrotescaro/redisus/issues/27) | P0 | security | security, devops | issue 26 |
| 3 | [Endurecer validacoes de artefatos e seguranca no CI](https://github.com/pedrotescaro/redisus/issues/28) | P0 | ci | devops, security, data | issue 27 |
| 4 | [Ampliar testes de contrato FHIR e API clinica](https://github.com/pedrotescaro/redisus/issues/29) | P1 | test | fhir, backend | issue 28 |
| 5 | [Documentar politica de dados clinicos e artefatos](https://github.com/pedrotescaro/redisus/issues/30) | P1 | docs | data, security, docs | issue 28 |
| 6 | [Organizar entrypoints e scripts de execucao](https://github.com/pedrotescaro/redisus/issues/31) | P1 | refactor | architecture, backend | issues 28 e 29 |
| 7 | [Aumentar cobertura minima para 55%](https://github.com/pedrotescaro/redisus/issues/32) | P2 | test | devops, test | issue 29 |
| 8 | [Preparar release v0.1.0-alpha](https://github.com/pedrotescaro/redisus/issues/33) | P1 | ci | product, devops, docs | issues 26 a 32 |

## Backlog pronto para issues

### P0 - Criar issues e labels de governanca do roadmap

Descricao: versionar o catalogo de labels, padronizar template de issue de roadmap e abrir as issues que guiam o ciclo de estabilizacao.

Criterios de aceite:
- `.github/labels.yml` lista prioridades, tipos, areas e status.
- `.github/ISSUE_TEMPLATE/roadmap_task.yml` coleta prioridade, area, objetivo, aceite, impacto e dependencias.
- As issues iniciais existem no GitHub ou estao documentadas aqui para criacao manual.

### P0 - Adicionar Dependabot e endurecer CodeQL

Descricao: configurar atualizacoes semanais de dependencias Python, npm e GitHub Actions, com agrupamento por ecossistema e analise CodeQL para Python e TypeScript.

Criterios de aceite:
- Dependabot cobre `pip`, `npm` e `github-actions`.
- CodeQL usa queries de seguranca ampliadas.
- Secret scanning local via workflow continua ativo.

### P0 - Endurecer validacoes de artefatos e seguranca no CI

Descricao: bloquear datasets, pesos, bancos locais, caches, videos e outros artefatos gerados no Git, alem de validar arquivos de governanca obrigatorios.

Criterios de aceite:
- CI falha quando arquivos proibidos sao rastreados.
- CI falha quando arquivos grandes indevidos entram no commit.
- Workflow publica mensagens acionaveis para o contribuidor.

### P1 - Ampliar testes de contrato FHIR e API clinica

Descricao: aumentar cobertura de contratos de interoperabilidade, bundles FHIR R4, payloads clinicos, erros de validacao e rotas criticas da API.

Criterios de aceite:
- Testes marcados como `contract` e `fhir` cobrem bundle, referencias, transacao e payload minimo.
- API clinica preserva campos obrigatorios e respostas de erro estaveis.
- Smoke suite continua rapida o suficiente para CI.

### P1 - Documentar politica de dados clinicos e artefatos

Descricao: consolidar regras de dados sensiveis, PHI/LGPD, datasets, modelos, hashes, armazenamento externo e publicacao de exemplos.

Criterios de aceite:
- Documentacao explica o que nunca deve entrar no Git.
- Politica define caminho para modelos e datasets externos.
- Pull requests passam a apontar para a politica.

### P1 - Organizar entrypoints e scripts de execucao

Descricao: reduzir ambiguidade de entrypoints na raiz e padronizar comandos de execucao para CLI, dashboard, treinamento e smoke tests.

Criterios de aceite:
- Scripts executaveis tem dono e finalidade documentados.
- Entry points da raiz apontam para modulos internos ou wrappers claros.
- Nenhuma funcionalidade e removida sem alternativa documentada.

### P2 - Aumentar cobertura minima para 55%

Descricao: elevar gradualmente o gate de cobertura do CI depois de ampliar testes de contrato.

Criterios de aceite:
- `REDISUS_COVERAGE_MIN` sobe para 55.
- Suite CI passa localmente e no GitHub.
- Lacunas restantes continuam registradas como divida tecnica.

### P1 - Preparar release v0.1.0-alpha

Descricao: criar release alpha com escopo explicito, changelog, criterios de validacao e aviso de nao uso clinico.

Criterios de aceite:
- `CHANGELOG.md` registra `v0.1.0-alpha`.
- Documento de criterios de release referencia testes, seguranca e politica de dados.
- GitHub Actions de release valida formato basico antes de publicar artefatos.
