# Processo de release

O Redisus deve usar versionamento semântico.

## Canais

- `v0.1.x`: governança, reprodutibilidade e demo técnica.
- `v0.2.x`: contratos de API, cobertura e smoke tests estáveis.
- `v0.3.x`: FHIR/RNDS, benchmark mínimo e model registry externo.
- `v1.0.0`: piloto técnico com limites clínicos documentados.

## Critérios mínimos

Antes de criar uma tag:

1. CI Python verde.
2. CI Web verde.
3. Artifact Guard verde.
4. CodeQL e Secret Scan sem achados críticos abertos.
5. `CHANGELOG.md` atualizado.
6. `ml/registry/models.yaml` sem apontar para artefatos versionados obrigatórios.
7. Limitações clínicas documentadas.

## Como publicar

```powershell
git tag v0.1.0-alpha
git push origin v0.1.0-alpha
```

O workflow `Release` cria uma release draft usando `docs/operations/releases/<tag>.md`. O mantenedor deve revisar notas, riscos conhecidos e artefatos antes de publicar.

## Rollback

Como o projeto ainda está antes de `v1.0.0`, mudanças incompatíveis podem ocorrer em `0.x`, mas devem estar explícitas no changelog. Em piloto, rollback deve ser operacional: voltar para a tag anterior e preservar dados de avaliação em backup seguro.
