"""
REDISUS - Sistema de Diagnóstico de Feridas
Módulo de Detecção em Tempo Real

Este módulo implementa a detecção de feridas em tempo real usando
modelos leves otimizados para edge devices (YOLO Nano, MobileNet SSD).
"""
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple, Union

import cv2
import numpy as np
from loguru import logger

from ..core.config import ModelConfig, RealtimeConfig
from ..core.exceptions import InferenceError, ModelLoadError, ModelNotFoundError


@dataclass
class Detection:
    """Container para uma detecção de ferida"""
    bbox: Tuple[int, int, int, int]  # (x1, y1, x2, y2)
    confidence: float
    class_id: int = 0
    class_name: str = "wound"
    
    @property
    def x1(self) -> int:
        return self.bbox[0]
    
    @property
    def y1(self) -> int:
        return self.bbox[1]
    
    @property
    def x2(self) -> int:
        return self.bbox[2]
    
    @property
    def y2(self) -> int:
        return self.bbox[3]
    
    @property
    def width(self) -> int:
        return self.x2 - self.x1
    
    @property
    def height(self) -> int:
        return self.y2 - self.y1
    
    @property
    def center(self) -> Tuple[int, int]:
        return ((self.x1 + self.x2) // 2, (self.y1 + self.y2) // 2)
    
    @property
    def area(self) -> int:
        return self.width * self.height


class BaseDetector(ABC):
    """Classe base abstrata para detectores"""
    
    @abstractmethod
    def load_model(self, model_path: str):
        """Carrega o modelo"""
        pass
    
    @abstractmethod
    def detect(self, frame: np.ndarray) -> List[Detection]:
        """Realiza detecção em um frame"""
        pass
    
    @abstractmethod
    def warmup(self):
        """Aquece o modelo com inferências dummy"""
        pass


class YOLODetector(BaseDetector):
    """
    Detector baseado em YOLO (You Only Look Once).
    
    Suporta:
    - YOLOv8 Nano/Small via Ultralytics
    - ONNX Runtime para inferência otimizada
    - TensorFlow Lite para mobile
    
    Características:
    - Latência < 30ms em GPU
    - Latência < 100ms em CPU
    - Otimizado para single-class (ferida)
    """
    
    def __init__(
        self,
        model_path: Optional[str] = None,
        config: Optional[ModelConfig] = None,
        use_onnx: bool = True
    ):
        """
        Inicializa o detector YOLO.
        
        Args:
            model_path: Caminho para o modelo (.pt, .onnx, .tflite)
            config: Configurações do modelo
            use_onnx: Usar ONNX Runtime para inferência
        """
        self.config = config or ModelConfig(
            model_path=model_path or "models/yolo_wound_nano.onnx",
            input_size=(320, 320),
            num_classes=1,
            confidence_threshold=0.5
        )
        self.use_onnx = use_onnx
        
        self._model = None
        self._session = None  # ONNX Runtime session
        self._input_name = None
        self._output_names = None
        
        # Métricas
        self._inference_times: List[float] = []
        
    def load_model(self, model_path: Optional[str] = None):
        """
        Carrega o modelo de detecção.
        
        Args:
            model_path: Caminho alternativo para o modelo
        """
        path = Path(model_path or self.config.model_path)
        
        if not path.exists():
            # Tenta criar um modelo placeholder para demonstração
            logger.warning(
                f"Modelo não encontrado: {path}. "
                "Usando modo de simulação para demonstração."
            )
            self._model = "simulation"
            return
        
        suffix = path.suffix.lower()
        
        try:
            if suffix == ".onnx" and self.use_onnx:
                self._load_onnx(str(path))
            elif suffix == ".pt":
                self._load_ultralytics(str(path))
            elif suffix == ".tflite":
                self._load_tflite(str(path))
            else:
                raise ModelLoadError(f"Formato não suportado: {suffix}")
                
            logger.info(f"Modelo carregado: {path.name}")
            
        except Exception as e:
            raise ModelLoadError(f"Erro ao carregar modelo: {e}")
    
    def _load_onnx(self, model_path: str):
        """Carrega modelo ONNX"""
        try:
            import onnxruntime as ort
            
            # Configura providers (GPU > CPU)
            providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
            
            self._session = ort.InferenceSession(
                model_path,
                providers=providers
            )
            
            # Obtém nomes de entrada/saída
            self._input_name = self._session.get_inputs()[0].name
            self._output_names = [o.name for o in self._session.get_outputs()]
            
            logger.debug(f"ONNX carregado com providers: {self._session.get_providers()}")
            
        except ImportError:
            raise ModelLoadError("onnxruntime não instalado. Execute: pip install onnxruntime-gpu")
    
    def _load_ultralytics(self, model_path: str):
        """Carrega modelo Ultralytics YOLO"""
        try:
            from ultralytics import YOLO
            
            self._model = YOLO(model_path)
            logger.debug("Modelo Ultralytics YOLO carregado")
            
        except ImportError:
            raise ModelLoadError("ultralytics não instalado. Execute: pip install ultralytics")
    
    def _load_tflite(self, model_path: str):
        """Carrega modelo TensorFlow Lite"""
        try:
            # Tentar tflite_runtime primeiro (mais leve para dispositivos móveis)
            try:
                import tflite_runtime.interpreter as tflite  # type: ignore[import-not-found]
            except ImportError:
                # Fallback para tensorflow.lite (instalação completa)
                import tensorflow.lite as tflite
            
            self._model = tflite.Interpreter(model_path=model_path)
            self._model.allocate_tensors()
            
            logger.debug("Modelo TFLite carregado")
            
        except ImportError:
            raise ModelLoadError("TFLite não disponível. Instale tensorflow ou tflite-runtime")
    
    def warmup(self, iterations: int = 3):
        """
        Aquece o modelo com inferências dummy.
        
        Args:
            iterations: Número de iterações de aquecimento
        """
        logger.info(f"Aquecendo modelo ({iterations} iterações)...")
        
        dummy_input = np.random.randint(
            0, 255,
            (*self.config.input_size[::-1], 3),
            dtype=np.uint8
        )
        
        for _ in range(iterations):
            self.detect(dummy_input)
        
        logger.info("Modelo aquecido")
    
    def detect(self, frame: np.ndarray) -> List[Detection]:
        """
        Detecta feridas em um frame.
        
        Args:
            frame: Imagem BGR (numpy array)
            
        Returns:
            Lista de Detection objects
        """
        start_time = time.perf_counter()
        
        # Pré-processamento
        input_tensor = self._preprocess(frame)
        
        # Inferência
        if self._model == "simulation":
            # Modo simulação para demonstração
            detections = self._simulate_detection(frame)
        elif self._session is not None:
            detections = self._infer_onnx(input_tensor, frame.shape[:2])
        elif self._model is not None:
            detections = self._infer_ultralytics(frame)
        else:
            raise InferenceError("Modelo não carregado")
        
        # Métricas
        inference_time = (time.perf_counter() - start_time) * 1000
        self._inference_times.append(inference_time)
        if len(self._inference_times) > 100:
            self._inference_times.pop(0)
        
        return detections
    
    def _preprocess(self, frame: np.ndarray) -> np.ndarray:
        """Pré-processa frame para inferência"""
        # Resize
        input_h, input_w = self.config.input_size
        resized = cv2.resize(frame, (input_w, input_h))
        
        # BGR -> RGB
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        
        # Normaliza [0, 1]
        normalized = rgb.astype(np.float32) / 255.0
        
        # Adiciona dimensão batch: (H, W, C) -> (1, C, H, W)
        tensor = np.transpose(normalized, (2, 0, 1))
        tensor = np.expand_dims(tensor, axis=0)
        
        return tensor
    
    def _infer_onnx(
        self,
        input_tensor: np.ndarray,
        original_shape: Tuple[int, int]
    ) -> List[Detection]:
        """Inferência via ONNX Runtime"""
        outputs = self._session.run(
            self._output_names,
            {self._input_name: input_tensor}
        )
        
        # Parse outputs (formato YOLO)
        return self._parse_yolo_output(outputs[0], original_shape)
    
    def _infer_ultralytics(self, frame: np.ndarray) -> List[Detection]:
        """Inferência via Ultralytics"""
        results = self._model.predict(
            frame,
            conf=self.config.confidence_threshold,
            verbose=False
        )
        
        detections = []
        for result in results:
            boxes = result.boxes
            if boxes is not None:
                for box in boxes:
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    conf = float(box.conf[0])
                    cls = int(box.cls[0])
                    
                    detections.append(Detection(
                        bbox=(int(x1), int(y1), int(x2), int(y2)),
                        confidence=conf,
                        class_id=cls,
                        class_name="wound"
                    ))
        
        return detections
    
    def _parse_yolo_output(
        self,
        output: np.ndarray,
        original_shape: Tuple[int, int]
    ) -> List[Detection]:
        """Parse da saída do modelo YOLO"""
        detections = []
        orig_h, orig_w = original_shape
        input_h, input_w = self.config.input_size
        
        # Scale factors
        scale_x = orig_w / input_w
        scale_y = orig_h / input_h
        
        # Output shape: (1, num_detections, 5+num_classes) ou (1, 5+num_classes, num_detections)
        if output.ndim == 3:
            output = output[0]  # Remove batch dim
        
        # Transpõe se necessário
        if output.shape[0] < output.shape[1]:
            output = output.T
        
        for detection in output:
            # YOLOv8 formato: [x_center, y_center, width, height, class1_conf, class2_conf, ...]
            # YOLOv8 NAO tem objectness score separado; indices 4+ sao probabilidades de classe
            x_center, y_center, w, h = detection[:4]

            class_scores = detection[4:]
            class_id = int(np.argmax(class_scores))
            confidence = float(class_scores[class_id])

            if confidence < self.config.confidence_threshold:
                continue

            # Converte para coordenadas absolutas
            x1 = int((x_center - w / 2) * scale_x)
            y1 = int((y_center - h / 2) * scale_y)
            x2 = int((x_center + w / 2) * scale_x)
            y2 = int((y_center + h / 2) * scale_y)

            # Clamp para limites da imagem
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(orig_w, x2), min(orig_h, y2)

            detections.append(Detection(
                bbox=(x1, y1, x2, y2),
                confidence=confidence,
                class_id=class_id,
                class_name="wound" if class_id == 0 else f"class_{class_id}"
            ))
        
        # Non-Maximum Suppression
        return self._nms(detections, iou_threshold=0.45)
    
    def _simulate_detection(self, frame: np.ndarray) -> List[Detection]:
        """
        Simula detecção para demonstração (quando modelo não está disponível).
        
        Na produção, substitua pelo modelo real treinado.
        """
        h, w = frame.shape[:2]
        
        # Simula detecção baseada em cores (áreas avermelhadas/escuras)
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Máscara para tons avermelhados (possível ferida)
        lower_red1 = np.array([0, 50, 50])
        upper_red1 = np.array([10, 255, 255])
        lower_red2 = np.array([170, 50, 50])
        upper_red2 = np.array([180, 255, 255])
        
        mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
        mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
        mask = cv2.bitwise_or(mask1, mask2)
        
        # Encontra contornos
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        detections = []
        min_area = (w * h) * 0.01  # Mínimo 1% da imagem
        
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < min_area:
                continue
            
            x, y, bw, bh = cv2.boundingRect(contour)
            
            # Simula confidence baseado na área
            confidence = min(0.95, 0.5 + (area / (w * h)))
            
            detections.append(Detection(
                bbox=(x, y, x + bw, y + bh),
                confidence=confidence,
                class_id=0,
                class_name="wound"
            ))
        
        return self._nms(detections, iou_threshold=0.45)
    
    @staticmethod
    def _nms(
        detections: List[Detection],
        iou_threshold: float = 0.45
    ) -> List[Detection]:
        """Non-Maximum Suppression"""
        if len(detections) <= 1:
            return detections
        
        # Ordena por confidence
        detections = sorted(detections, key=lambda d: d.confidence, reverse=True)
        
        keep = []
        while detections:
            best = detections.pop(0)
            keep.append(best)
            
            detections = [
                d for d in detections
                if YOLODetector._iou(best.bbox, d.bbox) < iou_threshold
            ]
        
        return keep
    
    @staticmethod
    def _iou(box1: Tuple[int, int, int, int], box2: Tuple[int, int, int, int]) -> float:
        """Calcula Intersection over Union"""
        x1 = max(box1[0], box2[0])
        y1 = max(box1[1], box2[1])
        x2 = min(box1[2], box2[2])
        y2 = min(box1[3], box2[3])
        
        intersection = max(0, x2 - x1) * max(0, y2 - y1)
        
        area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
        area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
        union = area1 + area2 - intersection
        
        return intersection / union if union > 0 else 0
    
    @property
    def avg_inference_time(self) -> float:
        """Tempo médio de inferência em ms"""
        if not self._inference_times:
            return 0
        return sum(self._inference_times) / len(self._inference_times)
    
    @property
    def fps(self) -> float:
        """FPS estimado baseado no tempo de inferência"""
        avg_time = self.avg_inference_time
        return 1000 / avg_time if avg_time > 0 else 0


class RealtimeWoundDetector:
    """
    Classe de alto nível para detecção de feridas em tempo real.
    
    Integra:
    - Detector YOLO
    - Visualização de bounding boxes
    - Métricas de performance
    - Lógica de captura automática
    
    Uso:
        detector = RealtimeWoundDetector()
        detector.start()
        
        # No loop de frames
        annotated_frame, detections = detector.process_frame(frame)
        
        # Verifica se deve capturar
        if detector.should_capture():
            snapshot = frame.copy()
    """
    
    def __init__(
        self,
        config: Optional[RealtimeConfig] = None,
        auto_capture_threshold: float = 0.85,
        auto_capture_frames: int = 10
    ):
        """
        Args:
            config: Configurações de tempo real
            auto_capture_threshold: Confidence mínima para auto-capture
            auto_capture_frames: Frames consecutivos estáveis para trigger
        """
        self.config = config or RealtimeConfig()
        self.auto_capture_threshold = auto_capture_threshold
        self.auto_capture_frames = auto_capture_frames
        
        self._detector = YOLODetector(config=self.config.detector)
        self._stable_detection_count = 0
        self._last_detection: Optional[Detection] = None
        
    def start(self):
        """Inicializa o detector"""
        self._detector.load_model()
        self._detector.warmup()
        logger.info("Detector em tempo real iniciado")
    
    def process_frame(
        self,
        frame: np.ndarray,
        draw_boxes: bool = True
    ) -> Tuple[np.ndarray, List[Detection]]:
        """
        Processa um frame e retorna com anotações.
        
        Args:
            frame: Frame BGR da câmera
            draw_boxes: Desenhar bounding boxes
            
        Returns:
            (frame_anotado, lista_de_detecções)
        """
        # Detecta feridas
        detections = self._detector.detect(frame)
        
        # Atualiza contador de estabilidade
        self._update_stability(detections)
        
        # Desenha anotações
        annotated = frame.copy()
        if draw_boxes and detections:
            annotated = self._draw_annotations(annotated, detections)
        
        # Adiciona métricas na tela
        annotated = self._draw_metrics(annotated)
        
        return annotated, detections
    
    def _update_stability(self, detections: List[Detection]):
        """Atualiza contador de detecções estáveis"""
        if not detections:
            self._stable_detection_count = 0
            self._last_detection = None
            return
        
        best = max(detections, key=lambda d: d.confidence)
        
        if best.confidence >= self.auto_capture_threshold:
            if self._last_detection is not None:
                # Verifica se a detecção é similar à anterior
                iou = YOLODetector._iou(best.bbox, self._last_detection.bbox)
                if iou > 0.7:
                    self._stable_detection_count += 1
                else:
                    self._stable_detection_count = 1
            else:
                self._stable_detection_count = 1
            
            self._last_detection = best
        else:
            self._stable_detection_count = 0
            self._last_detection = None
    
    def should_capture(self) -> bool:
        """Verifica se deve disparar captura automática"""
        return self._stable_detection_count >= self.auto_capture_frames
    
    def reset_capture_trigger(self):
        """Reseta o trigger de captura"""
        self._stable_detection_count = 0
    
    def _draw_annotations(
        self,
        frame: np.ndarray,
        detections: List[Detection]
    ) -> np.ndarray:
        """Desenha bounding boxes e informações"""
        for det in detections:
            color = self.config.box_color
            thickness = self.config.box_thickness
            
            # Cor baseada na confidence
            if det.confidence >= self.auto_capture_threshold:
                color = (0, 255, 0)  # Verde = alta confiança
            elif det.confidence >= self.config.detector.confidence_threshold:
                color = (0, 255, 255)  # Amarelo = média confiança
            else:
                color = (0, 0, 255)  # Vermelho = baixa confiança
            
            # Desenha retângulo
            cv2.rectangle(frame, (det.x1, det.y1), (det.x2, det.y2), color, thickness)
            
            # Label com confidence
            if self.config.draw_confidence:
                label = f"Wound: {det.confidence:.0%}"
                
                # Background do label
                (label_w, label_h), baseline = cv2.getTextSize(
                    label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2
                )
                cv2.rectangle(
                    frame,
                    (det.x1, det.y1 - label_h - 10),
                    (det.x1 + label_w + 10, det.y1),
                    color,
                    -1
                )
                
                # Texto
                cv2.putText(
                    frame,
                    label,
                    (det.x1 + 5, det.y1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 0, 0),
                    2
                )
            
            # Indicador de estabilidade (progresso para auto-capture)
            if self._stable_detection_count > 0:
                progress = min(1.0, self._stable_detection_count / self.auto_capture_frames)
                bar_length = det.width
                bar_height = 8
                filled = int(bar_length * progress)
                
                cv2.rectangle(
                    frame,
                    (det.x1, det.y2 + 5),
                    (det.x1 + bar_length, det.y2 + 5 + bar_height),
                    (100, 100, 100),
                    -1
                )
                cv2.rectangle(
                    frame,
                    (det.x1, det.y2 + 5),
                    (det.x1 + filled, det.y2 + 5 + bar_height),
                    (0, 255, 0),
                    -1
                )
        
        return frame
    
    def _draw_metrics(self, frame: np.ndarray) -> np.ndarray:
        """Desenha métricas de performance na tela"""
        fps = self._detector.fps
        latency = self._detector.avg_inference_time
        
        # Background semi-transparente
        overlay = frame.copy()
        cv2.rectangle(overlay, (10, 10), (250, 80), (0, 0, 0), -1)
        frame = cv2.addWeighted(frame, 0.7, overlay, 0.3, 0)
        
        # Texto
        cv2.putText(
            frame,
            f"FPS: {fps:.1f}",
            (20, 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2
        )
        cv2.putText(
            frame,
            f"Latency: {latency:.1f}ms",
            (20, 65),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2
        )
        
        # Indicador de auto-capture
        if self.should_capture():
            cv2.putText(
                frame,
                "PRONTO PARA CAPTURA!",
                (frame.shape[1] // 2 - 150, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                (0, 255, 0),
                2
            )
        
        return frame
    
    @property
    def inference_time(self) -> float:
        """Tempo médio de inferência"""
        return self._detector.avg_inference_time
