# Estado Atual das Métricas

## Leitura Correta

O repositório possui artefatos úteis de benchmark, mas ainda não há um relatório unificado, reproduzível e congelado por versão de dataset.

## Artefatos Identificados

### Segmentador binario de ferida `small_unet_gn_v2`

Fonte: `ml/outputs/co2wounds_v2_unet_v2_final/final_metrics.json` e
`ml/model_cards/wound_segmentation.md` (artefatos locais fora do Git).

- dataset: CO2Wounds-V2, uso academico/nao comercial;
- registros originais: `607`;
- imagens unicas apos unir anotacoes duplicadas: `581`;
- split auditado: `461` treino e `120` validacao;
- hashes exatos compartilhados entre treino/validacao: `0`;
- melhor epoch: `8`;
- Dice macro por imagem: `0.6253`;
- IoU macro por imagem: `0.4900`;
- Dice agregado por pixel: `0.7014`;
- precision/recall agregados: `0.7069` / `0.6960`;
- threshold calibrado na validacao: `0.60`.

Leitura correta: primeiro baseline executavel e rastreavel de segmentacao
ferida/fundo no repositorio. Ainda nao ha teste externo ou separacao comprovada
por paciente; o modelo permanece experimental e nao comercial.

### Auditoria do Medetec local

Fonte: `ml/scripts/audit_classification_dataset.py`.

- arquivos: `1220`;
- hashes exatos unicos: `609`;
- copias extras: `611`;
- grupos duplicados: `609`;
- existe imagem exata com rotulos conflitantes;
- identificadores de paciente nao estao disponiveis.

Decisao: nao retreinar nem promover o classificador etiologico com esse layout
antes de deduplicacao, revisao de rotulos e split por paciente/fonte.

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
