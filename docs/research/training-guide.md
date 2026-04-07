# REDISUS — Guia de Treinamento Real (YOLO + U-Net)

> **Objetivo**: substituir o fallback OpenCV por modelos de Deep Learning treinados
> nos dados reais de feridas do projeto Heal+.

---

## 1. Estrutura de Diretórios Esperada

```
dataset/
├── yolo_wounds/                    ← YOLO (detecção de ferida)
│   ├── data.yaml                   ← metadados lidos pelo Ultralytics
│   ├── train/
│   │   ├── images/                 ← .jpg/.png  (640×640 recomendado)
│   │   └── labels/                 ← .txt  formato: class x_c y_c w h (norm.)
│   ├── val/
│   │   ├── images/
│   │   └── labels/
│   └── test/                       ← opcional
│       ├── images/
│       └── labels/
│
├── tissue_segmentation/            ← U-Net (segmentação de tecidos)
│   ├── train/
│   │   ├── images/                 ← .jpg/.png  (256×256 ou 512×512)
│   │   └── masks/                  ← .png single-channel, px = 0-4
│   ├── val/
│   │   ├── images/
│   │   └── masks/
│   └── test/
│       ├── images/
│       └── masks/
│
└── medetec/                        ← dataset cru (já existente)
```

### Classes da máscara U-Net (valor do pixel)

| Pixel | Classe         | Cor clínica        |
|-------|----------------|--------------------|
| 0     | Background     | —                  |
| 1     | Granulação     | Vermelho vivo      |
| 2     | Esfacelo       | Amarelo / branco   |
| 3     | Necrose        | Preto / marrom     |
| 4     | Perilesional   | Tom de pele normal |

---

## 2. Pipeline Completo (passo a passo)

### 2.1 Criar a estrutura de pastas

```bash
python scripts/setup_dataset_structure.py
```

### 2.2 Popular o dataset YOLO (auto-detecção a partir do medetec)

```bash
# Gera bounding boxes automáticas via OpenCV + split train/val
python scripts/prepare_yolo_dataset.py --source dataset/medetec --output dataset/yolo_wounds --split 0.8

# Visualização de sanity-check (gera preview)
python scripts/prepare_yolo_dataset.py --source dataset/medetec --preview --preview-samples 10
```

### 2.3 Pré-processar imagens

```bash
# YOLO: redimensiona para 640×640
python scripts/preprocess_dataset.py --task yolo --imgsz 640

# U-Net: redimensiona para 256×256 (ou 512)
python scripts/preprocess_dataset.py --task unet --imgsz 256

# Verificar integridade (imagens ↔ labels/masks pareados)
python scripts/preprocess_dataset.py --verify --task both
```

### 2.4 Augmentação offline (opcional, para datasets muito pequenos)

```bash
# Gera 3x mais imagens augmentadas para U-Net
python scripts/medical_augmentation.py \
    --input dataset/tissue_segmentation/train \
    --output dataset/tissue_segmentation_aug/train \
    --factor 3 --level moderate --imgsz 256
```

---

## 3. Comandos de Treinamento

### 3.1 YOLO — Detecção de Ferida

```bash
# ── Cenário 1: Dataset PEQUENO (<200 imagens) ──
python scripts/train_yolo_wound.py \
    --model yolov8n.pt \
    --data dataset/yolo_wounds/data.yaml \
    --imgsz 640 \
    --epochs 150 \
    --batch 8 \
    --device 0

# ── Cenário 2: Dataset MÉDIO (200-1000 imagens) ──
python scripts/train_yolo_wound.py \
    --model yolov8n.pt \
    --data dataset/yolo_wounds/data.yaml \
    --imgsz 640 \
    --epochs 100 \
    --batch 16 \
    --device 0

# ── Cenário 3: Dataset GRANDE (>1000) + GPU forte ──
python scripts/train_yolo_wound.py \
    --model yolov8s.pt \
    --data dataset/yolo_wounds/data.yaml \
    --imgsz 640 \
    --epochs 80 \
    --batch 32 \
    --device 0

# ── Exportar para ONNX após treinamento ──
python scripts/train_yolo_wound.py \
    --export-only \
    --weights runs/detect/wound/wound_yolov8/weights/best.pt \
    --benchmark

# ── Apenas avaliar ──
python scripts/train_yolo_wound.py --evaluate \
    --weights runs/detect/wound/wound_yolov8/weights/best.pt
```

### 3.2 U-Net — Segmentação de Tecidos

```bash
# ── Cenário 1: Dataset PEQUENO (<100 imagens) ──
python scripts/train_unet_tissue.py \
    --encoder efficientnet-b0 \
    --imgsz 256 \
    --epochs 120 \
    --batch 4 \
    --lr 5e-5 \
    --device cuda

# ── Cenário 2: Dataset MÉDIO (100-500 imagens) ──
python scripts/train_unet_tissue.py \
    --encoder efficientnet-b0 \
    --imgsz 512 \
    --epochs 80 \
    --batch 8 \
    --lr 1e-4 \
    --device cuda

# ── Cenário 3: Encoder maior + mais dados ──
python scripts/train_unet_tissue.py \
    --encoder efficientnet-b2 \
    --imgsz 512 \
    --epochs 60 \
    --batch 4 \
    --lr 1e-4 \
    --device cuda

# ── Exportar para ONNX ──
python scripts/train_unet_tissue.py \
    --export-only \
    --weights runs/segment/tissue/best_model.pt \
    --benchmark

# ── Treino apenas CPU (sem GPU) ──
python scripts/train_unet_tissue.py \
    --encoder efficientnet-b0 \
    --imgsz 256 \
    --epochs 50 \
    --batch 2 \
    --lr 1e-4 \
    --device cpu
```

---

## 4. Hiperparâmetros Anti-Overfitting para Datasets Médicos Pequenos

| Parâmetro             | Dataset Pequeno | Dataset Médio | Justificativa                            |
|-----------------------|-----------------|---------------|------------------------------------------|
| **Epochs**            | 120-150         | 80-100        | Mais epochs + early stopping             |
| **Batch size**        | 4-8             | 8-16          | Batch menor = mais ruído = regularização |
| **Learning rate**     | 5e-5            | 1e-4          | LR menor → convergência mais estável     |
| **Patience (E.S.)**   | 20-25           | 15            | Margem para sinais tardios               |
| **Weight decay**      | 1e-3            | 1e-4          | Regularização L2 mais forte              |
| **Encoder**           | efficientnet-b0 | b0 ou b2      | Encoder menor → menos params → menos OF  |
| **Input size**        | 256×256         | 512×512       | Menor resolução → menos compute          |
| **Augmentation**      | aggressive      | moderate      | Mais augment. compensa menos dados       |
| **Mosaic (YOLO)**     | 1.0             | 0.5           | Mosaic é extremamente eficaz em poucos dados |
| **Dropout** (custom)  | 0.3-0.5         | 0.1-0.2       | Regularização extra                      |

### Dicas práticas:

1. **Sempre use early stopping** (`patience=20`). Nunca treine "por tempo fixo".
2. **Congele o encoder** nas primeiras 5-10 epochs, depois descongele com LR 10x menor.
3. **Monitore a curva val_loss**: se divergir da train_loss → overfitting.
4. **Use class weights** na loss (o `train_unet_tissue.py` já implementa):
   - Background: 0.5 (sub-representado)
   - Necrose: 2.0 (classe rara mas clinicamente crítica)

---

## 5. Data Augmentation — O que É e Não É Seguro

### SEGURO (usar livremente)

| Técnica               | Config                          | Motivo                                    |
|-----------------------|---------------------------------|-------------------------------------------|
| Flip horizontal       | `p=0.5`                        | Orientação não é diagnóstica              |
| Flip vertical         | `p=0.5`                        | Idem                                      |
| Rotação ±15°          | `rotate_limit=15`              | Simula ângulo de captura variado          |
| Zoom ±10%             | `scale_limit=0.1`              | Simula distância da câmera               |
| Translação ±5%        | `shift_limit=0.05`             | Centralização variável                   |
| Ruído Gaussiano       | `var_limit=(5,20)`             | Simula ruído de câmera de celular        |
| Blur leve             | `blur_limit=(3,5)`             | Simula foco impreciso                    |
| CLAHE                 | `clip_limit=2.0`               | Melhora contraste sem alterar matiz      |

### MODERADO (usar com parcimônia)

| Técnica               | Config                          | Motivo                                    |
|-----------------------|---------------------------------|-------------------------------------------|
| Brilho ±10%           | `brightness_limit=0.1`         | Simula iluminação variada, mas cuidado   |
| Contraste ±10%        | `contrast_limit=0.1`           | Não deve mascarar texturas              |
| Elastic Transform     | `alpha=30, sigma=6`            | Simula deformação natural de tecido mole |
| Mosaic (YOLO)         | `mosaic=1.0`                   | Excelente para datasets pequenos         |

### PROIBIDO (evitar em feridas)

| Técnica               | Motivo                                                       |
|-----------------------|--------------------------------------------------------------|
| Hue shift > ±5        | **Altera a cor diagnóstica** (vermelho↔amarelo = diagnósticos diferentes!) |
| Saturação forte       | Muda percepção de tecido granulação vs. esfacelo             |
| ColorJitter forte     | Mistura canais de cor → informação clínica perdida           |
| Random Erasing/Cutout | Remove pixels da lesão → perde informação clínica           |
| Mixup forte (>0.2)    | Funde texturas de tecidos distintos                          |
| Perspective forte     | Deforma morfologia da ferida                                 |

---

## 6. Após o Treinamento

Os modelos ONNX exportados são salvos em:
- `models/yolo_wound_nano.onnx` (detecção)
- `models/unet_tissue_segmentation.onnx` (segmentação)

Esses caminhos já estão configurados em `src/core/config.py` como:
- `RealtimeConfig.yolo_model_path`
- `RealtimeConfig.unet_model_path`

O sistema automaticamente usa Deep Learning quando os `.onnx` existem,
com fallback para OpenCV caso contrário (comportamento atual).

---

## 7. Checklist Rápido

- [ ] Rodar `setup_dataset_structure.py` para criar pastas
- [ ] Popular YOLO: `prepare_yolo_dataset.py` (ou anotar manualmente)
- [ ] Popular U-Net: anotar máscaras com LabelMe/CVAT (valores 0-4)
- [ ] Pré-processar: `preprocess_dataset.py --task both`
- [ ] Verificar: `preprocess_dataset.py --verify`
- [ ] Treinar YOLO: `train_yolo_wound.py --epochs 100`
- [ ] Treinar U-Net: `train_unet_tissue.py --epochs 80`
- [ ] Exportar ONNX: usar `--export-only` em cada script
- [ ] Copiar `.onnx` para `models/` (feito automaticamente)
- [ ] Testar inferência: `python realtime_app.py`
