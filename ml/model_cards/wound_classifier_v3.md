# Model Card - Wound Classifier v3

## Identificação

- nome: `WoundClassifier_v3_PyTorch`
- artefato principal: `models/wound_classifier_v2/wound_classifier_v2.pt`
- metadados: `models/wound_classifier_v2/model_metadata_v2.json`
- status: experimental

## Objetivo

Classificar imagens de feridas em grupos clínicos consolidados para apoio exploratório ao diagnóstico por imagem.

## Classes

- abdominal_wounds
- burns
- diabetic_ulcers
- epidermolysis_bullosa
- malignant_wounds
- miscellaneous
- necrotic_wounds
- pilonidal_sinus
- pressure_ulcers
- surgical_wounds
- venous_arterial_ulcers

## Dados

- fonte principal: acervo `Medetec`
- natureza: dataset público de imagens de feridas, heterogêneo e não multicêntrico
- limitação: taxonomia de origem não coincide integralmente com taxonomia clínica final do produto

## Métricas Registradas

- accuracy: `0.6025`
- top-3 accuracy: `0.8484`
- validação: `244` amostras

## Limitações

- forte desequilíbrio entre classes;
- baixa robustez para classes raras;
- ausência de validação clínica formal;
- ausência de benchmark congelado com governança completa de dados;
- não deve ser usado para decisão clínica autônoma.

## Uso Responsável

- usar apenas como apoio experimental;
- exigir revisão humana especializada;
- evitar exposição como produto médico validado.

## Próxima Revisão

- consolidar splits;
- comparar com baseline heurístico;
- alinhar classes do modelo com contrato clínico do sistema;
- publicar nova versão apenas com rastreabilidade completa.
