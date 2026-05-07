# HEAL+ ML Workspace

Pipeline offline para treino e avaliacao de modelos de feridas cronicas. O frontend nao executa treino pesado e nao deve fingir IA clinica validada.

## Estrutura

- `datasets/`: manifestos e datasets locais nao versionados.
- `notebooks/`: exploracao e auditoria.
- `scripts/`: preparacao, treino, avaliacao, exportacao e inferencia.
- `models/`: pesos locais nao versionados.
- `configs/`: configuracoes de treino.
- `outputs/`: metricas, predicoes e relatorios.
- `benchmarks/`, `model_cards/`, `registry/`: governanca ja existente.

## Ordem recomendada

1. Preparar dataset licenciado com imagens e mascaras.
2. Validar mascaras.
3. Treinar segmentacao ferida vs fundo.
4. Avaliar Dice, IoU, Precision, Recall, F1, FPR e FNR.
5. Testar imagens fora do dataset.
6. Treinar validador de entrada/ROI.
7. Somente depois treinar classificacao tecidual.

## Segurança

Nao coloque imagens clinicas identificaveis no Git. Remova EXIF, nomes, documentos, rosto e metadados sensiveis. Exija consentimento e revisao profissional antes de exportar ROIs internas.
