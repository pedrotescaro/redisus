"""
REDISUS - Sistema de Diagnóstico de Feridas
Aplicação Principal com Detecção em Tempo Real

Este módulo integra todas as camadas do sistema:
- Camada de Apresentação (UI/Visualização)
- Camada de Processamento (Detecção/Análise)
- Camada de Dados (Persistência/Cache)

Uso:
    python realtime_app.py --mode webcam
    python realtime_app.py --mode image --input foto.jpg
    python realtime_app.py --mode demo
"""
import argparse
import os
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any

import cv2
import numpy as np
from loguru import logger

from packages.shared.runtime import ensure_project_root_on_path

ensure_project_root_on_path()

# Importa módulos do projeto
from src.presentation.ui_renderer import UIRenderer, HUDPanel, AnalysisOverlay, UITheme
from src.presentation.visualization import WoundVisualization, ColorMaps
from src.presentation.window_manager import WindowManager, InteractiveOverlay

from src.processing.wound_detector_cv import WoundDetectorCV, DetectionResult, DetectionMethod
from src.processing.image_processor import ImageProcessor, PreprocessingPipeline
from src.processing.tissue_analyzer import TissueAnalyzerCV, TissueResult
from src.processing.wound_classifier_cv import WoundClassifierCV, ClassificationResult, WoundEtiology, ETIOLOGY_INFO

from src.data.database import Database, AnalysisRecord, PatientRecord
from src.data.export import ExportManager, ReportGenerator
from src.data.cache import FrameCache, ResultCache, compute_frame_hash


class RedisusRealtimeApp:
    """
    Aplicação principal do REDISUS com detecção em tempo real.
    
    Modos de operação:
    - webcam: Detecção em tempo real com análise sob demanda
    - image: Análise de imagem estática
    - demo: Demonstração com imagem sintética
    
    Arquitetura:
    ┌─────────────┐     ┌──────────────┐     ┌────────────┐
    │   Captura   │────►│ Processamento│────►│  Interface │
    │  (Webcam)   │     │  (OpenCV)    │     │   (HUD)    │
    └─────────────┘     └──────────────┘     └────────────┘
          │                   │                    │
          └───────────────────┼────────────────────┘
                              ▼
                      ┌──────────────┐
                      │    Dados     │
                      │  (SQLite)    │
                      └──────────────┘
    """
    
    def __init__(self):
        # Módulos
        self.window_manager: Optional[WindowManager] = None
        self.ui_renderer: Optional[UIRenderer] = None
        self.visualization: Optional[WoundVisualization] = None
        
        self.detector: Optional[WoundDetectorCV] = None
        self.tissue_analyzer: Optional[TissueAnalyzerCV] = None
        self.classifier: Optional[WoundClassifierCV] = None
        self.image_processor: Optional[ImageProcessor] = None

        # Backends de deep learning (opcionais)
        self._yolo_detector = None
        self._unet_segmenter = None
        self._use_yolo = False
        self._use_unet = False
        
        self.database: Optional[Database] = None
        self.export_manager: Optional[ExportManager] = None
        self.frame_cache: Optional[FrameCache] = None
        self.result_cache: Optional[ResultCache] = None
        
        # Estado
        self.running = False
        self.mode = "detection"  # "detection", "analysis", "review"
        self.current_patient_id = "default_patient"
        
        # Dados da sessão
        self.last_frame: Optional[np.ndarray] = None
        self.last_detections: List[DetectionResult] = []
        self.last_analysis: Optional[Dict] = None
        self.auto_capture = False
        self.auto_capture_frames = 0
        self.auto_capture_threshold = 0.8
        self.auto_capture_required_frames = 15
        
        # Configuração de logging
        self._setup_logging()
        
    def _setup_logging(self):
        """Configura sistema de logging"""
        logger.remove()
        logger.add(
            sys.stdout,
            format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
            level="INFO"
        )
        
        # Log em arquivo
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        logger.add(
            log_dir / "redisus_{time}.log",
            rotation="10 MB",
            level="DEBUG"
        )
        
    def initialize(self, mode: str = "webcam"):
        """
        Inicializa todos os módulos necessários.
        
        Args:
            mode: Modo de operação ("webcam", "image", "demo")
        """
        logger.info(f"Inicializando REDISUS no modo: {mode}")
        
        # Cria diretórios necessários
        for dir_path in ["output", "output/captures", "output/reports", "output/exports", "data"]:
            Path(dir_path).mkdir(parents=True, exist_ok=True)
            
        # === Camada de Apresentação ===
        self.window_manager = WindowManager()
        self.ui_renderer = UIRenderer(theme=UITheme.MEDICAL)
        self.visualization = WoundVisualization()
        
        # === Camada de Processamento ===
        # Tenta YOLOv8 primeiro, fallback para OpenCV
        yolo_model_path = Path("models/yolo_wound_nano.onnx")
        if yolo_model_path.exists():
            try:
                from src.detection.realtime_detector import YOLODetector
                from src.core.config import ModelConfig

                yolo_config = ModelConfig(
                    model_path=str(yolo_model_path),
                    input_size=(320, 320),
                    num_classes=1,
                    confidence_threshold=0.5,
                    device="cuda"
                )
                self._yolo_detector = YOLODetector(config=yolo_config, use_onnx=True)
                self._yolo_detector.load_model()
                self._yolo_detector.warmup()
                self._use_yolo = True
                logger.info("YOLOv8 detector carregado com sucesso (ONNX)")
            except Exception as e:
                logger.warning(f"Falha ao carregar YOLOv8: {e}. Usando OpenCV.")
                self._use_yolo = False

        # Detector OpenCV (sempre instanciado como fallback)
        self.detector = WoundDetectorCV(
            method=DetectionMethod.COMBINED,
            min_area=500,
            max_area=300000,
            confidence_threshold=0.35
        )
        self.detector.warmup()

        # Tenta U-Net para segmentacao, fallback para OpenCV
        unet_model_path = Path("models/unet_tissue_segmentation.onnx")
        if unet_model_path.exists():
            try:
                from src.diagnosis.tissue_segmenter import UNetSegmenter
                from src.core.config import ModelConfig

                unet_config = ModelConfig(
                    model_path=str(unet_model_path),
                    input_size=(512, 512),
                    num_classes=5,
                    confidence_threshold=0.5,
                    device="cuda"
                )
                self._unet_segmenter = UNetSegmenter(config=unet_config)
                self._unet_segmenter.load_model()
                self._use_unet = True
                logger.info("U-Net segmenter carregado com sucesso (ONNX)")
            except Exception as e:
                logger.warning(f"Falha ao carregar U-Net: {e}. Usando OpenCV.")
                self._use_unet = False

        # Analisador de tecidos OpenCV (sempre instanciado como fallback)
        self.tissue_analyzer = TissueAnalyzerCV()
        
        # Classificador
        # Por padrão usa classificação heurística (mais rápido)
        # O modelo Keras é opcional e pode ser ativado se necessário
        model_path = Path("models/wound_classifier/wound_classifier_final.keras")
        use_keras = False  # Desabilitado por padrão para inicialização rápida
        
        self.classifier = WoundClassifierCV(
            model_path=str(model_path) if model_path.exists() and use_keras else None,
            use_keras_model=use_keras
        )
        logger.info("Classificador inicializado (modo heurístico)")
        
        # Processador de imagens
        self.image_processor = ImageProcessor()
        
        # === Camada de Dados ===
        self.database = Database("data/redisus.db")
        self.export_manager = ExportManager()
        self.frame_cache = FrameCache(max_frames=60)
        self.result_cache = ResultCache(ttl_seconds=30)
        
        # Cria paciente padrão se não existir
        if not self.database.get_patient(self.current_patient_id):
            self.database.save_patient(PatientRecord(
                id=self.current_patient_id,
                name="Paciente Demonstração"
            ))
            
        logger.info("Inicialização completa")
        
    def run_webcam_mode(self, camera_id: int = 0):
        """
        Executa modo webcam com detecção em tempo real.
        
        Controles:
        - SPACE: Capturar e analisar
        - A: Toggle auto-capture
        - S: Salvar imagem
        - R: Gerar relatório
        - Q/ESC: Sair
        """
        logger.info("Iniciando modo webcam...")
        
        # Abre câmera
        cap = cv2.VideoCapture(camera_id)
        if not cap.isOpened():
            logger.error(f"Não foi possível abrir a câmera {camera_id}")
            return
            
        # Configura câmera
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        # Cria janela principal
        self.window_manager.create_window(
            "main",
            "REDISUS - Detecção de Feridas em Tempo Real",
            width=1280,
            height=720
        )
        
        # Configura bindings de teclas
        self._setup_key_bindings()
        
        self.running = True
        self.mode = "detection"
        
        # Variáveis de FPS
        fps_timer = time.time()
        fps_counter = 0
        current_fps = 0.0
        
        logger.info("Pressione SPACE para capturar, Q para sair")
        
        try:
            while self.running:
                ret, frame = cap.read()
                
                if not ret:
                    logger.warning("Falha ao ler frame")
                    time.sleep(0.01)
                    continue
                    
                self.last_frame = frame.copy()
                
                # Adiciona ao cache
                self.frame_cache.add(frame)
                
                # Processa frame
                output_frame = self._process_frame(frame)
                
                # Calcula FPS
                fps_counter += 1
                if time.time() - fps_timer >= 1.0:
                    current_fps = fps_counter
                    fps_counter = 0
                    fps_timer = time.time()
                    
                # Renderiza UI
                detections_dict = [
                    {
                        "bbox": det.bbox,
                        "confidence": det.confidence,
                        "type": det.wound_type,
                        "label": self._get_wound_label(det)
                    }
                    for det in self.last_detections
                ]
                
                extra_info = {
                    "Modo": "Auto" if self.auto_capture else "Manual",
                    "Detecções": len(self.last_detections)
                }
                
                if self.last_detections:
                    best_det = max(self.last_detections, key=lambda d: d.confidence)
                    extra_info["Melhor Conf."] = f"{best_det.confidence:.0%}"
                    
                rendered = self.ui_renderer.render_realtime_view(
                    output_frame,
                    detections_dict,
                    fps=current_fps,
                    mode=self.mode,
                    extra_info=extra_info
                )
                
                # Exibe
                self.window_manager.show("main", rendered)
                
                # Processa eventos
                key = self.window_manager.process_events(1)
                self._handle_key(key)
                
        except KeyboardInterrupt:
            logger.info("Interrompido pelo usuário")
            
        finally:
            cap.release()
            self.window_manager.cleanup()
            
    def _yolo_to_detection_result(self, detection, frame: np.ndarray) -> DetectionResult:
        """Converte Detection (YOLO) para DetectionResult (pipeline OpenCV)."""
        x1, y1, x2, y2 = detection.bbox
        h, w = frame.shape[:2]

        # Mascara simples a partir da bounding box
        mask = np.zeros((h, w), dtype=np.uint8)
        mask[max(0, y1):min(h, y2), max(0, x1):min(w, x2)] = 255

        return DetectionResult(
            bbox=detection.bbox,
            confidence=detection.confidence,
            mask=mask,
            contour=None,
            wound_type="wound",
            area_pixels=detection.area,
            center=detection.center,
            features={"backend": "yolo"}
        )

    def _process_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        Processa frame com detecção de feridas.
        
        Args:
            frame: Frame BGR
            
        Returns:
            Frame processado com anotações
        """
        output = frame.copy()

        # Detecta feridas (YOLO ou OpenCV)
        if self._use_yolo:
            yolo_detections = self._yolo_detector.detect(frame)
            self.last_detections = [
                self._yolo_to_detection_result(d, frame) for d in yolo_detections
            ]
        else:
            self.last_detections = self.detector.detect(frame)
        
        # Desenha detecções
        for det in self.last_detections:
            output = self.ui_renderer.overlay.draw_detection_box(
                output,
                bbox=det.bbox,
                label=self._get_wound_label(det),
                confidence=det.confidence,
                wound_type=det.wound_type
            )
            
        # Verifica auto-capture
        if self.auto_capture and self.last_detections:
            best_conf = max(d.confidence for d in self.last_detections)
            if best_conf >= self.auto_capture_threshold:
                self.auto_capture_frames += 1
                
                # Desenha indicador de progresso
                progress = self.auto_capture_frames / self.auto_capture_required_frames
                h = frame.shape[0]
                cv2.rectangle(output, (10, h - 50), (10 + int(200 * progress), h - 40), (0, 255, 0), -1)
                cv2.rectangle(output, (10, h - 50), (210, h - 40), (255, 255, 255), 1)
                cv2.putText(output, "Auto-captura...", (15, h - 55), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                
                if self.auto_capture_frames >= self.auto_capture_required_frames:
                    logger.info("Auto-capture ativado!")
                    self._capture_and_analyze()
                    self.auto_capture_frames = 0
            else:
                self.auto_capture_frames = max(0, self.auto_capture_frames - 1)
                
        return output
    
    def _get_wound_label(self, detection: DetectionResult) -> str:
        """Gera label para uma detecção"""
        wound_type = detection.wound_type
        
        # Traduz tipos conhecidos
        translations = {
            "wound": "Ferida",
            "granulating_wound": "Granulação",
            "necrotic_wound": "Necrótica",
            "infected_wound": "Infectada",
            "pressure_injury": "Pressão",
            "surgical_wound": "Cirúrgica"
        }
        
        return translations.get(wound_type, wound_type.replace("_", " ").title())

    def _health_from_segmentation(self, seg_result) -> float:
        """Calcula health score a partir da segmentacao U-Net."""
        pcts = seg_result.tissue_percentages
        granulation = pcts.get("Granulacao", pcts.get("Granulação", 0))
        necrosis = pcts.get("Necrose", 0)
        slough = pcts.get("Esfacelo", 0)

        positive = granulation * 1.0
        negative = necrosis * 1.5 + slough * 0.5
        score = 50 + (positive - negative) * 0.5
        return max(0.0, min(100.0, score))

    def _capture_and_analyze(self):
        """Captura snapshot e realiza análise completa"""
        if self.last_frame is None:
            logger.warning("Nenhum frame disponível para captura")
            return
            
        logger.info("Capturando e analisando...")
        
        frame = self.last_frame.copy()
        timestamp = datetime.now()
        
        # === Análise Completa ===
        
        # 1. Detecção (já temos)
        detections = self.last_detections.copy()
        
        if not detections:
            logger.warning("Nenhuma ferida detectada para análise")
            return
            
        # Pega maior detecção
        main_detection = max(detections, key=lambda d: d.area_pixels)
        
        # 2. Extrai ROI
        x1, y1, x2, y2 = main_detection.bbox
        roi = frame[y1:y2, x1:x2]
        
        # 3. Análise de tecidos (U-Net ou OpenCV)
        if self._use_unet:
            seg_result = self._unet_segmenter.segment(roi)
            tissue_result = TissueResult(
                tissue_mask=seg_result.mask,
                tissue_percentages=seg_result.tissue_percentages,
                dominant_tissue=max(
                    seg_result.tissue_percentages,
                    key=seg_result.tissue_percentages.get
                ) if seg_result.tissue_percentages else "Background",
                wound_area_pixels=seg_result.wound_area_pixels,
                color_map=seg_result.get_colored_mask(),
                health_score=self._health_from_segmentation(seg_result),
                features={"backend": "unet"}
            )
        else:
            tissue_result = self.tissue_analyzer.analyze(roi, main_detection.mask)
        
        # 4. Classificação de etiologia
        classification_result = self.classifier.classify(
            roi,
            tissue_percentages=tissue_result.tissue_percentages,
            wound_mask=main_detection.mask
        )
        
        # 5. Avaliação de qualidade
        quality = self.image_processor.assess_quality(roi)
        
        # === Monta resultado ===
        analysis_id = str(uuid.uuid4())[:8]
        
        self.last_analysis = {
            "id": analysis_id,
            "patient_id": self.current_patient_id,
            "timestamp": timestamp.isoformat(),
            "bbox": main_detection.bbox,
            "etiology": classification_result.name,
            "etiology_type": classification_result.etiology.value,
            "confidence": classification_result.confidence,
            "description": classification_result.description,
            "tissue_percentages": tissue_result.tissue_percentages,
            "health_score": tissue_result.health_score,
            "wound_area_pixels": main_detection.area_pixels,
            "needs_review": classification_result.needs_review,
            "quality_score": quality.quality_score,
            "quality_issues": quality.issues
        }
        
        # === Salva no banco ===
        # Salva imagem
        image_path = f"output/captures/capture_{analysis_id}.jpg"
        cv2.imwrite(image_path, frame)
        
        # Salva registro
        record = AnalysisRecord(
            id=analysis_id,
            patient_id=self.current_patient_id,
            timestamp=timestamp.isoformat(),
            image_path=image_path,
            etiology=classification_result.etiology.value,
            confidence=classification_result.confidence,
            tissue_percentages=tissue_result.tissue_percentages,
            health_score=tissue_result.health_score,
            wound_area_cm2=None,  # Precisaria de calibração
            recommendations=self._get_recommendations(classification_result, tissue_result)
        )
        self.database.save_analysis(record)
        
        # === Exibe resultado ===
        self._show_analysis_result(frame, self.last_analysis, tissue_result.color_map)
        
        logger.info(f"Análise completa - Etiologia: {classification_result.name} ({classification_result.confidence:.1%})")
        
    def _show_analysis_result(
        self,
        frame: np.ndarray,
        analysis: Dict,
        tissue_color_map: np.ndarray
    ):
        """Exibe resultado da análise em nova janela"""
        # Cria dashboard
        h, w = frame.shape[:2]
        
        # Redimensiona mapa de tecidos
        x1, y1, x2, y2 = analysis["bbox"]
        roi = frame[y1:y2, x1:x2]
        
        # Cria visualização
        tissue_overlay = roi.copy()
        if tissue_color_map.shape[:2] == roi.shape[:2]:
            cv2.addWeighted(tissue_color_map, 0.5, tissue_overlay, 0.5, 0, tissue_overlay)
        else:
            tissue_color_map_resized = cv2.resize(tissue_color_map, (roi.shape[1], roi.shape[0]))
            cv2.addWeighted(tissue_color_map_resized, 0.5, tissue_overlay, 0.5, 0, tissue_overlay)
            
        # Cria canvas
        canvas_width = w + 400
        canvas = np.zeros((max(h, 500), canvas_width, 3), dtype=np.uint8)
        canvas[:] = (30, 30, 30)
        
        # Imagem original com bbox
        frame_annotated = self.ui_renderer.overlay.draw_detection_box(
            frame.copy(),
            bbox=analysis["bbox"],
            label=analysis["etiology"],
            confidence=analysis["confidence"],
            wound_type=analysis["etiology_type"]
        )
        canvas[:h, :w] = frame_annotated
        
        # Painel lateral
        self._draw_analysis_panel(canvas, analysis, x_start=w + 20)
        
        # Cria/atualiza janela de análise
        if "analysis" not in self.window_manager._windows:
            self.window_manager.create_window(
                "analysis",
                "REDISUS - Resultado da Análise",
                width=canvas_width,
                height=max(h, 500)
            )
            
        self.window_manager.show("analysis", canvas)
        
        # Imprime no console
        self._print_analysis_summary(analysis)
        
    def _draw_analysis_panel(self, canvas: np.ndarray, analysis: Dict, x_start: int):
        """Desenha painel de análise no canvas"""
        y = 30
        font = cv2.FONT_HERSHEY_SIMPLEX
        
        # Título
        cv2.putText(canvas, "RESULTADO DA ANÁLISE", (x_start, y), font, 0.7, (0, 200, 150), 2)
        y += 40
        
        # Etiologia
        cv2.putText(canvas, "Etiologia:", (x_start, y), font, 0.5, (150, 150, 150), 1)
        y += 25
        cv2.putText(canvas, analysis["etiology"], (x_start, y), font, 0.7, (255, 255, 255), 1)
        y += 25
        cv2.putText(canvas, f"Confiança: {analysis['confidence']:.1%}", (x_start, y), font, 0.5, (200, 200, 200), 1)
        y += 35
        
        # Descrição
        cv2.putText(canvas, "Descrição:", (x_start, y), font, 0.5, (150, 150, 150), 1)
        y += 20
        
        # Quebra descrição em linhas
        description = analysis.get("description", "")
        words = description.split()
        line = ""
        for word in words:
            if len(line + word) < 35:
                line += word + " "
            else:
                cv2.putText(canvas, line.strip(), (x_start, y), font, 0.4, (200, 200, 200), 1)
                y += 18
                line = word + " "
        if line:
            cv2.putText(canvas, line.strip(), (x_start, y), font, 0.4, (200, 200, 200), 1)
            y += 25
            
        # Separador
        y += 10
        cv2.line(canvas, (x_start, y), (x_start + 350, y), (80, 80, 80), 1)
        y += 20
        
        # Score de saúde
        health_score = analysis.get("health_score", 0)
        score_color = (0, 200, 0) if health_score >= 60 else ((0, 200, 255) if health_score >= 40 else (0, 0, 255))
        cv2.putText(canvas, f"Score de Saúde: {health_score:.0f}/100", (x_start, y), font, 0.6, score_color, 1)
        y += 35
        
        # Composição tecidual
        cv2.putText(canvas, "Composição Tecidual:", (x_start, y), font, 0.5, (150, 150, 150), 1)
        y += 25
        
        tissue_colors = {
            "granulation": (60, 60, 220),
            "slough": (80, 220, 220),
            "necrosis": (50, 50, 50),
            "epithelialization": (200, 180, 255),
            "fibrin": (100, 200, 250)
        }
        
        for tissue, percentage in sorted(analysis.get("tissue_percentages", {}).items(), key=lambda x: -x[1]):
            if percentage > 1:
                color = tissue_colors.get(tissue, (150, 150, 150))
                
                # Barra
                bar_width = int(percentage * 2)
                cv2.rectangle(canvas, (x_start, y - 8), (x_start + bar_width, y + 5), color, -1)
                cv2.rectangle(canvas, (x_start, y - 8), (x_start + 200, y + 5), (80, 80, 80), 1)
                
                # Texto
                cv2.putText(canvas, f"{tissue}: {percentage:.1f}%", (x_start + 210, y), font, 0.4, (200, 200, 200), 1)
                y += 22
                
        # Aviso de revisão
        if analysis.get("needs_review", False):
            y += 20
            cv2.putText(canvas, "⚠ Requer revisão por especialista", (x_start, y), font, 0.5, (0, 165, 255), 1)
            
        # Qualidade da imagem
        quality_issues = analysis.get("quality_issues", [])
        if quality_issues:
            y += 30
            cv2.putText(canvas, "Avisos de qualidade:", (x_start, y), font, 0.45, (150, 150, 150), 1)
            for issue in quality_issues[:3]:
                y += 18
                cv2.putText(canvas, f"• {issue}", (x_start + 10, y), font, 0.4, (255, 165, 0), 1)
                
    def _print_analysis_summary(self, analysis: Dict):
        """Imprime resumo da análise no console"""
        print("\n" + "=" * 60)
        print("REDISUS - RESULTADO DA ANÁLISE")
        print("=" * 60)
        print(f"\n📋 Etiologia: {analysis['etiology']}")
        print(f"   Confiança: {analysis['confidence']:.1%}")
        print(f"\n📝 {analysis.get('description', '')}")
        print(f"\n💊 Score de Saúde: {analysis.get('health_score', 0):.0f}/100")
        
        print("\n🔬 Composição Tecidual:")
        for tissue, pct in sorted(analysis.get("tissue_percentages", {}).items(), key=lambda x: -x[1]):
            if pct > 1:
                bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
                print(f"   {tissue:15} [{bar}] {pct:.1f}%")
                
        if analysis.get("needs_review"):
            print("\n⚠️  ATENÇÃO: Esta análise requer revisão por especialista")
            
        print("=" * 60 + "\n")
        
    def _get_recommendations(
        self,
        classification: ClassificationResult,
        tissue: TissueResult
    ) -> List[str]:
        """Gera recomendações baseadas na análise"""
        recommendations = []
        
        # Baseado na etiologia
        if classification.etiology == WoundEtiology.VENOUS_ULCER:
            recommendations.append("Considerar terapia compressiva")
            recommendations.append("Avaliar necessidade de elevação de membros")
        elif classification.etiology == WoundEtiology.PRESSURE_INJURY:
            recommendations.append("Reposicionar paciente frequentemente")
            recommendations.append("Avaliar superfícies de suporte")
        elif classification.etiology == WoundEtiology.DIABETIC_FOOT:
            recommendations.append("Controlar glicemia")
            recommendations.append("Avaliar calçados e órteses")
            
        # Baseado nos tecidos
        if tissue.tissue_percentages.get("necrosis", 0) > 20:
            recommendations.append("Considerar desbridamento do tecido necrótico")
        if tissue.tissue_percentages.get("slough", 0) > 30:
            recommendations.append("Avaliar necessidade de desbridamento do esfacelo")
        if tissue.tissue_percentages.get("granulation", 0) > 50:
            recommendations.append("Manter ambiente úmido para cicatrização")
            
        # Baseado no score de saúde
        if tissue.health_score < 30:
            recommendations.insert(0, "ATENÇÃO: Ferida em estado crítico - avaliar intervenção urgente")
            
        return recommendations
    
    def _setup_key_bindings(self):
        """Configura atalhos de teclado"""
        pass  # Tratados no _handle_key
        
    def _handle_key(self, key: int):
        """Processa tecla pressionada"""
        if key == -1:
            return
            
        if key == ord('q') or key == 27:  # Q ou ESC
            self.running = False
            
        elif key == ord(' '):  # SPACE - captura
            self._capture_and_analyze()
            
        elif key == ord('a'):  # A - toggle auto-capture
            self.auto_capture = not self.auto_capture
            self.auto_capture_frames = 0
            logger.info(f"Auto-capture: {'ON' if self.auto_capture else 'OFF'}")
            
        elif key == ord('s'):  # S - salvar imagem
            self._save_current_frame()
            
        elif key == ord('r'):  # R - gerar relatório
            self._generate_report()
            
        elif key == ord('h'):  # H - ajuda
            self._show_help()
            
    def _save_current_frame(self):
        """Salva frame atual"""
        if self.last_frame is None:
            return
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = f"output/captures/manual_{timestamp}.jpg"
        cv2.imwrite(filepath, self.last_frame)
        logger.info(f"Imagem salva: {filepath}")
        
    def _generate_report(self):
        """Gera relatório da última análise"""
        if self.last_analysis is None:
            logger.warning("Nenhuma análise disponível para relatório")
            return
            
        report_gen = ReportGenerator()
        files = report_gen.generate_analysis_report(
            self.last_analysis,
            self.last_frame
        )
        
        logger.info(f"Relatório gerado: {files}")
        
    def _show_help(self):
        """Mostra ajuda"""
        help_text = """
╔══════════════════════════════════════════════════════════╗
║               REDISUS - AJUDA                            ║
╠══════════════════════════════════════════════════════════╣
║  SPACE  - Capturar e analisar                           ║
║  A      - Toggle auto-capture                            ║
║  S      - Salvar imagem                                  ║
║  R      - Gerar relatório                                ║
║  H      - Mostrar esta ajuda                             ║
║  Q/ESC  - Sair                                           ║
╚══════════════════════════════════════════════════════════╝
"""
        print(help_text)
        
    def run_image_mode(self, image_path: str):
        """Analisa imagem estática"""
        logger.info(f"Analisando imagem: {image_path}")
        
        # Carrega imagem
        image = cv2.imread(image_path)
        if image is None:
            logger.error(f"Não foi possível carregar: {image_path}")
            return
            
        self.last_frame = image.copy()
        
        # Detecta e analisa
        self.last_detections = self.detector.detect(image)
        
        if not self.last_detections:
            logger.warning("Nenhuma ferida detectada na imagem")
            # Ainda assim mostra a imagem
            cv2.imshow("REDISUS - Imagem", image)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
            return
            
        # Realiza análise completa
        self._capture_and_analyze()
        
        # Aguarda
        logger.info("Pressione qualquer tecla para sair...")
        cv2.waitKey(0)
        cv2.destroyAllWindows()
        
    def run_demo_mode(self):
        """Executa demonstração com imagem sintética"""
        logger.info("Executando modo demonstração...")
        
        # Cria imagem de demonstração
        demo_image = self._create_demo_image()
        self.last_frame = demo_image.copy()
        
        # Detecta
        self.last_detections = self.detector.detect(demo_image)
        
        logger.info(f"Detecções na demo: {len(self.last_detections)}")
        
        if self.last_detections:
            self._capture_and_analyze()
        else:
            # Mostra imagem mesmo sem detecções
            annotated = demo_image.copy()
            cv2.putText(annotated, "DEMO - Nenhuma ferida detectada", (20, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            cv2.imshow("REDISUS - Demo", annotated)
            
        logger.info("Pressione qualquer tecla para sair...")
        cv2.waitKey(0)
        cv2.destroyAllWindows()
        
    def _create_demo_image(self) -> np.ndarray:
        """Cria imagem sintética de demonstração"""
        # Imagem base (pele)
        image = np.ones((600, 800, 3), dtype=np.uint8)
        image[:, :] = (180, 160, 150)  # Tom de pele em BGR
        
        # Adiciona textura
        noise = np.random.randint(-15, 15, image.shape, dtype=np.int16)
        image = np.clip(image.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        
        # Área da "ferida" (elipse no centro)
        center = (400, 300)
        axes = (100, 70)
        
        # Borda da ferida (eritema)
        cv2.ellipse(image, center, (axes[0] + 20, axes[1] + 20), 0, 0, 360, (130, 130, 180), -1)
        
        # Granulação (vermelho)
        cv2.ellipse(image, center, axes, 0, 0, 360, (70, 70, 200), -1)
        
        # Esfacelo (amarelo) - parte menor
        cv2.ellipse(image, (420, 310), (40, 25), 30, 0, 360, (90, 200, 220), -1)
        
        # Necrose (escuro) - pequena área
        cv2.ellipse(image, (370, 280), (20, 12), -20, 0, 360, (35, 35, 50), -1)
        
        # Suaviza bordas
        image = cv2.GaussianBlur(image, (7, 7), 0)
        
        # Adiciona texto
        cv2.putText(image, "IMAGEM DE DEMONSTRACAO", (20, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                   
        return image


def main():
    """Ponto de entrada principal"""
    parser = argparse.ArgumentParser(
        description="REDISUS - Sistema de Diagnóstico de Feridas em Tempo Real",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python realtime_app.py --mode webcam          # Inicia com webcam
  python realtime_app.py --mode webcam --camera 1  # Usa câmera secundária
  python realtime_app.py --mode image --input foto.jpg  # Analisa imagem
  python realtime_app.py --mode demo            # Executa demonstração

Controles (modo webcam):
  SPACE  - Capturar e analisar
  A      - Toggle auto-capture
  S      - Salvar imagem atual
  R      - Gerar relatório
  Q/ESC  - Sair
        """
    )
    
    parser.add_argument(
        "--mode",
        choices=["webcam", "image", "demo"],
        default="demo",
        help="Modo de operação (default: demo)"
    )
    
    parser.add_argument(
        "--input", "-i",
        type=str,
        help="Caminho da imagem para análise (modo image)"
    )
    
    parser.add_argument(
        "--camera", "-c",
        type=int,
        default=0,
        help="ID da câmera (default: 0)"
    )
    
    parser.add_argument(
        "--patient", "-p",
        type=str,
        default="default_patient",
        help="ID do paciente"
    )
    
    args = parser.parse_args()
    
    # Cria e executa aplicação
    app = RedisusRealtimeApp()
    app.current_patient_id = args.patient
    
    try:
        app.initialize(mode=args.mode)
        
        if args.mode == "webcam":
            app.run_webcam_mode(camera_id=args.camera)
            
        elif args.mode == "image":
            if not args.input:
                logger.error("Modo 'image' requer --input com caminho da imagem")
                sys.exit(1)
            if not Path(args.input).exists():
                logger.error(f"Arquivo não encontrado: {args.input}")
                sys.exit(1)
            app.run_image_mode(args.input)
            
        elif args.mode == "demo":
            app.run_demo_mode()
            
    except Exception as e:
        logger.exception(f"Erro fatal: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
