# Roadmap

## Now

- Consolidar o módulo de diagnóstico como espinha dorsal do projeto.
- Tornar o repositório legível para banca, portfólio e parceiros.
- Fechar requisitos, arquitetura real e contrato de dados.
- Documentar dataset, benchmark atual e limitações.
- Organizar a jornada de demo clínica.

## Next

- Definir um backend oficial para o fluxo clínico.
- Separar ambientes `dev`, `train` e `prod`.
- Criar pipeline de CI para Python e frontend.
- Padronizar a taxonomia clínica entre dataset, modelo, API e UI.
- Estruturar catálogo de modelos com versionamento.

## Later

- Gateway FHIR com testes de integração.
- Observabilidade e auditoria de eventos clínicos.
- Pilotos multicêntricos e governança operacional.
- Estratégia de transferência tecnológica.

## Plano de 4 Semanas

### Semana 1

- limpar a raiz do repositório;
- publicar o novo README;
- criar a matriz de requisitos e o mapa arquitetural real;
- revisar o contrato de dados clínicos.

### Semana 2

- fechar protocolo de coleta e checklist de qualidade;
- gerar inventário e splits versionados do dataset;
- publicar dataset card e relatório de curadoria.

### Semana 3

- consolidar baseline de modelos;
- escrever model cards;
- identificar claramente o que é pipeline real, fallback e demo.

### Semana 4

- fechar roteiro de demonstração;
- capturar screenshots e GIF;
- preparar backlog priorizado de interface e usabilidade;
- estabilizar workflows de CI.

## Roadmap técnico de profissionalização

### Fase 1: limpeza e governança

- Remover datasets, checkpoints, bancos locais e runs do versionamento.
- Ativar Artifact Guard em PRs.
- Adicionar `CODEOWNERS` e documentar branch protection.
- Consolidar `apps/api` e `web/redisus-frontend` como entrypoints oficiais.

### Fase 2: testes, CI/CD e reprodutibilidade

- Padronizar comandos com `pyproject.toml`, `Makefile` e pre-commit.
- Rodar lint, format check, typecheck informativo, smoke tests e cobertura na CI.
- Separar testes por marcadores: `unit`, `contract`, `fhir`, `integration`, `smoke`, `security`, `e2e`, `ml` e `slow`.
- Publicar release draft por tag semântica.

### Fase 3: arquitetura e modularização

- Isolar domínio clínico, persistência, segurança, inferência e interoperabilidade.
- Reduzir dependência de scripts grandes na raiz.
- Formalizar OpenAPI para rotas clínicas oficiais.
- Usar banco temporário em testes e configuração explícita em produção.

### Fase 4: interoperabilidade e produto

- Validar bundles FHIR R4 com snapshots e terminologias.
- Documentar mapeamento RNDS/SUS aplicável.
- Alinhar frontend ao contrato clínico versionado.
- Publicar model registry com URIs externas, checksums e limitações.

### Fase 5: release piloto

- Publicar `v0.1.0` apenas com CI verde, Artifact Guard verde, changelog e limitações clínicas.
- Tratar qualquer saída de IA como apoio à decisão com revisão humana obrigatória.
- Definir storage institucional para datasets, modelos e evidências de validação.
