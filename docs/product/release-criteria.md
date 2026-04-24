# Critérios de release piloto

O piloto não deve ser tratado como liberação assistencial irrestrita. Ele é uma etapa técnica supervisionada.

## v0.1.0-alpha

- Repositório sem datasets, checkpoints, runs e bancos versionados.
- README alinhado com arquitetura real.
- `SECURITY.md`, `CODEOWNERS`, templates e branch protection documentados.
- CI Python, CI Web, CodeQL, Secret Scan e Artifact Guard ativos.
- Documentação de setup, testes, releases e política de artefatos.
- Changelog e notas em `docs/operations/releases/v0.1.0-alpha.md`.
- Aviso claro de que o release nao e liberacao assistencial.

## v0.2.0

- OpenAPI inicial publicado.
- Testes de contrato para rotas clínicas principais.
- Cobertura mínima global de 60% no recorte crítico.
- DB temporário em testes.
- Frontend validado contra contrato da API.

## v0.3.0

- FHIR R4 com validação estrutural dos bundles principais.
- Model registry com URIs externas e checksums.
- Dataset cards e manifests completos.
- Benchmark mínimo reproduzível para inferência e pipeline de imagem.

## Piloto técnico

- Fluxo paciente-lesão-imagem-avaliação-plano testado ponta a ponta.
- Limitações clínicas explícitas na interface e na documentação.
- Revisão humana obrigatória para qualquer saída de IA.
- Política LGPD revisada por responsável institucional.
- Plano de incidentes e rollback documentado.
