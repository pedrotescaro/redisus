# -*- coding: utf-8 -*-
"""
HEAL+ / REDISUS — Analisador Clínico de Feridas v3.0 (Desktop PyQt6)
=====================================================================

Aplicação especialista em Estomaterapia com Visão Computacional + IA.

Taxonomia clínica rigorosa:
  1. Necrose de Coagulação (Escara)  — preto/marrom, endurecido, seco ou úmido
  2. Esfacelo (Fibrina)              — amarelo/branco, viscoso ou fibroso
  3. Tecido de Granulação             — vermelho brilhante, úmido, granulado
  4. Epitelização                     — rosa claro/translúcido, avança das bordas

Classificação Etiológica (ResNet50 Two-Stage):
  Estágio 1: Normal vs. Ferida (classificação binária)
  Estágio 2: Tipo de Ferida (Diabética, Pressão, Venosa)
  Explicabilidade: Grad-CAM sobre layer4 do ResNet50

Pipeline v3:
  Imagem → Validação → Detecção → ROI Contorno → Zonas (Periferia/Core)
        → Segmentação Multi-Espaço (HSV+LAB) restrita à ROI
        → Gradiente de Borda (Scharr) → Epitelização Periférica
        → Análise de Textura → Classificação DL (EfficientNet + TTA)
        → ResNet50 Two-Stage (Normal/Ferida + Tipo) com TTA 4-flip
        → Grad-CAM (explicabilidade)
        → Análise de Bordas → Laudo Clínico

Melhorias v3 vs v2:
  - Máscara ROI por contorno (não mais bounding box retangular)
  - Zonas espaciais: periferia vs. core vs. anel externo
  - Detecção de epitelização por gradiente na borda (Scharr)
  - Classificação espacial de background (variância + crominância + conectividade)
    separa fundo de câmera de tecido necrótico por contexto espacial
  - Necrose priorizada por luminância: pixels V < 50 dentro do perímetro
    anatômico segmentado são tratados como necrose de alta confiança
  - Esfacelo restrito ao core; epitelização à periferia
  - Distance transform para peso espacial

Melhorias v2 vs v1:
  - Segmentação multi-espaço de cor (HSV 60% + LAB 40%)
  - Refinamento por textura (variância local, LBP)
  - CLAHE para normalização de iluminação
  - Integração com modelo DL (EfficientNetB3, TTA 4x flips)
  - Intervalos HSV/LAB clínicos recalibrados
  - Classes consolidadas (24 → 10 categorias significativas)

Uso:
    python heal_analyzer.py
"""
import sys
import os
import io
import time
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple, List

# Força o console do Windows a aceitar UTF-8
try:
    if sys.stdout and sys.stdout.encoding != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    if sys.stderr and sys.stderr.encoding != 'utf-8':
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
except Exception:
    pass

# Import torch BEFORE cv2 to avoid DLL conflicts on Windows
try:
    import torch
    from torchvision import transforms as _tv_transforms
    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False

import cv2
import numpy as np

# PIL para renderizar texto com UTF-8/acentos (cv2.putText não suporta)
try:
    from PIL import Image, ImageDraw, ImageFont
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

# Path setup
sys.path.insert(0, str(Path(__file__).resolve().parent))

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QScrollArea, QFrame,
    QProgressBar, QSplitter, QGroupBox, QTextEdit, QSizePolicy,
    QGraphicsDropShadowEffect, QTabWidget, QComboBox, QSlider,
)
from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal, QTimer, QMutex
from PyQt6.QtGui import QImage, QPixmap, QFont, QColor, QPalette, QIcon

# ============================================================
# HELPER: Texto UTF-8 no OpenCV (via PIL)
# ============================================================

def cv2_put_text_utf8(
    img: np.ndarray,
    text: str,
    pos: Tuple[int, int],
    font_size: int = 16,
    color: Tuple[int, int, int] = (255, 255, 255),
    bg_color: Optional[Tuple[int, int, int]] = None,
    font_path: Optional[str] = None
) -> np.ndarray:
    """
    Desenha texto com suporte a UTF-8/acentos usando PIL.
    
    Args:
        img: Imagem BGR do OpenCV
        text: Texto a desenhar (suporta acentos)
        pos: Posição (x, y) do canto superior esquerdo
        font_size: Tamanho da fonte em pixels
        color: Cor BGR do texto
        bg_color: Cor BGR do fundo (opcional)
        font_path: Caminho para fonte .ttf (opcional)
    
    Returns:
        Imagem com texto desenhado
    """
    if not _PIL_AVAILABLE:
        # Fallback: usa cv2.putText sem acentos
        cv2.putText(img, text.encode('ascii', 'replace').decode(), pos,
                    cv2.FONT_HERSHEY_SIMPLEX, font_size/30, color[::-1], 1)
        return img
    
    # Converte BGR -> RGB para PIL
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(img_rgb)
    draw = ImageDraw.Draw(pil_img)
    
    # Carrega fonte
    try:
        if font_path and Path(font_path).exists():
            font = ImageFont.truetype(font_path, font_size)
        else:
            # Tenta fontes comuns do Windows
            for fallback in ['segoeui.ttf', 'arial.ttf', 'tahoma.ttf']:
                try:
                    font = ImageFont.truetype(fallback, font_size)
                    break
                except OSError:
                    continue
            else:
                font = ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()
    
    # Calcula tamanho do texto para background
    bbox = draw.textbbox(pos, text, font=font)
    
    # Desenha background se especificado
    if bg_color is not None:
        padding = 2
        draw.rectangle(
            [bbox[0] - padding, bbox[1] - padding, bbox[2] + padding, bbox[3] + padding],
            fill=bg_color[::-1]  # BGR -> RGB
        )
    
    # Desenha texto (cor BGR -> RGB)
    draw.text(pos, text, font=font, fill=color[::-1])
    
    # Converte de volta para BGR
    result = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    return result


# ============================================================
# Módulos do projeto
# ============================================================
from src.processing.wound_detector_cv import WoundDetectorCV, DetectionMethod

logger = logging.getLogger(__name__)

# Escalas clínicas validadas
try:
    from src.clinical.scales import ScaleCalculator  # noqa: F401
    HAS_CLINICAL_SCALES = True
except ImportError:
    HAS_CLINICAL_SCALES = False


# ============================================================
# CORE HEADLESS COMPARTILHADO
# ============================================================
# O desktop PyQt6 agora reutiliza o motor extraido em src/processing,
# mantendo a interface aqui e a logica clinica no modulo headless.
from src.processing.clinical_wound_analyzer_core import (
    BorderAnalysis,
    CLINICAL_TISSUES,
    ClinicalReport,
    ClinicalWoundAnalyzer,
    TissueClassification,
)

# ============================================================
# THREAD DE ANALISE (nao trava a UI)
# ============================================================

class AnalysisThread(QThread):
    # IMPORTANT: Do NOT name this 'finished' — it shadows QThread.finished
    # and breaks Qt's internal thread cleanup, causing crashes.
    result_ready = pyqtSignal(object)
    progress = pyqtSignal(str)

    def __init__(self, image_path: str, parent=None):
        super().__init__(parent)  # Parent garante cleanup adequado
        self.image_path = image_path
        # NÃO conecte finished.connect(deleteLater) - causa crash
        # Lifecycle é gerenciado manualmente

    def run(self):
        self.progress.emit("Carregando imagem...")
        image = cv2.imread(self.image_path)
        if image is None:
            report = ClinicalReport(is_valid_wound=False,
                                    rejection_reason="Não foi possível carregar a imagem.")
            self.result_ready.emit(report)
            return

        self.progress.emit("Analisando ferida...")
        analyzer = ClinicalWoundAnalyzer()
        report = analyzer.analyze(image)
        self.result_ready.emit(report)


# ============================================================
# THREAD DE WEBCAM (captura em tempo real)
# ============================================================

class FaceExclusionFilter:
    """
    Filtro de exclusão de rostos usando Haar Cascade do OpenCV.

    Impede que o detector de feridas marque rostos humanos como ferida.
    Também rejeita regiões com pele uniformemente saudável (sem textura de lesão).
    """

    def __init__(self):
        # Haar cascade para detecção de rostos (incluso no OpenCV)
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self._face_cascade = cv2.CascadeClassifier(cascade_path)
        profile_path = cv2.data.haarcascades + "haarcascade_profileface.xml"
        self._profile_cascade = cv2.CascadeClassifier(profile_path)
        self._face_rects: List[Tuple[int, int, int, int]] = []
        self._face_update_interval = 5  # Atualiza faces a cada N frames
        self._frame_counter = 0

    def update_faces(self, gray_frame: np.ndarray):
        """Detecta rostos no frame (chamado periodicamente)."""
        self._frame_counter += 1
        if self._frame_counter % self._face_update_interval != 0:
            return

        # Reduz resolução para velocidade
        h, w = gray_frame.shape[:2]
        scale = min(320 / max(h, w), 1.0)
        small = cv2.resize(gray_frame, (int(w * scale), int(h * scale)))

        faces = self._face_cascade.detectMultiScale(
            small, scaleFactor=1.15, minNeighbors=4, minSize=(40, 40)
        )
        profiles = self._profile_cascade.detectMultiScale(
            small, scaleFactor=1.15, minNeighbors=4, minSize=(40, 40)
        )

        all_faces = []
        for (fx, fy, fw, fh) in list(faces) + list(profiles):
            # Escala de volta + margem de 30%
            margin = 0.3
            fx1 = int((fx - fw * margin) / scale)
            fy1 = int((fy - fh * margin) / scale)
            fx2 = int((fx + fw + fw * margin) / scale)
            fy2 = int((fy + fh + fh * margin) / scale)
            all_faces.append((max(0, fx1), max(0, fy1), min(w, fx2), min(h, fy2)))

        self._face_rects = all_faces

    def overlaps_face(self, bbox: Tuple[int, int, int, int]) -> bool:
        """Verifica se uma bounding box intersecta algum rosto."""
        x1, y1, x2, y2 = bbox
        for fx1, fy1, fx2, fy2 in self._face_rects:
            # IoU parcial: se >30% de overlap, é rosto
            ix1 = max(x1, fx1)
            iy1 = max(y1, fy1)
            ix2 = min(x2, fx2)
            iy2 = min(y2, fy2)
            inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
            det_area = max((x2 - x1) * (y2 - y1), 1)
            if inter / det_area > 0.25:
                return True
        return False

    def get_face_rects(self) -> List[Tuple[int, int, int, int]]:
        return self._face_rects

    @staticmethod
    def is_uniform_skin(roi_bgr: np.ndarray) -> bool:
        """
        Verifica se a ROI é pele uniforme saudável (sem textura de lesão).
        Pele saudável tem: baixa variância de cor, tom uniforme.
        AGRESSIVO: prefere rejeitar do que aceitar falsos positivos.
        """
        if roi_bgr is None or roi_bgr.size < 100:
            return True

        hsv = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2HSV)
        h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]

        # Pele uniforme: saturação e valor com pouca variação
        s_std = np.std(s)
        v_std = np.std(v)
        h_std = np.std(h)

        # Variância de textura (Laplaciano)
        gray = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY)
        lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()

        # AGRESSIVO: Pele saudável uniforme (thresholds aumentados)
        if s_std < 25 and v_std < 30 and lap_var < 400:
            return True

        # Cor muito uniforme (pouca variação de hue)
        if h_std < 15 and s_std < 30 and lap_var < 500:
            return True

        # Tom de pele fortemente dominante, pouca textura
        skin_lower = np.array([0, 15, 60])  # Ampliado para capturar mais tons de pele
        skin_upper = np.array([30, 170, 255])
        skin_mask = cv2.inRange(hsv, skin_lower, skin_upper)
        skin_ratio = np.sum(skin_mask > 0) / max(skin_mask.size, 1)

        # Se >70% é pele e textura baixa, provavelmente é pele saudável
        if skin_ratio > 0.70 and lap_var < 500:
            return True

        # Gradiente da imagem - feridas têm bordas mais marcadas
        sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        gradient_mag = np.sqrt(sobelx**2 + sobely**2).mean()

        # Pele saudável tem gradiente baixo (superfície lisa)
        if gradient_mag < 15 and skin_ratio > 0.5:
            return True

        return False


class WebcamThread(QThread):
    """
    Thread para captura de vídeo + detecção rápida em cada frame.

    Estratégia anti-falso-positivo:
    1. Detector com TEXTURE_PRIORITY (peso 50% textura, 25% cor)
    2. Confiança mínima 0.45
    3. Área mínima 1200px
    4. Filtro de falsos positivos DESLIGADO (fast-path)
    5. Exclusão automática de rostos (Haar Cascade)
    6. Rejeição de pele uniforme saudável
    7. Detecção a cada 2 frames para responsividade
    """
    frame_ready = pyqtSignal(np.ndarray, np.ndarray)  # (annotated_frame, raw_frame)
    error = pyqtSignal(str)

    def __init__(self, camera_id: int = 0, parent=None):
        super().__init__(parent)  # Parent garante cleanup adequado
        self.camera_id = camera_id
        self._running = False
        self._mutex = QMutex()
        # NÃO conecte finished.connect(deleteLater) - causa crash
        # Lifecycle é gerenciado manualmente

    def run(self):
        cap = cv2.VideoCapture(self.camera_id)
        if not cap.isOpened():
            self.error.emit(f"Não foi possível abrir a câmera {self.camera_id}")
            return

        # Configurações da câmera
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        # Detector RÁPIDO para overlay (sem FP filter pesado;
        # WebcamThread já tem filtros próprios: rosto, pele, aspect ratio)
        # Detector RÁPIDO para overlay - mais conservador para evitar falsos positivos
        detector = WoundDetectorCV(
            method=DetectionMethod.TEXTURE_PRIORITY,
            min_area=2000,              # Aumentado: áreas pequenas são mais propensas a FP
            confidence_threshold=0.55,   # Aumentado: exige mais certeza
            enable_false_positive_filter=False,  # Desligado no fast-path
            texture_weight=0.6,          # Aumentado: textura é mais confiável
            color_weight=0.2,            # Reduzido: cor de pele causa FP
        )

        # Filtro de rostos
        face_filter = FaceExclusionFilter()

        fps_timer = time.perf_counter()
        fps_count = 0
        fps_display = 0.0
        n_faces = 0

        # Controle de throtlling: detecta a cada N frames
        frame_counter = 0
        detect_every_n = 2          # Roda detecção a cada 2 frames
        cached_detections = []       # Reutiliza detecções entre frames
        cached_n_det = 0
        cached_annotations = []      # (x1,y1,x2,y2,label,conf)

        self._running = True
        while self._running:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.01)
                continue

            h, w = frame.shape[:2]
            frame_counter += 1

            # Atualiza detecção de rostos (já tem throttle interno de 5 frames)
            gray_full = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            face_filter.update_faces(gray_full)
            n_faces = len(face_filter.get_face_rects())

            # Só roda detecção a cada N frames; reusa resultado nos intermediários
            if frame_counter % detect_every_n == 0:
                # Redimensiona para processamento rápido
                proc_frame = frame
                if max(h, w) > 768:
                    scale = 768 / max(h, w)
                    proc_frame = cv2.resize(frame, (int(w * scale), int(h * scale)))

                cached_annotations = []
                cached_n_det = 0
                try:
                    detections = detector.detect(proc_frame)
                    scale_x = w / proc_frame.shape[1]
                    scale_y = h / proc_frame.shape[0]

                    for det in detections:
                        x1, y1, x2, y2 = det.bbox
                        x1 = int(x1 * scale_x)
                        y1 = int(y1 * scale_y)
                        x2 = int(x2 * scale_x)
                        y2 = int(y2 * scale_y)
                        conf = det.confidence

                        # FILTRO 1: Rejeita se sobrepõe rosto
                        if face_filter.overlaps_face((x1, y1, x2, y2)):
                            continue

                        # FILTRO 2: Rejeita pele uniforme saudável
                        roi = frame[max(0, y1):min(h, y2), max(0, x1):min(w, x2)]
                        if FaceExclusionFilter.is_uniform_skin(roi):
                            continue

                        # FILTRO 3: Aspect ratio
                        det_w = x2 - x1
                        det_h = y2 - y1
                        aspect = max(det_w, det_h) / max(min(det_w, det_h), 1)
                        if aspect > 5.0:
                            continue

                        wound_type = det.wound_type or "wound"
                        type_labels = {
                            "granulating_wound": "Granulação",
                            "necrotic_wound": "Necrose",
                            "infected_wound": "Infectada",
                            "pressure_injury": "Pressão",
                            "surgical_wound": "Cirúrgica",
                            "wound": "Ferida",
                        }
                        label_txt = type_labels.get(wound_type, "Ferida")
                        cached_annotations.append((x1, y1, x2, y2, f"{label_txt} {conf:.0%}", conf))
                        cached_n_det += 1

                except Exception:
                    cached_annotations = []
                    cached_n_det = 0

            # Desenha anotações (cached) sobre o frame atual
            annotated = frame.copy()
            for (x1, y1, x2, y2, label, conf) in cached_annotations:
                cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
                # Usa PIL para texto com acentos
                annotated = cv2_put_text_utf8(
                    annotated, label, (x1 + 3, max(y1 - 20, 5)),
                    font_size=16, color=(0, 0, 0), bg_color=(0, 255, 0)
                )

            # Desenha rostos excluídos (azul tracejado)
            for (fx1, fy1, fx2, fy2) in face_filter.get_face_rects():
                cv2.rectangle(annotated, (fx1, fy1), (fx2, fy2), (255, 150, 50), 1)
                annotated = cv2_put_text_utf8(
                    annotated, "Rosto (ignorado)", (fx1, max(fy1 - 18, 5)),
                    font_size=12, color=(255, 150, 50)
                )

            # FPS
            fps_count += 1
            elapsed = time.perf_counter() - fps_timer
            if elapsed >= 1.0:
                fps_display = fps_count / elapsed
                fps_count = 0
                fps_timer = time.perf_counter()

            # HUD overlay
            n_det = cached_n_det
            hud_h = 90 if n_faces > 0 else 72
            cv2.rectangle(annotated, (8, 8), (290, hud_h), (0, 0, 0), -1)
            cv2.rectangle(annotated, (8, 8), (290, hud_h), (0, 255, 0), 1)
            annotated = cv2_put_text_utf8(
                annotated, f"HEAL+ LIVE  |  {fps_display:.0f} FPS",
                (14, 12), font_size=16, color=(0, 255, 0)
            )

            det_color = (0, 255, 0) if n_det > 0 else (100, 100, 100)
            status_txt = f"Feridas: {n_det}" if n_det > 0 else "Nenhuma ferida"
            annotated = cv2_put_text_utf8(
                annotated, status_txt,
                (14, 38), font_size=14, color=det_color
            )

            if n_faces > 0:
                annotated = cv2_put_text_utf8(
                    annotated, f"Rostos ignorados: {n_faces}",
                    (14, 62), font_size=12, color=(255, 150, 50)
                )

            # Indicador de "escaneando"
            scan_x = int((time.perf_counter() * 150) % w)
            cv2.line(annotated, (scan_x, 0), (scan_x, h), (0, 255, 0), 1)

            self.frame_ready.emit(annotated, frame)

        cap.release()

    def stop(self):
        """Para a thread de forma segura. Retorna True se parou com sucesso."""
        self._mutex.lock()
        self._running = False
        self._mutex.unlock()
        # Espera até 5 segundos para a thread terminar
        if not self.wait(5000):
            # Se não terminou, tenta terminar forçadamente
            self.terminate()
            self.wait(1000)
            return False
        return True


class RealtimeAnalysisThread(QThread):
    """Thread para análise clínica completa de um frame (roda em background)."""
    # IMPORTANT: Do NOT name this 'finished' — it shadows QThread.finished
    result_ready = pyqtSignal(object)

    def __init__(self, frame: np.ndarray, analyzer: ClinicalWoundAnalyzer, parent=None):
        super().__init__(parent)  # Parent garante cleanup adequado
        self.frame = frame.copy()
        self.analyzer = analyzer
        self._cancelled = False
        # NÃO conecte finished.connect(deleteLater) - causa crash
        # Lifecycle é gerenciado manualmente

    def run(self):
        try:
            if self._cancelled:
                return
            report = self.analyzer.analyze(self.frame)
            if not self._cancelled:
                self.result_ready.emit(report)
        except Exception as e:
            print(f"[HEAL+] Erro na análise em tempo real: {e}")

    def cancel(self):
        """Marca a thread como cancelada (não emitirá resultado)."""
        self._cancelled = True


# ============================================================
# APLICAÇÃO DESKTOP PyQt6
# ============================================================

def np_to_qpixmap(img: np.ndarray, max_w: int = 500) -> QPixmap:
    """Converte imagem OpenCV (BGR) para QPixmap."""
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    h, w, ch = rgb.shape
    if w > max_w:
        scale = max_w / w
        rgb = cv2.resize(rgb, (max_w, int(h * scale)))
        h, w = rgb.shape[:2]
    bytes_per_line = ch * w
    qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimg.copy())


class HealAnalyzerApp(QMainWindow):
    """Janela principal do analisador de feridas HEAL+."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("HEAL+ — Analisador Clínico de Feridas")
        self.setMinimumSize(1200, 800)
        self._current_report: Optional[ClinicalReport] = None
        self._thread: Optional[AnalysisThread] = None

        # Webcam
        self._webcam_thread: Optional[WebcamThread] = None
        self._realtime_thread: Optional[RealtimeAnalysisThread] = None
        self._last_frame: Optional[np.ndarray] = None
        self._webcam_active = False
        self._analysis_interval_ms = 1000  # Análise completa a cada 1s
        self._last_analysis_time = 0.0
        self._rt_analyzer: Optional[ClinicalWoundAnalyzer] = None  # Instância reutilizável

        self._setup_ui()

    # -------------------------------------------------------
    # UI
    # -------------------------------------------------------
    def _setup_ui(self):
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#0f172a"))
        palette.setColor(QPalette.ColorRole.WindowText, QColor("#e2e8f0"))
        palette.setColor(QPalette.ColorRole.Base, QColor("#1e293b"))
        palette.setColor(QPalette.ColorRole.Text, QColor("#e2e8f0"))
        palette.setColor(QPalette.ColorRole.Button, QColor("#334155"))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor("#e2e8f0"))
        palette.setColor(QPalette.ColorRole.Highlight, QColor("#38bdf8"))
        self.setPalette(palette)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(10)

        # === HEADER ===
        header_layout = QHBoxLayout()
        
        title_layout = QVBoxLayout()
        header = QLabel("HEAL+  —  Analisador Clínico de Feridas")
        header.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        header.setStyleSheet("color: #e2e8f0; padding: 0px; margin: 0px;")
        title_layout.addWidget(header)

        subtitle = QLabel("Estomaterapia + Visão Computacional  ·  ResNet50 Two-Stage + Grad-CAM  ·  Classificação Tecidual e Etiológica")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        subtitle.setFont(QFont("Segoe UI", 10))
        subtitle.setStyleSheet("color: #94a3b8; padding: 0px; margin: 0px;")
        title_layout.addWidget(subtitle)
        
        header_layout.addLayout(title_layout)
        header_layout.addStretch()
        main_layout.addLayout(header_layout)

        # Linha separadora
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setFixedHeight(1)
        line.setStyleSheet("background: #334155; border: none;")
        main_layout.addWidget(line)

        # === TOOLBAR ===
        toolbar = QHBoxLayout()
        self.lbl_status = QLabel("Selecione uma aba para começar")
        self.lbl_status.setFont(QFont("Segoe UI", 10))
        self.lbl_status.setStyleSheet("color: #94a3b8; padding-left: 10px;")
        toolbar.addWidget(self.lbl_status, stretch=1)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setFixedWidth(180)
        self.progress.setVisible(False)
        self.progress.setStyleSheet("""
            QProgressBar { background: #1e293b; border: 1px solid #334155;
                border-radius: 6px; height: 14px; }
            QProgressBar::chunk { background: #38bdf8; border-radius: 5px; }
        """)
        toolbar.addWidget(self.progress)
        main_layout.addLayout(toolbar)

        # === TABS ===
        self.tab_widget = QTabWidget()
        self.tab_widget.setFont(QFont("Segoe UI", 11))
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #334155;
                border-radius: 8px;
                background: #1e293b;
            }
            QTabBar::tab {
                background: #1e293b;
                color: #94a3b8;
                padding: 10px 24px;
                margin-right: 4px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background: #0ea5e9;
                color: white;
            }
            QTabBar::tab:hover:!selected {
                background: #334155;
                color: #e2e8f0;
            }
        """)

        # === TAB 1: ARQUIVO DE IMAGEM ===
        self.tab_image = QWidget()
        self._setup_image_tab()
        self.tab_widget.addTab(self.tab_image, "Arquivo de Imagem")

        # === TAB 2: TEMPO REAL (WEBCAM) ===
        self.tab_webcam = QWidget()
        self._setup_webcam_tab()
        self.tab_widget.addTab(self.tab_webcam, "Tempo Real (Webcam)")

        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        main_layout.addWidget(self.tab_widget, stretch=1)

        footer = QLabel("HEAL/REDISUS  —  Plataforma Nacional de Saúde Digital  ·  Cluster REDISUS  —  RNP/RUTE")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setFont(QFont("Segoe UI", 8))
        footer.setStyleSheet("color: #475569; padding: 6px;")
        main_layout.addWidget(footer)

    # -------------------------------------------------------
    def _make_image_panel(self, title: str) -> QLabel:
        frame = QLabel(title)
        frame.setAlignment(Qt.AlignmentFlag.AlignCenter)
        frame.setMinimumSize(240, 180)
        frame.setFont(QFont("Segoe UI", 9))
        frame.setStyleSheet("""
            QLabel {
                background: #1e293b;
                border: 1px solid #334155;
                border-radius: 10px;
                color: #64748b;
                padding: 4px;
            }
        """)
        frame.setScaledContents(False)
        return frame

    # -------------------------------------------------------
    def _setup_image_tab(self):
        """Configura aba de análise de imagem estática."""
        layout = QVBoxLayout(self.tab_image)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Toolbar da aba
        toolbar = QHBoxLayout()
        self.btn_open = QPushButton("Abrir Imagem de Ferida")
        self.btn_open.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.btn_open.setMinimumHeight(40)
        self.btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open.setStyleSheet("""
            QPushButton {
                background: #0ea5e9;
                color: white; border: none; border-radius: 6px;
                padding: 0 24px; font-size: 13px;
            }
            QPushButton:hover { background: #38bdf8; }
            QPushButton:pressed { background: #0284c7; }
        """)
        self.btn_open.clicked.connect(self._on_open_image)
        toolbar.addWidget(self.btn_open)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Splitter principal
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(2)

        # LEFT: Imagens
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        self.lbl_img_original = self._make_image_panel("Imagem Original")
        self.lbl_img_detection = self._make_image_panel("Detecção de Feridas")
        self.lbl_img_segmentation = self._make_image_panel("Mapa de Segmentação")
        self.lbl_img_overlay = self._make_image_panel("Overlay Tecidual")
        self.lbl_img_gradcam = self._make_image_panel("Grad-CAM (Explicabilidade)")

        img_grid = QHBoxLayout()
        col1 = QVBoxLayout()
        col1.addWidget(self.lbl_img_original)
        col1.addWidget(self.lbl_img_segmentation)
        col1.addWidget(self.lbl_img_gradcam)
        col2 = QVBoxLayout()
        col2.addWidget(self.lbl_img_detection)
        col2.addWidget(self.lbl_img_overlay)
        img_grid.addLayout(col1)
        img_grid.addLayout(col2)
        left_layout.addLayout(img_grid)

        splitter.addWidget(left)

        # RIGHT: Laudo
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: #0f172a;
            }
            QScrollBar:vertical {
                background: #0f172a;
                width: 8px;
                margin: 4px 2px;
            }
            QScrollBar::handle:vertical {
                background: #475569;
                border-radius: 4px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: #64748b;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        self.right_panel = QWidget()
        self.right_panel.setStyleSheet("background: #0f172a;")
        self.right_layout = QVBoxLayout(self.right_panel)
        self.right_layout.setContentsMargins(10, 8, 10, 10)
        self.right_layout.setSpacing(10)
        self.right_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Placeholder
        self.lbl_placeholder = QLabel(
            "Abra uma imagem de ferida para iniciar a análise clínica.\n\n"
            "Formatos suportados: JPG, PNG, BMP, TIFF\n\n"
            "O sistema irá classificar o tecido predominante em:\n"
            "  • Necrose de Coagulação (Escara)\n"
            "  • Esfacelo (Fibrina)\n"
            "  • Tecido de Granulação\n"
            "  • Epitelização"
        )
        self.lbl_placeholder.setFont(QFont("Segoe UI", 11))
        self.lbl_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_placeholder.setStyleSheet("""
            color: #64748b;
            padding: 40px;
            background: #0f172a;
        """)
        self.lbl_placeholder.setWordWrap(True)
        self.right_layout.addWidget(self.lbl_placeholder)

        right_scroll.setWidget(self.right_panel)
        splitter.addWidget(right_scroll)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, stretch=1)

    # -------------------------------------------------------
    def _setup_webcam_tab(self):
        """Configura aba de análise em tempo real (webcam)."""
        layout = QVBoxLayout(self.tab_webcam)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Toolbar da aba
        toolbar = QHBoxLayout()

        # Botão iniciar/parar webcam
        self.btn_webcam = QPushButton("Iniciar Detecção em Tempo Real")
        self.btn_webcam.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.btn_webcam.setMinimumHeight(40)
        self.btn_webcam.setMinimumWidth(260)
        self.btn_webcam.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_webcam.setStyleSheet("""
            QPushButton {
                background: #16a34a;
                color: white; border: none; border-radius: 6px;
                padding: 0 24px; font-size: 13px;
            }
            QPushButton:hover { background: #22c55e; }
            QPushButton:pressed { background: #15803d; }
        """)
        self.btn_webcam.clicked.connect(self._toggle_webcam)
        toolbar.addWidget(self.btn_webcam)

        # Seletor de câmera
        toolbar.addSpacing(10)
        toolbar.addWidget(self._styled_label("Câmera:", "#94a3b8", 10))
        self.combo_camera = QComboBox()
        self.combo_camera.addItems(["0 (Padrão)", "1", "2", "3"])
        self.combo_camera.setMinimumWidth(100)
        self.combo_camera.setStyleSheet("""
            QComboBox {
                background: #334155; color: #e2e8f0; border: 1px solid #475569;
                border-radius: 6px; padding: 6px 12px;
            }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView { background: #1e293b; color: #e2e8f0; }
        """)
        toolbar.addWidget(self.combo_camera)

        # Indicador de status
        toolbar.addSpacing(20)
        self.lbl_rt_status = QLabel("Parado")
        self.lbl_rt_status.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.lbl_rt_status.setStyleSheet("color: #64748b;")
        toolbar.addWidget(self.lbl_rt_status)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Splitter principal
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(2)

        # LEFT: Feed da webcam
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        self.lbl_webcam_feed = QLabel("Clique em \"Iniciar Detecção\" para análise em tempo real")
        self.lbl_webcam_feed.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_webcam_feed.setMinimumSize(640, 480)
        self.lbl_webcam_feed.setFont(QFont("Segoe UI", 13))
        self.lbl_webcam_feed.setStyleSheet("""
            QLabel {
                background: #0f172a;
                border: 1px solid #334155;
                border-radius: 8px;
                color: #64748b;
            }
        """)
        left_layout.addWidget(self.lbl_webcam_feed, stretch=3)

        # Imagens de análise em tempo real
        rt_grid = QHBoxLayout()
        self.lbl_rt_segmentation = self._make_image_panel("Segmentação Tecidual")
        self.lbl_rt_overlay = self._make_image_panel("Overlay Clínico")
        rt_grid.addWidget(self.lbl_rt_segmentation)
        rt_grid.addWidget(self.lbl_rt_overlay)
        left_layout.addLayout(rt_grid, stretch=1)

        splitter.addWidget(left)

        # RIGHT: Laudo em tempo real
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: #0f172a;
            }
            QScrollBar:vertical {
                background: #0f172a;
                width: 8px;
                margin: 4px 2px;
            }
            QScrollBar::handle:vertical {
                background: #475569;
                border-radius: 4px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: #64748b;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        self.rt_right_panel = QWidget()
        self.rt_right_panel.setStyleSheet("background: #0f172a;")
        self.rt_right_layout = QVBoxLayout(self.rt_right_panel)
        self.rt_right_layout.setContentsMargins(10, 8, 10, 10)
        self.rt_right_layout.setSpacing(10)
        self.rt_right_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Placeholder
        self.rt_placeholder = QLabel(
            "Detecção e classificação de feridas em tempo real.\n\n"
            "Ao iniciar:\n"
            "  • Detecção de feridas a cada frame (bounding boxes)\n"
            "  • Classificação tecidual automática contínua\n"
            "  • Laudo clínico atualizado em tempo real\n\n"
            "Basta apontar a câmera para a ferida."
        )
        self.rt_placeholder.setFont(QFont("Segoe UI", 11))
        self.rt_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rt_placeholder.setStyleSheet("""
            color: #64748b;
            padding: 40px;
            background: #0f172a;
        """)
        self.rt_placeholder.setWordWrap(True)
        self.rt_right_layout.addWidget(self.rt_placeholder)

        right_scroll.setWidget(self.rt_right_panel)
        splitter.addWidget(right_scroll)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, stretch=1)

    # -------------------------------------------------------
    def _on_tab_changed(self, index: int):
        """Callback quando troca de aba."""
        if index == 0:
            # Aba de imagem - para webcam se estiver ativa
            if self._webcam_active:
                self._stop_webcam()
            self.lbl_status.setText("Modo: Arquivo de Imagem")
        else:
            # Aba de tempo real
            self.lbl_status.setText("Modo: Tempo Real (Webcam)")

    # -------------------------------------------------------
    # WEBCAM METHODS
    # -------------------------------------------------------
    def _toggle_webcam(self):
        """Liga/desliga a webcam."""
        if self._webcam_active:
            self._stop_webcam()
        else:
            self._start_webcam()

    def _start_webcam(self):
        """Inicia detecção em tempo real."""
        camera_id = self.combo_camera.currentIndex()

        # Cria analyzer reutilizável (uma vez)
        if self._rt_analyzer is None:
            self.lbl_status.setText("Carregando motor de análise...")
            self.lbl_status.setStyleSheet("color: #fbbf24;")
            QApplication.processEvents()
            self._rt_analyzer = ClinicalWoundAnalyzer()

        self._webcam_thread = WebcamThread(camera_id, parent=self)
        # QueuedConnection garante que signals são processados na main thread
        self._webcam_thread.frame_ready.connect(self._on_frame_ready, Qt.ConnectionType.QueuedConnection)
        self._webcam_thread.error.connect(self._on_webcam_error, Qt.ConnectionType.QueuedConnection)
        self._webcam_thread.start()

        self._webcam_active = True
        self.btn_webcam.setText("Parar Detecção")
        self.btn_webcam.setStyleSheet("""
            QPushButton {
                background: #dc2626;
                color: white; border: none; border-radius: 6px;
                padding: 0 24px; font-size: 13px;
            }
            QPushButton:hover { background: #ef4444; }
            QPushButton:pressed { background: #b91c1c; }
        """)
        self.combo_camera.setEnabled(False)
        self.lbl_rt_status.setText("Escaneando")
        self.lbl_rt_status.setStyleSheet("color: #22c55e;")
        self.lbl_status.setText("Detecção em tempo real ativa — aponte a câmera para a ferida")
        self.lbl_status.setStyleSheet("color: #22c55e;")

    def _stop_webcam(self):
        """Para detecção em tempo real com shutdown seguro."""
        self._webcam_active = False

        # 1. DESCONECTA SIGNALS PRIMEIRO (impede novos callbacks durante cleanup)
        if self._webcam_thread is not None:
            try:
                self._webcam_thread.frame_ready.disconnect(self._on_frame_ready)
                self._webcam_thread.error.disconnect(self._on_webcam_error)
            except (TypeError, RuntimeError):
                pass  # Já desconectados ou objeto inválido

        # 2. Para a thread da webcam
        if self._webcam_thread is not None:
            self._webcam_thread.stop()  # seta _running=False + wait
            # NÃO define como None imediatamente; deleteLater cuidará disso
            wt = self._webcam_thread
            self._webcam_thread = None
            # Processa eventos pendentes para permitir deleteLater
            QApplication.processEvents()

        # 3. Para a thread de análise clínica (se estiver rodando)
        if self._realtime_thread is not None:
            try:
                self._realtime_thread.result_ready.disconnect(self._on_realtime_analysis_done)
            except (TypeError, RuntimeError):
                pass
            self._realtime_thread.cancel()
            if self._realtime_thread.isRunning():
                if not self._realtime_thread.wait(5000):
                    self._realtime_thread.terminate()
                    self._realtime_thread.wait(1000)
            self._realtime_thread = None
        self.btn_webcam.setText("Iniciar Detecção em Tempo Real")
        self.btn_webcam.setStyleSheet("""
            QPushButton {
                background: #16a34a;
                color: white; border: none; border-radius: 6px;
                padding: 0 24px; font-size: 13px;
            }
            QPushButton:hover { background: #22c55e; }
            QPushButton:pressed { background: #15803d; }
        """)
        self.combo_camera.setEnabled(True)
        self.lbl_webcam_feed.setText("Clique em \"Iniciar Detecção\" para análise em tempo real")
        self.lbl_webcam_feed.setPixmap(QPixmap())
        self.lbl_rt_status.setText("Parado")
        self.lbl_rt_status.setStyleSheet("color: #64748b;")
        self.lbl_status.setText("Detecção parada")
        self.lbl_status.setStyleSheet("color: #94a3b8;")

    def _on_frame_ready(self, annotated_frame: np.ndarray, raw_frame: np.ndarray):
        """Callback quando um frame com detecção está pronto."""
        # Guard: ignora se webcam já foi parada (signal pode ter chegado após stop)
        if not self._webcam_active or self._webcam_thread is None:
            return

        self._last_frame = raw_frame

        # Exibe frame anotado (já tem bounding boxes do detector)
        pixmap = np_to_qpixmap(annotated_frame, max_w=900)
        self.lbl_webcam_feed.setPixmap(pixmap)

        # Dispara análise clínica completa automaticamente a cada intervalo
        # Verifica que não há thread de análise ativa E que analyzer foi inicializado
        if self._webcam_active and self._realtime_thread is None and self._rt_analyzer is not None:
            current_time = time.time() * 1000
            if current_time - self._last_analysis_time > self._analysis_interval_ms:
                self._last_analysis_time = current_time
                thread = RealtimeAnalysisThread(raw_frame, self._rt_analyzer, parent=self)
                thread.result_ready.connect(self._on_realtime_analysis_done, Qt.ConnectionType.QueuedConnection)
                self._realtime_thread = thread  # referência forte antes de start()
                thread.start()

    def _on_webcam_error(self, error: str):
        """Callback de erro da webcam."""
        self.lbl_status.setText(f"Erro: {error}")
        self.lbl_status.setStyleSheet("color: #ef4444;")
        self.lbl_rt_status.setText("Erro")
        self.lbl_rt_status.setStyleSheet("color: #ef4444;")
        self._stop_webcam()

    def _on_realtime_analysis_done(self, report: ClinicalReport):
        """Callback quando análise clínica completa termina."""
        # Guard: ignora se webcam foi parada durante a análise
        if not self._webcam_active:
            self._realtime_thread = None
            return

        # Permite que a próxima análise seja agendada.
        # deleteLater (connected no __init__) cuida da limpeza segura do QThread.
        self._realtime_thread = None

        if not report.is_valid_wound:
            # Não mostra erro, apenas continua escaneando
            self.lbl_rt_status.setText("Escaneando (sem ferida)")
            self.lbl_rt_status.setStyleSheet("color: #f59e0b;")
            return

        # Monta status realtime com ResNet50
        rt_resnet_tag = ""
        if report.resnet_prediction:
            rn = report.resnet_prediction
            final_pt = rn.get("final_class_pt", "")
            if final_pt:
                rt_resnet_tag = f"  |  {final_pt}"

        self.lbl_rt_status.setText("Ferida detectada")
        self.lbl_rt_status.setStyleSheet("color: #22c55e;")
        self.lbl_status.setText(
            f"Ferida: {report.primary_tissue}  |  Score: {report.health_score:.0f}/100{rt_resnet_tag}  |  {report.processing_time_ms:.0f}ms"
        )
        self.lbl_status.setStyleSheet("color: #22c55e;")

        # Atualiza imagens de análise
        if report.segmentation_map is not None:
            self.lbl_rt_segmentation.setPixmap(np_to_qpixmap(report.segmentation_map, 350))
        if report.tissue_overlay is not None:
            self.lbl_rt_overlay.setPixmap(np_to_qpixmap(report.tissue_overlay, 350))

        # Atualiza laudo
        self._show_realtime_results(report)

    def _show_realtime_results(self, r: ClinicalReport):
        """Exibe resultados da análise em tempo real."""
        self._clear_rt_right_panel()

        # Classificação principal
        box_main = self._make_group("CLASSIFICAÇÃO")
        lbl_primary = QLabel(r.primary_tissue)
        lbl_primary.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        lbl_primary.setStyleSheet("color: #38bdf8; padding: 2px 0;")
        box_main.layout().addWidget(lbl_primary)

        # Score
        score_color = "#22c55e" if r.health_score >= 60 else ("#fbbf24" if r.health_score >= 30 else "#ef4444")
        score_row = QWidget()
        sl = QHBoxLayout(score_row)
        sl.setContentsMargins(0, 2, 0, 0)
        sl.addWidget(self._styled_label("Score:", "#94a3b8", 10))
        sl.addWidget(self._styled_label(f"{r.health_score:.0f}/100", score_color, 12, bold=True))
        sl.addStretch()
        box_main.layout().addWidget(score_row)

        self.rt_right_layout.addWidget(box_main)

        # Composição tecidual
        box_tissue = self._make_group("TECIDOS")
        for t in sorted(r.tissues, key=lambda x: -x.percentage):
            if t.percentage > 1:
                row = QWidget()
                rl = QHBoxLayout(row)
                rl.setContentsMargins(0, 1, 0, 1)
                swatch = QLabel()
                swatch.setFixedSize(10, 10)
                swatch.setStyleSheet(f"background: {t.color_hex}; border-radius: 2px;")
                rl.addWidget(swatch)
                # Trunca de forma segura para UTF-8 (sem cortar no meio de caractere)
                tissue_name = t.name if len(t.name) <= 25 else t.name[:22] + "..."
                rl.addWidget(self._styled_label(tissue_name, "#e2e8f0", 9))
                rl.addStretch()
                rl.addWidget(self._styled_label(f"{t.percentage:.0f}%", "#38bdf8", 9, bold=True))
                box_tissue.layout().addWidget(row)
        self.rt_right_layout.addWidget(box_tissue)

        # DL prediction
        if r.dl_prediction:
            box_dl = self._make_group("IA")
            dl = r.dl_prediction
            conf = dl.get("confidence", 0)
            conf_color = "#22c55e" if conf >= 0.7 else ("#fbbf24" if conf >= 0.4 else "#ef4444")
            lbl_cls = QLabel(f"{dl.get('display_name', 'N/A')} ({conf:.0%})")
            lbl_cls.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            lbl_cls.setStyleSheet(f"color: {conf_color};")
            box_dl.layout().addWidget(lbl_cls)
            self.rt_right_layout.addWidget(box_dl)

        # ResNet50 Two-Stage prediction (tempo real)
        if r.resnet_prediction:
            rn = r.resnet_prediction
            box_rn = self._make_group("ETIOLOGIA (ResNet50)")

            s1 = rn.get("stage1", {})
            if s1:
                s1_wound = s1.get("is_wound", True)
                s1_conf = s1.get("confidence", 0)
                s1_text = "Ferida" if s1_wound else "Normal"
                s1_color = "#ef4444" if s1_wound else "#22c55e"
                s1_row = QWidget()
                s1l = QHBoxLayout(s1_row)
                s1l.setContentsMargins(0, 1, 0, 1)
                s1l.addWidget(self._styled_label("Triagem:", "#94a3b8", 9))
                s1l.addWidget(self._styled_label(f"{s1_text} ({s1_conf:.0%})", s1_color, 9, bold=True))
                s1l.addStretch()
                box_rn.layout().addWidget(s1_row)

            s2 = rn.get("stage2", {})
            if s2:
                s2_pt = s2.get("wound_type_pt", "")
                s2_conf = s2.get("confidence", 0)
                s2_color = "#22c55e" if s2_conf >= 0.7 else ("#fbbf24" if s2_conf >= 0.45 else "#ef4444")
                lbl_type = QLabel(f"{s2_pt} ({s2_conf:.0%})")
                lbl_type.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
                lbl_type.setStyleSheet(f"color: {s2_color};")
                box_rn.layout().addWidget(lbl_type)

            self.rt_right_layout.addWidget(box_rn)

        # Ação clínica
        box_action = self._make_group("AÇÃO CLÍNICA")
        dominant = max(r.tissues, key=lambda x: x.percentage)
        lbl_act = QLabel(dominant.clinical_action[:150] + "..." if len(dominant.clinical_action) > 150 else dominant.clinical_action)
        lbl_act.setWordWrap(True)
        lbl_act.setFont(QFont("Segoe UI", 9))
        lbl_act.setStyleSheet("color: #cbd5e1;")
        box_action.layout().addWidget(lbl_act)
        self.rt_right_layout.addWidget(box_action)

        # Escalas Clínicas (PUSH e BWAT) - versão compacta para tempo real
        if HAS_CLINICAL_SCALES and (r.push_score is not None or r.bwat_score is not None):
            box_scales = self._make_group("ESCALAS")
            
            # PUSH Score compacto
            if r.push_score is not None:
                push_total = r.push_score.get("total_score", 0)
                push_row = QWidget()
                pl = QHBoxLayout(push_row)
                pl.setContentsMargins(0, 1, 0, 1)
                pl.addWidget(self._styled_label("PUSH:", "#94a3b8", 9))
                push_color = "#22c55e" if push_total <= 5 else ("#fbbf24" if push_total <= 10 else "#ef4444")
                pl.addWidget(self._styled_label(f"{push_total}/17", push_color, 10, bold=True))
                pl.addStretch()
                box_scales.layout().addWidget(push_row)
            
            # BWAT Score compacto
            if r.bwat_score is not None:
                bwat_total = r.bwat_score.get("total_score", 0)
                severity = r.bwat_score.get("severity", "")
                bwat_row = QWidget()
                bl = QHBoxLayout(bwat_row)
                bl.setContentsMargins(0, 1, 0, 1)
                bl.addWidget(self._styled_label("BWAT:", "#94a3b8", 9))
                bwat_color = "#22c55e" if bwat_total <= 20 else ("#fbbf24" if bwat_total <= 35 else "#ef4444")
                bl.addWidget(self._styled_label(f"{bwat_total}/65 ({severity})", bwat_color, 10, bold=True))
                bl.addStretch()
                box_scales.layout().addWidget(bwat_row)
            
            self.rt_right_layout.addWidget(box_scales)

        self.rt_right_layout.addStretch()

    def _clear_rt_right_panel(self):
        """Limpa painel direito da aba tempo real."""
        while self.rt_right_layout.count():
            w = self.rt_right_layout.takeAt(0).widget()
            if w:
                w.deleteLater()

    # -------------------------------------------------------
    # ACTIONS
    # -------------------------------------------------------
    def _on_open_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar Imagem de Ferida",
            str(Path(__file__).parent / "dataset"),
            "Imagens (*.jpg *.jpeg *.png *.bmp *.tif *.tiff);;Todos (*)",
        )
        if not path:
            return

        self.lbl_status.setText(f"Analisando: {Path(path).name}")
        self.lbl_status.setStyleSheet("color: #fbbf24;")
        self.progress.setVisible(True)
        self.btn_open.setEnabled(False)

        self._thread = AnalysisThread(path, parent=self)
        self._thread.progress.connect(self._on_progress, Qt.ConnectionType.QueuedConnection)
        self._thread.result_ready.connect(self._on_analysis_done, Qt.ConnectionType.QueuedConnection)
        self._thread.start()

    def _on_progress(self, msg: str):
        self.lbl_status.setText(msg)

    def _on_analysis_done(self, report: ClinicalReport):
        self.progress.setVisible(False)
        self.btn_open.setEnabled(True)
        self._current_report = report

        if not report.is_valid_wound:
            self.lbl_status.setText("Análise concluída — Input Inválido")
            self.lbl_status.setStyleSheet("color: #ef4444;")
            self._show_invalid(report)
            return

        # Monta status final com ResNet50 se disponível
        resnet_tag = ""
        if report.resnet_prediction:
            rn = report.resnet_prediction
            final_pt = rn.get("final_class_pt", "")
            final_conf = rn.get("final_confidence", 0)
            if final_pt:
                resnet_tag = f"  |  Etiologia: {final_pt} ({final_conf:.0%})"

        self.lbl_status.setText(
            f"Análise concluída  |  {report.processing_time_ms:.0f}ms  |  "
            f"Tecido: {report.primary_tissue}{resnet_tag}"
        )
        self.lbl_status.setStyleSheet("color: #22c55e;")
        self._show_results(report)

    # -------------------------------------------------------
    def _show_invalid(self, report: ClinicalReport):
        if report.original is not None:
            self.lbl_img_original.setPixmap(np_to_qpixmap(report.original, 400))
        self._clear_right_panel()
        lbl = QLabel(report.rejection_reason)
        lbl.setFont(QFont("Segoe UI", 13))
        lbl.setWordWrap(True)
        lbl.setStyleSheet("color: #ef4444; padding: 30px;")
        self.right_layout.addWidget(lbl)

    # -------------------------------------------------------
    def _show_results(self, r: ClinicalReport):
        # Imagens
        if r.original is not None:
            self.lbl_img_original.setPixmap(np_to_qpixmap(r.original, 400))
        if r.detection_overlay is not None:
            self.lbl_img_detection.setPixmap(np_to_qpixmap(r.detection_overlay, 400))
        if r.segmentation_map is not None:
            self.lbl_img_segmentation.setPixmap(np_to_qpixmap(r.segmentation_map, 400))
        if r.tissue_overlay is not None:
            self.lbl_img_overlay.setPixmap(np_to_qpixmap(r.tissue_overlay, 400))
        if r.grad_cam_overlay is not None:
            self.lbl_img_gradcam.setPixmap(np_to_qpixmap(r.grad_cam_overlay, 400))
        else:
            self.lbl_img_gradcam.setText("Grad-CAM (modelo não carregado)")

        self._clear_right_panel()

        # --- CLASSIFICAÇÃO PRINCIPAL ---
        box_main = self._make_group("CLASSIFICAÇÃO PRINCIPAL")
        
        # Layout horizontal para texto
        main_hl = QHBoxLayout()
        
        # Texto da classificação
        text_vl = QVBoxLayout()
        # Cor dinâmica baseada no tecido
        tissue_colors = {
            "Tecido de Granulação": "#22c55e",
            "Epitelização": "#a78bfa",
            "Esfacelo (Fibrina)": "#fbbf24",
            "Necrose de Coagulação (Escara)": "#ef4444",
        }
        primary_color = tissue_colors.get(r.primary_tissue, "#38bdf8")

        lbl_primary = QLabel(r.primary_tissue)
        lbl_primary.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        lbl_primary.setStyleSheet(f"color: {primary_color}; padding: 0px;")
        text_vl.addWidget(lbl_primary)

        lbl_just = QLabel(r.primary_justification)
        lbl_just.setWordWrap(True)
        lbl_just.setFont(QFont("Segoe UI", 10))
        lbl_just.setStyleSheet("color: #cbd5e1; padding: 2px 0 6px; line-height: 1.4;")
        text_vl.addWidget(lbl_just)
        
        main_hl.addLayout(text_vl)
        box_main.layout().addLayout(main_hl)
        self.right_layout.addWidget(box_main)

        # --- COMPOSIÇÃO TECIDUAL ---
        box_tissue = self._make_group("COMPOSIÇÃO TECIDUAL")
        for t in sorted(r.tissues, key=lambda x: -x.percentage):
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 2, 0, 2)

            # Cor
            swatch = QLabel()
            swatch.setFixedSize(14, 14)
            swatch.setStyleSheet(f"background: {t.color_hex}; border-radius: 3px; border: 1px solid #475569;")
            rl.addWidget(swatch)

            # Nome + %
            rl.addWidget(self._styled_label(t.name, "#e2e8f0", 10))
            rl.addStretch()
            rl.addWidget(self._styled_label(f"{t.percentage:.1f}%", "#38bdf8", 10, bold=True))

            box_tissue.layout().addWidget(row)

            # Barra
            bar_bg = QFrame()
            bar_bg.setFixedHeight(8)
            bar_bg.setStyleSheet("background: #0f172a; border-radius: 4px;")
            bar_inner = QFrame(bar_bg)
            bar_inner.setFixedHeight(8)
            pct_clamped = min(t.percentage, 100)
            bar_inner.setFixedWidth(max(int(pct_clamped * 2.5), 1))
            bar_inner.setStyleSheet(f"background: {t.color_hex}; border-radius: 4px;")
            box_tissue.layout().addWidget(bar_bg)

        # Score
        score_row = QWidget()
        score_color = "#22c55e" if r.health_score >= 60 else ("#fbbf24" if r.health_score >= 30 else "#ef4444")
        score_row.setStyleSheet("""
            QWidget {
                background: #0f172a;
                border: 1px solid #334155;
                border-radius: 6px;
                margin-top: 6px;
            }
        """)
        sl = QHBoxLayout(score_row)
        sl.setContentsMargins(12, 8, 12, 8)
        sl.addWidget(self._styled_label("Score de Saúde:", "#94a3b8", 11))
        sl.addWidget(self._styled_label(f"{r.health_score:.0f}/100", score_color, 14, bold=True))
        sl.addStretch()
        box_tissue.layout().addWidget(score_row)

        self.right_layout.addWidget(box_tissue)

        # --- CLASSIFICAÇÃO IA (Deep Learning) ---
        if r.dl_prediction:
            box_dl = self._make_group("CLASSIFICAÇÃO IA (Deep Learning)")
            dl = r.dl_prediction

            # Classe principal
            lbl_cls = QLabel(dl.get("display_name", "N/A"))
            lbl_cls.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
            conf = dl.get("confidence", 0)
            conf_color = "#22c55e" if conf >= 0.7 else ("#fbbf24" if conf >= 0.4 else "#ef4444")
            lbl_cls.setStyleSheet(f"color: {conf_color}; padding: 4px 0;")
            box_dl.layout().addWidget(lbl_cls)

            # Confiança
            conf_row = QWidget()
            cl = QHBoxLayout(conf_row)
            cl.setContentsMargins(0, 2, 0, 2)
            cl.addWidget(self._styled_label("Confiança:", "#94a3b8", 10))
            cl.addWidget(self._styled_label(f"{conf:.1%}", conf_color, 11, bold=True))
            cl.addStretch()
            box_dl.layout().addWidget(conf_row)

            # Top-3 predictions
            top3 = dl.get("top3", [])
            if len(top3) > 1:
                box_dl.layout().addWidget(self._styled_label("Diagnósticos diferenciais:", "#64748b", 9))
                for pred in top3[1:]:
                    p_conf = pred.get("confidence", 0)
                    p_name = pred.get("display", pred.get("class", ""))
                    row = QWidget()
                    rl = QHBoxLayout(row)
                    rl.setContentsMargins(8, 0, 0, 0)
                    rl.addWidget(self._styled_label(f"• {p_name}", "#94a3b8", 9))
                    rl.addStretch()
                    rl.addWidget(self._styled_label(f"{p_conf:.1%}", "#64748b", 9))
                    box_dl.layout().addWidget(row)

            # Nota sobre modelo
            if conf < 0.5:
                note = QLabel("Confiança baixa — recomenda-se avaliação por especialista")
                note.setWordWrap(True)
                note.setFont(QFont("Segoe UI", 9))
                note.setStyleSheet("color: #fbbf24; padding-top: 4px;")
                box_dl.layout().addWidget(note)

            self.right_layout.addWidget(box_dl)

        # --- CLASSIFICAÇÃO RESNET50 (Dois Estágios) ---
        if r.resnet_prediction:
            rn = r.resnet_prediction
            box_rn = self._make_group("CLASSIFICAÇÃO ETIOLÓGICA (ResNet50)")

            # Estágio 1 — Normal vs Ferida
            s1 = rn.get("stage1", {})
            if s1:
                s1_conf = s1.get("confidence", 0)
                s1_wound = s1.get("is_wound", True)
                s1_text = "Ferida Detectada" if s1_wound else "Pele Normal"
                s1_color = "#ef4444" if s1_wound else "#22c55e"

                s1_row = QWidget()
                s1l = QHBoxLayout(s1_row)
                s1l.setContentsMargins(0, 2, 0, 2)
                s1l.addWidget(self._styled_label("Triagem:", "#94a3b8", 10))
                s1l.addWidget(self._styled_label(s1_text, s1_color, 11, bold=True))
                s1l.addWidget(self._styled_label(f"({s1_conf:.0%})", "#64748b", 9))
                s1l.addStretch()
                box_rn.layout().addWidget(s1_row)

            # Estágio 2 — Tipo de Ferida
            s2 = rn.get("stage2", {})
            if s2:
                wound_type_pt = s2.get("wound_type_pt", "")
                s2_conf = s2.get("confidence", 0)
                s2_color = "#22c55e" if s2_conf >= 0.7 else ("#fbbf24" if s2_conf >= 0.45 else "#ef4444")

                lbl_type = QLabel(wound_type_pt)
                lbl_type.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
                lbl_type.setStyleSheet(f"color: {s2_color}; padding: 4px 0;")
                box_rn.layout().addWidget(lbl_type)

                # Confiança
                conf_row = QWidget()
                crl = QHBoxLayout(conf_row)
                crl.setContentsMargins(0, 2, 0, 2)
                crl.addWidget(self._styled_label("Confiança:", "#94a3b8", 10))
                crl.addWidget(self._styled_label(f"{s2_conf:.1%}", s2_color, 11, bold=True))
                crl.addStretch()
                box_rn.layout().addWidget(conf_row)

                # Diagnósticos diferenciais
                top_preds = s2.get("top_predictions", [])
                if len(top_preds) > 1:
                    box_rn.layout().addWidget(self._styled_label("Diagnósticos diferenciais:", "#64748b", 9))
                    for pred in top_preds[1:]:
                        p_conf = pred.get("confidence", 0)
                        p_name = pred.get("class_pt", pred.get("class", ""))
                        row = QWidget()
                        rl = QHBoxLayout(row)
                        rl.setContentsMargins(8, 0, 0, 0)
                        rl.addWidget(self._styled_label(f"• {p_name}", "#94a3b8", 9))
                        rl.addStretch()
                        rl.addWidget(self._styled_label(f"{p_conf:.1%}", "#64748b", 9))
                        box_rn.layout().addWidget(row)

            # Ação clínica específica da etiologia
            clinical_action = rn.get("clinical_action", "")
            if clinical_action:
                lbl_action = QLabel(clinical_action)
                lbl_action.setWordWrap(True)
                lbl_action.setFont(QFont("Segoe UI", 9))
                lbl_action.setStyleSheet("color: #cbd5e1; padding-top: 6px;")
                box_rn.layout().addWidget(lbl_action)

            # Nota de confiança baixa
            final_conf = rn.get("final_confidence", 0)
            if final_conf < 0.5:
                note = QLabel("Confiança baixa — recomenda-se avaliação por especialista em estomaterapia")
                note.setWordWrap(True)
                note.setFont(QFont("Segoe UI", 9))
                note.setStyleSheet("color: #fbbf24; padding-top: 4px;")
                box_rn.layout().addWidget(note)

            self.right_layout.addWidget(box_rn)

        # --- GRAD-CAM (Explicabilidade) ---
        if r.grad_cam_overlay is not None:
            box_gcam = self._make_group("GRAD-CAM (Explicabilidade IA)")
            lbl_gcam_desc = QLabel(
                "Mapa de calor indicando as regiões da imagem que mais "
                "influenciaram a decisão do modelo de classificação."
            )
            lbl_gcam_desc.setWordWrap(True)
            lbl_gcam_desc.setFont(QFont("Segoe UI", 9))
            lbl_gcam_desc.setStyleSheet("color: #94a3b8;")
            box_gcam.layout().addWidget(lbl_gcam_desc)

            lbl_gcam_img = QLabel()
            lbl_gcam_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_gcam_img.setPixmap(np_to_qpixmap(r.grad_cam_overlay, 320))
            lbl_gcam_img.setStyleSheet("border: 1px solid #334155; border-radius: 4px; padding: 4px;")
            box_gcam.layout().addWidget(lbl_gcam_img)
            self.right_layout.addWidget(box_gcam)

        # --- ENSEMBLE MULTI-MODELO (IA Pré-Treinada) ---
        if r.ensemble_classification:
            box_ens = self._make_group("ENSEMBLE MULTI-MODELO (IA Pré-Treinada)")
            ec = r.ensemble_classification

            # Classe principal
            ens_name = ec.get("class_name", "N/A")
            ens_conf = ec.get("confidence", 0)
            ens_color = "#22c55e" if ens_conf >= 0.7 else ("#fbbf24" if ens_conf >= 0.4 else "#ef4444")

            lbl_ens = QLabel(ens_name)
            lbl_ens.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
            lbl_ens.setStyleSheet(f"color: {ens_color}; padding: 4px 0;")
            box_ens.layout().addWidget(lbl_ens)

            # Confiança + agreement
            conf_row = QWidget()
            cr = QHBoxLayout(conf_row)
            cr.setContentsMargins(0, 2, 0, 2)
            cr.addWidget(self._styled_label("Confiança ensemble:", "#94a3b8", 10))
            cr.addWidget(self._styled_label(f"{ens_conf:.1%}", ens_color, 11, bold=True))
            cr.addStretch()
            box_ens.layout().addWidget(conf_row)

            # Agreement
            if r.ensemble_agreement:
                agr = r.ensemble_agreement
                agr_score = agr.get("agreement_score", 0)
                agr_icon = "Concordam" if agr.get("models_agree") else "Divergem"
                agr_color = "#22c55e" if agr.get("models_agree") else "#fbbf24"

                agr_row = QWidget()
                al = QHBoxLayout(agr_row)
                al.setContentsMargins(0, 2, 0, 2)
                al.addWidget(self._styled_label(f"Modelos: {agr_icon} ({agr_score:.0%})", agr_color, 10))
                al.addStretch()
                box_ens.layout().addWidget(agr_row)

                # Predições individuais
                indiv = agr.get("individual_predictions", {})
                if indiv:
                    box_ens.layout().addWidget(self._styled_label("Predições por modelo:", "#64748b", 9))
                    for model_name, pred_cls in indiv.items():
                        row = QWidget()
                        rl = QHBoxLayout(row)
                        rl.setContentsMargins(8, 0, 0, 0)
                        rl.addWidget(self._styled_label(f"• {model_name}:", "#94a3b8", 9))
                        rl.addWidget(self._styled_label(pred_cls, "#e2e8f0", 9, bold=True))
                        rl.addStretch()
                        box_ens.layout().addWidget(row)

            # Modelos carregados
            if r.ensemble_models_loaded:
                loaded_str = ", ".join(
                    f"{k}={'OK' if v else 'OFF'}" for k, v in r.ensemble_models_loaded.items()
                )
                box_ens.layout().addWidget(self._styled_label(f"Modelos: {loaded_str}", "#475569", 8))

            # Probabilidades
            all_probs = ec.get("all_probabilities", {})
            if all_probs:
                box_ens.layout().addWidget(self._styled_label("Probabilidades:", "#64748b", 9))
                etiology_names = {
                    0: "Úlcera Venosa", 1: "Úlcera Arterial", 2: "Pé Diabético",
                    3: "Lesão por Pressão", 4: "Ferida Cirúrgica"
                }
                sorted_probs = sorted(all_probs.items(), key=lambda x: x[1], reverse=True)
                for cid_str, prob in sorted_probs:
                    cid = int(cid_str) if isinstance(cid_str, str) else cid_str
                    name = etiology_names.get(cid, f"Classe {cid}")
                    p_color = "#22c55e" if prob >= 0.3 else "#94a3b8"
                    row = QWidget()
                    rl = QHBoxLayout(row)
                    rl.setContentsMargins(8, 0, 0, 0)
                    rl.addWidget(self._styled_label(f"• {name}", "#94a3b8", 9))
                    rl.addStretch()
                    rl.addWidget(self._styled_label(f"{prob:.1%}", p_color, 9))
                    box_ens.layout().addWidget(row)

            self.right_layout.addWidget(box_ens)

        # --- ANÁLISE DE INFECÇÃO E GRAVIDADE (BiomedCLIP) ---
        if r.ensemble_infection or r.ensemble_severity is not None:
            box_inf = self._make_group("ANÁLISE DE INFECÇÃO E GRAVIDADE")

            # Severidade
            if r.ensemble_severity is not None:
                sev = r.ensemble_severity
                if sev < 0.25:
                    sev_text, sev_color = "Leve", "#22c55e"
                elif sev < 0.50:
                    sev_text, sev_color = "Moderada", "#fbbf24"
                elif sev < 0.75:
                    sev_text, sev_color = "Grave", "#f97316"
                else:
                    sev_text, sev_color = "Crítica", "#ef4444"

                sev_row = QWidget()
                sl = QHBoxLayout(sev_row)
                sl.setContentsMargins(0, 2, 0, 2)
                sl.addWidget(self._styled_label("Gravidade:", "#94a3b8", 10))
                sl.addWidget(self._styled_label(f"{sev_text} ({sev:.0%})", sev_color, 11, bold=True))
                sl.addStretch()
                box_inf.layout().addWidget(sev_row)

            # Infecção
            if r.ensemble_infection:
                inf_scores = r.ensemble_infection
                infected = inf_scores.get("Infectada", 0) + inf_scores.get("Celulite", 0)
                clean = inf_scores.get("Limpa", 0)
                risk = infected / (infected + clean + 1e-8)

                if risk >= 0.6:
                    risk_text, risk_color = "ALTO", "#ef4444"
                elif risk >= 0.35:
                    risk_text, risk_color = "MODERADO", "#fbbf24"
                else:
                    risk_text, risk_color = "BAIXO", "#22c55e"

                inf_row = QWidget()
                il = QHBoxLayout(inf_row)
                il.setContentsMargins(0, 2, 0, 2)
                il.addWidget(self._styled_label("Risco de infecção:", "#94a3b8", 10))
                il.addWidget(self._styled_label(f"{risk_text} ({risk:.0%})", risk_color, 11, bold=True))
                il.addStretch()
                box_inf.layout().addWidget(inf_row)

                if risk >= 0.6:
                    alert = QLabel("ALERTA: Sinais de infecção detectados — encaminhar para avaliação")
                    alert.setWordWrap(True)
                    alert.setFont(QFont("Segoe UI", 9))
                    alert.setStyleSheet("color: #ef4444; padding-top: 4px;")
                    box_inf.layout().addWidget(alert)

                # Scores individuais
                box_inf.layout().addWidget(self._styled_label("Detalhes:", "#475569", 8))
                for lbl, sc in inf_scores.items():
                    row = QWidget()
                    rl = QHBoxLayout(row)
                    rl.setContentsMargins(8, 0, 0, 0)
                    rl.addWidget(self._styled_label(f"• {lbl}", "#94a3b8", 8))
                    rl.addStretch()
                    rl.addWidget(self._styled_label(f"{sc:.0%}", "#64748b", 8))
                    box_inf.layout().addWidget(row)

            self.right_layout.addWidget(box_inf)

        # --- ANÁLISE DE BORDAS ---
        if r.border_analysis:
            box_border = self._make_group("ANÁLISE DE BORDAS E PERILESÃO")
            ba = r.border_analysis

            flags = []
            if ba.maceration:
                flags.append(("Maceração perilesional", "#fbbf24"))
            if ba.inflammation:
                flags.append(("Inflamação perilesional", "#ef4444"))
            if not ba.regular_borders:
                flags.append(("Bordas irregulares", "#f97316"))
            if not flags:
                flags.append(("Sem alterações perilesionais", "#22c55e"))

            for text, color in flags:
                box_border.layout().addWidget(self._styled_label(text, color, 10))

            lbl_desc = QLabel(ba.description)
            lbl_desc.setWordWrap(True)
            lbl_desc.setFont(QFont("Segoe UI", 9))
            lbl_desc.setStyleSheet("color: #94a3b8; padding-top: 4px;")
            box_border.layout().addWidget(lbl_desc)
            self.right_layout.addWidget(box_border)

        # --- AÇÕES CLÍNICAS ---
        box_actions = self._make_group("RECOMENDAÇÕES CLÍNICAS")
        dominant = max(r.tissues, key=lambda x: x.percentage)
        lbl_act = QLabel(dominant.clinical_action)
        lbl_act.setWordWrap(True)
        lbl_act.setFont(QFont("Segoe UI", 10))
        lbl_act.setStyleSheet("color: #cbd5e1; padding: 4px 0;")
        box_actions.layout().addWidget(lbl_act)

        for t in r.tissues:
            if t.percentage > 10 and t.name != dominant.name:
                lbl_sec = QLabel(f"{t.name}: {t.clinical_action}")
                lbl_sec.setWordWrap(True)
                lbl_sec.setFont(QFont("Segoe UI", 9))
                lbl_sec.setStyleSheet("color: #94a3b8; padding: 2px 0 2px 8px;")
                box_actions.layout().addWidget(lbl_sec)

        self.right_layout.addWidget(box_actions)

        # --- ESCALAS CLÍNICAS (PUSH/BWAT) ---
        if r.push_score or r.bwat_score:
            box_scales = self._make_group("ESCALAS CLÍNICAS")
            
            # PUSH Score
            if r.push_score:
                push = r.push_score
                push_total = push.get("total_score", 0)
                push_color = "#22c55e" if push_total <= 5 else ("#fbbf24" if push_total <= 10 else "#ef4444")
                
                push_row = QWidget()
                pl = QHBoxLayout(push_row)
                pl.setContentsMargins(0, 2, 0, 2)
                pl.addWidget(self._styled_label("PUSH Score:", "#94a3b8", 10))
                pl.addWidget(self._styled_label(f"{push_total}/17", push_color, 11, bold=True))
                pl.addStretch()
                box_scales.layout().addWidget(push_row)
                
                # Detalhes PUSH
                push_details = f"Área: {push.get('area_score', 0)} | Exsudato: {push.get('exudate_score', 0)} | Tecido: {push.get('tissue_score', 0)}"
                lbl_push_det = QLabel(push_details)
                lbl_push_det.setFont(QFont("Segoe UI", 8))
                lbl_push_det.setStyleSheet("color: #64748b;")
                box_scales.layout().addWidget(lbl_push_det)
                
                # Interpretação PUSH
                lbl_push_int = QLabel(push.get("interpretation", ""))
                lbl_push_int.setWordWrap(True)
                lbl_push_int.setFont(QFont("Segoe UI", 9))
                lbl_push_int.setStyleSheet(f"color: {push_color}; padding: 2px 0;")
                box_scales.layout().addWidget(lbl_push_int)
            
            # BWAT Score
            if r.bwat_score:
                bwat = r.bwat_score
                bwat_total = bwat.get("total_score", 0)
                severity = bwat.get("severity", "")
                
                # Cor baseada na severidade
                severity_colors = {
                    "LEVE": "#22c55e",
                    "MODERADA": "#fbbf24",
                    "GRAVE": "#f97316",
                    "CRÍTICA": "#ef4444",
                }
                bwat_color = severity_colors.get(severity, "#94a3b8")
                
                bwat_row = QWidget()
                bl = QHBoxLayout(bwat_row)
                bl.setContentsMargins(0, 6, 0, 2)
                bl.addWidget(self._styled_label("BWAT Score:", "#94a3b8", 10))
                bl.addWidget(self._styled_label(f"{bwat_total}/65", bwat_color, 11, bold=True))
                bl.addWidget(self._styled_label(f"({severity})", bwat_color, 9))
                bl.addStretch()
                box_scales.layout().addWidget(bwat_row)
                
                # Itens auto-preenchidos vs pendentes
                auto_count = len(bwat.get("auto_filled", {}))
                manual_count = len(bwat.get("manual_filled", {}))
                pending = 13 - auto_count - manual_count
                
                fill_text = f"Auto: {auto_count} | Manual: {manual_count}"
                if pending > 0:
                    fill_text += f" | Pendente: {pending}"
                lbl_fill = QLabel(fill_text)
                lbl_fill.setFont(QFont("Segoe UI", 8))
                lbl_fill.setStyleSheet("color: #64748b;")
                box_scales.layout().addWidget(lbl_fill)
            
            self.right_layout.addWidget(box_scales)

        # --- ANÁLISE DE IMAGEM (Iluminação e Parte do Corpo) ---
        if r.lighting_analysis or r.body_part:
            box_img_analysis = self._make_group("ANÁLISE DE IMAGEM")
            
            # Análise de iluminação
            if r.lighting_analysis:
                lighting = r.lighting_analysis
                condition = lighting.get("condition", "unknown")
                quality = lighting.get("quality_score", 0)
                
                # Cor baseada na qualidade
                qual_color = "#22c55e" if quality >= 0.7 else ("#fbbf24" if quality >= 0.4 else "#ef4444")
                
                # Linha de qualidade
                qual_row = QWidget()
                ql = QHBoxLayout(qual_row)
                ql.setContentsMargins(0, 2, 0, 2)
                ql.addWidget(self._styled_label("Qualidade:", "#94a3b8", 9))
                ql.addWidget(self._styled_label(f"{quality:.0%}", qual_color, 10, bold=True))
                ql.addStretch()
                box_img_analysis.layout().addWidget(qual_row)
                
                # Condição de iluminação
                condition_names = {
                    "optimal": "Ideal",
                    "underexposed": "Subexposta",
                    "overexposed": "Superexposta",
                    "uneven": "Irregular",
                    "warm": "Luz quente",
                    "cool": "Luz fria",
                    "flash": "Flash detectado",
                }
                cond_text = condition_names.get(condition, condition)
                
                cond_row = QWidget()
                cl = QHBoxLayout(cond_row)
                cl.setContentsMargins(0, 1, 0, 1)
                cl.addWidget(self._styled_label("Iluminação:", "#94a3b8", 9))
                cl.addWidget(self._styled_label(cond_text, "#e2e8f0", 9))
                cl.addStretch()
                box_img_analysis.layout().addWidget(cond_row)
                
                # Temperatura de cor
                temp_k = lighting.get("color_temperature_k", 5500)
                temp_row = QWidget()
                tl = QHBoxLayout(temp_row)
                tl.setContentsMargins(0, 1, 0, 1)
                tl.addWidget(self._styled_label("Temp. cor:", "#94a3b8", 9))
                tl.addWidget(self._styled_label(f"{temp_k}K", "#e2e8f0", 9))
                tl.addStretch()
                box_img_analysis.layout().addWidget(temp_row)
                
                # Correções aplicadas
                if r.image_corrections:
                    corrections_text = ", ".join(r.image_corrections.keys())
                    corr_row = QWidget()
                    crl = QHBoxLayout(corr_row)
                    crl.setContentsMargins(0, 1, 0, 1)
                    crl.addWidget(self._styled_label("Correções:", "#94a3b8", 9))
                    crl.addWidget(self._styled_label(corrections_text[:30], "#22c55e", 9))
                    crl.addStretch()
                    box_img_analysis.layout().addWidget(corr_row)
            
            # Detecção de parte do corpo
            if r.body_part:
                body = r.body_part
                region_name = body.get("name_pt", "Desconhecido")
                confidence = body.get("confidence", 0)
                is_pressure = body.get("is_pressure_point", False)
                is_reliable = body.get("is_reliable", True)
                reliability_note = body.get("reliability_note", "")
                
                # Separador visual
                sep = QWidget()
                sep.setFixedHeight(6)
                box_img_analysis.layout().addWidget(sep)
                
                # Região anatômica
                body_row = QWidget()
                bl = QHBoxLayout(body_row)
                bl.setContentsMargins(0, 2, 0, 2)
                bl.addWidget(self._styled_label("Região:", "#94a3b8", 9))
                body_color = "#38bdf8" if is_reliable else "#fbbf24"
                bl.addWidget(self._styled_label(region_name, body_color, 10, bold=True))
                bl.addWidget(self._styled_label(f"({confidence:.0%})", "#64748b", 8))
                bl.addStretch()
                box_img_analysis.layout().addWidget(body_row)

                if not is_reliable and reliability_note:
                    warn_row = QWidget()
                    wl = QHBoxLayout(warn_row)
                    wl.setContentsMargins(0, 1, 0, 1)
                    wl.addWidget(self._styled_label("Atenção", "#f97316", 9, bold=True))
                    wl.addWidget(self._styled_label(reliability_note[:48], "#f97316", 8))
                    wl.addStretch()
                    box_img_analysis.layout().addWidget(warn_row)
                
                # Ponto de pressão
                if is_pressure:
                    press_row = QWidget()
                    pl = QHBoxLayout(press_row)
                    pl.setContentsMargins(0, 1, 0, 1)
                    pl.addWidget(self._styled_label("Ponto de pressão", "#f97316", 9))
                    pl.addStretch()
                    box_img_analysis.layout().addWidget(press_row)
                
                # Feridas comuns na região
                common = body.get("common_wounds", [])
                if common:
                    common_text = ", ".join(common[:3])
                    common_row = QWidget()
                    cwl = QHBoxLayout(common_row)
                    cwl.setContentsMargins(0, 1, 0, 1)
                    cwl.addWidget(self._styled_label("Típico:", "#94a3b8", 8))
                    cwl.addWidget(self._styled_label(common_text[:35], "#64748b", 8))
                    cwl.addStretch()
                    box_img_analysis.layout().addWidget(common_row)
            
            self.right_layout.addWidget(box_img_analysis)

        # --- METADADOS ---
        box_meta = self._make_group("METADADOS")
        dl_status = "Ativo (TTA)" if r.dl_prediction else "Não disponível"
        resnet_status = "ResNet50 Two-Stage (TTA + Grad-CAM)" if r.resnet_prediction else "Não disponível"
        pipeline_desc = "Detecção → Segm. HSV+LAB → Textura → ResNet50 → Grad-CAM"
        meta_items = [
            ("Área da ferida", f"{r.wound_area_px:,} px"),
            ("Tempo de processamento", f"{r.processing_time_ms:.0f} ms"),
            ("Pipeline", pipeline_desc),
            ("Segmentação", "Multi-espaço (HSV 60% + LAB 40%) + Textura"),
            ("Classificação DL", dl_status),
            ("Etiologia ResNet50", resnet_status),
            ("Explicabilidade", "Grad-CAM (layer4 ResNet50)"),
            ("Versão", "HEAL+ v3.0 — ResNet50 Two-Stage + Grad-CAM"),
        ]
        for k, v in meta_items:
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 1, 0, 1)
            rl.addWidget(self._styled_label(k, "#64748b", 9))
            rl.addStretch()
            rl.addWidget(self._styled_label(v, "#94a3b8", 9))
            box_meta.layout().addWidget(row)

        self.right_layout.addWidget(box_meta)

        # --- ANÁLISE DE ILUMINAÇÃO ---
        if r.lighting_analysis:
            box_light = self._make_group("ILUMINAÇÃO")
            la = r.lighting_analysis
            
            # Condição de iluminação
            condition = la.get("condition", "unknown")
            cond_colors = {
                "optimal": "#22c55e",
                "underexposed": "#ef4444",
                "overexposed": "#fbbf24",
                "uneven": "#f97316",
                "warm": "#fbbf24",
                "cool": "#3b82f6",
                "flash": "#f97316",
            }
            cond_color = cond_colors.get(condition, "#94a3b8")
            cond_names = {
                "optimal": "Adequada",
                "underexposed": "Subexposta",
                "overexposed": "Superexposta",
                "uneven": "Irregular",
                "warm": "Luz Quente",
                "cool": "Luz Fria",
                "flash": "Flash Detectado",
            }
            cond_name = cond_names.get(condition, condition)
            
            cond_row = QWidget()
            cl = QHBoxLayout(cond_row)
            cl.setContentsMargins(0, 2, 0, 2)
            cl.addWidget(self._styled_label("Condição:", "#94a3b8", 9))
            cl.addWidget(self._styled_label(cond_name, cond_color, 10, bold=True))
            cl.addStretch()
            box_light.layout().addWidget(cond_row)
            
            # Score de qualidade
            quality = la.get("quality_score", 0)
            q_color = "#22c55e" if quality >= 0.7 else ("#fbbf24" if quality >= 0.4 else "#ef4444")
            q_row = QWidget()
            ql = QHBoxLayout(q_row)
            ql.setContentsMargins(0, 1, 0, 1)
            ql.addWidget(self._styled_label("Qualidade:", "#94a3b8", 9))
            ql.addWidget(self._styled_label(f"{quality:.0%}", q_color, 10, bold=True))
            ql.addStretch()
            box_light.layout().addWidget(q_row)
            
            # Correções aplicadas
            if r.image_corrections:
                corr_text = ", ".join(r.image_corrections.keys())
                lbl_corr = QLabel(f"Correções: {corr_text}")
                lbl_corr.setFont(QFont("Segoe UI", 8))
                lbl_corr.setStyleSheet("color: #64748b;")
                box_light.layout().addWidget(lbl_corr)
            
            self.right_layout.addWidget(box_light)

        # --- PARTE DO CORPO ---
        if r.body_part:
            box_body = self._make_group("REGIÃO ANATÔMICA")
            bp = r.body_part
            
            region_name = bp.get("name_pt", "Não identificado")
            confidence = bp.get("confidence", 0)
            is_pressure = bp.get("is_pressure_point", False)
            is_reliable = bp.get("is_reliable", True)
            reliability_note = bp.get("reliability_note", "")
            
            # Nome da região
            bp_color = "#38bdf8" if is_reliable else "#fbbf24"
            bp_row = QWidget()
            bl = QHBoxLayout(bp_row)
            bl.setContentsMargins(0, 2, 0, 2)
            bl.addWidget(self._styled_label(region_name, bp_color, 11, bold=True))
            if confidence > 0:
                bl.addWidget(self._styled_label(f"({confidence:.0%})", "#64748b", 9))
            bl.addStretch()
            box_body.layout().addWidget(bp_row)

            if not is_reliable and reliability_note:
                lbl_rel = QLabel(reliability_note)
                lbl_rel.setWordWrap(True)
                lbl_rel.setFont(QFont("Segoe UI", 8))
                lbl_rel.setStyleSheet("color: #f97316;")
                box_body.layout().addWidget(lbl_rel)
            
            # Ponto de pressão
            if is_pressure:
                lbl_press = QLabel("Ponto de pressão - risco de LPP")
                lbl_press.setFont(QFont("Segoe UI", 9))
                lbl_press.setStyleSheet("color: #f97316;")
                box_body.layout().addWidget(lbl_press)
            
            # Feridas comuns nesta região
            common = bp.get("common_wounds", [])
            if common:
                common_text = ", ".join(w.replace("_", " ").title() for w in common[:3])
                lbl_common = QLabel(f"Etiologias comuns: {common_text}")
                lbl_common.setFont(QFont("Segoe UI", 8))
                lbl_common.setStyleSheet("color: #64748b;")
                lbl_common.setWordWrap(True)
                box_body.layout().addWidget(lbl_common)
            
            self.right_layout.addWidget(box_body)

        self.right_layout.addStretch()

    # -------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------
    def _make_group(self, title: str) -> QGroupBox:
        box = QGroupBox(title)
        box.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        box.setStyleSheet("""
            QGroupBox {
                background: #1e293b;
                border: 1px solid #334155;
                border-radius: 8px;
                margin-top: 12px;
                padding: 16px 12px 10px;
                color: #94a3b8;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 1px 6px;
                color: #94a3b8;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
        """)
        layout = QVBoxLayout()
        layout.setSpacing(6)
        box.setLayout(layout)
        return box

    def _styled_label(self, text: str, color: str, size: int, bold: bool = False) -> QLabel:
        lbl = QLabel(text)
        weight = QFont.Weight.Bold if bold else QFont.Weight.Normal
        lbl.setFont(QFont("Segoe UI", size, weight))
        lbl.setStyleSheet(f"color: {color};")
        return lbl

    def _clear_right_panel(self):
        while self.right_layout.count():
            w = self.right_layout.takeAt(0).widget()
            if w:
                w.deleteLater()

    def closeEvent(self, event):
        """Encerramento seguro: para todas as threads antes de fechar."""
        print("[HEAL+] Finalizando componentes com segurança...")

        # Para webcam + análise em tempo real (sempre, mesmo se _webcam_active é False)
        self._stop_webcam()

        # Para thread de análise de imagem estática (se existir)
        if self._thread is not None:
            try:
                self._thread.result_ready.disconnect()
                self._thread.progress.disconnect()
            except (TypeError, RuntimeError):
                pass
            if self._thread.isRunning():
                if not self._thread.wait(5000):
                    self._thread.terminate()
                    self._thread.wait(1000)
            self._thread = None

        # Processa eventos pendentes (deleteLater, etc.) várias vezes
        # para garantir que objetos sejam destruídos corretamente
        for _ in range(3):
            QApplication.processEvents()

        print("[HEAL+] Encerramento concluído.")
        event.accept()


# ============================================================
# MAIN
# ============================================================

def main():
    # Garante UTF-8 no Qt
    import locale
    try:
        locale.setlocale(locale.LC_ALL, '')
    except locale.Error:
        pass
    
    # Força UTF-8 em variável de ambiente para Qt
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    os.environ.setdefault('QT_QPA_PLATFORM_PLUGIN_PATH', '')
    
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = HealAnalyzerApp()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
