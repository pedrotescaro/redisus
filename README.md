# REDISUS - Sistema de Diagnóstico de Feridas por Visão Computacional

## 🏥 Sobre o Projeto

Sistema híbrido (Desktop/Mobile) de auxílio ao diagnóstico e tratamento de feridas para profissionais de estomaterapia, utilizando técnicas avançadas de Visão Computacional e Deep Learning.

## 🏗️ Arquitetura do Sistema

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CAMADA DE APRESENTAÇÃO                             │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │   Desktop (PyQt/Electron)    │    Mobile (Flutter/React Native)      │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CAMADA DE PROCESSAMENTO                              │
│                                                                              │
│  ┌─────────────────────────┐      ┌─────────────────────────────────────┐   │
│  │   MÓDULO TEMPO REAL     │      │      MÓDULO DIAGNÓSTICO PROFUNDO    │   │
│  │   (Edge Processing)      │      │      (Cloud/Local Heavy Processing) │   │
│  │                          │      │                                     │   │
│  │  • YOLOv8 Nano/TFLite   │      │  • U-Net (Segmentação de Tecidos)   │   │
│  │  • ~30-60 FPS           │      │  • CNN (Classificação Etiologia)    │   │
│  │  • Bounding Box         │      │  • ResNet50/EfficientNet            │   │
│  │  • Baixa Latência       │      │  • Alta Precisão                    │   │
│  └─────────────────────────┘      └─────────────────────────────────────┘   │
│              │                                    │                          │
│              │         ┌──────────────────┐       │                          │
│              └────────►│  ORQUESTRADOR    │◄──────┘                          │
│                        │  DE PIPELINE     │                                  │
│                        └──────────────────┘                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CAMADA DE DADOS                                    │
│  ┌──────────────────┐  ┌──────────────────┐  ┌─────────────────────────┐    │
│  │ Histórico        │  │ Modelos Treinados│  │ Protocolos de           │    │
│  │ do Paciente      │  │ (.onnx/.tflite)  │  │ Tratamento              │    │
│  └──────────────────┘  └──────────────────┘  └─────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 📁 Estrutura do Projeto

```
redisus/
├── src/
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py              # Configurações globais
│   │   └── exceptions.py          # Exceções customizadas
│   │
│   ├── capture/
│   │   ├── __init__.py
│   │   ├── video_stream.py        # Captura de vídeo (webcam/mobile)
│   │   └── image_loader.py        # Upload de imagens estáticas
│   │
│   ├── detection/
│   │   ├── __init__.py
│   │   ├── realtime_detector.py   # YOLO Nano para detecção tempo real
│   │   └── preprocessing.py       # Pré-processamento de frames
│   │
│   ├── diagnosis/
│   │   ├── __init__.py
│   │   ├── tissue_segmenter.py    # U-Net para segmentação de tecidos
│   │   ├── etiology_classifier.py # CNN para classificação de etiologia
│   │   └── wound_analyzer.py      # Análise completa integrada
│   │
│   ├── treatment/
│   │   ├── __init__.py
│   │   ├── recommender.py         # Motor de recomendação
│   │   ├── evolution_tracker.py   # Comparação temporal
│   │   └── protocols.py           # Base de protocolos
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── yolo_wrapper.py        # Wrapper para YOLO
│   │   ├── unet_model.py          # Arquitetura U-Net
│   │   └── efficientnet_model.py  # Classificador de etiologia
│   │
│   └── utils/
│       ├── __init__.py
│       ├── image_utils.py         # Utilitários de imagem
│       ├── metrics.py             # Métricas de avaliação
│       └── visualization.py       # Visualização de resultados
│
├── models/                         # Pesos dos modelos treinados
│   ├── yolo_wound_nano.onnx
│   ├── unet_tissue_segmentation.onnx
│   └── efficientnet_etiology.onnx
│
├── data/
│   ├── protocols/                  # Protocolos de tratamento (JSON)
│   └── samples/                    # Imagens de exemplo
│
├── tests/
│   ├── test_detection.py
│   ├── test_segmentation.py
│   └── test_classification.py
│
├── main.py                         # Ponto de entrada principal
├── requirements.txt
└── README.md
```

## 🚀 Instalação

```bash
# Clone o repositório
git clone https://github.com/seu-usuario/redisus.git
cd redisus

# Crie ambiente virtual
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Instale dependências
pip install -r requirements.txt
```

## 💻 Uso

### Aplicação Principal em Tempo Real

```bash
# Modo demonstração (imagem sintética)
python realtime_app.py --mode demo

# Modo webcam com detecção em tempo real
python realtime_app.py --mode webcam

# Usar câmera secundária
python realtime_app.py --mode webcam --camera 1

# Análise de imagem estática
python realtime_app.py --mode image --input caminho/para/imagem.jpg

# Com ID de paciente
python realtime_app.py --mode webcam --patient PAC001
```

### Controles (Modo Webcam)

| Tecla | Ação |
|-------|------|
| `SPACE` | Capturar e analisar ferida |
| `A` | Ativar/desativar auto-capture |
| `S` | Salvar imagem atual |
| `R` | Gerar relatório da última análise |
| `H` | Mostrar ajuda |
| `Q` / `ESC` | Sair |

### Legado (main.py)

```bash
# Comparação de evolução
python main.py --mode evolution --patient-id 12345
```

## 🔬 Módulos Funcionais

### Arquitetura em Camadas

```
┌────────────────────────────────────────────────────────────────────┐
│                    CAMADA DE APRESENTAÇÃO                          │
│  ┌─────────────────┐  ┌────────────────┐  ┌───────────────────┐   │
│  │   UIRenderer    │  │ Visualization  │  │  WindowManager    │   │
│  │   (HUD/Overlay) │  │ (Mapas/Gráficos│  │  (Multi-janelas)  │   │
│  └─────────────────┘  └────────────────┘  └───────────────────┘   │
└────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│                    CAMADA DE PROCESSAMENTO                         │
│  ┌─────────────────┐  ┌────────────────┐  ┌───────────────────┐   │
│  │  WoundDetectorCV │  │ TissueAnalyzer │  │ WoundClassifierCV │   │
│  │  (OpenCV/YOLO)   │  │  (HSV Segment) │  │  (Etiologia)      │   │
│  └─────────────────┘  └────────────────┘  └───────────────────┘   │
│                              │                                     │
│                   ┌──────────┴──────────┐                         │
│                   │   ImageProcessor    │                         │
│                   │ (Pré-processamento) │                         │
│                   └─────────────────────┘                         │
└────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│                      CAMADA DE DADOS                               │
│  ┌─────────────────┐  ┌────────────────┐  ┌───────────────────┐   │
│  │    Database     │  │ ExportManager  │  │     Cache         │   │
│  │    (SQLite)     │  │ (JSON/CSV/PDF) │  │  (Frame/Result)   │   │
│  └─────────────────┘  └────────────────┘  └───────────────────┘   │
└────────────────────────────────────────────────────────────────────┘
```

### Módulo 1: Detecção em Tempo Real (OpenCV)
- **Métodos**: Segmentação por cor (HSV), detecção de bordas, análise de textura
- **Performance**: 30+ FPS em CPU
- **Output**: Bounding box, máscara, confiança, tipo

### Módulo 2: Análise de Tecidos
- **Técnica**: Segmentação por espaço de cor HSV
- **Tecidos**: Granulação, Esfacelo, Necrose, Epitelização, Fibrina
- **Output**: Percentuais, mapa de cores, score de saúde (0-100)

### Módulo 3: Classificação de Etiologia
- **Modelo**: Heurístico + Keras (quando disponível)
- **Classes**: Úlcera Venosa, Arterial, Pé Diabético, Lesão por Pressão, etc.
- **Output**: Classificação, confiança, recomendações

## 📊 Classes de Tecido (Segmentação)

| Classe | Cor RGB | Descrição |
|--------|---------|-----------|
| Granulação | (255, 0, 0) | Tecido vermelho, saudável |
| Esfacelo | (255, 255, 0) | Tecido amarelo/branco, fibrina |
| Necrose | (0, 0, 0) | Tecido preto, necrótico |
| Pele Perilesional | (0, 255, 0) | Pele ao redor da ferida |
| Background | (128, 128, 128) | Fundo da imagem |

## 🏷️ Classes de Etiologia (Classificação)

1. **Úlcera Venosa** - Insuficiência venosa crônica
2. **Úlcera Arterial** - Doença arterial periférica
3. **Úlcera Neuropática** - Pé diabético
4. **Lesão por Pressão** - Decúbito
5. **Ferida Cirúrgica** - Pós-operatório

## 📄 Licença

Este projeto é destinado para uso em pesquisa e desenvolvimento em saúde.
Consulte seu comitê de ética antes de uso clínico.

## ⚠️ Aviso Legal

Este software é uma ferramenta de **auxílio ao diagnóstico** e não substitui
a avaliação clínica profissional. Todas as decisões terapêuticas devem ser
validadas por profissionais de saúde qualificados.
