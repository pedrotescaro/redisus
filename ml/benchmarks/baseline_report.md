# Baseline Report

## Objetivo

Registrar o estado atual dos modelos e separar o que é benchmark utilizável do que é apenas artefato exploratório.

## Resumo

| Modelo | Artefato | Estado | Métrica disponível | Leitura |
|---|---|---|---|---|
| `wound_classifier` v1 | `models/wound_classifier/` | Exploratório | `0.4426` | baseline inicial com 24 classes |
| `wound_classifier_v2` | `models/wound_classifier_v2/` | Melhor baseline atual | `accuracy 0.6025`, `top3 0.8484` | resultado mais útil hoje |
| YOLO detector | `runs/detect/.../results.csv` | Exploratório | `mAP50 0.9912`, `mAP50-95 0.7654` | promissor, mas sem benchmark congelado |

## Achados Importantes

- os arquivos ONNX referenciados pelo runtime atual não estão presentes:
  - `models/yolo_wound_nano.onnx`
  - `models/unet_tissue_segmentation.onnx`
  - `models/efficientnet_etiology.onnx`
- isso significa que parte do pipeline “oficial” ainda cai em simulação, fallback ou caminhos alternativos.

## Decisão

Até a consolidação dos manifests e dos experimentos:

- usar `wound_classifier_v2` como baseline principal documentado;
- tratar YOLO como experimento promissor, não benchmark final;
- evitar claims clínicos fortes no README ou em apresentações.

## Próximas Entregas

1. congelar dataset e split;
2. repetir benchmark com relatório único;
3. vincular benchmark a versão de modelo, dataset e script;
4. publicar comparação entre heurística, DL e fallback.
