# Arquitetura Técnica - REDISUS

## 1. Visão Geral da Arquitetura

O sistema REDISUS utiliza uma **arquitetura de dois estágios** para otimizar o trade-off entre latência e precisão:

### Estágio 1: Pipeline de Tempo Real (Edge)
```
┌────────────┐    ┌───────────────┐    ┌─────────────────┐    ┌──────────────┐
│   Câmera   │───►│ Preprocessor  │───►│  YOLO Nano      │───►│  Renderer    │
│   Stream   │    │ (Resize/Norm) │    │  (Detecção)     │    │  (BBox Draw) │
└────────────┘    └───────────────┘    └─────────────────┘    └──────────────┘
     │                                          │
     │                                          ▼
     │                                 ┌─────────────────┐
     │                                 │ Confidence > τ  │
     │                                 │ Trigger Capture │
     │                                 └─────────────────┘
     │                                          │
     ▼                                          ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                        SNAPSHOT (Full Resolution)                           │
└────────────────────────────────────────────────────────────────────────────┘
```

### Estágio 2: Pipeline de Diagnóstico (Heavy Processing)
```
┌─────────────────┐
│    SNAPSHOT     │
│  High-Res Image │
└────────┬────────┘
         │
         ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                         PARALLEL PROCESSING                                 │
│                                                                             │
│  ┌─────────────────────┐              ┌─────────────────────────────────┐  │
│  │   U-Net Segmentor   │              │   EfficientNet Classifier       │  │
│  │                     │              │                                 │  │
│  │  Input: 512x512     │              │  Input: 224x224                 │  │
│  │  Output: Mask       │              │  Output: 5 Classes              │  │
│  │  - Granulation      │              │  - Venosa                       │  │
│  │  - Slough           │              │  - Arterial                     │  │
│  │  - Necrosis         │              │  - Neuropática                  │  │
│  │  - Periwound        │              │  - Pressão                      │  │
│  │                     │              │  - Cirúrgica                    │  │
│  └──────────┬──────────┘              └───────────────┬─────────────────┘  │
│             │                                         │                     │
│             ▼                                         ▼                     │
│  ┌─────────────────────┐              ┌─────────────────────────────────┐  │
│  │ Tissue Analysis     │              │  Etiology Confidence            │  │
│  │ - % each tissue     │              │  - Probability distribution     │  │
│  │ - Area calculation  │              │  - Top-K predictions            │  │
│  └──────────┬──────────┘              └───────────────┬─────────────────┘  │
│             │                                         │                     │
│             └──────────────────┬──────────────────────┘                     │
│                                ▼                                            │
│                    ┌─────────────────────┐                                  │
│                    │  FUSION MODULE      │                                  │
│                    │  Combine Results    │                                  │
│                    └─────────────────────┘                                  │
└────────────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                    RECOMMENDATION ENGINE                                    │
│                                                                             │
│  ┌─────────────────┐    ┌──────────────────┐    ┌─────────────────────┐    │
│  │ Protocol Lookup │───►│ Evolution Tracker│───►│ Treatment Report    │    │
│  │ (Knowledge Base)│    │ (Historical Data)│    │ (Final Output)      │    │
│  └─────────────────┘    └──────────────────┘    └─────────────────────┘    │
└────────────────────────────────────────────────────────────────────────────┘
```

## 2. Estratégia de Modelos

### 2.1 Modelo de Tempo Real (YOLO Nano)

| Característica | Especificação |
|----------------|---------------|
| Arquitetura | YOLOv8 Nano |
| Input Size | 320x320 ou 416x416 |
| Parâmetros | ~3.2M |
| FLOPs | ~4.8G |
| Latência Target | < 30ms (CPU) / < 10ms (GPU) |
| Formato | ONNX / TensorFlow Lite |

**Otimizações aplicadas:**
- Quantização INT8 para edge devices
- Model pruning (30% dos parâmetros)
- Knowledge distillation do modelo maior
- Batch size = 1 (streaming)

### 2.2 Modelo de Segmentação (U-Net)

| Característica | Especificação |
|----------------|---------------|
| Arquitetura | U-Net com EfficientNet-B0 encoder |
| Input Size | 512x512 RGB |
| Output | 512x512 x 5 classes |
| Parâmetros | ~12M |
| Latência Target | < 500ms (GPU) |

**Classes de segmentação:**
```python
TISSUE_CLASSES = {
    0: "background",
    1: "granulation",    # Tecido de granulação (vermelho)
    2: "slough",         # Esfacelo (amarelo/branco)
    3: "necrosis",       # Necrose (preto)
    4: "periwound"       # Pele perilesional
}
```

### 2.3 Modelo de Classificação (EfficientNet)

| Característica | Especificação |
|----------------|---------------|
| Arquitetura | EfficientNet-B3 |
| Input Size | 224x224 RGB |
| Output | 5 classes (softmax) |
| Parâmetros | ~12M |
| Latência Target | < 100ms (GPU) |

**Classes de etiologia:**
```python
ETIOLOGY_CLASSES = {
    0: "venous_ulcer",      # Úlcera venosa
    1: "arterial_ulcer",    # Úlcera arterial
    2: "diabetic_foot",     # Pé diabético (neuropática)
    3: "pressure_injury",   # Lesão por pressão
    4: "surgical_wound"     # Ferida cirúrgica
}
```

## 3. Fluxo de Dados Detalhado

### 3.1 Modo Webcam (Tempo Real)

```python
# Pseudocódigo do loop principal
while camera.is_open():
    frame = camera.read()  # 1080p @ 30fps
    
    # Resize para modelo leve
    frame_small = resize(frame, 320x320)
    
    # Inferência rápida
    detections = yolo_nano.infer(frame_small)
    
    # Desenha bounding boxes
    frame_annotated = draw_boxes(frame, detections)
    
    # Exibe na tela
    display(frame_annotated)
    
    # Verifica trigger de captura
    if user_pressed_capture() or high_confidence_stable():
        snapshot = frame.copy()  # Full resolution
        
        # Envia para processamento assíncrono
        diagnosis_queue.put(snapshot)
```

### 3.2 Modo Upload (Foto Estática)

```python
def process_uploaded_image(image_path):
    # Carrega em alta resolução
    image = load_image(image_path)
    
    # Valida qualidade
    if not quality_check(image):
        return error("Imagem de baixa qualidade")
    
    # Processamento paralelo
    with ThreadPoolExecutor() as executor:
        seg_future = executor.submit(segment_tissues, image)
        cls_future = executor.submit(classify_etiology, image)
        
        segmentation_mask = seg_future.result()
        etiology_prediction = cls_future.result()
    
    # Fusão e análise
    report = generate_report(segmentation_mask, etiology_prediction)
    
    return report
```

## 4. Considerações de Performance

### 4.1 Otimização para Desktop (GPU NVIDIA)

```yaml
inference_backend: "tensorrt"
precision: "fp16"
batch_size: 1
stream_buffer: 3
async_inference: true
```

### 4.2 Otimização para Mobile (Edge)

```yaml
inference_backend: "tflite"
precision: "int8"
use_gpu_delegate: true  # Mali/Adreno
use_nnapi: true         # Android Neural Networks API
num_threads: 4
```

### 4.3 Estratégia de Threading

```
┌────────────────────────────────────────────────────────────────┐
│                        MAIN THREAD                              │
│  - UI Rendering                                                 │
│  - User Input Handling                                          │
│  - Display Annotated Frames                                     │
└──────────────────────────┬─────────────────────────────────────┘
                           │
         ┌─────────────────┴─────────────────┐
         ▼                                   ▼
┌─────────────────────┐           ┌─────────────────────────────┐
│   CAPTURE THREAD    │           │   INFERENCE THREAD          │
│  - Frame grabbing   │           │  - YOLO inference           │
│  - Buffer frames    │           │  - Non-blocking queue       │
│  - 60 FPS capture   │           │  - Results callback         │
└─────────────────────┘           └─────────────────────────────┘
                                              │
                                              ▼
                                  ┌─────────────────────────────┐
                                  │   DIAGNOSIS THREAD          │
                                  │  - U-Net + EfficientNet     │
                                  │  - Async processing         │
                                  │  - Result notification      │
                                  └─────────────────────────────┘
```

## 5. Formatos de Modelo Suportados

| Formato | Uso | Framework |
|---------|-----|-----------|
| `.onnx` | Desktop (CPU/GPU) | ONNX Runtime |
| `.tflite` | Mobile Android/iOS | TensorFlow Lite |
| `.engine` | NVIDIA Jetson | TensorRT |
| `.pt` | Desenvolvimento | PyTorch |

## 6. Métricas de Avaliação

### Detecção em Tempo Real
- **mAP@0.5**: > 0.85
- **Latência P95**: < 30ms
- **FPS mínimo**: 30

### Segmentação de Tecidos
- **Dice Score**: > 0.80 por classe
- **IoU médio**: > 0.75
- **Boundary F1**: > 0.70

### Classificação de Etiologia
- **Accuracy**: > 0.90
- **Macro F1**: > 0.85
- **AUC-ROC**: > 0.92

## 7. Escalabilidade Futura

### Fase 2 (Planejado)
- Integração com prontuário eletrônico (HL7 FHIR)
- Modelo multimodal (imagem + texto clínico)
- Federated Learning para hospitais

### Fase 3 (Visão)
- 3D wound reconstruction (depth camera)
- AR overlay para procedimentos
- Edge AI em dispositivos vestíveis
