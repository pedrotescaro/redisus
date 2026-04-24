# Política de artefatos, dados e modelos

O repositório deve ser leve, auditável e seguro. Artefatos gerados não devem ser versionados no Git.

Esta politica deve ser lida junto com `docs/data/clinical-data-policy.md`, `docs/security/data-classification.md` e `SECURITY.md`.

## Permitido no Git

- Código-fonte.
- Testes e fixtures sintéticas pequenas.
- Documentação.
- Model cards.
- Dataset cards.
- Manifests e checksums.
- Schemas e contratos.
- Imagens pequenas de UI ou exemplo sintético explicitamente justificadas.

## Proibido no Git

- Dados clínicos reais.
- Dumps de banco.
- Arquivos `.db`, `.sqlite` ou `.sqlite3`.
- Checkpoints e pesos: `.pt`, `.pth`, `.keras`, `.h5`, `.ckpt`, `.onnx`, `.tflite`, `.task`, `.pb`.
- Diretórios `dataset/`, `models/`, `runs/` e `tmp_images/`.
- Logs de treinamento e TensorBoard events.
- DOCX/PDF gerados automaticamente quando houver fonte em Markdown, LaTeX ou script.

## Registro de modelos

Cada modelo publicado deve ter entrada em `ml/registry/models.yaml` com:

- `id`
- `version`
- `status`
- `task`
- `artifact_uri`
- `local_cache_path`
- `sha256`
- `license`
- `intended_use`
- `limitations`
- `metrics`

Enquanto o storage externo não for definido, use `artifact_uri: pending://...` e mantenha o arquivo local ignorado pelo Git.

## Registro de datasets

Cada dataset deve ter dataset card em `docs/data/` ou manifest em `data/manifests/`, incluindo origem, licença, termos de uso, data de coleta, splits, transformações, riscos e limitações.

## Fluxo recomendado para artefatos externos

1. Gere ou baixe o artefato fora do Git.
2. Calcule checksum SHA-256.
3. Registre origem, licenca, versao, data e responsavel.
4. Atualize dataset card, manifest ou model card.
5. Aponte `artifact_uri` para storage externo ou `pending://...` enquanto a decisao institucional estiver pendente.
6. Execute Artifact Guard antes do PR.

## Dados clinicos e LGPD

Dados clinicos reais, identificaveis ou sensiveis sao proibidos no Git. Isso inclui imagens de feridas, FHIR Bundles reais, relatorios, timelines, dumps, screenshots e logs com dados pessoais.

Quando a validacao clinica exigir material real, o repositorio deve guardar apenas metadados, protocolo, hash, versao anonimizada aprovada e referencia ao local externo autorizado.

## Exceções

Exceções precisam ser pequenas, justificadas e revisadas em PR. Exemplos atuais aceitáveis: `examples/synthetic_wound.jpg`, logos e assets estáticos essenciais do frontend.
