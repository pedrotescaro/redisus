# ANALISE INICIAL - Modernizacao IA/CV e Arquitetura Multi-Modelo

Data da analise: 2026-07-04

Branch inspecionada: `develop` (`git status`: limpa em relacao ao trabalho local antes desta analise).

Escopo: reconhecimento obrigatorio antes de alteracoes funcionais. Este arquivo documenta o estado real encontrado no repositorio `redisus`, especialmente Python/visao computacional, geracao generativa, chat assistente, upload/storage de imagens, dependencias e divergencias em relacao ao prompt.

## 1. Resumo executivo

O repositorio nao e um backend TypeScript/Node unico. O estado atual e hibrido:

- Backend/API principal: Flask/Python em `apps/api`, com dominio compartilhado em `packages/clinical_domain` e pipeline de CV em `src/processing`.
- Frontend: React/Vite/TypeScript em `web/redisus-frontend`.
- IA/CV Python: grande pipeline OpenCV + modelos PyTorch opcionais, scripts de treino/validacao e artefatos documentados.
- IA/CV TypeScript ja existente: pipeline browser/canvas em `web/redisus-frontend/src/services/ai`, mas ele nao e paridade numerica do Python e nao carrega ONNX/TF.js.
- IA generativa atual: chamadas diretas e dispersas a Gemini no backend Python e Groq/OpenAI-compatible no frontend. Nao existe camada unica `GenerativeModelProvider`.
- Imagens: o frontend salva imagens de avaliacoes em Supabase Storage (`wound-images`) com URL publica; o backend `/api/v1/analyze` recebe `multipart/form-data` e processa em memoria; tambem existe setup Firebase Admin/Storage, mas o fluxo web de avaliacao usa Supabase.

Conclusao: antes de implementar a migracao completa para TypeScript e multi-provider, existem divergencias arquiteturais e de compliance que devem ser decididas. Principalmente: hoje chaves Groq sao usadas no cliente (`VITE_GROQ_API_KEY`), o envio multimodal de imagens a provedores externos precisaria de decisao LGPD/compliance, e nao ha artefatos ONNX/TF.js versionados para a maior parte dos modelos de CV.

## 2. Inventario Python relacionado a IA, CV, treino e inferencia

### 2.1 Runtime principal de CV/inferencia

- `src/processing/clinical_wound_analyzer_core.py`
  - Motor headless principal usado pelo backend.
  - Classe: `ClinicalWoundAnalyzer`.
  - Metodo principal: `analyze(image, manual_roi_mask=None, manual_roi_masks=None, roi_metadata=None, roi_metadata_list=None)`.
  - Saida: `ClinicalReport` com validade, tecidos, bordas, area, score, predicoes DL/ResNet/ensemble, overlays e metadados.
- `src/processing/wound_detector_cv.py`
  - Detector OpenCV por cor, borda, textura, combinado e `TEXTURE_PRIORITY`.
  - Tambem tem caminho `ML_MODEL`, mas a inferencia especifica esta marcada como TODO.
- `src/processing/tissue_analyzer.py`
  - Analise tecidual CV/heuristica.
- `src/processing/wound_classifier_cv.py`
  - Classificador CV classico.
- `src/processing/roi_segmentation.py`
  - Segmentacao/ROI.
- `src/processing/preprocessing_filters.py`
  - Filtros experimentais: median, gaussian, equalizacao, CLAHE etc.
- `src/processing/image_processor.py`
  - Processamento de imagem.
- `src/processing/image_enhancer.py`
  - Analise de iluminacao, contraste, white balance, correcoes e `prepare_for_cnn`.
- `src/processing/false_positive_filter.py`
  - Filtro de falso positivo.
- `src/processing/dl_tissue_pipeline.py`
  - Pipeline DL de mascara de ferida e segmentacao tecidual baseado em artefatos esperados em `models/`.

### 2.2 Modelos e inferidores em `src/diagnosis`

- `src/diagnosis/resnet_wound_classifier.py`
  - `TwoStageWoundClassifier`: ResNet50 em dois estagios.
  - Stage 1: `Normal` vs `Wound`.
  - Stage 2: `Diabetic Wounds`, `Pressure Wounds`, `Venous Wounds`.
  - Preprocessamento: OpenCV BGR -> RGB/PIL -> `Resize((224,224))` -> `ToTensor` -> ImageNet normalize.
  - Usa TTA e Grad-CAM quando pesos existem.
- `src/diagnosis/pressure_injury_stage_classifier.py`
  - `PressureInjuryStageClassifier`: ResNet50 para estagios `stage_1` a `stage_4`, com fallback heuristico.
  - Artefato presente: `models/pressure_injury_stage_classifier/pressure_injury_stage_resnet50.pth`.
- `src/diagnosis/tissue_segmenter.py`
  - `UNetSegmenter`: suporta ONNX/PyTorch, default `models/unet_tissue_segmentation.onnx`, com modo simulacao se artefato ausente.
- `src/diagnosis/two_stage_tissue_pipeline.py`
  - Pipeline de mascara de ferida + segmentacao tecidual.
- `src/diagnosis/etiology_classifier.py`
  - Classificador de etiologia.
- `src/diagnosis/wound_analyzer.py`
  - Orquestracao diagnostica.
- `src/diagnosis/clinical_ml.py`
  - Contrato clinico/ML e fallback.

### 2.3 Camada adicional multi-modelo Python

- `src/ai_layer/ensemble_orchestrator.py`
  - Combina EfficientNet/base REDISUS, DermaIntel, BiomedCLIP e sinais de segmentacao.
  - Calcula `confidence_entropy`, `confidence_margin`, concordancia e `needs_expert_review`.
- `src/ai_layer/dermaintel_classifier.py`
  - Hugging Face ViT: `PayamFard123/dermaintel-wound-classifier`.
- `src/ai_layer/biomedclip_analyzer.py`
  - BiomedCLIP: `microsoft/BiomedCLIP-PubMedBERT_256-vit_base_patch16_224`.
  - Fallback heuristico quando modelo indisponivel.
- `src/ai_layer/medsam_segmenter.py`
  - MedSAM/SAM com fallback GrabCut.
- `src/ai_layer/confidence_calibration.py`
  - Calibracao, thresholds, ECE, entropy, margin e filtro por confianca.

### 2.4 Treinamento, datasets, validacao e export

- `src/training/advanced_training.py`
- `src/training/ensemble_finetuning.py`
- `src/training/fine_tuning_guide.py`
- `src/training/medsam_finetuning.py`
- `src/training/prepare_wound_datasets.py`
- `src/training/pressure_injury_dataset.py`
- `src/training/pressure_injury_stage_training.py`
- `src/training/segmentation_dataset.py`
- `src/training/segmentation_metrics.py`
- `src/training/tissue_segmentation_training.py`
- `src/training/train_body_part_detector.py`
- `src/training/wound_classifier_training.py`
- `src/training/wound_mask_training.py`
- `ml/scripts/prepare_dataset.py`
- `ml/scripts/prepare_co2wounds_v2.py`
- `ml/scripts/train_segmentation.py`
- `ml/scripts/evaluate_segmentation.py`
- `ml/scripts/infer_single_image.py`
- `ml/scripts/export_model.py`
- `ml/scripts/validate_masks.py`
- `scripts/preprocess_dataset.py`
- `scripts/medical_augmentation.py`
- `scripts/prepare_yolo_dataset.py`
- `scripts/train_yolo_wound.py`
- `scripts/train_wound_detector.py`
- `scripts/train_unet_tissue.py`
- `scripts/train_resnet50_two_stage.py`
- `scripts/train_pressure_injury_classifier.py`
- `scripts/train_improved.py`
- `scripts/train_fast.py`
- `scripts/train_s1_quick.py`
- `scripts/calibrate_pressure_injury_stage_classifier.py`
- `scripts/validate_heal_analyzer_piid.py`
- `scripts/validate_medetec_pressure_resolution.py`
- `scripts/validate_medetec_pressure_multiresolution.py`
- `scripts/evaluate_spatial_resolution_piid.py`
- `scripts/convert_keras_to_onnx.py`
- `scripts/download_model.py`
- `scripts/finalize_body_part_model.py`
- `scripts/setup_dataset_structure.py`
- `scripts/run_training.py`
- `scripts/run_train.bat`
- `scripts/run_preprocessing_experiments.py`
- `scripts/test_dl_integration.py`
- `scripts/test_training_components.py`
- `scripts/test_unet_ready.py`

### 2.5 Exemplos e demos

- `examples/visual_wound_test.py`
- `examples/test_wound_synthetic.py`
- `examples/realtime_detection_demo.py`
- `examples/ensemble_analysis_demo.py`
- `examples/synthetic_wound.jpg`
- `main.py`
- `realtime_app.py`
- `heal_analyzer.py`
- `heal_model_standalone.py`
- `build_standalone.py`
- `heal_platform.py`
- `heal_web_launcher.py`
- `retrain.py`

### 2.6 Testes Python relacionados

- `tests/test_clinical_wound_analyzer_core.py`
- `tests/test_wound_detector_cv.py`
- `tests/test_wound_classifier_cv.py`
- `tests/test_tissue_analyzer.py`
- `tests/test_two_stage_tissue_pipeline.py`
- `tests/test_pressure_injury_stage_classifier.py`
- `tests/test_pressure_injury_dataset.py`
- `tests/test_segmentation_dataset.py`
- `tests/test_segmentation_metrics.py`
- `tests/test_tissue_segmentation_training.py`
- `tests/test_preprocessing_filters.py`
- `tests/test_image_recognition.py`
- `tests/test_heal_model_standalone.py`
- `tests/test_workflow_headless_adapter.py`
- `tests/test_integration_analyze_route.py`
- `tests/test_wound_progression.py`

### 2.7 Documentos, model cards e notebooks

- `docs/data/dataset-card.md`
- `ml/benchmarks/baseline_report.md`
- `ml/model_cards/wound_classifier_v3.md`
- `ml/model_cards/pressure_injury_stage_classifier.md`
- `ml/registry/models.yaml`
- `ml/configs/segmentation_baseline.yaml`
- `ml/configs/co2wounds_v2_segmentation.yaml`
- `ml/notebooks/README.md`
- `docs/HEAL_ANALYZER_AI_STRATEGY.md`
- `docs/HEAL_ANALYZER_TRAINING_STRATEGY.md`
- `docs/experimentos/pre_processamento_opencv_ia.md`
- `docs/research/training-guide.md`
- `docs/research/metrics-current-state.md`

Nao encontrei arquivos `.ipynb` versionados; ha apenas `ml/notebooks/README.md`.

## 3. Estado dos artefatos de modelo

Arquivos fisicos encontrados em `models/`:

- `models/mediapipe/blaze_face_short_range.tflite`
- `models/mediapipe/hand_landmarker.task`
- `models/mediapipe/pose_landmarker_lite.task`
- `models/pressure_injury_stage_classifier/model_metadata.json`
- `models/pressure_injury_stage_classifier/pressure_injury_stage_resnet50.pth`
- `models/pressure_injury_stage_classifier/training_history.json`

Arquivos citados, mas nao encontrados versionados no repositorio:

- `models/wound_classifier_v2/wound_classifier_v2_traced.pt`
- `models/wound_classifier_v2/wound_classifier_v2_full.pt`
- `models/wound_classifier_v2/wound_classifier_v2.pt`
- `models/wound_classifier_v2/modelo_estagio1.pth`
- `models/wound_classifier_v2/modelo_estagio2_semAugmentation.pth`
- `models/yolo_wound_nano.onnx`
- `models/unet_tissue_segmentation.onnx`
- `models/efficientnet_etiology.onnx`
- `models/wound_mask_deeplabv3`
- `models/tissue_segmentation_deeplabv3`

Isto significa que varios caminhos de runtime caem em fallback, heuristica ou simplesmente ficam indisponiveis no clone atual.

## 4. Metricas e datasets documentados

Fontes:

- `ml/benchmarks/baseline_report.md`
- `ml/model_cards/wound_classifier_v3.md`
- `ml/model_cards/pressure_injury_stage_classifier.md`
- `docs/data/dataset-card.md`
- `ml/registry/models.yaml`

Metricas registradas:

- `wound_classifier_v1`: metrica `0.4426`, exploratorio, 24 classes.
- `wound_classifier_v2/v3`: accuracy `0.6025`, top-3 accuracy `0.8484`, validacao com `244` amostras, status experimental.
- YOLO detector: `mAP50 0.9912`, `mAP50-95 0.7654`, mas documentado como exploratorio e sem benchmark congelado.
- `PressureInjuryStageClassifier`: dataset PIID local com `1091` imagens; split `763` treino, `163` validacao, `165` teste; validation accuracy `0.7730`; test accuracy `0.7030`; stage accuracies: stage_1 `0.7143`, stage_2 `0.7021`, stage_3 `0.5476`, stage_4 `0.8537`.

Gaps documentados:

- Forte desequilibrio de classes.
- Dataset experimental, heterogeneo e nao multicentrico.
- Manifests oficiais de split ainda nao versionados em `data/manifests` (ha apenas README).
- Pesos principais de `wound_classifier_v2` nao estao no clone.
- Alguns ramos de DL citados usam fallback/simulacao sem artefatos.

## 5. Pipeline Python atual de visao computacional

Entrada principal:

- Backend Flask recebe imagem em `apps/api/routes/integration.py` na rota `POST /api/v1/analyze`.
- A imagem e validada por `packages/clinical_domain/validation.py::validate_and_sanitize_image_upload`.
- Formatos aceitos pelo backend: definidos em `ALLOWED_IMAGE_FORMATS`; validacao inclui PIL `verify`, `ImageOps.exif_transpose`, limites de bytes e megapixels, MIME/extensao coerentes.
- O backend converte PIL RGB para OpenCV BGR antes de chamar `ClinicalWoundAnalyzer`.

Fluxo de `ClinicalWoundAnalyzer.analyze`:

1. Valida `np.ndarray` BGR 3 canais.
2. Aplica mascara manual de ROI se fornecida; caso contrario detecta automaticamente.
3. Valida se a imagem tem caracteristicas de ferida.
4. Reduz imagens com maior lado acima de `1024`, mantendo proporcao.
5. Analisa iluminacao com `ImageEnhancer` e aplica correcoes automaticas quando necessario.
6. Detecta parte do corpo quando `BodyPartDetector` esta disponivel.
7. Cria mascara da ferida via ROI manual ou `WoundDetectorCV`.
8. Remove fundo cirurgico e fundo espacial.
9. Cria zonas: periferia, core e anel externo.
10. Segmenta tecidos via `_segment_clinical_v3`: HSV + LAB + textura + gradiente Scharr + exclusao de pele/fundo + zonas.
11. Produz percentuais de necrose, esfacelo, granulacao e epitelizacao.
12. Analisa bordas/perilesao.
13. Calcula `health_score`.
14. Calcula escalas clinicas PUSH/BWAT quando disponiveis.
15. Tenta predicao DL, ResNet50 two-stage e ensemble.
16. Retorna `ClinicalReport` com overlays e metadados.

Saida convertida para API:

- `packages/clinical_domain/workflow.py::build_headless_analyzer_result` transforma `ClinicalReport` em contrato com:
  - `contract_version`
  - `analysis_type`
  - `model_version`
  - `generated_at`
  - `patient_id`
  - `case_id`
  - `evaluation_id`
  - `inference`
  - `interpretation`
  - `metadata`
  - campos legados: `is_valid_wound`, `primary_tissue`, `tissues`, `border_analysis`, `wound_area_px`, `health_score`, `visuals`, `roi`, `rois`.

## 6. Pipeline TypeScript atual de visao computacional

Arquivos principais:

- `web/redisus-frontend/src/services/ai/woundAnalysisPipeline.ts`
- `web/redisus-frontend/src/services/ai/imageQualityService.ts`
- `web/redisus-frontend/src/services/ai/woundInputValidationService.ts`
- `web/redisus-frontend/src/services/ai/woundDetectionService.ts`
- `web/redisus-frontend/src/services/ai/woundSegmentationService.ts`
- `web/redisus-frontend/src/services/ai/tissueClassificationService.ts`
- `web/redisus-frontend/src/services/ai/roiCropService.ts`
- `web/redisus-frontend/src/services/ai/heal-analyzer-service.ts`

Estado real:

- Roda no browser usando canvas/ImageData.
- Exige ROI manual.
- Valida qualidade de imagem por brilho, contraste e sharpness.
- Valida ROI por ratios RGB/HSV, textura e area.
- Segmentacao atual usa mascara manual e heuristicas de cor para percentuais teciduais.
- `tissueClassificationService.ts` usa resultado validado do backend Python quando `VITE_HEAL_ANALYZER_ENABLE_SERVER_INFERENCE=true`; caso contrario usa percentuais calculados no frontend.
- As mensagens em `woundSegmentationService.ts` e `tissueClassificationService.ts` dizem "rede neural em TypeScript", mas o codigo encontrado e heuristico/canvas, sem ONNX Runtime ou TensorFlow.js.

Conclusao: ja existe modulo TS de analise assistiva, mas nao e uma migracao numericamente equivalente do Python. Para cumprir o prompt seria necessario escolher/exportar um modelo real (provavelmente ONNX, dada a presenca de `onnxruntime` e scripts de export), adicionar runtime JS e testes de paridade.

## 7. Pontos atuais de IA generativa

### 7.1 Backend Python - Gemini direto

Arquivo: `apps/api/routes/integration.py`

Funcoes:

- `_get_active_keys()`
  - Le `GEMINI_API_KEY_1..5`, `GOOGLE_AI_API_KEY`, `GEMINI_API_KEY`, `GOOGLE_GENAI_API_KEY`.
- `_call_gemini_with_key(api_key, prompt, system_instruction)`
  - Usa `google.generativeai`.
  - Modelo hardcoded: `gemini-2.0-flash`.
- `_call_gemini_vision(image_bytes, prompt)`
  - Abre imagem com PIL e chama `model.generate_content([prompt, pil_image])`.
  - Modelo hardcoded: `gemini-2.0-flash`.
- `_generate_best_response(prompt, system_instruction, is_json=False)`
  - Chama todas as chaves Gemini configuradas e escolhe por heuristica de score.
- `_init_gemini()`
  - Inicializa singleton Gemini com `gemini-2.0-flash`.

Rotas:

- `POST /api/v1/analyze`
  - Usa Gemini Vision somente como fallback quando `ClinicalWoundAnalyzer` local nao esta disponivel.
  - Gera JSON de analise/parecer visual diretamente via prompt multimodal.
- `POST /api/v1/image-labels`
  - Usa Gemini Vision para labels de imagem.
- `POST /api/v1/ai-chat`
  - Usa Gemini para chat, com fallback em `_rule_based_response`.
- `GET /api/v1/ai-chat/history`
- `GET /api/v1/ai-chat/history/<conversation_id>`
- `DELETE /api/v1/ai-chat/history/<conversation_id>`

Persistencia do chat backend:

- Firestore collection `ai_conversations`.
- Subcollection `messages`.
- Persistem `role`, `content`, `timestamp`, `owner_uid`.
- Nao persiste modelo selecionado por usuario porque nao existe selecao.

### 7.2 Frontend React - Groq direto no client e Gemini via backend

Arquivos:

- `web/redisus-frontend/src/features/chat/ChatPage.tsx`
  - Chama Groq direto em `https://api.groq.com/openai/v1/chat/completions`.
  - API key: `VITE_GROQ_API_KEY`.
  - Modelo default: `VITE_AI_MODEL || 'llama-3.1-8b-instant'`.
  - Tambem chama `/api/clinical/ai-chat` (proxy Vite para Flask) e escolhe a melhor resposta entre Groq e Gemini por `scoreResponse`.
  - Historico local em `localStorage` (`heal-chat-history`).
- `web/redisus-frontend/src/features/reports/ReportsPage.tsx`
  - Gera "Analise e Parecer de IA Generativa".
  - Chama Groq direto e Gemini via `/api/clinical/ai-chat`.
  - Escolhe melhor resposta por score.
  - Inclui texto no LaTeX/PDF gerado.
  - Nao incorpora analise de imagem neural estruturada antes do parecer, exceto dados clinicos textuais da avaliacao.
- `web/redisus-frontend/src/components/reports/ComparisonView.tsx`
  - Gera parecer comparativo evolutivo.
  - Chama Groq direto no cliente.
- `web/redisus-frontend/src/components/heal-analyzer/analyzer-workbench.tsx`
  - Depois de `ClinicalResultPanel`, gera "Parecer Clinico Generativo".
  - Chama Groq direto no cliente.
  - Usa resultado tecnico do analyzer como texto estruturado, mas nao passa a imagem multimodalmente.

Divergencia de seguranca:

- `VITE_GROQ_API_KEY` e lido no frontend. Variaveis `VITE_*` sao expostas no bundle do cliente. Isto conflita com o requisito "chaves de API apenas via variaveis de ambiente/secret manager; nunca no client-side em texto puro".

## 8. Chat assistente existente

Frontend:

- Rota: `/chat` em `web/redisus-frontend/src/app/router.tsx`.
- UI: `web/redisus-frontend/src/features/chat/ChatPage.tsx`.
- Contexto local usado no prompt:
  - pacientes via `subscribePatients`;
  - agenda via `subscribeAppointments`;
  - avaliacoes via `listEvaluations`;
  - historico recente da conversa em `messages`.
- Provedores atuais:
  - Groq direto no browser;
  - Gemini via backend `/api/clinical/ai-chat`;
  - fallback local/rules.
- Troca de modelo: inexistente. O texto da UI informa "Groq / Gemini (Adaptativo)".
- Historico:
  - frontend salva sessoes em `localStorage`;
  - backend tambem salva conversas em Firestore quando chamado.

Backend:

- Rota real: `POST /api/v1/ai-chat`.
- Proxy Vite: `/api/clinical/ai-chat` -> `http://127.0.0.1:5000/api/v1/ai-chat`.
- Payload validado por `AIChatPayload` em `packages/clinical_domain/validation.py`.
- Campo `context` suporta apenas `patient_id`.
- Nao ha suporte a imagens no chat atual.

## 9. Geração de parecer/laudo/relatorio

Pontos encontrados:

- `web/redisus-frontend/src/features/reports/ReportsPage.tsx`
  - Gera parecer textual de IA para uma avaliacao.
  - Gera LaTeX e chama backend `/api/clinical/generate-pdf`.
  - O parecer nao e salvo como entidade auditavel separada; fica em estado React e no PDF.
- `web/redisus-frontend/src/components/reports/ComparisonView.tsx`
  - Gera parecer evolutivo comparativo.
  - Nao salva modelo usado.
- `web/redisus-frontend/src/components/heal-analyzer/analyzer-workbench.tsx`
  - Gera parecer generativo a partir de resultado tecnico do analyzer.
  - Nao salva modelo usado.
- `apps/api/routes/integration.py::analyze_image`
  - Quando o analyzer local falha/nao carrega, usa Gemini Vision para gerar todo o JSON da analise.
  - Este e um fluxo multimodal direto, mas apenas fallback.
- `apps/api/routes/integration.py::generate_pdf`
  - Gera PDF a partir de LaTeX recebido.

Nao encontrei:

- seletor de modelo nas telas de parecer;
- persistencia do modelo usado junto ao parecer;
- camada unica `generativeService`;
- auditoria de custo/modelo centralizada;
- fluxo padrao "CV estruturado + imagem + contexto clinico -> provider selecionado" para parecer.

## 10. Recebimento, armazenamento e processamento de imagens

### 10.1 Frontend - avaliacao clinica

Arquivos:

- `web/redisus-frontend/src/features/evaluations/EvaluationForm.tsx`
- `web/redisus-frontend/src/features/evaluations/evaluationService.ts`
- `web/redisus-frontend/src/lib/validators.ts`
- `web/redisus-frontend/src/lib/constants.ts`
- `web/redisus-frontend/src/lib/types.ts`
- `web/redisus-frontend/src/lib/supabase.ts`

Fluxo:

1. UI aceita `<input type="file" accept="image/*" multiple>`.
2. `validateImageFile(file)` verifica apenas `file.type.startsWith('image/')` e tamanho.
3. Limite default: `VITE_MAX_IMAGE_UPLOAD_MB || 10`.
4. Cria `ImageDraft` com preview local e ROIs.
5. Upload em `uploadEvaluationImages` para Supabase Storage:
   - bucket: `wound-images`;
   - path: `${uid}/${generateUUID()}.${ext}`;
   - `contentType: image.file.type`;
   - `upsert: false`.
6. Obtem URL publica via `getPublicUrl`.
7. Persiste em tabela Supabase `evaluations`, campo `images`, uma lista de `WoundImage` com:
   - `id`, `storagePath`, `downloadURL`, `fileName`, `contentType`, `size`, `rois`, `uploadedAt`.

Observacao: existem `storage.rules` Firebase e `web/redisus-frontend/storage.rules`, mas o fluxo de avaliacao inspecionado usa Supabase Storage, nao Firebase Storage.

### 10.2 Backend - analise HEAL Analyzer

Arquivo: `apps/api/routes/integration.py`

Rota:

- `POST /api/v1/analyze`
  - multipart field obrigatorio: `image`;
  - campos permitidos: `patient_id`, `roi_payload`;
  - valida acesso ao paciente se `patient_id` informado;
  - sanitiza imagem;
  - converte para OpenCV BGR;
  - aplica ROI manual quando enviada;
  - roda `ClinicalWoundAnalyzer`.

Validacao backend:

- `packages/clinical_domain/validation.py::validate_and_sanitize_image_upload`
  - rejeita upload vazio;
  - limite de bytes por `REDISUS_MAX_UPLOAD_BYTES` (default 10 MB);
  - `PIL.Image.verify`;
  - `ImageOps.exif_transpose`;
  - formatos aceitos por `ALLOWED_IMAGE_FORMATS`;
  - valida dimensoes e megapixels (`REDISUS_MAX_IMAGE_MEGAPIXELS`, default 12);
  - compara MIME declarado com conteudo;
  - compara extensao com formato detectado;
  - regrava imagem sanitizada.

### 10.3 Formatos aceitos

- Frontend: qualquer `image/*`, limitado por tamanho.
- Backend: formatos em `ALLOWED_IMAGE_FORMATS` (validado por PIL). A busca confirmou uso de JPEG/PNG/WEBP/TIFF/BMP em scripts e frontend, mas o conjunto exato fica no dicionario do arquivo de validacao.

## 11. Dependencias atuais

### 11.1 Python raiz - `requirements.txt`

Principais:

- `numpy>=1.24.0`
- `opencv-python>=4.8.0`
- `Pillow>=10.0.0`
- `torch>=2.0.0`
- `torchvision>=0.15.0`
- `onnxruntime>=1.16.0`
- `onnxruntime-gpu>=1.16.0`
- `ultralytics>=8.0.0`
- `segmentation-models-pytorch>=0.3.3`
- `scipy>=1.11.0`
- `scikit-image>=0.21.0`
- `albumentations>=1.3.0`
- `matplotlib>=3.7.0`
- `pydantic>=2.0.0`
- `python-dotenv>=1.0.0`
- `loguru>=0.7.0`
- `pytest>=7.4.0`
- `pytest-cov>=4.1.0`
- `reportlab>=4.0.0`
- `fpdf2>=2.7.0`
- `tensorflow>=2.13.0`
- `tf2onnx>=1.16.0`
- `onnx>=1.14.0`
- `requests>=2.31.0`
- `fhir.resources>=7.0.0`
- `google-auth>=2.0.0`
- `flask>=3.0.0`
- `flask-cors>=4.0.1`
- `PyQt6>=6.5.0`
- `mediapipe>=0.10.0`
- `transformers>=4.35.0`
- `open_clip_torch>=2.23.0`

### 11.2 Backend - `backend/requirements.txt`

- `firebase-admin>=6.0.0`
- `flask>=3.0.0`
- `flask-cors>=5.0.0`
- `python-dotenv>=1.0.0`
- `google-generativeai>=0.3.0`
- `Pillow>=10.0.0`

### 11.3 Frontend - `web/redisus-frontend/package.json`

Runtime:

- `@headlessui/react:^2.2.10`
- `@hookform/resolvers:^3.10.0`
- `@supabase/supabase-js:^2.110.0`
- `date-fns:^3.6.0`
- `firebase:^12.12.1`
- `lucide-react:^0.468.0`
- `react:^18.3.1`
- `react-dom:^18.3.1`
- `react-hook-form:^7.53.2`
- `react-router-dom:^6.28.0`
- `zod:^3.24.1`

Dev/test:

- `typescript:^5.7.2`
- `vite:^6.0.3`
- `vitest:^2.1.8`
- `@playwright/test:^1.49.1`
- `firebase-tools:^15.15.0`
- `tailwindcss:^3.4.17`

Nao ha hoje dependencias TS para:

- `onnxruntime-node`
- `onnxruntime-web`
- `@tensorflow/tfjs`
- `sharp`
- SDKs server-side de OpenAI/Anthropic/Gemini no frontend package.

## 12. Perguntas obrigatorias respondidas

### Quais provedores de IA generativa ja sao usados hoje?

- Backend: Google Gemini via `google-generativeai`, modelo hardcoded `gemini-2.0-flash`.
- Frontend: Groq API compativel com OpenAI Chat Completions, modelo default `llama-3.1-8b-instant`, configurado por `VITE_AI_MODEL`.
- Nao encontrei uso atual de OpenAI direto nem Anthropic.

### O pipeline de visao computacional hoje e servico Python separado ou embutido no backend?

- Ele e codigo Python embutido/importado pelo backend Flask (`apps/api/routes/integration.py` importa `src.processing.clinical_wound_analyzer_core.ClinicalWoundAnalyzer`).
- Tambem ha apps/demos desktop/standalone.
- O frontend pode chamar esse backend por `/api/clinical/analyze`, proxy Vite para `/api/v1/analyze`.
- Nao ha microservico Python separado dedicado apenas a CV.

### O modelo de CV e proprietario/treinado do zero ou pre-treinado ajustado?

Estado misto:

- Pipeline principal de segmentacao tecidual e majoritariamente OpenCV/heuristico clinico.
- `PressureInjuryStageClassifier` e ResNet50 treinado localmente para PIID, com pesos presentes.
- `TwoStageWoundClassifier` e ResNet50 two-stage, mas pesos citados nao estao presentes.
- `WoundClassifier_v3` e PyTorch experimental, mas artefato principal nao esta presente.
- Ensemble usa modelos pre-treinados externos/fine-tuning potencial: DermaIntel, BiomedCLIP, MedSAM; disponibilidade depende de downloads/checkpoints externos.
- YOLO/U-Net/DeepLab sao citados em scripts/documentos, mas artefatos release nao estao versionados.

Isso favorece ONNX para modelos PyTorch presentes/futuros, mas a paridade completa exige congelar quais artefatos sao o alvo.

### Onde o chat assistente roda hoje?

- UI roda no frontend React em `web/redisus-frontend/src/features/chat/ChatPage.tsx`.
- Faz chamadas generativas tanto client-side (Groq direto) quanto backend (`/api/clinical/ai-chat` -> Flask/Gemini).
- Historico existe em `localStorage` no frontend e em Firestore no backend quando a rota backend e usada.

### Existe requisito de compliance/LGPD que restrinja enviar imagens a provedores externos?

- Ha documentacao de LGPD em `docs/compliance/LGPD.md` e regras de seguranca em `docs/security/*`.
- O codigo atual ja envia imagem a Gemini Vision como fallback na rota `/api/v1/analyze` se o analyzer local esta indisponivel.
- Nao encontrei uma decisao explicita permitindo multi-provider externo com imagens em todos os fluxos.
- Portanto, antes de habilitar seletor multimodal para provedores externos, e necessario confirmar a politica LGPD/consentimento/auditoria.

## 13. Divergencias e bloqueios antes de implementar

1. O prompt pede migrar a camada de IA/CV para TypeScript sem Python paralelo, mas o produto atual depende de Flask/Python para o pipeline validado; o TS existente e browser/heuristico, nao paridade do Python.
2. Nao ha artefatos ONNX/TF.js versionados para o pipeline completo. O unico peso CV relevante presente e `pressure_injury_stage_resnet50.pth`.
3. Parte do pipeline Python e heuristica/OpenCV, nao "modelo neural" exportavel diretamente para ONNX.
4. As chamadas Groq atuais usam `VITE_GROQ_API_KEY` no frontend, expondo chave no cliente. Isso deve ser removido/centralizado no backend antes de adicionar providers.
5. Gemini Vision ja recebe imagem no fallback backend, mas a politica LGPD para envio multimodal a multiplos providers nao esta explicitamente aprovada no repo.
6. O README/.env usam varias variaveis `NEXT_PUBLIC_*`, enquanto o app Vite usa `VITE_*`; ha documentacao/config divergente.
7. O fluxo de relatorio/parecer nao persiste o parecer nem o modelo usado como entidade auditavel; apenas mostra em estado React/PDF.
8. O frontend salva imagens em Supabase Storage com URL publica (`getPublicUrl`), enquanto tambem ha Firebase Storage rules e docs Firebase. A estrategia oficial de storage precisa ser confirmada.
9. O chat hoje mistura historico local e backend; trocar modelo no meio de uma conversa precisara definir qual historico e fonte da verdade.
10. A migracao TS proposta precisa escolher alvo: Node server-side com `sharp`/`onnxruntime-node`, browser com `onnxruntime-web`, ou manter pipeline local Python ate paridade estar comprovada.

## 14. Recomendacao de proximo passo

Antes de alteracoes funcionais, recomendo confirmar estas decisoes:

- Provider generativo padrao inicial: manter Gemini backend, mover Groq para backend, ou adicionar OpenAI/Anthropic agora?
- Politica LGPD: imagens podem ser enviadas a provedores externos? Se sim, sob quais consentimentos/auditoria?
- Target da migracao CV TS: apenas `PressureInjuryStageClassifier` primeiro, ou todo `ClinicalWoundAnalyzer` heuristico tambem?
- Runtime TS: Node (`onnxruntime-node` + `sharp`) e preferivel para manter chaves/modelos fora do browser; browser so deveria rodar analise local quando os modelos forem publicos e leves.
- Storage oficial: Supabase Storage atual ou Firebase Storage?
- Persistencia de parecer: criar tabela/colecao propria ou anexar metadados no registro de avaliacao?

So depois dessas confirmacoes e seguro implementar as partes 1, 2 e 3 do prompt sem criar uma arquitetura paralela inconsistente com o estado real do repositorio.
