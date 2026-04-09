# Model Card - Pressure Injury Stage Classifier

## Identificacao

- nome: `PressureInjuryStageClassifier`
- artefato principal: `models/pressure_injury_stage_classifier/pressure_injury_stage_resnet50.pth`
- metadados: `models/pressure_injury_stage_classifier/model_metadata.json`
- status: research-specialist

## Objetivo

Refinar casos de **lesao por pressao** com classificacao especifica de estagio I-IV e explicabilidade mais clara no diagnostico.

## Dataset

- fonte esperada: `PIID (Pressure Injury Images Dataset)`
- modo de uso no projeto: dataset local, fora do Git
- finalidade recomendada: pesquisa, benchmark interno e prototipacao
- total local usado no baseline inicial: `1091` imagens
- split local: `763` treino, `163` validacao, `165` teste

## Classes

- `stage_1`
- `stage_2`
- `stage_3`
- `stage_4`

## O que o modelo/fallback considera

- tons rosados superficiais;
- vermelho vivo de leito exposto;
- tons amarelados associados a fibrina/esfacelo;
- areas escuras associadas a necrose/dano profundo;
- textura e densidade de bordas;
- contexto estruturado de area e dor quando disponivel.

## Saida esperada

- estagio LP sugerido;
- probabilidades por estagio;
- margem entre top-2 classes;
- recomendacoes por estagio;
- fatores considerados e sinais visuais agregados.

## Baseline Local Inicial

- data do treino: `2026-04-09`
- ambiente: `PyTorch 2.11.0 CPU`
- epocas: `8`
- melhor epoca: `8`
- validation accuracy: `0.7730`
- test accuracy: `0.7030`
- stage_1 test accuracy: `0.7143`
- stage_2 test accuracy: `0.7021`
- stage_3 test accuracy: `0.5476`
- stage_4 test accuracy: `0.8537`

Matriz de confusao no teste:

```text
           pred_s1 pred_s2 pred_s3 pred_s4
true_s1       25       7       0       3
true_s2        7      33       6       1
true_s3        1       3      23      15
true_s4        0       0       6      35
```

## Limitacoes

- nao substitui estadiamento clinico presencial;
- depende de qualidade fotografica e enquadramento;
- pode superestimar profundidade em imagens muito escuras ou com artefatos;
- sem pesos treinados, opera em modo heuristico especializado.

## Mitigacao stage_3 vs stage_4

- o inferenciador agora marca casos `stage_3`/`stage_4` com baixa margem ou confianca insuficiente para revisao especializada;
- existe script de calibracao local em `scripts/calibrate_pressure_injury_stage_classifier.py`;
- a calibracao par-a-par so e aplicada quando `model_metadata.json` trouxer `stage34_calibration.enabled=true`;
- a primeira calibracao testada em 2026-04-09 nao ficou ativa porque nao melhorou o baseline no teste;
- o pipeline de treino passou a suportar focal loss, label smoothing e peso/amostragem extra para `stage_3`/`stage_4`.

## Uso responsavel

- usar apenas como apoio a decisao;
- exigir revisao humana especializada;
- nao apresentar como diagnostico autonomo.
