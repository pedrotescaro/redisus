# Estado Atual das Métricas

## Leitura Correta

O repositório possui artefatos úteis de benchmark, mas ainda não há um relatório unificado, reproduzível e congelado por versão de dataset.

## Artefatos Identificados

### Classificador `wound_classifier` v1

Fonte: `models/wound_classifier/evaluation_report.json`

- métrica agregada registrada: `0.4426`
- classes: 24 categorias do acervo original
- leitura: baseline exploratório com taxonomia ainda muito fragmentada

### Classificador `wound_classifier_v2`

Fonte: `models/wound_classifier_v2/model_metadata_v2.json`

- accuracy: `0.6025`
- top-3 accuracy: `0.8484`
- amostras de validação: `244`
- leitura: melhor baseline atual do repositório, mas ainda experimental

### Detector YOLO

Fonte: `runs/detect/runs/detect/wound/wound_yolov8/results.csv`

No artefato local disponível:

- precision(B): `0.9790`
- recall(B): `0.9918`
- mAP50(B): `0.9912`
- mAP50-95(B): `0.7654`

Leitura correta:

- o run disponível não está amarrado a um relatório formal de dataset congelado;
- os números são promissores, mas ainda devem ser tratados como resultados exploratórios de experimento.

## Débitos de Reprodutibilidade

- faltam manifests oficiais de split;
- faltam versões explícitas de dataset por experimento;
- faltam relatórios únicos por modelo;
- os paths canônicos de ONNX referenciados pelo runtime principal ainda não estão presentes no repositório.

## Conclusão

O projeto já tem sinais técnicos relevantes, mas a apresentação correta hoje é:

- benchmark em consolidação;
- resultados iniciais promissores;
- ainda não clinicamente validados;
- ainda não prontos para claims fortes de produção.
