# PIID LP-Only Guide

## Objetivo

Esta trilha adiciona um fluxo dedicado para **lesao por pressao (LP)** usando o PIID como dataset local de pesquisa.

Ela cobre:
- preparo do dataset local;
- split estratificado e manifesto auditavel;
- treino de um classificador dedicado de estagio LP;
- explicabilidade no diagnostico com tudo o que a IA considerou.

## Estrutura local esperada

```text
dataset/
  piid/
    raw/
      stage_1/
      stage_2/
      stage_3/
      stage_4/
    manifests/
      piid_lp_split.json
```

## Passo 1: criar o layout local

```powershell
python scripts/train_pressure_injury_classifier.py --init-layout --prepare-only
```

## Passo 2: colocar as imagens do PIID

Coloque as imagens baixadas localmente nas pastas `stage_1`, `stage_2`, `stage_3` e `stage_4`.

Observacao:
- o projeto **nao redistribui** o PIID;
- o dataset fica fora do Git por `.gitignore`;
- confirme a licenca/termos do dataset antes de uso alem de pesquisa/prototipo.

## Passo 3: gerar o manifesto auditavel

```powershell
python scripts/train_pressure_injury_classifier.py --prepare-only
```

O manifesto registra:
- raiz do dataset;
- classes canonicas;
- split train/val/test;
- total de imagens por estagio.

## Passo 4: treinar

```powershell
python scripts/train_pressure_injury_classifier.py --epochs 35 --batch-size 16
```

Artefatos gerados:
- `models/pressure_injury_stage_classifier/pressure_injury_stage_resnet50.pth`
- `models/pressure_injury_stage_classifier/model_metadata.json`
- `models/pressure_injury_stage_classifier/training_history.json`

Baseline local treinado em 2026-04-09:
- `1091` imagens PIID;
- split `763/163/165`;
- `8` epocas em CPU;
- validation accuracy `0.7730`;
- test accuracy `0.7030`.

## Como o diagnostico explica a decisao

Quando o caso parece LP, o `ClinicalMLService` roda o especialista LP-only e adiciona em `metadata.pressure_injury_stage_assessment`:
- estagio sugerido;
- probabilidades por estagio;
- margem entre top-2 classes;
- sinais visuais medidos;
- lista textual do que foi considerado;
- acoes recomendadas por estagio.

## Sinais considerados pela IA

Mesmo sem pesos treinados, o fallback heuristico especializado declara os fatores usados:
- proporcao de tons rosados;
- proporcao de vermelho vivo;
- proporcao de tons amarelados;
- proporcao de areas escuras;
- densidade de bordas e textura;
- media e variacao de luminosidade;
- contexto estruturado: area da lesao e dor, quando disponiveis.

## Validacao

Arquivos de teste adicionados:
- `tests/test_pressure_injury_dataset.py`
- `tests/test_pressure_injury_stage_classifier.py`

Esses testes validam:
- aliases de pastas do PIID;
- split estratificado;
- explicabilidade do classificador LP;
- enriquecimento do raw output com o estagio especializado.
