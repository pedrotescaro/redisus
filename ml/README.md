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

## CO2Wounds-V2

Uso permitido neste projeto: pesquisa, TCC, prova de conceito e treinamento experimental inicial de segmentacao ferida vs. fundo. Nao usar o modelo resultante como IA clinica validada nem em produto comercial sem autorizacao formal dos autores.

Fluxo esperado depois de baixar o dataset fora do Git:

```bash
python ml/scripts/prepare_co2wounds_v2.py --root data/external/co2wounds-v2 --accept-non-commercial-research-license
python ml/scripts/validate_masks.py --manifest ml/datasets/co2wounds_v2_train.jsonl
python ml/scripts/train_segmentation.py --accept-experimental-non-commercial-use --epochs 30
```

O script aceita o layout oficial `train`, `train_anns`, `val`, `val_anns` ou o layout COCO `annotations/merged_annotations.json` + `imgs/`, gerando mascaras binarizadas quando necessario.
