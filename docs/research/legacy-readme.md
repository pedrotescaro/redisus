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
13. [Contextualização na Rede REDI-SUS](#13-contextualização-na-rede-redi-sus)
14. [Papel da Fatec Ferraz no Projeto](#14-papel-da-fatec-ferraz-no-projeto)
15. [Entregas e Cronograma do HEAL+](#15-entregas-e-cronograma-do-heal)
16. [Integração com Módulos da Rede REDI-SUS](#16-integração-com-módulos-da-rede-redi-sus)
17. [Interoperabilidade Federada com o SUS Digital (PT7)](#17-interoperabilidade-federada-com-o-sus-digital-pt7)
18. [Governança de Dados e Conformidade LGPD](#18-governança-de-dados-e-conformidade-lgpd)
19. [Validação Clínica e Escalabilidade (PT6)](#19-validação-clínica-e-escalabilidade-pt6)
20. [Referências Bibliográficas](#20-referências-bibliográficas)

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

### Abstract

**Background.** Chronic wounds (venous ulcers, pressure injuries, diabetic foot ulcers) represent a major global public health burden, with an estimated prevalence of 1–2% in developed countries and costs reaching up to 3% of healthcare budgets (Sen et al., 2009; Järbrink et al., 2017). In Brazil, the Unified Health System (SUS) faces additional challenges of scale and infrastructure heterogeneity, where wound assessment largely depends on the subjective experience of wound care specialists.

**Objective.** This work presents **HEAL+** (REDISUS), a computer-aided diagnosis platform for chronic wounds that integrates Computer Vision and Deep Learning into a complete end-to-end pipeline: from image capture to automated clinical reporting with evidence-based treatment recommendations.

**Methods.** The system employs a two-stage architecture:
- **Stage 1 — Real-time detection:** YOLOv8 Nano for wound localization in the camera frame (latency < 30 ms on GPU).
- **Stage 2 — Deep diagnosis (parallel processing):**
  - **Tissue segmentation:** U-Net with EfficientNet-B0 encoder (input 512×512, 5 classes: background, granulation, slough, necrosis, periwound).
  - **Two-stage etiological classification:** ResNet50 with transfer learning (ImageNet) — Stage 1: Normal vs. Wound (binary); Stage 2: Diabetic / Pressure / Venous (3 classes). Explainability via Grad-CAM on `layer4`.
  - **Multi-model ensemble:** EfficientNet-B3 (0.35) + DermaIntel ViT (0.40) + BiomedCLIP (0.25) with soft voting.
  - **Boundary segmentation:** MedSAM (ViT-Base, trained on 1.6M medical image-mask pairs) for precise wound delineation.

**Target results.** mAP@0.5 > 0.85 (detection), Dice > 0.80 per class (segmentation), Accuracy > 0.90 and AUC-ROC > 0.92 (classification).

**Contribution.** The platform further integrates interoperability with Brazil's public health system (HL7 FHIR R4, e-SUS PEC, DATASUS/SIGTAP), validated clinical scales (PUSH Tool 3.0, BWAT, Braden), a patient digital twin (Twin@Home), and an evidence-based clinical knowledge base via RAG with Oxford CEBM evidence levels.

**Keywords:** Computer Vision, Deep Learning, Wound Segmentation, Etiological Classification, U-Net, YOLOv8, ResNet50, Wound Care Nursing, SUS, FHIR.

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

## 13. Contextualização na Rede REDI-SUS

### 13.1 Visão Geral da Rede

O **REDI-SUS** (Rede de Saúde Digital Inteligente) é um projeto de pesquisa cooperativa (Cluster 7) financiado no âmbito da Rede Nacional de Ensino e Pesquisa (RNP), em parceria com a Rede RUTE e programas de Telessaúde. Seu objetivo é desenvolver uma **plataforma modular e interoperável** que apoie profissionais de saúde e pacientes em toda a jornada de cuidado — do diagnóstico ao acompanhamento de longo prazo —, integrando dispositivos médicos, aplicações móveis, inteligência artificial e gêmeos digitais.

A rede articula múltiplas instituições de pesquisa (UFRGS, FURG, Fatec Ferraz, Nutes/UEPB, ISI-EQ, entre outras), hospitais universitários, Unidades Básicas de Saúde (UBS) e serviços de atenção domiciliar, atuando em conformidade com o SUS Digital e a LGPD.

### 13.2 Jornada do Paciente — Três Etapas

A plataforma REDI-SUS organiza-se em três etapas que refletem a jornada típica do paciente no SUS:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    JORNADA DO PACIENTE — REDI-SUS                            │
│                                                                              │
│   ETAPA 1                  ETAPA 2                    ETAPA 3                │
│   DIAGNOSTICAR             PLANO DE CUIDADO           MONITORAR              │
│                                                                              │
│   ┌──────────────┐        ┌──────────────┐           ┌──────────────┐       │
│   │  DermaSUS    │        │  REDE VIVA   │           │  TAKERE      │       │
│   │  REDE VIVA   │        │  TAKERE      │           │  Twin@Home   │       │
│   │  HEAL+       │        │  HEAL+       │           │  HEAL+       │       │
│   └──────────────┘        └──────────────┘           └──────────────┘       │
│                                                                              │
│   Detecção precoce,        Elaboração e gestão        Adesão ao              │
│   classificação,           de planos de cuidado       tratamento,            │
│   triagem digital          personalizados             desfechos clínicos     │
└─────────────────────────────────────────────────────────────────────────────┘
```

> **O HEAL+ é o único módulo presente em todas as três etapas**, atuando como eixo transversal de diagnóstico por imagem, apoio à decisão clínica e monitoramento da evolução de feridas crônicas.

### 13.3 Módulos da Rede

| Módulo | Foco Principal | Etapas |
|--------|---------------|--------|
| **DermaSUS** | Classificação de lesões cutâneas (dermatologia) | Diagnosticar |
| **REDE VIVA** | Vigilância digital, esporotricose, testes rápidos, georreferenciamento | Diagnosticar, Plano de Cuidado |
| **HEAL+** | Diagnóstico de feridas crônicas por visão computacional e IA; apoio à decisão clínica; monitoramento de evolução | **Diagnosticar, Plano de Cuidado, Monitorar** |
| **TAKERE** | Plataforma mHealth para geração de planos de cuidado individualizados via linguagem natural | Plano de Cuidado, Monitorar |
| **Twin@Home** | Gêmeo digital para monitoramento domiciliar com reconstrução 3D, sensores IoT e alertas preditivos | Monitorar |

### 13.4 Objetivos Específicos do REDI-SUS (Contribuição do HEAL+)

| # | Objetivo da Rede | Contribuição do HEAL+ |
|---|---|---|
| 1 | Plataforma unificada expansível e interoperável com o SUS | Módulo de diagnóstico por imagem integrado via FHIR R4; arquitetura conceitual (PT2) |
| 2 | Dispositivos e protocolos rápidos de diagnóstico | Protocolos de coleta e calibração de imagens clínicas de feridas |
| 3 | IA em imagens clínicas e sinais vitais | Pipeline completo: YOLOv8 + U-Net + ResNet50 + Ensemble + MedSAM + Grad-CAM |
| 4 | Gêmeo digital para monitoramento domiciliar | Integração com Twin@Home via dados longitudinais de feridas |
| 5 | Plataforma mHealth com planos de cuidado | Interface com TAKERE para planos de cuidado baseados em diagnóstico HEAL+ |
| 6 | Gestão clínica e painéis de acompanhamento | Painéis preditivos, escalas clínicas (PUSH, BWAT, Braden), exportação FHIR |
| 7 | Fortalecimento de equipes multiprofissionais | Estratificação de risco, alertas, recomendações baseadas em evidências (RAG clínico) |

---

## 14. Papel da Fatec Ferraz no Projeto

A **Fatec Ferraz de Vasconcelos** (liderada por Márcia Bissaco) possui papel estratégico na rede REDI-SUS, com **liderança de dois pacotes de trabalho** e participação ativa em todos os demais:

### 14.1 Pacotes de Trabalho Liderados

| PT | Nome | Período | Escopo |
|----|------|---------|--------|
| **PT2** | Requisitos e Arquitetura Conceitual | M1–M6 (T1–T2) | Levantamento unificado de requisitos técnicos e clínicos junto ao SUS; definição de parâmetros de monitoramento (sinais vitais, imagens médicas, geolocalização); perfis de usuários; arquitetura conceitual de interoperabilidade; dicionário de dados |
| **PT7** | Interoperabilidade Federada com o SUS Digital | M9–M24 (T3–T8) | Infraestrutura federada; Gateway FHIR; aprendizado federado com preservação de privacidade (LGPD); comunicação segura entre dispositivos, modelos de IA e sistemas SUS (e-SUS, PEC, RNDS) |

### 14.2 Participação nos Demais Pacotes

| PT | Nome | Papel da Fatec / HEAL+ |
|----|------|------------------------|
| **PT1** | Gestão, Governança e Disseminação | Participação nos workshops, relatórios trimestrais e conformidade LGPD |
| **PT3** | Dispositivos e Aquisição de Dados | Protocolos de coleta e calibração de imagens; bases de dados clínicos com imagens rotuladas; módulos de coleta de dados; infraestrutura de coleta |
| **PT4** | IA para Cuidado Personalizado | Modelos de segmentação e classificação de imagens; biblioteca federada de modelos de IA; sistema integrado de IA com painéis preditivos |
| **PT5** | Experiência do Paciente | Protótipos de interface do processo diagnóstico; jornadas de usuário validadas; testes de usabilidade |
| **PT6** | Validação Clínica e Escalabilidade | Pilotos multicêntricos; relatório de validação; modelo de transferência tecnológica |

### 14.3 Todos os Pacotes de Trabalho do REDI-SUS

| PT | Nome | Líder | Período |
|----|------|-------|---------|
| PT1 | Gestão, Governança e Disseminação Científica | UFRGS (Érika Cota) / FURG (Vinícius Menezes) | T1–T8 |
| PT2 | Requisitos e Arquitetura Conceitual | **Fatec Ferraz (Márcia Bissaco)** | M1–M6 |
| PT3 | Dispositivos e Aquisição de Dados Clínicos | FURG (Vinícius Menezes) | T2–T5 |
| PT4 | IA para Cuidado Personalizado e Suporte à Decisão | Nutes/UEPB (Robson de Sousa) | T3–T7 |
| PT5 | Experiência do Paciente e Humanização | UFRGS (Érika Cota) | T4–T7 |
| PT6 | Validação Clínica, Escalabilidade e Replicação | ISI-EQ (Camila Proença) | T5–T8 |
| PT7 | Interoperabilidade Federada com o SUS Digital | **Fatec Ferraz (Márcia Bissaco)** | T3–T8 |

---

## 15. Entregas e Cronograma do HEAL+

### 15.1 Cronograma Geral (24 meses, 8 trimestres)

```
T1 ──── T2 ──── T3 ──── T4 ──── T5 ──── T6 ──── T7 ──── T8
 │       │       │       │       │       │       │       │
 │       │       │       │       │       │       │       └─ Manual técnico
 │       │       │       │       │       │       │          Relatório final validação
 │       │       │       │       │       │       │          Workshop Resultados Finais
 │       │       │       │       │       │       │
 │       │       │       │       │       │       └─ Sistema IA + Painéis Preditivos
 │       │       │       │       │       │          Plataforma interoperável SUS
 │       │       │       │       │       │          Materiais capacitação digital
 │       │       │       │       │       │
 │       │       │       │       │       └─ Biblioteca Federada Modelos IA
 │       │       │       │       │          Protótipos funcionais + usabilidade
 │       │       │       │       │          Pilotos Multicêntricos
 │       │       │       │       │
 │       │       │       │       └─ Gateway FHIR operacional
 │       │       │       │          Bases de dados consolidadas
 │       │       │       │          Protótipos interface diagnóstico
 │       │       │       │
 │       │       │       └─ Protótipos IA + Bases imagens rotuladas
 │       │       │          Módulos de coleta de dados
 │       │       │          Workshop Resultados Parciais
 │       │       │
 │       │       └─ Protocolos coleta e calibração HEAL+
 │       │
 │       └─ Arquitetura Conceitual + Dicionário Dados
 │
 └─ Documento Requisitos Técnicos e Clínicos
```

### 15.2 Entregas Específicas do HEAL+ por Trimestre

| Trimestre | Entrega | PT |
|-----------|---------|-----|
| **T1** | Documento de Requisitos Técnicos e Clínicos do REDI-SUS (liderança Fatec) | PT2 |
| **T2** | Relatório Técnico da Arquitetura Conceitual e Dicionário de Dados (liderança Fatec) | PT2 |
| **T3** | Protocolos de coleta e calibração de imagens clínicas de feridas | PT3 |
| **T4** | Bases de dados clínicos com imagens rotuladas (Medetec, FUSeg, Wseg, DFUC) | PT3 |
| **T4** | Módulos de coleta de dados (pipeline de captura e pré-processamento) | PT3 |
| **T4** | Protótipos iniciais de modelos de IA e relatório de arquiteturas (YOLOv8, U-Net, ResNet50, Ensemble) | PT4 |
| **T5** | Infraestrutura de coleta de dados consolidada | PT3 |
| **T5** | Bases de dados clínicos consolidadas e expandidas | PT3 |
| **T5** | Protótipos de interface do processo diagnóstico e jornadas de usuário validadas | PT5 |
| **T5** | Gateway FHIR operacional (liderança Fatec) | PT7 |
| **T6** | Biblioteca Federada de Modelos de IA e Módulos de Apoio à Decisão | PT4 |
| **T6** | Protótipos funcionais e relatório de testes de usabilidade | PT5 |
| **T6** | Relatório de Início dos Pilotos Multicêntricos e Plano de Avaliação | PT6 |
| **T7** | Sistema Integrado de IA com Painéis Preditivos e Relatório de Validação | PT4 |
| **T7** | Plataforma interoperável com o SUS Digital, dashboards de rastreabilidade e documentação de arquitetura (liderança Fatec) | PT7 |
| **T7** | Materiais de capacitação digital | PT5 |
| **T7** | Relatório da percepção do usuário (satisfação, usabilidade, autoeficácia) | PT5 |
| **T8** | Relatório final de validação e modelo de transferência tecnológica | PT6 |
| **T8** | Manual técnico de operação (liderança Fatec) | PT7 |

### 15.3 Mapeamento Entrega × Componente de Software

| Entrega | Componentes do Repositório |
|---------|---------------------------|
| Requisitos e Arquitetura (PT2) | `docs/ARCHITECTURE.md`, dicionário de dados, especificações FHIR |
| Protocolos de coleta e calibração | `src/processing/image_processor.py`, `src/processing/image_enhancer.py`, `scripts/preprocess_dataset.py` |
| Bases de dados com imagens rotuladas | `scripts/medetec_scraper.py`, `scripts/prepare_yolo_dataset.py`, `dataset/` |
| Módulos de coleta de dados | `src/capture/video_stream.py`, `src/detection/realtime_detector.py`, pipeline de pré-processamento |
| Protótipos de modelos de IA | `src/diagnosis/`, `src/ai_layer/`, `scripts/train_*.py` |
| Infraestrutura de coleta consolidada | Pipeline completo: captura → pré-processamento → detecção → análise |
| Biblioteca Federada de Modelos de IA | `src/ai_layer/ensemble_orchestrator.py`, modelos ONNX exportados, aprendizado federado |
| Sistema Integrado de IA + Painéis Preditivos | `heal_platform.py`, `src/risk/stratification.py`, `src/clinical/scales.py`, dashboards |
| Gateway FHIR | `src/interoperability/fhir_client.py`, `src/interoperability/datasus_integration.py`, `src/interoperability/esus_integration.py` |
| Plataforma interoperável com SUS Digital | Integração RNDS, e-SUS PEC, SIGTAP; documentação de APIs |
| Manual técnico de operação | `docs/`, README, guias de instalação e configuração |

---

## 16. Integração com Módulos da Rede REDI-SUS

### 16.1 Diagrama de Integração entre Módulos

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         PLATAFORMA REDI-SUS                                   │
│                                                                               │
│                      ┌──────────────────┐                                    │
│                      │     HEAL+        │                                    │
│                      │  (Fatec Ferraz)  │                                    │
│                      │  Diagnóstico de  │                                    │
│                      │  Feridas por IA  │                                    │
│                      └─────┬──┬──┬──────┘                                    │
│                            │  │  │                                           │
│          ┌─────────────────┘  │  └──────────────────┐                        │
│          │                    │                      │                        │
│          ▼                    ▼                      ▼                        │
│  ┌───────────────┐   ┌───────────────┐   ┌──────────────────┐               │
│  │   DermaSUS    │   │   TAKERE      │   │   Twin@Home      │               │
│  │  Lesões       │   │   mHealth     │   │   Gêmeo Digital  │               │
│  │  Cutâneas     │   │   Planos de   │   │   Monitoramento  │               │
│  │               │   │   Cuidado     │   │   Domiciliar     │               │
│  └───────┬───────┘   └───────┬───────┘   └──────┬───────────┘               │
│          │                   │                    │                           │
│          └───────────┬───────┘                    │                           │
│                      │                            │                           │
│                      ▼                            ▼                           │
│              ┌───────────────┐           ┌──────────────────┐                │
│              │   REDE VIVA   │           │   Sensores IoT   │                │
│              │  Vigilância   │           │   Dispositivos   │                │
│              │  Digital      │           │   Vestíveis      │                │
│              └───────────────┘           └──────────────────┘                │
│                                                                               │
│  ═══════════════════════════════════════════════════════════════════════════  │
│                    CAMADA DE INTEROPERABILIDADE (PT7 — Fatec)                 │
│              Gateway FHIR R4 │ e-SUS PEC │ RNDS │ DATASUS/SIGTAP            │
│              Aprendizado Federado │ LGPD │ Comunicação Segura               │
│  ═══════════════════════════════════════════════════════════════════════════  │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 16.2 Interfaces de Serviço entre Módulos

| Interface | De → Para | Dados Trocados | Padrão |
|-----------|-----------|----------------|--------|
| **HEAL+ → DermaSUS** | Diagnóstico de ferida → Triagem dermatológica | Imagem segmentada, classificação etiológica, scores de confiança | FHIR DiagnosticReport |
| **HEAL+ → TAKERE** | Diagnóstico → Plano de cuidado | Composição tecidual (%), tipo de ferida, escalas (PUSH, BWAT, Braden), recomendações de tratamento | FHIR CarePlan + Observation |
| **HEAL+ → Twin@Home** | Dados longitudinais de ferida → Simulação de cicatrização | Série temporal de Health Score, área da ferida, evolução tecidual | FHIR Observation (série temporal) |
| **HEAL+ → REDE VIVA** | Dados epidemiológicos → Vigilância digital | Classificação de feridas por região, geolocalização, dados agregados | FHIR Encounter + Location |
| **HEAL+ ← Twin@Home** | Alertas preditivos → Reavaliação | Alerta de deterioração, previsão de cicatrização | FHIR Flag + RiskAssessment |
| **HEAL+ ← TAKERE** | Plano de cuidado ativo → Contexto clínico | Plano de cuidado vigente, medicamentos, curativos prescritos | FHIR CarePlan |

### 16.3 Dados e Infraestrutura Compartilhados

| Recurso Compartilhado | Módulos | Descrição |
|------------------------|---------|-----------|
| **Gateway FHIR R4** | Todos | Barramento central de interoperabilidade (PT7 — Fatec) |
| **Infraestrutura de Aprendizado Federado** | HEAL+, DermaSUS, REDE VIVA | Treinamento de modelos distribuídos sem compartilhar dados de pacientes |
| **Dicionário de Dados Unificado** | Todos | Definido no PT2; terminologias SNOMED CT, LOINC, ICD-10, CID-10 |
| **Base de Dados Clínicos** | HEAL+, DermaSUS | Imagens médicas rotuladas, anotações de especialistas |
| **Protocolos de Segurança** | Todos | Criptografia, autenticação, trilha de auditoria (LGPD) |

---

## 17. Interoperabilidade Federada com o SUS Digital (PT7)

Este pacote de trabalho, **liderado pela Fatec Ferraz**, define a infraestrutura federada que conecta todos os módulos da rede ao ecossistema do SUS Digital.

### 17.1 Arquitetura de Interoperabilidade

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                     CAMADA DE INTEROPERABILIDADE PT7                          │
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                       GATEWAY FHIR R4                                    │ │
│  │                                                                          │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │ │
│  │  │ Patient  │  │Observat. │  │Diagnost. │  │CarePlan  │  │ RiskAss. │ │ │
│  │  │ Resource │  │ Resource │  │ Report   │  │ Resource │  │ Resource │ │ │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘ │ │
│  │                                                                          │ │
│  │  Terminologias: SNOMED CT │ LOINC │ ICD-10 │ CID-10 │ SIGTAP          │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                    │                                         │
│           ┌────────────────────────┼────────────────────────┐               │
│           ▼                        ▼                        ▼               │
│  ┌─────────────────┐    ┌──────────────────┐    ┌──────────────────┐       │
│  │    e-SUS PEC    │    │      RNDS        │    │  DATASUS/SIGTAP  │       │
│  │  Prontuário     │    │  Rede Nacional   │    │  Procedimentos   │       │
│  │  Eletrônico     │    │  de Dados em     │    │  BPA / SISAB     │       │
│  │                 │    │  Saúde           │    │  CNES            │       │
│  └─────────────────┘    └──────────────────┘    └──────────────────┘       │
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │              APRENDIZADO FEDERADO (Federated Learning)                   │ │
│  │                                                                          │ │
│  │   Hospital A ─┐                                                          │ │
│  │   Hospital B ──┼── Agregação de Gradientes ── Modelo Global Atualizado  │ │
│  │   UBS C ──────┘    (sem troca de dados)       (privacidade preservada)  │ │
│  │                                                                          │ │
│  │   Protocolo: FedAvg │ Comunicação: TLS 1.3 │ Privacidade: LGPD         │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │              SEGURANÇA E GOVERNANÇA                                      │ │
│  │  • Autenticação: OAuth 2.0 / OpenID Connect                            │ │
│  │  • Criptografia: AES-256 (em repouso) + TLS 1.3 (em trânsito)        │ │
│  │  • Auditoria: log de acesso imutável (LGPD Art. 37)                   │ │
│  │  • Consentimento: termo digital rastreável (LGPD Art. 7–8)            │ │
│  │  • Anonimização: k-anonimato + differential privacy para dados agre.  │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 17.2 Recursos FHIR Implementados no HEAL+

| Recurso FHIR | Uso no HEAL+ | Módulo de Código |
|---------------|-------------|------------------|
| **Patient** | Dados demográficos do paciente (anonimizados para pesquisa) | `src/interoperability/fhir_client.py` |
| **Observation** | Composição tecidual (%), Health Score, sinais vitais, área da ferida | `src/interoperability/fhir_client.py` |
| **DiagnosticReport** | Laudo clínico automatizado com classificação etiológica e escalas | `src/interoperability/fhir_client.py` |
| **Condition** | Diagnóstico codificado (ICD-10, SNOMED CT) | `src/interoperability/fhir_client.py` |
| **Media** | Imagem da ferida (referência, não embarcada) | `src/interoperability/fhir_client.py` |
| **CarePlan** | Plano de cuidado recomendado (integração TAKERE) | `src/interoperability/fhir_client.py` |
| **RiskAssessment** | Estratificação de risco (Braden, risco de amputação) | `src/risk/stratification.py` |
| **Procedure** | Procedimentos realizados (códigos SIGTAP) | `src/interoperability/datasus_integration.py` |

### 17.3 Integração com Sistemas SUS

| Sistema | Integração | Status | Módulo |
|---------|-----------|--------|--------|
| **e-SUS PEC** | Envio de dados ao Prontuário Eletrônico do Cidadão | Implementado (endpoint) | `src/interoperability/esus_integration.py` |
| **DATASUS/SIGTAP** | Consulta de procedimentos; geração de BPA (Boletim de Produção Ambulatorial) | Implementado | `src/interoperability/datasus_integration.py` |
| **SISAB** | Envio de dados para o Sistema de Informação em Saúde da Atenção Básica | Planejado | `src/interoperability/datasus_integration.py` |
| **CNES** | Consulta de estabelecimentos de saúde | Implementado | `src/interoperability/datasus_integration.py` |
| **RNDS** | Publicação na Rede Nacional de Dados em Saúde | Em desenvolvimento | `src/interoperability/fhir_client.py` |

### 17.4 Entregas do PT7

| Trimestre | Entrega |
|-----------|---------|
| **T5** | Gateway FHIR R4 operacional com suporte aos recursos Patient, Observation, DiagnosticReport |
| **T7** | Plataforma interoperável com o SUS Digital; dashboards de rastreabilidade; documentação completa de arquitetura |
| **T8** | Manual técnico de operação para implantação e manutenção do gateway em ambientes SUS |

---

## 18. Governança de Dados e Conformidade LGPD

### 18.1 Princípios de Governança

O HEAL+ segue os princípios de governança de dados definidos pelo REDI-SUS em conformidade com a **Lei Geral de Proteção de Dados (LGPD — Lei 13.709/2018)** e as normas do **CEP/CONEP** para pesquisa com seres humanos:

| Princípio LGPD | Implementação no HEAL+ |
|-----------------|------------------------|
| **Finalidade** (Art. 6°, I) | Dados utilizados exclusivamente para diagnóstico, tratamento e pesquisa aprovada pelo CEP |
| **Adequação** (Art. 6°, II) | Coleta limitada aos dados estritamente necessários (imagens de feridas, dados clínicos mínimos) |
| **Necessidade** (Art. 6°, III) | Minimização de dados pessoais; prioridade para dados anonimizados |
| **Livre acesso** (Art. 6°, IV) | Paciente pode consultar e solicitar exclusão de seus dados |
| **Qualidade dos dados** (Art. 6°, V) | Validação de qualidade de imagem; protocolos de calibração |
| **Transparência** (Art. 6°, VI) | Laudo explicável (Grad-CAM); transparência algorítmica |
| **Segurança** (Art. 6°, VII) | Criptografia AES-256; TLS 1.3; controle de acesso |
| **Prevenção** (Art. 6°, VIII) | Privacy by design; avaliação de impacto à proteção de dados |
| **Não discriminação** (Art. 6°, IX) | Monitoramento de viés em datasets (Fitzpatrick I–VI) |

### 18.2 Protocolos de Compartilhamento Seguro de Dados

```
┌────────────────────────────────────────────────────────────────────┐
│                  FLUXO DE DADOS — LGPD COMPLIANT                    │
│                                                                     │
│  Paciente ──→ Consentimento ──→ Coleta de     ──→ Anonimização    │
│               Informado          Imagem/Dados      (k-anonimato)   │
│               (TCLE digital)                                        │
│                                       │                             │
│                                       ▼                             │
│                              ┌─────────────────┐                   │
│                              │  Armazenamento   │                   │
│                              │  Local (SQLite)  │                   │
│                              │  Criptografado   │                   │
│                              └────────┬────────┘                   │
│                                       │                             │
│                        ┌──────────────┼──────────────┐             │
│                        ▼              ▼              ▼             │
│                   Diagnóstico    Pesquisa        Integração        │
│                   Local (IA)     (dados anon.)   SUS (FHIR)        │
│                        │              │              │             │
│                        ▼              ▼              ▼             │
│                   Laudo para     FL (gradientes  RNDS / e-SUS      │
│                   profissional   sem dados)      (dados mín.)      │
│                                                                     │
│  Trilha de Auditoria: todos os acessos são registrados (Art. 37)   │
└────────────────────────────────────────────────────────────────────┘
```

### 18.3 Aprendizado Federado e Privacidade

O módulo de aprendizado federado permite que múltiplas instituições treinem modelos de IA colaborativamente **sem compartilhar dados de pacientes**:

| Aspecto | Especificação |
|---------|---------------|
| **Protocolo** | Federated Averaging (FedAvg) — McMahan et al., 2017 |
| **Comunicação** | Apenas gradientes/pesos agregados trafegam entre nós |
| **Privacidade** | Differential privacy (ε-DP) adicionada aos gradientes |
| **Infraestrutura** | Cada instituição mantém seus dados localmente; servidor de agregação na RNP |
| **Modelos federados** | U-Net (segmentação), ResNet50 (classificação), EfficientNet (ensemble) |
| **Conformidade** | LGPD Art. 12 (anonimização) + Art. 46 (medidas de segurança) |

### 18.4 Ética em Pesquisa (CEP/CONEP)

| Documento | Descrição | Status |
|-----------|-----------|--------|
| Protocolo de pesquisa | Submetido à Plataforma Brasil | Requerido antes de coleta |
| TCLE (Termo de Consentimento Livre e Esclarecido) | Versão digital com assinatura eletrônica | Template disponível |
| DPIA (Data Protection Impact Assessment) | Avaliação de impacto à proteção de dados pessoais | Em elaboração |
| Relatório de conformidade LGPD | Documentação de medidas técnicas e organizacionais | Trimestral (PT1) |

---

## 19. Validação Clínica e Escalabilidade (PT6)

### 19.1 Estratégia de Validação Multicêntrica

O HEAL+ será validado em ambientes reais do SUS seguindo protocolo multicêntrico coordenado pelo PT6 (ISI-EQ):

| Fase | Período | Ambiente | Objetivo |
|------|---------|----------|----------|
| **Pré-piloto** | T4–T5 | Laboratório / ambiente simulado | Validação técnica dos modelos de IA; calibração de thresholds |
| **Piloto** | T6–T7 | Hospitais universitários, UBS | Validação clínica com pacientes reais; concordância com especialistas |
| **Escala** | T7–T8 | Múltiplos centros via RUTE/Telessaúde | Replicação; avaliação de generalização; custo-benefício |

### 19.2 Protocolo de Validação do HEAL+

| Critério | Método | Métrica |
|----------|--------|---------|
| **Acurácia diagnóstica** | Comparação com anotações de estomaterapeutas (gold standard) | Sensibilidade, Especificidade, AUC-ROC |
| **Concordância inter-observador** | HEAL+ vs. 2–3 especialistas em estomaterapia | Cohen's Kappa (κ ≥ 0.61 = bom) |
| **Segmentação tecidual** | Comparação com máscaras manuais de especialistas | Dice Score, IoU por classe |
| **Tempo de diagnóstico** | Tempo HEAL+ vs. tempo profissional sem auxílio | Redução percentual |
| **Aceitação profissional** | Questionário SUS (System Usability Scale) + TAM | Score SUS ≥ 68; TAM positivo |
| **Impacto clínico** | Decisão do profissional com vs. sem HEAL+ | Mudança no plano de tratamento |

### 19.3 Nível de Maturidade Tecnológica (TRL)

| TRL | Descrição | Status HEAL+ |
|-----|-----------|-------------|
| TRL 1 | Princípios básicos observados | ✅ Completo |
| TRL 2 | Conceito tecnológico formulado | ✅ Completo |
| TRL 3 | Prova de conceito experimental | ✅ Completo |
| TRL 4 | Validação em ambiente laboratorial | ✅ Em andamento (atual) |
| TRL 5 | Validação em ambiente relevante | 🔄 Planejado (T6–T7) |
| TRL 6 | Demonstração em ambiente relevante | 🔄 Planejado (T7–T8) |
| TRL 7–9 | Qualificação, demonstração e operação | Pós-projeto (ANVISA SaMD) |

### 19.4 Escalabilidade e Modelo de Transferência Tecnológica

| Estratégia | Descrição |
|------------|-----------|
| **Modularidade** | Arquitetura de microsserviços permite deploy independente de cada componente |
| **Modelos ONNX** | Formato agnóstico de plataforma; inferência otimizada em CPU, GPU ou edge |
| **TFLite** | Conversão para dispositivos Android (Atenção Primária) com quantização INT8 |
| **Docker** | Containerização para deploy padronizado em diferentes ambientes SUS |
| **Documentação** | Manual técnico de operação (PT7, T8) com guias de instalação, configuração e manutenção |
| **Capacitação** | Materiais de capacitação digital (PT5, T7) para treinamento de profissionais de saúde |
| **Replicação via RUTE** | Disseminação nacional através da Rede Universitária de Telemedicina |
| **Código aberto** | Repositório público para revisão por pares e contribuições da comunidade |

### 19.5 Resultados Esperados

| Indicador | Meta |
|-----------|------|
| Decisões clínicas mais assertivas e precoces | Redução do tempo de diagnóstico em estomaterapia |
| Redução de internações evitáveis | Detecção precoce de deterioração via monitoramento contínuo |
| Aumento da adesão a tratamentos | Acompanhamento individualizado com alertas e planos personalizados |
| Equidade no acesso | Municípios remotos com acesso a diagnóstico especializado via IA |
| Padronização do cuidado | Protocolo de avaliação reprodutível e objetivo (vs. subjetividade) |
| Fortalecimento da Atenção Primária | Deploy mobile em UBS sem especialista em estomaterapia |

---

## 20. Referências Bibliográficas

1. ARAÚJO, T. M. et al. Realidade virtual no alívio da dor durante a troca de curativos de feridas crônicas. Revista da Escola de Enfermagem da USP, São Paulo, v. 55, e20200513, 2021. DOI: https://doi.org/10.1590/1980-220X-REEUSP-2020-0513. Disponível em: https://www.scielo.br/j/reeusp/a/xLqsRvkycBVLt3DD7BsM4tP/?lang=pt&format=pdf. Acesso em: 30 maio 2025.
2. BORGES, Eline Lima; SOUZA, Perla Oliveira Soares de. Feridas: como tratar. 3. ed. Rio de Janeiro: Rubio, 2024. p. 61-88.
3. FLORIANÓPOLIS. Prefeitura Municipal. Secretaria Municipal de Saúde. Protocolo de cuidados de feridas. Florianópolis, SC: SMS, 2008.
4. GERMANO, Renan Soares; ELISEO, Maria Amelia; SILVEIRA, Ismar Frango. Introdução à acessibilidade na Web: do conceito à prática. In: JORNADAS IBERO-AMERICANAS DE INTERAÇÃO HUMANO-COMPUTADOR, 7., 2021, São Paulo. Anais [...]. São Paulo: Sociedade Brasileira de Computação, 2021.
5. LIMA, E. V. M. et al. Construction of a mobile application for wound assessment for nursing students and professionals. Estima – Brazilian Journal of Enterostomal Therapy, [S. l.], v. 22, art. 1515, 2024. Disponível em: https://www.revistaestima.com.br/estima/article/view/1515. Acesso em: 1 nov. 2024.
6. MADRIL MEDEIROS, R. M. et al. Contribuição de um software para o registro, monitoramento e avaliação de feridas. Global Academic Nursing Journal, [S. l.], v. 2, n. 3, p. e146, 2021. DOI: 10.5935/2675-5602.20200146. Disponível em: https://www.globalacademicnursing.com/index.php/globacadnurs/article/view/123. Acesso em: 7 mar. 2025.
7. MEDETEC. Medetec Image Databases. A collection of wound images for research and education. Disponível em: https://www.medetec.co.uk/files/medetec-image-databases.html.
8. MENOITA, E.; SEARA, A.; SANTOS, V. Plano de Tratamento dirigido aos Sinais Clínicos da Infecção da Ferida. Journal of Aging & Inovation, v. 3, n. 2, p. 62-73, 2014.
9. PAULA, M. A. B.; SANTOS, V. L. C. G. O significado de ser especialista para o enfermeiro estomaterapeuta. Revista Latino-Americana de Enfermagem, Ribeirão Preto, v. 11, n. 4, p. 474–482, jul. 2003. Disponível em: https://www.scielo.br/j/rlae/a/mvBJQ3wFgTGjT6hJ4NNDVxS/. Acesso em: 13 nov. 2024.
10. ROCHA, Adiel Andrade. Feridômetro: aplicativo de auxílio à aprendizagem do acrônimo TIMERS. 2021. Trabalho de Conclusão de Curso (Graduação em Ciência da Computação) – Universidade Federal de Campina Grande, Campina Grande, 2021. Disponível em: https://dspace.sti.ufcg.edu.br/bitstream/riufcg/19691/1/ADIEL%20ANDRADE%20ROCHA%20-%20TCC%20CI%C3%8ANCIA%20DA%20COMPUTA%C3%87%C3%83O%202021.pdf. Acesso em: 2 set. 2025.
11. SILVA, Cláudio Xavier da. Sis-MF - Aplicativo para monitoramento da cicatrização de feridas. 2018. Dissertação (Mestrado Profissional em Ciências) – Universidade Federal de São Paulo, São Paulo, 2018.
12. SOARES PACZEK, R. et al. A ESTOMATERAPIA COMO CAMPO DE ESTÁGIO. In: CONGRESSO BRASILEIRO DE ESTOMATERAPIA, [S. l.], 2024. Anais [...]. [S. l.]: SOBEST, 2024. Disponível em: https://anais.sobest.com.br/cbe/article/view/447. Acesso em: 20 out. 2024.
13. Sen, C. K., et al. (2009). Human skin wounds: A major and snowballing threat to public health and the economy. *Wound Repair and Regeneration*, 17(6), 763–771.
14. Järbrink, K., et al. (2017). The humanistic and economic burden of chronic wounds: a protocol for a systematic review. *Systematic Reviews*, 6(1), 15.
15. Ma, J., et al. (2024). Segment anything in medical images. *Nature Communications*, 15, 654. *(MedSAM)*
16. Zhang, Y., et al. (2023). BiomedCLIP: A multimodal biomedical foundation model pretrained from fifteen million scientific image-text pairs. *arXiv:2303.00915*. *(BiomedCLIP)*
17. Schultz, G. S., et al. (2003). Wound bed preparation: a systematic approach to wound management. *Wound Repair and Regeneration*, 11(S1), S1–S28. *(Abordagem TIME)*
18. O'Meara, S., et al. (2012). Compression for venous leg ulcers. *Cochrane Database of Systematic Reviews*. *(Compressão multicomponente)*
19. Bergstrom, N., et al. (1987). The Braden Scale for predicting pressure sore risk. *Nursing Research*, 36(4), 205–210.
20. Wagner, F. W. (1981). The dysvascular foot: a system for diagnosis and treatment. *Foot & Ankle*, 2(2), 64–122. *(Escala de Wagner)*
21. Anisuzzaman, D. M., et al. (2022). Image-based artificial intelligence in wound assessment: A systematic review. *Advances in Wound Care*, 11(12), 687–709.
22. Ronneberger, O., et al. (2015). U-Net: Convolutional Networks for Biomedical Image Segmentation. *MICCAI*, 234–241.
23. He, K., et al. (2016). Deep Residual Learning for Image Recognition. *CVPR*, 770–778. *(ResNet)*
24. Redmon, J., et al. (2016–2023). YOLOv1→v8: evolução de detectores de objetos em tempo real. *Ultralytics*. *(YOLOv8)*
25. Tan, M. & Le, Q. (2019). EfficientNet: Rethinking Model Scaling for Convolutional Neural Networks. *ICML*. *(EfficientNet)*
26. Wang, C., et al. (2023). Wound Segmentation Network (WSNet). *WACV 2023*. *(Wseg dataset — 2686 imagens)*
27. Cassidy, B., et al. (2021). The DFUC 2020 dataset: Analysis towards diabetic foot ulcer detection. *BioMedical Engineering OnLine*. *(DFUC Challenge)*
28. Botelho, S. S. C., et al. (2024). Performance-watt analysis of GPU-based digital twin simulations. In: *IECON 2024 — 50th Annual Conference of the IEEE Industrial Electronics Society* (USA).
29. Niemiec, W.; Cota, E. (2025). Towards a component-based framework for mHealth apps: Bridging the gap between the nursing domain language and the computation domain. *Journal of Systems and Software*, 230:112497. https://doi.org/10.1016/j.jss.2025.112497 *(TAKERE)*
30. Niemiec, W.; Tavares, A. R.; Cota, E. (2025). Leveraging Natural Language Processing for mHealth Development: A Component-Based Approach Using Nursing Taxonomies. *Proc. IEEE CBMS*. doi:10.1109/CBMS65348.2025.00084 *(TAKERE/NLP)*
31. Oliveira, V. M., et al. (2024). Digital Twin Across Industry 5.0: Integrating Dimensional Analysis to a Rotor Inspection Module. In: *2024 IEEE 22nd Int. Conf. on Industrial Informatics*, Beijing. *(Twin@Home)*
32. Carvalho, R.; Sampaio, A. F.; Vasconcelos, M. J. M. (2025). Automating Tissue Segmentation and Quantification for Wound Healing Assessment. In: *2025 IEEE 38th CBMS*, Madrid, p. 160–166. doi:10.1109/CBMS65348.2025.00042
33. Bahadır, E. B.; Sezgintürk, M. K. (2016). Lateral flow assays: principles, designs and labels. *TrAC Trends in Analytical Chemistry*. *(REDE VIVA)*
34. Pias, M. R., et al. (2025). On the scaling of digital twins by aggregation. *Data & Policy*, 7:e9. *(Twin@Home)*
35. Gomis-Pastor, M., et al. Improving patients' experience and medication adherence after heart failure treatment: mixed methods study. *(Experiência do Paciente)*
36. INCA. (2021). *Detecção precoce do câncer*. Rio de Janeiro: INCA. 72 p. ISBN 978-65-88517-22-2. *(DermaSUS)*
37. Jakob, R., et al. (2022). Factors Influencing Adherence to mHealth Apps for Prevention or Management of Noncommunicable Diseases: Systematic Review. *J Med Internet Res*, 24(5):e35371. doi:10.2196/35371 *(mHealth/Adesão)*
38. Laubenbacher, R., et al. (2024). Digital twins in medicine. *Nature Computational Science*. *(Twin@Home)*
39. Liu, Y., et al. (2019). A Novel Cloud-Based Framework for the Elderly Healthcare Services Using Digital Twin. *IEEE Access*. *(Twin@Home)*
40. Orofino-Costa, R., et al. (2017). Sporotrichosis: an update on epidemiology, etiopathogenesis, laboratory and clinical therapeutics. *An Bras Dermatol*. *(REDE VIVA)*
41. Sehat Ullah, et al. (2025). Machine Learning and Digital-Twins-Based Internet of Robotic Things for Remote Patient Monitoring. *IEEE Journals & Magazine*. *(Twin@Home/IoT)*
42. Shamsuddeen, A., et al. (2024). The future of skin cancer diagnosis: a comprehensive systematic review of ML and DL models. *Cogent Engineering*, 11(1):2395425. https://doi.org/10.1080/23311916.2024.2395425 *(DermaSUS)*
43. Somfai, E., et al. (2023). Handling dataset dependence with model ensembles for skin lesion classification from dermoscopic and clinical images. *Int J Imaging Syst Technol*, 33(2):556–571. *(Ensemble/DermaSUS)*
44. Tambella, A. M., et al. (2025). Avanços na medição sem contato da área da ferida usando aplicativo móvel. *Skin Wound Care*, 38(7):360–366. doi:10.1097/ASW.0000000000000296 *(Medição de feridas/mHealth)*
45. McMahan, B., et al. (2017). Communication-Efficient Learning of Deep Networks from Decentralized Data. *AISTATS*. *(Federated Learning)*

---

<p align="center">
  <strong>HEAL+ / REDISUS</strong> — Cluster 7 REDI-SUS — RNP/RUTE<br>
  Rede de Pesquisa em Saúde Digital Inteligente<br>
  Diagnóstico, Planos de Cuidado e Acompanhamento Remoto<br>
  <em>Fatec Ferraz de Vasconcelos — Módulo HEAL+ (PT2 + PT7)</em>
</p>
