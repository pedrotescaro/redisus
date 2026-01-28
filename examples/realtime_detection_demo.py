"""
REDISUS - Exemplo de Detecção em Tempo Real
============================================

Este script demonstra o fluxo de detecção em tempo real usando webcam.
É um exemplo focado em Visão Computacional que prioriza performance.

Arquitetura:
    [Webcam] -> [Frame Buffer] -> [YOLO Nano] -> [Bounding Box] -> [Display]
                                      |
                                      v
                              [Trigger Captura]
                                      |
                                      v
                              [Pipeline Pesado]
                              [U-Net + EfficientNet]

Otimizações aplicadas:
- Threading para captura de frames
- Modelo leve (YOLO Nano) para baixa latência
- Queue com buffer mínimo
- Processamento pesado apenas no snapshot
"""
import time
from queue import Queue
from threading import Thread
from typing import Optional, Tuple

import cv2
import numpy as np


# ============================================================================
# CONFIGURAÇÕES
# ============================================================================

CAMERA_ID = 0
FRAME_WIDTH = 1280
FRAME_HEIGHT = 720
DETECTION_INPUT_SIZE = (320, 320)  # Tamanho de entrada do YOLO Nano
CONFIDENCE_THRESHOLD = 0.5
AUTO_CAPTURE_CONFIDENCE = 0.85
AUTO_CAPTURE_STABLE_FRAMES = 10


# ============================================================================
# CLASSE DE DETECÇÃO LEVE (YOLO PLACEHOLDER)
# ============================================================================

class LightweightDetector:
    """
    Detector leve para tempo real.
    
    Em produção, substituir por modelo YOLO treinado:
    
    from ultralytics import YOLO
    self.model = YOLO('yolo_wound_nano.pt')
    
    Ou via ONNX Runtime:
    
    import onnxruntime as ort
    self.session = ort.InferenceSession('yolo_wound_nano.onnx')
    """
    
    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path
        self.model = None
        self._inference_times = []
        
        # Placeholder - em produção carregar modelo real
        self._load_model()
    
    def _load_model(self):
        """
        Carrega o modelo de detecção.
        
        SUBSTITUA por:
        
        # Opção 1: Ultralytics YOLO
        from ultralytics import YOLO
        self.model = YOLO(self.model_path)
        
        # Opção 2: ONNX Runtime
        import onnxruntime as ort
        self.session = ort.InferenceSession(self.model_path)
        """
        print("[INFO] Detector inicializado (modo simulação)")
        print("[INFO] Para produção, carregue modelo YOLO treinado")
    
    def detect(self, frame: np.ndarray) -> list:
        """
        Detecta feridas no frame.
        
        Args:
            frame: Imagem BGR da câmera
            
        Returns:
            Lista de detecções: [(x1, y1, x2, y2, confidence), ...]
        """
        start_time = time.perf_counter()
        
        # ====================================================================
        # PLACEHOLDER: Detecção baseada em cor
        # SUBSTITUIR por inferência do modelo real:
        #
        # # Ultralytics YOLO
        # results = self.model.predict(frame, conf=CONFIDENCE_THRESHOLD)
        # detections = []
        # for r in results:
        #     for box in r.boxes:
        #         x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
        #         conf = float(box.conf[0])
        #         detections.append((int(x1), int(y1), int(x2), int(y2), conf))
        # return detections
        # ====================================================================
        
        detections = self._simulate_detection(frame)
        
        # Métricas de tempo
        inference_time = (time.perf_counter() - start_time) * 1000
        self._inference_times.append(inference_time)
        if len(self._inference_times) > 100:
            self._inference_times.pop(0)
        
        return detections
    
    def _simulate_detection(self, frame: np.ndarray) -> list:
        """Simulação de detecção baseada em cor (para demonstração)"""
        h, w = frame.shape[:2]
        
        # Converte para HSV para detectar tons avermelhados
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Máscara para tons avermelhados (simula detecção de ferida)
        lower_red1 = np.array([0, 70, 50])
        upper_red1 = np.array([10, 255, 255])
        lower_red2 = np.array([170, 70, 50])
        upper_red2 = np.array([180, 255, 255])
        
        mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
        mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
        mask = cv2.bitwise_or(mask1, mask2)
        
        # Operações morfológicas para limpar ruído
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        
        # Encontra contornos
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        detections = []
        min_area = (w * h) * 0.005  # Mínimo 0.5% da imagem
        
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < min_area:
                continue
            
            x, y, bw, bh = cv2.boundingRect(contour)
            
            # Simula confidence baseado na área e circularidade
            perimeter = cv2.arcLength(contour, True)
            circularity = 4 * np.pi * area / (perimeter ** 2) if perimeter > 0 else 0
            
            confidence = min(0.95, 0.5 + (area / (w * h)) * 5 + circularity * 0.3)
            
            if confidence >= CONFIDENCE_THRESHOLD:
                detections.append((x, y, x + bw, y + bh, confidence))
        
        # NMS simples
        return self._nms(detections, iou_threshold=0.45)
    
    @staticmethod
    def _nms(detections: list, iou_threshold: float) -> list:
        """Non-Maximum Suppression"""
        if len(detections) <= 1:
            return detections
        
        # Ordena por confidence
        detections = sorted(detections, key=lambda d: d[4], reverse=True)
        
        keep = []
        while detections:
            best = detections.pop(0)
            keep.append(best)
            
            detections = [
                d for d in detections
                if LightweightDetector._iou(best[:4], d[:4]) < iou_threshold
            ]
        
        return keep
    
    @staticmethod
    def _iou(box1, box2) -> float:
        """Intersection over Union"""
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
    def avg_inference_time_ms(self) -> float:
        if not self._inference_times:
            return 0
        return sum(self._inference_times) / len(self._inference_times)


# ============================================================================
# PIPELINE DE DIAGNÓSTICO PESADO (SNAPSHOT)
# ============================================================================

class HeavyDiagnosisPipeline:
    """
    Pipeline de diagnóstico pesado executado apenas em snapshots.
    
    Inclui:
    - Segmentação de tecidos (U-Net)
    - Classificação de etiologia (EfficientNet)
    - Geração de relatório
    """
    
    def __init__(self):
        self.segmenter = None  # Placeholder para U-Net
        self.classifier = None  # Placeholder para EfficientNet
    
    def analyze(self, image: np.ndarray) -> dict:
        """
        Realiza análise completa de uma imagem.
        
        Args:
            image: Imagem BGR em alta resolução
            
        Returns:
            Dicionário com resultados da análise
        """
        print("\n" + "=" * 50)
        print("EXECUTANDO DIAGNÓSTICO PROFUNDO...")
        print("=" * 50)
        
        start_time = time.perf_counter()
        
        # ====================================================================
        # PLACEHOLDER: Simulação de segmentação e classificação
        #
        # Em produção, usar modelos reais:
        #
        # # Segmentação
        # segmentation = self.segmenter.segment(image)
        #
        # # Classificação
        # classification = self.classifier.classify(image)
        # ====================================================================
        
        # Simula tempo de processamento pesado
        time.sleep(0.5)  # Simula ~500ms de inferência
        
        result = self._simulate_analysis(image)
        
        total_time = (time.perf_counter() - start_time) * 1000
        result['inference_time_ms'] = total_time
        
        self._print_result(result)
        
        return result
    
    def _simulate_analysis(self, image: np.ndarray) -> dict:
        """Simula análise para demonstração"""
        return {
            'etiology': {
                'class': 'Úlcera Venosa',
                'confidence': 0.87,
                'description': 'Úlcera causada por insuficiência venosa crônica'
            },
            'segmentation': {
                'granulation': 45.2,
                'slough': 32.1,
                'necrosis': 8.5,
                'periwound': 14.2
            },
            'recommendation': 'Terapia compressiva + cobertura absorvente'
        }
    
    def _print_result(self, result: dict):
        """Imprime resultado formatado"""
        print(f"\n📋 ETIOLOGIA: {result['etiology']['class']}")
        print(f"   Confiança: {result['etiology']['confidence']:.1%}")
        print(f"   {result['etiology']['description']}")
        
        print("\n🔬 COMPOSIÇÃO TECIDUAL:")
        for tissue, pct in result['segmentation'].items():
            print(f"   • {tissue.capitalize()}: {pct:.1f}%")
        
        print(f"\n💊 RECOMENDAÇÃO: {result['recommendation']}")
        print(f"\n⏱️ Tempo de processamento: {result['inference_time_ms']:.0f}ms")
        print("=" * 50 + "\n")


# ============================================================================
# LOOP PRINCIPAL DE VÍDEO
# ============================================================================

def draw_detections(
    frame: np.ndarray,
    detections: list,
    stable_count: int,
    target_count: int
) -> np.ndarray:
    """Desenha bounding boxes e informações no frame"""
    for det in detections:
        x1, y1, x2, y2, conf = det
        
        # Cor baseada na confiança
        if conf >= AUTO_CAPTURE_CONFIDENCE:
            color = (0, 255, 0)  # Verde
        elif conf >= CONFIDENCE_THRESHOLD:
            color = (0, 255, 255)  # Amarelo
        else:
            color = (0, 0, 255)  # Vermelho
        
        # Bounding box
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        
        # Label
        label = f"Ferida: {conf:.0%}"
        (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        cv2.rectangle(frame, (x1, y1 - lh - 10), (x1 + lw + 10, y1), color, -1)
        cv2.putText(frame, label, (x1 + 5, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
        
        # Barra de progresso para auto-capture
        if stable_count > 0:
            progress = min(1.0, stable_count / target_count)
            bar_width = x2 - x1
            filled = int(bar_width * progress)
            
            cv2.rectangle(frame, (x1, y2 + 5), (x2, y2 + 15), (100, 100, 100), -1)
            cv2.rectangle(frame, (x1, y2 + 5), (x1 + filled, y2 + 15), (0, 255, 0), -1)
    
    return frame


def draw_hud(
    frame: np.ndarray,
    fps: float,
    latency: float,
    auto_capture_ready: bool
) -> np.ndarray:
    """Desenha HUD com métricas"""
    h, w = frame.shape[:2]
    
    # Background semi-transparente
    overlay = frame.copy()
    cv2.rectangle(overlay, (10, 10), (200, 80), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
    
    # Métricas
    cv2.putText(frame, f"FPS: {fps:.1f}", (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    cv2.putText(frame, f"Latencia: {latency:.1f}ms", (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    
    # Indicador de auto-capture
    if auto_capture_ready:
        cv2.putText(
            frame,
            "PRONTO PARA CAPTURA!",
            (w // 2 - 150, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (0, 255, 0),
            2
        )
    
    # Instruções
    cv2.putText(
        frame,
        "SPACE: Capturar | Q: Sair",
        (w // 2 - 120, h - 20),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 255, 255),
        1
    )
    
    return frame


def main():
    """Função principal do demo de tempo real"""
    print("\n" + "=" * 60)
    print("REDISUS - DETECÇÃO DE FERIDAS EM TEMPO REAL")
    print("=" * 60)
    print("\nInicializando...")
    
    # Inicializa detector leve
    detector = LightweightDetector()
    
    # Inicializa pipeline pesado
    diagnosis_pipeline = HeavyDiagnosisPipeline()
    
    # Inicializa câmera
    cap = cv2.VideoCapture(CAMERA_ID)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Buffer mínimo para baixa latência
    
    if not cap.isOpened():
        print("[ERRO] Não foi possível abrir a câmera")
        return
    
    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"\n✓ Câmera inicializada: {actual_w}x{actual_h}")
    print("\nControles:")
    print("  SPACE - Capturar e analisar")
    print("  Q     - Sair")
    print("\n" + "-" * 60 + "\n")
    
    # Estado
    stable_count = 0
    last_detection = None
    fps_timer = time.time()
    fps_counter = 0
    fps = 0.0
    
    cv2.namedWindow("REDISUS - Deteccao em Tempo Real", cv2.WINDOW_NORMAL)
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                continue
            
            # ================================================================
            # DETECÇÃO EM TEMPO REAL (MODELO LEVE)
            # ================================================================
            detections = detector.detect(frame)
            
            # Atualiza contador de estabilidade
            if detections:
                best = max(detections, key=lambda d: d[4])
                
                if best[4] >= AUTO_CAPTURE_CONFIDENCE:
                    if last_detection is not None:
                        iou = detector._iou(best[:4], last_detection[:4])
                        if iou > 0.7:
                            stable_count += 1
                        else:
                            stable_count = 1
                    else:
                        stable_count = 1
                    
                    last_detection = best
                else:
                    stable_count = 0
                    last_detection = None
            else:
                stable_count = 0
                last_detection = None
            
            auto_capture_ready = stable_count >= AUTO_CAPTURE_STABLE_FRAMES
            
            # Desenha visualizações
            frame = draw_detections(frame, detections, stable_count, AUTO_CAPTURE_STABLE_FRAMES)
            
            # Calcula FPS
            fps_counter += 1
            if time.time() - fps_timer >= 1.0:
                fps = fps_counter
                fps_counter = 0
                fps_timer = time.time()
            
            frame = draw_hud(frame, fps, detector.avg_inference_time_ms, auto_capture_ready)
            
            # Exibe
            cv2.imshow("REDISUS - Deteccao em Tempo Real", frame)
            
            # ================================================================
            # PROCESSA TECLAS
            # ================================================================
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('q') or key == 27:  # Q ou ESC
                break
            
            elif key == ord(' '):  # SPACE - captura manual
                print("\n[CAPTURA] Snapshot capturado!")
                
                # Executa pipeline pesado no snapshot
                result = diagnosis_pipeline.analyze(frame.copy())
                
                # Reseta contador
                stable_count = 0
            
            # Auto-capture se estável
            elif auto_capture_ready:
                print("\n[AUTO-CAPTURE] Detecção estável, capturando...")
                
                result = diagnosis_pipeline.analyze(frame.copy())
                
                stable_count = 0
    
    except KeyboardInterrupt:
        print("\n[INFO] Interrompido pelo usuário")
    
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("\n[INFO] Aplicação encerrada")


if __name__ == "__main__":
    main()
