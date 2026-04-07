# Artifacts

Esta pasta concentra arquivos que não representam a fonte principal do produto:

- `legacy/`: backups e versões antigas preservadas apenas como referência;
- `logs/`: logs históricos de treino e marcações auxiliares.

## Regras

- não usar `artifacts/` como fonte de verdade para documentação ou benchmark;
- novos outputs gerados automaticamente devem ir para buckets dedicados e preferencialmente fora do Git;
- qualquer artefato importante deve ter um documento associado explicando origem, versão e contexto.
