# Manifests

Esta pasta deve concentrar somente manifests versionados, nunca os arquivos brutos de dataset.

Exemplos esperados:

- `dataset_v1.csv`: lista de amostras sem dados pessoais e sem caminhos locais sensiveis.
- `splits_v1.json`: definicao reprodutivel de treino, validacao e teste.
- `class_map_v1.yaml`: taxonomia e mapeamento de classes.
- `checksums_v1.txt`: hashes SHA-256 dos artefatos armazenados fora do Git.

Cada manifest deve apontar para a politica em `docs/data/artifact-policy.md` e para o dataset card correspondente em `docs/data/`.
