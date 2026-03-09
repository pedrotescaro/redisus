# HEAL+ / REDISUS — Plataforma de Análise de Feridas por Visão Computacional

<p align="center">
  <strong>Sistema de Apoio ao Diagnóstico de Feridas Crônicas com Deep Learning e Processamento de Imagens Médicas</strong><br>
  Cluster REDISUS — RNP/RUTE | Plataforma Nacional de Saúde Digital Integrada
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?logo=python" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/PyTorch-2.0+-ee4c2c?logo=pytorch" alt="PyTorch">
  <img src="https://img.shields.io/badge/OpenCV-4.8+-5C3EE8?logo=opencv" alt="OpenCV">
  <img src="https://img.shields.io/badge/PyQt6-Desktop_GUI-41CD52?logo=qt" alt="PyQt6">
  <img src="https://img.shields.io/badge/FHIR_R4-Interop_SUS-orange" alt="FHIR R4">
  <img src="https://img.shields.io/badge/TRL-4--5-green" alt="TRL 4-5">
  <img src="https://img.shields.io/badge/license-Research-lightgrey" alt="License">
</p>

---

## Índice

1. [Resumo Científico (Abstract)](#1-resumo-científico-abstract)
2. [Problema Clínico](#2-problema-clínico)
3. [Arquitetura do Sistema](#3-arquitetura-do-sistema)
4. [Pipeline de Processamento](#4-pipeline-de-processamento)
5. [Metodologia de Treinamento](#5-metodologia-de-treinamento)
6. [Rastreabilidade do Dataset](#6-rastreabilidade-do-dataset)
7. [Métricas de Avaliação](#7-métricas-de-avaliação)
8. [Dicionário de Dados e Critérios de Decisão](#8-dicionário-de-dados-e-critérios-de-decisão)
9. [Stack Técnica e Justificativas](#9-stack-técnica-e-justificativas)
10. [Guia de Execução](#10-guia-de-execução)
11. [Estrutura do Projeto](#11-estrutura-do-projeto)
12. [Trabalhos Futuros e Hipóteses de Pesquisa](#12-trabalhos-futuros-e-hipóteses-de-pesquisa)
13. [Referências Bibliográficas](#13-referências-bibliográficas)

---

## 1. Resumo Científico (Abstract)

**Contexto.** Feridas crônicas (úlceras venosas, lesões por pressão, pé diabético) constituem um problema de saúde pública global, com prevalência estimada de 1–2% da população em países desenvolvidos e custos que chegam a 3% dos orçamentos de sistemas de saúde (Sen et al., 2009; Järbrink et al., 2017). No Brasil, o Sistema Único de Saúde (SUS) enfrenta desafios adicionais de escala e heterogeneidade de infraestrutura, onde a avaliação de feridas depende em grande parte da experiência subjetiva do profissional de estomaterapia.

**Objetivo.** Este trabalho apresenta o **HEAL+** (REDISUS), uma plataforma de apoio ao diagnóstico de feridas crônicas que integra Visão Computacional e *Deep Learning* em um pipeline completo de ponta a ponta: desde a captura da imagem até a emissão de laudo clínico automatizado com recomendação de tratamento baseada em evidências.

**Método.** O sistema utiliza uma arquitetura em dois estágios:
- **Estágio 1 — Detecção em tempo real:** YOLOv8 Nano para localização da ferida no *frame* da câmera (latência < 30 ms em GPU).
- **Estágio 2 — Diagnóstico profundo (paralelo):**
  - **Segmentação de tecidos:** U-Net com encoder EfficientNet-B0 (entrada 512×512, 5 classes: *background*, granulação, esfacelo, necrose, perilesional).
  - **Classificação etiológica em dois estágios:** ResNet50 com *transfer learning* (ImageNet) — Estágio 1: Normal vs. Ferida (binário); Estágio 2: Diabética / Pressão / Venosa (3 classes). Explicabilidade via Grad-CAM na `layer4`.
  - **Ensemble multi-modelo:** EfficientNet-B3 (0.35) + DermaIntel ViT (0.40) + BiomedCLIP (0.25) com *soft voting*.
  - **Segmentação de contorno:** MedSAM (ViT-Base, 1.6M pares imagem-máscara médicas) para delimitação precisa da ferida.

**Resultados-alvo.** mAP@0.5 > 0.85 (detecção), Dice > 0.80 por classe (segmentação), Accuracy > 0.90 e AUC-ROC > 0.92 (classificação).

**Contribuição.** A plataforma integra ainda interoperabilidade com o SUS (HL7 FHIR R4, e-SUS PEC, DATASUS/SIGTAP), escalas clínicas validadas (PUSH Tool 3.0, BWAT, Braden), gêmeo digital do paciente (Twin@Home) e base de conhecimento via RAG com níveis de evidência Oxford CEBM.

**Palavras-chave:** Visão Computacional, *Deep Learning*, Segmentação de Feridas, Classificação Etiológica, U-Net, YOLOv8, ResNet50, Estomaterapia, SUS, FHIR.

---

## 2. Problema Clínico

| Aspecto | Descrição |
|---------|-----------|
| **Prevalência** | 1–2% da população mundial sofre de feridas crônicas; no Brasil, úlceras venosas afetam ~1,5% da população adulta |
| **Custo** | Até 3% do orçamento de sistemas de saúde; curativos e internações prolongadas no SUS |
| **Subjetividade** | Avaliação visual da ferida (cor, textura, bordas) depende do treinamento subjetivo do profissional |
| **Desigualdade de acesso** | Municípios remotos não possuem especialistas em estomaterapia |
| **Necessidade** | Sistema objetivo, reprodutível e automatizado que auxilie na classificação tecidual e etiológica da ferida, padronizando o cuidado |

### Taxonomia Clínica do Leito da Ferida

| # | Tecido | Aparência Clínica | Significado |
|---|--------|-------------------|-------------|
| 1 | **Necrose de Coagulação (Escara)** | Preto/marrom, endurecido, seco ou úmido | Tecido desvitalizado — requer desbridamento |
| 2 | **Esfacelo (Fibrina)** | Amarelo/branco, viscoso ou fibroso | Tecido desvitalizado macio — dificulta cicatrização |
| 3 | **Tecido de Granulação** | Vermelho brilhante, úmido, granulado | Tecido saudável — indica cicatrização em progresso |
| 4 | **Epitelização** | Rosa claro/translúcido, avança das bordas | Fase final de cicatrização |

### Classificação Etiológica

| Etiologia | Localização Típica | Código ICD-10 | Código SNOMED CT |
|-----------|---------------------|---------------|-----------------|
| Úlcera Venosa | Maléolo medial, terço inferior da perna | I83.0 | 404684003 |
| Úlcera Arterial | Dedos, calcâneo, proeminências | — | 238792006 |
| Pé Diabético | Superfície plantar, dedos | E11.621 | 280137006 |
| Lesão por Pressão | Proeminências ósseas (sacro, trocânter) | L89 | 399912005 |
| Ferida Cirúrgica | Sítio da incisão | T81.4 | 225552003 |

---

## 3. Arquitetura do Sistema

O HEAL+/REDISUS é organizado em **5 Eixos Estruturantes**:

| Eixo | Nome | Módulos Principais |
|------|------|--------------------|
| 1 | **Diagnóstico e Monitoramento** | YOLO, U-Net, ResNet50, EfficientNet, Grad-CAM, MedSAM, BiomedCLIP |
| 2 | **Gestão Personalizada do Cuidado** | Planos de cuidado, mHealth Takere, Digital Twin (Twin@Home) |
| 3 | **Interoperabilidade SUS** | HL7 FHIR R4, e-SUS PEC, DATASUS/SIGTAP, RNDS |
| 4 | **Experiência do Paciente** | Educação em saúde, aderência, teleconsulta |
| 5 | **Validação e Escalabilidade** | TRL 4-5, pilotos multicêntricos, ANVISA, LGPD, RAG clínico |

### Diagrama da Plataforma

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           HEAL/REDISUS Platform v3.0                          │
│                                                                               │
│  Eixo 1: Diagnóstico       Eixo 2: Gestão          Eixo 3: Interop. SUS     │
│  ┌───────────────────┐    ┌────────────────┐       ┌────────────────────┐    │
│  │ YOLO → U-Net →    │    │ Care Plans     │       │ FHIR R4 / e-SUS   │    │
│  │ ResNet50 + Ensemble│    │ mHealth Takere │       │ DATASUS / SIGTAP   │    │
│  │ MedSAM + Grad-CAM │    │ Digital Twin   │       │ RNDS / Vigilância  │    │
│  └───────────────────┘    └────────────────┘       └────────────────────┘    │
│                                                                               │
│  Eixo 4: Experiência       Eixo 5: Validação                                │
│  ┌───────────────────┐    ┌────────────────┐                                 │
│  │ Educação Saúde    │    │ TRL 4-5        │                                 │
│  │ Aderência         │    │ RAG / CDS      │                                 │
│  │ Teleconsulta      │    │ ANVISA / LGPD  │                                 │
│  └───────────────────┘    └────────────────┘                                 │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Arquitetura de Camadas

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        CAMADA DE APRESENTAÇÃO                                 │
│   Desktop (PyQt6)  │  API (FastAPI/Flask)  │  Mobile (futuro)               │
└──────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                     CAMADA DE PROCESSAMENTO (IA)                              │
│                                                                               │
│  ┌──────────────────────┐      ┌───────────────────────────────────────────┐ │
│  │  MÓDULO TEMPO REAL   │      │   MÓDULO DIAGNÓSTICO PROFUNDO             │ │
│  │  (Edge Processing)   │      │                                           │ │
│  │                      │      │  U-Net (Segmentação 5 classes)            │ │
│  │  YOLOv8 Nano        │      │  ResNet50 Two-Stage (Normal→Etiologia)    │ │
│  │  30-60 FPS          │      │  Ensemble: EfficientNet+ViT+BiomedCLIP   │ │
│  │  Bounding Box       │      │  MedSAM (Contorno preciso)               │ │
│  │  Conf. > τ → Captura│      │  Grad-CAM (Explicabilidade)              │ │
│  └──────────┬───────────┘      └────────────────────┬──────────────────────┘ │
│             │                                       │                        │
│             └──────────┬────────────────────────────┘                        │
│                        ▼                                                     │
│             ┌────────────────────────┐                                       │
│             │  Filtro Falsos Positivos│  ← biological ≥ 0.20                 │
│             │  (Pele/Dedo/Dispositivo)│  ← finger ≤ 0.65                    │
│             └────────────┬───────────┘  ← device ≤ 0.55                     │
│                          ▼                                                   │
│             ┌────────────────────────┐                                       │
│             │  FUSÃO + LAUDO CLÍNICO │                                       │
│             └────────────────────────┘                                       │
└──────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                          CAMADA DE DADOS                                      │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐  ┌───────────┐  │
│  │ SQLite (dados  │  │ Modelos ONNX/  │  │ Protocolos de  │  │ RAG       │  │
│  │ do paciente)   │  │ PT / TFLite    │  │ Tratamento     │  │ Clínico   │  │
│  └────────────────┘  └────────────────┘  └────────────────┘  └───────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Pipeline de Processamento

### 4.1 Fluxo Completo (Upload de Imagem → Diagnóstico)

```
Imagem ─→ Validação de Qualidade
              │
              ▼
      Pré-processamento
      (Bilateral Filter + CLAHE em LAB)
              │
              ▼
   ┌──────────┴───────────┐
   │                      │
   ▼                      ▼
YOLO Nano              Processamento Paralelo
(Detecção 320×320)     ┌─────────────────────────────────────┐
   │                   │                                     │
   ▼                   ▼                                     ▼
BBox + Conf.      U-Net (512×512)               ResNet50 Two-Stage (224×224)
   │              Segmentação 5 classes:         Estágio 1: Normal vs Ferida
   │              0-Background                   Estágio 2: Diabética/Pressão/Venosa
   │              1-Granulação                          +
   │              2-Esfacelo                     Ensemble (EfficientNet+ViT+CLIP)
   │              3-Necrose                             +
   │              4-Perilesional                 Grad-CAM (explicabilidade)
   │                   │                                     │
   └───────────────────┴─────────────────────────────────────┘
                                    │
                                    ▼
                      Filtro de Falsos Positivos
                      (Biológico, Dedo, Dispositivo, Pele)
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │   ANÁLISE MULTI-ESPAÇO DE COR │
                    │   HSV (60%) + LAB (40%)        │
                    │   + Zona Periferia vs Core     │
                    │   + Gradiente Scharr (bordas)  │
                    │   + Distance Transform         │
                    └───────────────────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │       LAUDO CLÍNICO            │
                    │  • Composição tecidual (%)     │
                    │  • Classificação etiológica    │
                    │  • Health Score (0-100)        │
                    │  • Escalas: PUSH, BWAT, Braden │
                    │  • Recomendação de tratamento  │
                    │  • Exportação FHIR R4          │
                    └───────────────────────────────┘
```

### 4.2 Detalhes do Pré-processamento

| Etapa | Técnica | Parâmetros | Objetivo |
|-------|---------|------------|----------|
| Redução de ruído | Bilateral Filter | `d=9, sigmaColor=75, sigmaSpace=75` | Suaviza preservando bordas |
| Normalização de iluminação | CLAHE no canal L (LAB) | `clipLimit=2.0, tileGridSize=8×8` | Corrige iluminação não uniforme |
| Espaço de cor | HSV (60%) + LAB (40%) | Fusão multi-espaço | Robustez a variações de captura |
| ROI por contorno | Máscara convexa | Perímetro anatômico | Segmentação restrita à ferida |
| Zonas espaciais | Periferia vs Core | Distance Transform | Epitelização na borda, necrose no centro |

### 4.3 Segmentação Multi-Espaço de Cor (v3)

A segmentação utiliza intervalos HSV e LAB calibrados clinicamente:

| Tecido | Canal H (Matiz) | Canal S (Saturação) | Canal V (Valor) | Justificativa Clínica |
|--------|-----------------|---------------------|-----------------|----------------------|
| **Granulação** | 0–10, 160–180 | 60–255 | 80–255 | Vermelho vivo, bem vascularizado |
| **Esfacelo** | 15–38 | 50–255 | 140–255 | Amarelo/branco, tecido desvitalizado |
| **Necrose** | 0–80, 140–180 | 0–255 | 0–40 | Escuro (V < 50), avascular |
| **Epitelização** | 0–15, 155–175 | 15–70 | 170–255 | Rosa claro, periferia da ferida |
| **Fibrina** | 18–40 | — | — | Amarelo claro, viscoso |

> **Nota:** Matizes entre H=80–140 (azul/verde) são excluídos da necrose para evitar confusão com campos cirúrgicos.

### 4.4 Test-Time Augmentation (TTA)

Todas as classificações utilizam TTA com 4 flips (original, horizontal, vertical, ambos), com média das probabilidades *softmax* para aumentar a robustez.

---

## 5. Metodologia de Treinamento

### 5.1 Estratégia de Transfer Learning

| Modelo | Base Pré-treinada | Estratégia de Fine-tuning |
|--------|-------------------|---------------------------|
| **YOLOv8 Nano** | COCO (pesos oficiais) | Fine-tuning completo, 100–150 epochs |
| **U-Net** | EfficientNet-B0 (ImageNet) | Encoder congelado 5–10 epochs → descongelamento com LR 10× menor |
| **ResNet50** | ImageNet | `layer4` + `fc` descongelados |
| **EfficientNet-B3** | ImageNet | Phases: Feature Extraction (50 ep.) → Fine-tuning (30 ep.) |
| **DermaIntel ViT** | `PayamFard123/dermaintel-wound-classifier` | Pré-treinado, sem re-treino |
| **BiomedCLIP** | `microsoft/BiomedCLIP-PubMedBERT` (PMC-15M) | Zero-shot, sem re-treino |
| **MedSAM** | `bowang-lab/MedSAM` (1.6M pares) | Pré-treinado, sem re-treino |

### 5.2 ResNet50 Two-Stage (Classificação Etiológica)

```
                   ┌──────────────────┐
                   │    Imagem 224×224 │
                   └────────┬─────────┘
                            │
                            ▼
                   ┌──────────────────┐
                   │   ResNet50 Base   │  ← ImageNet pré-treinado
                   │   (congelado)     │
                   └────────┬─────────┘
                            │
              ┌─────────────┴──────────────┐
              ▼                            ▼
    ┌──────────────────┐         ┌──────────────────┐
    │  Estágio 1       │         │  Estágio 2       │
    │  Normal vs Ferida│         │  Tipo de Ferida   │
    │  (2 classes)     │         │  (3 classes)      │
    │  Binário         │         │  Diabética        │
    │                  │         │  Pressão          │
    │                  │         │  Venosa           │
    └──────────────────┘         └──────────────────┘
              │                            │
              └──────────┬─────────────────┘
                         ▼
                  Grad-CAM (layer4)
                  Mapa de ativação
```

**Estágio 1** — Triagem binária para filtrar imagens sem ferida (normal/pele saudável).  
**Estágio 2** — Classificação fina das 3 etiologias mais prevalentes.

### 5.3 *Data Augmentation* Médica

A augmentação de dados para imagens médicas de feridas segue restrições clínicas rigorosas, pois **a cor é diagnóstica** (vermelho = granulação saudável, amarelo = esfacelo, preto = necrose):

#### Técnicas Seguras (usar livremente)

| Técnica | Configuração | Justificativa |
|---------|-------------|---------------|
| Flip horizontal/vertical | `p=0.5` | Orientação não é diagnóstica |
| Rotação | `±15°` | Simula ângulo de captura variado |
| Zoom | `±10%` | Simula distância da câmera |
| Translação | `±5%` | Centralização variável |
| Ruído Gaussiano | `σ ≤ 20` | Simula ruído de câmera de celular |
| Blur leve | `kernel ≤ 5` | Simula foco impreciso |
| CLAHE | `clipLimit=2.0` | Melhora contraste sem alterar matiz |

#### Técnicas Proibidas

| Técnica | Motivo |
|---------|--------|
| **Hue shift > ±5** | Altera a cor diagnóstica (vermelho ↔ amarelo = diagnósticos diferentes) |
| Saturação forte | Muda percepção granulação vs esfacelo |
| ColorJitter forte | Mistura canais de cor → informação clínica perdida |
| Random Erasing / Cutout | Remove pixels da lesão → perde informação clínica |
| Mixup forte (> 0.2) | Funde texturas de tecidos distintos |

#### Augmentação Offline

```bash
# Gera 3× mais imagens augmentadas para U-Net (nível moderado recomendado)
python scripts/medical_augmentation.py \
    --input dataset/tissue_segmentation/train \
    --output dataset/tissue_segmentation_aug/train \
    --factor 3 --level moderate --imgsz 256
```

### 5.4 Hiperparâmetros Anti-Overfitting

| Parâmetro | Dataset Pequeno (< 200 img) | Dataset Médio (200–1000 img) |
|-----------|----------------------------|------------------------------|
| Epochs | 120–150 + Early Stopping | 80–100 |
| Batch Size | 4–8 | 8–16 |
| Learning Rate | 5×10⁻⁵ | 1×10⁻⁴ |
| Early Stopping Patience | 20–25 | 15 |
| Weight Decay (L2) | 1×10⁻³ | 1×10⁻⁴ |
| Dropout | 0.3–0.5 | 0.1–0.2 |
| Input Size (U-Net) | 256×256 | 512×512 |

### 5.5 Reprodutibilidade: Estrutura do Dataset

```
dataset/
├── yolo_wounds/                        ← YOLO (detecção de ferida)
│   ├── data.yaml                       ← metadados Ultralytics
│   ├── train/
│   │   ├── images/                     ← .jpg 640×640
│   │   └── labels/                     ← .txt (class x_c y_c w h normalizado)
│   └── val/
│       ├── images/
│       └── labels/
│
├── tissue_segmentation/                ← U-Net (segmentação de tecidos)
│   ├── train/
│   │   ├── images/                     ← .jpg 256×256 ou 512×512
│   │   └── masks/                      ← .png single-channel (px = 0–4)
│   └── val/
│       ├── images/
│       └── masks/
│
└── medetec/                            ← Dataset bruto (16 categorias)
    ├── abdominal_wounds/
    ├── burns/
    ├── diabetic_foot_ulcers/
    ├── pressure_ulcers_1/
    ├── pressure_ulcers_2/
    ├── venous_arterial_ulcers_1/
    ├── venous_arterial_ulcers_2/
    └── ... (16 categorias)
```

**Classes da máscara U-Net:**

| Valor do Pixel | Classe | Cor Clínica |
|----------------|--------|-------------|
| 0 | Background | — |
| 1 | Granulação | Vermelho vivo |
| 2 | Esfacelo | Amarelo/branco |
| 3 | Necrose | Preto/marrom |
| 4 | Perilesional | Tom de pele normal |

---

## 6. Rastreabilidade do Dataset

### 6.1 Fontes de Dados Utilizadas

| Dataset | Imagens | Tipo | Fonte / URL | Uso no Projeto |
|---------|---------|------|-------------|----------------|
| **Medetec Wound Image Database** | ~594 | Classificação (16 categorias) | [medetec.co.uk](https://www.medetec.co.uk/files/medetec-image-databases.html) | Treinamento ResNet50 Two-Stage + EfficientNet; geração de labels YOLO |
| **FUSeg (Foot Ulcer Segmentation)** | 1.210 (treino) + 200 (teste) | Segmentação (máscaras binárias) | [github.com/uwm-bigdata/wound-segmentation](https://github.com/uwm-bigdata/wound-segmentation) | Treinamento/validação U-Net; MICCAI Challenge |
| **AZH Chronic Wound Dataset** | Variável | Segmentação (anotações profissionais) | Mesmo repositório acima | Validação da segmentação |
| **Wseg (WSNet)** | 2.686 | Segmentação | [huggingface.co/datasets/subbareddy248/Wseg_dataset](https://huggingface.co/datasets/subbareddy248/Wseg_dataset) | Treinamento complementar U-Net; licença MIT |
| **DFUC (Diabetic Foot Ulcer Challenge)** | Variável | Detecção + Classificação | [dfu-challenge.github.io](https://dfu-challenge.github.io/) | Validação de pé diabético |

### 6.2 Como o Dataset Medetec é Obtido

O script `scripts/medetec_scraper.py` realiza *web scraping* respeitoso do site Medetec:
- Delay entre requisições: 1.5 s
- Retry com *backoff* exponencial (até 3 tentativas)
- Organiza em 16 subpastas por categoria clínica

```bash
python scripts/medetec_scraper.py
```

### 6.3 Geração Automática de Labels YOLO

O script `scripts/prepare_yolo_dataset.py` gera bounding boxes automáticas a partir das imagens Medetec usando segmentação por cor (HSV) + morfologia:
- Detecção por múltiplas faixas HSV (vermelho, amarelo, escuro, rosa)
- Operações morfológicas (CLOSE 7×7×2, OPEN 7×7×1)
- Maior contorno + margem de 5%
- Formato normalizado YOLO: `class x_center y_center width height`
- Filtro de área mínima: 1% da imagem

### 6.4 Geração de Amostras Normais (ResNet50 Estágio 1)

Para o estágio binário (Normal vs Ferida), ~200 amostras "normais" são sintetizadas:
- Recortes de bordas de imagens de feridas (regiões sem lesão)
- Imagens sintéticas de pele saudável

---

## 7. Métricas de Avaliação

### 7.1 Detecção em Tempo Real (YOLO)

| Métrica | Alvo | Descrição |
|---------|------|-----------|
| **mAP@0.5** | > 0.85 | Mean Average Precision no threshold IoU = 0.5 |
| **Latência P95** | < 30 ms (GPU) / < 100 ms (CPU) | Percentil 95 do tempo de inferência |
| **FPS mínimo** | ≥ 30 | Frames por segundo para uso em tempo real |

### 7.2 Segmentação de Tecidos (U-Net)

| Métrica | Alvo | Descrição |
|---------|------|-----------|
| **Dice Score** | > 0.80 por classe | Coeficiente Dice (F1 pixel-wise) |
| **IoU médio** (Jaccard) | > 0.75 | *Intersection over Union* — métrica padrão para segmentação semântica |
| **Boundary F1** | > 0.70 | F1-score nas bordas da segmentação |

$\text{IoU} = \frac{|A \cap B|}{|A \cup B|}$

$\text{Dice} = \frac{2|A \cap B|}{|A| + |B|}$

### 7.3 Classificação Etiológica (ResNet50 + Ensemble)

| Métrica | Alvo | Descrição |
|---------|------|-----------|
| **Accuracy** | > 0.90 | Acurácia geral |
| **Macro F1** | > 0.85 | F1-score médio entre classes (peso igual) |
| **AUC-ROC** | > 0.92 | Área sob a curva ROC |
| **Precisão** | Reportada por classe | Proporção de verdadeiros positivos entre preditos positivos |
| **Recall (Sensibilidade)** | Reportada por classe | Proporção de verdadeiros positivos identificados |

### 7.4 Escalas Clínicas Implementadas

| Escala | Range | Componentes | Referência |
|--------|-------|-------------|------------|
| **PUSH Tool 3.0** | 0–17 (0 = cicatrizada) | Área (0–10), Exsudato (0–3), Tecido (0–4) | NPUAP |
| **BWAT** | 13–65 | 13 itens (tamanho, profundidade, bordas, necrose, exsudato, perilesão, granulação, epitelização) | Bates-Jensen |
| **Escala de Braden** | 6–23 | 6 subescalas (percepção sensorial, umidade, atividade, mobilidade, nutrição, fricção) | Bergstrom et al., 1987 |

**Interpretação Braden:**

| Score | Risco |
|-------|-------|
| ≤ 9 | Muito alto |
| 10–12 | Alto |
| 13–14 | Moderado |
| 15–18 | Baixo |
| > 18 | Sem risco |

---

## 8. Dicionário de Dados e Critérios de Decisão

### 8.1 Filtro de Falsos Positivos (`false_positive_filter.py`)

O sistema implementa 5 estratégias de validação contextual para eliminar detecções incorretas:

| Critério | Limiar | Ação | Descrição |
|----------|--------|------|-----------|
| **Biological Score** | ≥ 0.20 | Aceita se biológico | Textura, irregularidade, variância — diferencia tecido vivo de objeto |
| **Contexto Perilesional** | ≥ 0.10 | Requer pele ao redor | Verifica presença de pele saudável circundante |
| **Finger Detection** | ≤ 0.65 | Rejeita se dedo | Formato alongado + proporção + cor de pele → provável dedo/mão |
| **Device Detection** | ≤ 0.55 | Rejeita se dispositivo | Bordas retas + textura uniforme → provável curativo/instrumento |
| **Healthy Skin** | ≤ 0.70 | Rejeita se pele saudável | Detecção YCrCb + HSV multi-espaço (Fitzpatrick I–VI) |
| **Texture Uniformity** | variância > 0.2 | Rejeita se uniforme | Regiões muito lisas = provavelmente pele saudável |

**Motivos de rejeição codificados:**
`FINGER_SHAPE`, `DEVICE_EDGE`, `HEALTHY_SKIN`, `NO_PERILESIONAL`, `ARTIFICIAL_TEXTURE`, `TOO_UNIFORM`, `GEOMETRIC_SHAPE`, `LOW_BIOLOGICAL_SCORE`

### 8.2 Detecção de Pele Saudável (`SkinDetector`)

Utiliza dois espaços de cor combinados (AND) para maior precisão:

| Espaço | Canal min | Canal max | Justificativa |
|--------|-----------|-----------|---------------|
| **YCrCb** | [0, 133, 77] | [255, 173, 127] | Invariante a iluminação |
| **HSV** | [0, 15, 60] | [25, 170, 255] | Captura tons de pele |

### 8.3 Critérios de Decisão Clínica

| Decisão | Critério | Implementação |
|---------|----------|---------------|
| "Necessita revisão manual" | Confiança < 0.6 **ou** top-2 probabilidades diferem < 0.15 | `needs_review = True` |
| Prioridade de sobreposição (tecidos) | Granulação > Necrose > Esfacelo > Fibrina > Epitelização | Resolução por máscara prioritária |
| Necrose de alta confiança | Pixel V < 50 dentro do perímetro segmentado | Prioridade absoluta por luminância |
| Epitelização | Apenas na **periferia** da ferida (Distance Transform) | Gradiente Scharr + zona periférica |
| Esfacelo | Restrito ao **core** da ferida | Zona central da máscara |
| Background vs Necrose | Variância + crominância + conectividade espacial | Contexto espacial distingue fundo escuro de tecido necrótico |

### 8.4 Campos Cirúrgicos (Exclusão)

Matizes H ∈ [80, 140] (azul/verde) são explicitamente excluídos da detecção de necrose para evitar confusão com campos cirúrgicos azuis/verdes.

### 8.5 Base de Conhecimento (RAG Clínico)

O módulo RAG (`src/rag/clinical_rag.py`) contém protocolos com níveis de evidência Oxford CEBM:

| Protocolo | Nível de Evidência | Fonte |
|-----------|-------------------|-------|
| Abordagem TIME (Tissue, Infection, Moisture, Edge) | Consenso de Especialistas | Schultz GS et al., 2003 |
| Tratamento de Úlcera Venosa (compressão multicomponente) | **1A** (revisão sistemática de RCTs) | O'Meara et al., 2012 (Cochrane) |
| Escala de Braden | **1B** (RCT individual) | Bergstrom et al., 1987 |
| Classificação de Wagner (Pé Diabético) | Consenso | Wagner, 1981 |

**Matriz de Curativos (implementada no RAG):**

| Condição do Leito | Curativo Recomendado | Evidência |
|--------------------|---------------------|-----------|
| Necrose seca | Hidrogel (autólise) / Alginato (enzimático) | Guideline SUS |
| Esfacelo | Alginato de cálcio / Hidrofibra | Guideline SUS |
| Granulação saudável | Espuma / Hidrocoloide | Guideline SUS |
| Exsudato abundante | Alginato / Espuma absorvente | Guideline SUS |
| Infecção | Prata iônica (Ag⁺) / PHMB / Mel medicinal | Guideline SUS |

---

## 9. Stack Técnica e Justificativas

### 9.1 Frameworks de Deep Learning

| Tecnologia | Versão | Uso no Projeto | Justificativa |
|------------|--------|----------------|---------------|
| **PyTorch ≥ 2.0** | Principal | Treinamento e inferência de ResNet50, U-Net, ensemble | Ecossistema dominante em pesquisa acadêmica; autograd dinâmico para prototipação rápida; suporte nativo a Grad-CAM |
| **TensorFlow ≥ 2.13** | Secundário | Conversão para TFLite (mobile); treinamento EfficientNet (Keras) | Necessário para deploy em dispositivos edge via TFLite; `tf2onnx` para conversão |
| **ONNX Runtime** | Inferência otimizada | Inferência em produção (CPU/GPU) | Formato agnóstico; otimização automática; suporte a quantização INT8 |
| **Ultralytics ≥ 8.0** | Detecção | YOLOv8 treinamento e inferência | API de alto nível para YOLO; augmentação integrada (Mosaic, MixUp) |
| **segmentation-models-pytorch** | Segmentação | U-Net com encoder EfficientNet | Implementações pré-validadas de U-Net, FPN, DeepLab com encoders intercambiáveis |

### 9.2 Processamento de Imagem

| Tecnologia | Uso | Justificativa |
|------------|-----|---------------|
| **OpenCV ≥ 4.8** | Pré-processamento, segmentação por cor, filtros morfológicos, fallback de detecção | Padrão da indústria; CLAHE, bilateral filter, conversão de espaço de cor; fallback robusto quando modelos DL não estão disponíveis |
| **Pillow ≥ 10.0** | Renderização de texto UTF-8 sobre imagens OpenCV | `cv2.putText` não suporta caracteres acentuados (português) |
| **scikit-image ≥ 0.21** | Análise de textura, LBP, métricas de forma | Complementa OpenCV com algoritmos de análise de features |
| **Albumentations ≥ 1.3** | Pipeline de augmentação para treinamento U-Net | Augmentações compostas com suporte a máscaras (imagem + máscara transformadas sincronizadamente) |

### 9.3 Interface e API

| Tecnologia | Uso | Justificativa |
|------------|-----|---------------|
| **PyQt6** | Interface desktop principal (`heal_analyzer.py`) | Framework multiplataforma maduro com suporte a threading (QThread) para inferência assíncrona sem travar a UI |
| **Flask ≥ 3.0** | Dashboard web clínico | Leve e suficiente para dashboard de monitoramento |
| **FastAPI** (futuro) | API REST para integração | Alto desempenho assíncrono, documentação automática OpenAPI |

### 9.4 Interoperabilidade

| Tecnologia | Uso | Justificativa |
|------------|-----|---------------|
| **fhir.resources** | Modelos HL7 FHIR R4 (Patient, Observation, DiagnosticReport) | Padrão obrigatório para integração com RNDS e sistemas SUS |
| **SQLite** | Armazenamento local de dados do paciente | Zero-configuração; adequado para aplicação desktop single-user |
| **Loguru** | Sistema de logging estruturado | Rotação de logs, formatação colorida, integração simples |

---

## 10. Guia de Execução

### 10.1 Pré-requisitos

- **Python:** 3.10 ou superior
- **GPU (recomendada):** NVIDIA com CUDA 11.8+ (para treinamento e inferência rápida)
- **RAM:** ≥ 8 GB (16 GB recomendado para treinamento)
- **Espaço em disco:** ≥ 5 GB (incluindo datasets e modelos)

### 10.2 Configuração do Ambiente

```bash
# 1. Clonar o repositório
git clone https://github.com/SEU_USUARIO/redisus.git
cd redisus

# 2. Criar ambiente virtual
python -m venv .venv

# 3. Ativar ambiente virtual
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Linux/macOS:
source .venv/bin/activate

# 4. Instalar dependências
pip install -r requirements.txt
```

### 10.3 Obtenção do Dataset

```bash
# Baixar dataset Medetec (~594 imagens, 16 categorias)
python scripts/medetec_scraper.py

# Criar estrutura de diretórios para treinamento
python scripts/setup_dataset_structure.py

# Preparar dataset YOLO (gera bounding boxes automáticos)
python scripts/prepare_yolo_dataset.py \
    --source dataset/medetec \
    --output dataset/yolo_wounds \
    --split 0.8

# Pré-processar imagens
python scripts/preprocess_dataset.py --task yolo --imgsz 640
python scripts/preprocess_dataset.py --task unet --imgsz 256

# (Opcional) Augmentação para datasets pequenos
python scripts/medical_augmentation.py \
    --input dataset/tissue_segmentation/train \
    --output dataset/tissue_segmentation_aug/train \
    --factor 3 --level moderate --imgsz 256
```

### 10.4 Treinamento dos Modelos

```bash
# ── YOLO: Detecção de ferida ──
python scripts/train_yolo_wound.py \
    --model yolov8n.pt \
    --data dataset/yolo_wounds/data.yaml \
    --imgsz 640 --epochs 150 --batch 8 --device 0

# ── U-Net: Segmentação de tecidos ──
python scripts/train_unet_tissue.py \
    --encoder efficientnet-b0 \
    --imgsz 256 --epochs 120 --batch 4 --lr 5e-5 --device cuda

# ── ResNet50: Classificação etiológica (Two-Stage) ──
python scripts/train_resnet50_two_stage.py

# ── EfficientNet: Classificação (Keras) ──
python scripts/run_training.py
```

### 10.5 Exportar Modelos para ONNX

```bash
python scripts/train_yolo_wound.py \
    --export-only \
    --weights runs/detect/wound/wound_yolov8/weights/best.pt \
    --benchmark

python scripts/train_unet_tissue.py \
    --export-only \
    --weights runs/segment/tissue/best_model.pt \
    --benchmark
```

### 10.6 Execução da Aplicação

```bash
# ── Interface Desktop (PyQt6) — análise interativa ──
python heal_analyzer.py

# ── Pipeline principal — múltiplos modos ──
python main.py --mode webcam     # Detecção em tempo real (câmera)
python main.py --mode image --input caminho/da/foto.jpg   # Análise de imagem
python main.py --mode demo       # Demonstração com imagem sintética

# ── Plataforma completa (5 eixos) ──
python heal_platform.py --mode realtime    # Detecção em tempo real
python heal_platform.py --mode dashboard   # Dashboard web clínico
python heal_platform.py --mode status      # Status de todos os módulos

# ── Aplicação em tempo real integrada ──
python realtime_app.py
```

### 10.7 Testes

```bash
# Executar suite de testes
pytest

# Testes com cobertura
pytest --cov=src --cov-report=html
```

---

## 11. Estrutura do Projeto

```
redisus/
├── heal_analyzer.py                # Aplicação Desktop PyQt6 (análise interativa)
├── heal_platform.py                # Launcher unificado da plataforma (5 eixos)
├── main.py                         # Pipeline principal integrado (webcam/image/demo)
├── realtime_app.py                 # App de detecção em tempo real
├── retrain.py                      # Launcher de re-treinamento
├── requirements.txt
│
├── src/                            # ── Código-fonte principal ──
│   ├── core/
│   │   └── config.py               # Configurações globais, enums, constantes
│   │
│   ├── ai_layer/                   # Camada de IA avançada
│   │   ├── ensemble_orchestrator.py # Orquestrador multi-modelo (soft voting)
│   │   ├── medsam_segmenter.py     # MedSAM (bowang-lab, Nature Comms. 2024)
│   │   ├── biomedclip_analyzer.py  # BiomedCLIP (Microsoft, PMC-15M, zero-shot)
│   │   ├── dermaintel_classifier.py # DermaIntel ViT (7 classes → 5 REDISUS)
│   │   └── confidence_calibration.py
│   │
│   ├── capture/
│   │   └── video_stream.py         # Captura assíncrona (DirectShow/MSMF)
│   │
│   ├── detection/
│   │   ├── realtime_detector.py    # YOLO (ONNX / PT / TFLite)
│   │   ├── body_part_detector.py   # Detecção de parte do corpo
│   │   └── mediapipe_body_detector.py
│   │
│   ├── processing/                 # Pipeline de processamento de imagem
│   │   ├── wound_detector_cv.py    # Detecção OpenCV (HSV + textura + bordas)
│   │   ├── tissue_analyzer.py      # Análise tecidual (HSV multi-range)
│   │   ├── wound_classifier_cv.py  # Classificação etiológica (features + ML)
│   │   ├── false_positive_filter.py # Filtro de FP (biológico/dedo/dispositivo)
│   │   ├── image_processor.py      # Normalização, denoising, CLAHE
│   │   └── image_enhancer.py       # Correção de iluminação avançada
│   │
│   ├── diagnosis/
│   │   └── wound_analyzer.py       # Analisador integrado (segm. + classif.)
│   │
│   ├── clinical/
│   │   └── scales.py               # PUSH Tool 3.0, BWAT, Escala de Braden
│   │
│   ├── risk/
│   │   └── stratification.py       # Estratificação de risco (LOW → CRITICAL)
│   │
│   ├── treatment/
│   │   ├── recommender.py          # Motor de recomendação de tratamento
│   │   └── evolution_tracker.py    # Tracking temporal de evolução
│   │
│   ├── rag/
│   │   └── clinical_rag.py         # Base de conhecimento clínico (Oxford CEBM)
│   │
│   ├── digital_twin/
│   │   └── twin_model.py           # Twin@Home (gêmeo digital do paciente)
│   │
│   ├── interoperability/           # Integração SUS
│   │   ├── fhir_client.py          # HL7 FHIR R4 (SNOMED CT, LOINC, ICD-10)
│   │   ├── datasus_integration.py  # SIGTAP, BPA, SISAB, CNES
│   │   └── esus_integration.py     # e-SUS PEC
│   │
│   ├── presentation/               # Camada de apresentação
│   │   ├── ui_renderer.py          # HUD médico
│   │   ├── visualization.py        # Mapas de cores e gráficos
│   │   └── window_manager.py       # Gerenciador de janelas
│   │
│   ├── training/                   # Scripts de treinamento modular
│   │   ├── wound_classifier_training.py # EfficientNet (Keras, 2 fases)
│   │   ├── prepare_wound_datasets.py    # Download/padronização (5 datasets)
│   │   ├── train_body_part_detector.py
│   │   ├── medsam_finetuning.py
│   │   └── ensemble_finetuning.py
│   │
│   ├── data/
│   │   ├── database.py             # SQLite (histórico do paciente)
│   │   ├── cache.py                # Cache de frames e resultados
│   │   └── export.py               # Exportação JSON/CSV/PDF
│   │
│   ├── utils/
│   │   ├── text_renderer.py        # Renderização UTF-8 (PIL sobre OpenCV)
│   │   └── image_utils.py
│   │
│   └── validation/
│       └── validation_framework.py # Framework de validação clínica
│
├── scripts/                        # ── Scripts de treinamento e dados ──
│   ├── medetec_scraper.py          # Web scraper do Medetec (16 categorias)
│   ├── prepare_yolo_dataset.py     # Geração automática de labels YOLO
│   ├── preprocess_dataset.py       # Padronização de imagens/máscaras
│   ├── medical_augmentation.py     # Augmentação médica conservativa
│   ├── train_resnet50_two_stage.py # ResNet50 Two-Stage (Normal→Etiologia)
│   ├── train_yolo_wound.py         # Treinamento YOLO wound detector
│   ├── train_unet_tissue.py        # Treinamento U-Net segmentação
│   └── setup_dataset_structure.py  # Criação de diretórios
│
├── models/                         # Pesos dos modelos treinados
│   ├── wound_classifier/
│   ├── wound_classifier_v2/
│   ├── wound_detector/
│   ├── body_part_detector/
│   └── mediapipe/
│
├── dataset/                        # Datasets (ver seção 6)
│   ├── medetec/                    # ~594 imagens, 16 categorias
│   ├── yolo_wounds/                # Formato YOLO (train/val)
│   └── body_parts/
│
├── data/
│   ├── protocols/                  # Protocolos de tratamento (JSON)
│   └── redisus.db                  # Banco SQLite local
│
├── docs/
│   ├── ARCHITECTURE.md             # Documentação técnica da arquitetura
│   └── TRAINING_GUIDE.md           # Guia completo de treinamento
│
├── tests/                          # Suite de testes (pytest)
│   ├── test_wound_detector_cv.py
│   ├── test_wound_classifier_cv.py
│   ├── test_tissue_analyzer.py
│   ├── test_treatment_recommender.py
│   ├── test_clinical_rag.py
│   ├── test_digital_twin.py
│   ├── test_fhir_client.py
│   ├── test_risk_stratification.py
│   └── test_clinical_dashboard.py
│
└── examples/                       # Exemplos de uso
    ├── ensemble_analysis_demo.py
    ├── realtime_detection_demo.py
    └── visual_wound_test.py
```

---

## 12. Trabalhos Futuros e Hipóteses de Pesquisa

As seguintes hipóteses e linhas de investigação são sugeridas para **Iniciação Científica** e continuidade do projeto:

### 12.1 Hipóteses de Pesquisa (IC)

| # | Hipótese | Métrica de Verificação | Prioridade |
|---|----------|------------------------|------------|
| **H1** | A classificação etiológica em dois estágios (ResNet50) atinge acurácia superior à classificação direta (single-stage) em datasets desbalanceados de feridas crônicas | Accuracy, Macro-F1, AUC-ROC comparativo | Alta |
| **H2** | O ensemble multi-modelo (EfficientNet + DermaIntel ViT + BiomedCLIP) reduz a taxa de erro em relação a qualquer modelo individual | Erro de classificação, concordância inter-modelo | Alta |
| **H3** | A augmentação médica conservativa (sem alteração de matiz > ±5) preserva a informação diagnóstica e melhora o Dice Score da segmentação U-Net em comparação com augmentação genérica | Dice Score por classe, confusion matrix de tecidos | Média |
| **H4** | A filtragem de falsos positivos por contexto perilesional (biological score + skin detection) reduz a taxa de falsos positivos em > 30% sem comprometer a sensibilidade | Precisão, Recall, F1 do detector | Média |
| **H5** | A explicabilidade via Grad-CAM sobre `layer4` do ResNet50 produz mapas de ativação que coincidem com as regiões clinicamente relevantes identificadas por especialistas em estomaterapia | IoU entre Grad-CAM e anotações de especialistas, estudo de concordância | Alta |

### 12.2 Trabalhos Futuros

**Curto prazo (6–12 meses):**
- **Validação clínica multicêntrica:** Aplicar o sistema em ambiente hospitalar real com anotações de estomaterapeutas, calculando concordância inter-observador (*Cohen's Kappa*) entre o sistema e o especialista.
- **Benchmark em datasets públicos:** Avaliar formalmente nos datasets FUSeg e DFUC com métricas padronizadas (Dice, IoU, mAP) e comparar com os *baselines* publicados.
- **Calibração de confiança:** Implementar *temperature scaling* ou *Platt scaling* para que as probabilidades do modelo sejam confiáveis do ponto de vista estatístico (reliability diagrams).

**Médio prazo (1–2 anos):**
- **Segmentação temporal:** Incorporar dados longitudinais de um mesmo paciente para treinar modelos de predição de cicatrização (*wound healing trajectory*), validando o gêmeo digital (Twin@Home).
- **Federated Learning:** Treinar modelos de forma federada entre múltiplas instituições SUS sem compartilhar imagens de pacientes (privacidade LGPD).
- **Deploy mobile:** Converter modelos para TFLite com quantização INT8 e validar em dispositivos Android para uso em Atenção Primária.
- **Detecção de infecção:** Treinar classificador binário adicional (infectada vs. limpa) usando features de cor + textura + temperatura (se disponível via câmera térmica).

**Longo prazo (2+ anos):**
- **Integração RNDS:** Publicar resultados diretamente na Rede Nacional de Dados em Saúde via FHIR R4 (já parcialmente implementado).
- **Registro ANVISA:** Preparar dossiê técnico para registro como Software como Dispositivo Médico (SaMD) classe II.
- **Estudo de impacto clínico:** RCT comparando desfechos clínicos (tempo de cicatrização, taxa de amputação) entre grupos com e sem auxílio do sistema.

### 12.3 Sugestões para o Plano de IC

1. **Revisão bibliográfica** focada em: *wound assessment tools* automatizados (Anisuzzaman et al., 2022), benchmarks de segmentação de feridas (FUSeg Challenge, MICCAI), e *transfer learning* para imaging médico com poucos dados.
2. **Experimento controlado** com o dataset Medetec + FUSeg: treinar os modelos, reportar métricas (Dice, IoU, F1, AUC), e comparar com baselines da literatura.
3. **Estudo de concordância** (opcional): apresentar imagens anotadas pelo sistema a 2–3 profissionais de enfermagem/estomaterapia e calcular *Cohen's Kappa* para concordância com a classificação tecidual automática.
4. **Documentar limitações:** vieses do dataset (Medetec predominantemente de peles claras), ausência de anotações de profundidade, e impacto de variações de iluminação/câmera.

---

## 13. Referências Bibliográficas

1. **Sen, C. K., et al.** (2009). Human skin wounds: A major and snowballing threat to public health and the economy. *Wound Repair and Regeneration*, 17(6), 763–771.
2. **Järbrink, K., et al.** (2017). The humanistic and economic burden of chronic wounds: a protocol for a systematic review. *Systematic Reviews*, 6(1), 15.
3. **Ma, J., et al.** (2024). Segment anything in medical images. *Nature Communications*, 15, 654. *(MedSAM)*
4. **Zhang, Y., et al.** (2023). BiomedCLIP: A multimodal biomedical foundation model pretrained from fifteen million scientific image-text pairs. *arXiv:2303.00915*. *(BiomedCLIP)*
5. **Schultz, G. S., et al.** (2003). Wound bed preparation: a systematic approach to wound management. *Wound Repair and Regeneration*, 11(S1), S1–S28. *(Abordagem TIME)*
6. **O'Meara, S., et al.** (2012). Compression for venous leg ulcers. *Cochrane Database of Systematic Reviews*. *(Compressão multicomponente)*
7. **Bergstrom, N., et al.** (1987). The Braden Scale for predicting pressure sore risk. *Nursing Research*, 36(4), 205–210.
8. **Wagner, F. W.** (1981). The dysvascular foot: a system for diagnosis and treatment. *Foot & Ankle*, 2(2), 64–122. *(Escala de Wagner)*
9. **Anisuzzaman, D. M., et al.** (2022). Image-based artificial intelligence in wound assessment: A systematic review. *Advances in Wound Care*, 11(12), 687–709.
10. **Ronneberger, O., et al.** (2015). U-Net: Convolutional Networks for Biomedical Image Segmentation. *MICCAI*, 234–241.
11. **He, K., et al.** (2016). Deep Residual Learning for Image Recognition. *CVPR*, 770–778. *(ResNet)*
12. **Redmon, J., et al.** (2016–2023). YOLOv1→v8: evolução de detectores de objetos em tempo real. *Ultralytics*. *(YOLOv8)*
13. **Tan, M. & Le, Q.** (2019). EfficientNet: Rethinking Model Scaling for Convolutional Neural Networks. *ICML*. *(EfficientNet)*
14. **Wang, C., et al.** (2023). Wound Segmentation Network (WSNet). *WACV 2023*. *(Wseg dataset — 2686 imagens)*
15. **Cassidy, B., et al.** (2021). The DFUC 2020 dataset: Analysis towards diabetic foot ulcer detection. *BioMedical Engineering OnLine*. *(DFUC Challenge)*

---

## Aviso Legal

> Este software é uma ferramenta de **auxílio ao diagnóstico** e **não substitui a avaliação clínica profissional**. Todas as decisões terapêuticas devem ser validadas por profissionais de saúde qualificados.  
> Consulte o Comitê de Ética em Pesquisa (CEP) de sua instituição antes de qualquer uso clínico.  
> O projeto encontra-se em nível TRL 4–5 (validação em ambiente laboratorial / ambiente relevante simulado).

## Licença

Este projeto é destinado ao uso em **pesquisa acadêmica e desenvolvimento em saúde**. Para uso comercial ou clínico, entre em contato com os autores e verifique conformidade regulatória (ANVISA, LGPD).

---

<p align="center">
  <strong>HEAL+ / REDISUS</strong> — Cluster REDISUS — RNP/RUTE<br>
  Plataforma Nacional de Saúde Digital Integrada
</p>
