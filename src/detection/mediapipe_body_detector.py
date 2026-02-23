# -*- coding: utf-8 -*-
"""
===============================================================================
REDISUS — Detector de Parte do Corpo via MediaPipe  (Tasks API ≥ 0.10.x)
===============================================================================

Usa a **MediaPipe Tasks API** (mp.tasks.vision) para determinar a região
anatômica em imagens close-up de feridas.

Ordem de detecção (hierárquica):
  1. HandLandmarker   → se detectou mão → HAND
  2. FaceDetector     → se detectou rosto → FACE
  3. PoseLandmarker   → usa landmarks visíveis para inferir região
  4. Fallback         → retorna "unknown"

Os modelos .task são baixados automaticamente na primeira execução para
  models/mediapipe/

Requisitos:
  pip install mediapipe>=0.10.0

Autor: REDISUS Team
===============================================================================
"""

from __future__ import annotations

import os
import cv2
import urllib.request
import numpy as np
from pathlib import Path
from typing import Dict, Optional, Tuple
from loguru import logger

# ── Importação segura do MediaPipe Tasks API ────────────────────────────────

_mp = None
_vision = None

def _safe_import_mediapipe():
    """Importa mediapipe Tasks API."""
    global _mp, _vision
    if _mp is not None:
        return _mp
    try:
        import mediapipe as mp
        # Verifica se Tasks API está disponível
        _ = mp.tasks.vision.HandLandmarker
        _mp = mp
        _vision = mp.tasks.vision
        return mp
    except (ImportError, AttributeError):
        return None

_safe_import_mediapipe()

# ── Diretório de modelos ────────────────────────────────────────────────────

_MODELS_DIR = Path(__file__).resolve().parent.parent.parent / "models" / "mediapipe"

# URLs oficiais dos modelos MediaPipe Tasks
_MODEL_URLS = {
    "hand_landmarker.task": (
        "https://storage.googleapis.com/mediapipe-models/"
        "hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"
    ),
    "blaze_face_short_range.tflite": (
        "https://storage.googleapis.com/mediapipe-models/"
        "face_detector/blaze_face_short_range/float16/latest/"
        "blaze_face_short_range.tflite"
    ),
    "pose_landmarker_lite.task": (
        "https://storage.googleapis.com/mediapipe-models/"
        "pose_landmarker/pose_landmarker_lite/float16/latest/"
        "pose_landmarker_lite.task"
    ),
}


def _ensure_model(name: str) -> Optional[str]:
    """Garante que o modelo .task está baixado. Retorna o caminho ou None."""
    path = _MODELS_DIR / name
    if path.exists():
        return str(path)
    url = _MODEL_URLS.get(name)
    if url is None:
        logger.error(f"URL desconhecida para modelo MediaPipe: {name}")
        return None
    try:
        _MODELS_DIR.mkdir(parents=True, exist_ok=True)
        logger.info(f"Baixando modelo MediaPipe: {name} …")
        urllib.request.urlretrieve(url, str(path))
        logger.info(f"Modelo salvo em {path} ({path.stat().st_size / 1e6:.1f} MB)")
        return str(path)
    except Exception as exc:
        logger.error(f"Falha ao baixar {name}: {exc}")
        if path.exists():
            path.unlink()
        return None


# ── Constantes de mapeamento ────────────────────────────────────────────────

# Landmarks do Pose com índice → agrupados por região anatômica
# Referência: https://developers.google.com/mediapipe/solutions/vision/pose_landmarker
_POSE_REGION_MAP = {
    # Cabeça / Face
    "face":      [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    # Ombros
    "chest":     [11, 12],
    # Braço direito
    "upper_arm": [11, 13],
    "forearm":   [13, 15],
    "hand":      [15, 17, 19, 21],
    # Braço esquerdo (espelhado)
    "upper_arm_l": [12, 14],
    "forearm_l":   [14, 16],
    "hand_l":      [16, 18, 20, 22],
    # Quadril / Tronco
    "abdomen":   [11, 12, 23, 24],
    # Coxa
    "upper_leg": [23, 25],
    "upper_leg_l": [24, 26],
    # Perna (abaixo do joelho)
    "lower_leg": [25, 27],
    "lower_leg_l": [26, 28],
    # Pé / Tornozelo
    "foot":      [27, 29, 31],
    "foot_l":    [28, 30, 32],
}

# Regiões simétricas → normaliza para um nome único
_SYMMETRIC_MAP = {
    "upper_arm_l": "upper_arm",
    "forearm_l":   "forearm",
    "hand_l":      "hand",
    "upper_leg_l": "upper_leg",
    "lower_leg_l": "lower_leg",
    "foot_l":      "foot",
}


class MediaPipeBodyDetector:
    """
    Detector de região anatômica usando MediaPipe Tasks API.

    Funciona em close-ups de partes do corpo — não precisa de corpo inteiro.
    Prioriza HandLandmarker (ótimo para close-up de mão) e FaceDetector,
    depois tenta PoseLandmarker para partes intermediárias.

    Os modelos .task são baixados automaticamente na primeira execução.

    Uso:
        detector = MediaPipeBodyDetector()
        region, confidence, all_probs = detector.detect(image_bgr)
        # region = "hand", confidence = 0.95
    """

    def __init__(
        self,
        hand_confidence: float = 0.35,
        face_confidence: float = 0.45,
        pose_confidence: float = 0.40,
    ):
        self._available = _mp is not None
        self._hand_conf = hand_confidence
        self._face_conf = face_confidence
        self._pose_conf = pose_confidence

        # Lazy-init dos modelos (só cria quando precisar)
        self._hands = None
        self._face = None
        self._pose = None
        self._initialized = False

    @property
    def available(self) -> bool:
        return self._available

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _to_mp_image(bgr: np.ndarray):
        """Converte imagem BGR (OpenCV) para mp.Image RGB."""
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        return _mp.Image(image_format=_mp.ImageFormat.SRGB, data=rgb)

    def _ensure_init(self):
        """Inicializa os modelos MediaPipe sob demanda."""
        if self._initialized or not self._available:
            return

        BaseOptions = _mp.tasks.BaseOptions

        # ── HandLandmarker ──
        model_path = _ensure_model("hand_landmarker.task")
        if model_path:
            try:
                opts = _vision.HandLandmarkerOptions(
                    base_options=BaseOptions(model_asset_path=model_path),
                    running_mode=_vision.RunningMode.IMAGE,
                    num_hands=2,
                    min_hand_detection_confidence=self._hand_conf,
                    min_hand_presence_confidence=self._hand_conf,
                )
                self._hands = _vision.HandLandmarker.create_from_options(opts)
            except Exception as e:
                logger.warning(f"MediaPipe HandLandmarker indisponível: {e}")

        # ── FaceDetector ──
        model_path = _ensure_model("blaze_face_short_range.tflite")
        if model_path:
            try:
                opts = _vision.FaceDetectorOptions(
                    base_options=BaseOptions(model_asset_path=model_path),
                    running_mode=_vision.RunningMode.IMAGE,
                    min_detection_confidence=self._face_conf,
                )
                self._face = _vision.FaceDetector.create_from_options(opts)
            except Exception as e:
                logger.warning(f"MediaPipe FaceDetector indisponível: {e}")

        # ── PoseLandmarker ──
        model_path = _ensure_model("pose_landmarker_lite.task")
        if model_path:
            try:
                opts = _vision.PoseLandmarkerOptions(
                    base_options=BaseOptions(model_asset_path=model_path),
                    running_mode=_vision.RunningMode.IMAGE,
                    min_pose_detection_confidence=self._pose_conf,
                )
                self._pose = _vision.PoseLandmarker.create_from_options(opts)
            except Exception as e:
                logger.warning(f"MediaPipe PoseLandmarker indisponível: {e}")

        self._initialized = True
        active = []
        if self._hands: active.append("Hands")
        if self._face: active.append("Face")
        if self._pose: active.append("Pose")
        logger.info(f"MediaPipe Tasks inicializados: {', '.join(active) or 'nenhum'}")

    def detect(self, image: np.ndarray) -> Tuple[str, float, Dict[str, float]]:
        """
        Detecta a região anatômica na imagem.

        Args:
            image: Imagem BGR (OpenCV)

        Returns:
            (region_name, confidence, all_probabilities)
        """
        if not self._available:
            return "unknown", 0.0, {}

        self._ensure_init()

        mp_img = self._to_mp_image(image)

        # Passo 1: HandLandmarker (ótimo para close-up de mão)
        region, conf, probs = self._try_hands(mp_img, image.shape)
        if region is not None:
            return region, conf, probs

        # Passo 2: FaceDetector
        region, conf, probs = self._try_face(mp_img)
        if region is not None:
            return region, conf, probs

        # Passo 3: PoseLandmarker para outras regiões
        region, conf, probs = self._try_pose(mp_img, image.shape)
        if region is not None:
            return region, conf, probs

        return "unknown", 0.0, {}

    # ── Detecção de Mão ─────────────────────────────────────────────────

    def _try_hands(self, mp_img, shape: Tuple[int, ...]) -> Tuple[Optional[str], float, Dict[str, float]]:
        """Tenta detectar mão com HandLandmarker."""
        if self._hands is None:
            return None, 0.0, {}

        try:
            result = self._hands.detect(mp_img)
            if result.hand_landmarks and result.handedness:
                # Pega a detecção com maior score
                best_score = 0.0
                for handedness_list in result.handedness:
                    for cat in handedness_list:
                        best_score = max(best_score, cat.score)

                if best_score > 0.3:
                    # Coverage: quanto da imagem a mão detectada ocupa
                    coverage = self._landmarks_coverage(result.hand_landmarks[0], shape)
                    adjusted_conf = min(best_score * (0.7 + 0.3 * coverage), 1.0)
                    probs = {"hand": adjusted_conf}
                    return "hand", adjusted_conf, probs
        except Exception as e:
            logger.debug(f"MediaPipe HandLandmarker erro: {e}")

        return None, 0.0, {}

    @staticmethod
    def _landmarks_coverage(landmarks, shape: Tuple[int, ...]) -> float:
        """Calcula % da imagem coberta pelos landmarks detectados."""
        xs = [lm.x for lm in landmarks]
        ys = [lm.y for lm in landmarks]
        w_box = max(xs) - min(xs)
        h_box = max(ys) - min(ys)
        return min(w_box * h_box * 4.0, 1.0)

    # ── Detecção de Face ─────────────────────────────────────────────────

    def _try_face(self, mp_img) -> Tuple[Optional[str], float, Dict[str, float]]:
        """Tenta detectar face com FaceDetector."""
        if self._face is None:
            return None, 0.0, {}

        try:
            result = self._face.detect(mp_img)
            if result.detections:
                best_score = 0.0
                for det in result.detections:
                    for cat in det.categories:
                        best_score = max(best_score, cat.score)
                if best_score > 0.4:
                    probs = {"face": float(best_score)}
                    return "face", float(best_score), probs
        except Exception as e:
            logger.debug(f"MediaPipe FaceDetector erro: {e}")

        return None, 0.0, {}

    # ── Detecção via Pose Landmarks ──────────────────────────────────────

    def _try_pose(
        self, mp_img, shape: Tuple[int, ...]
    ) -> Tuple[Optional[str], float, Dict[str, float]]:
        """Usa PoseLandmarker para inferir a região anatômica dominante."""
        if self._pose is None:
            return None, 0.0, {}

        try:
            result = self._pose.detect(mp_img)
            if not result.pose_landmarks or len(result.pose_landmarks) == 0:
                return None, 0.0, {}

            landmarks = result.pose_landmarks[0]  # primeiro corpo
            h, w = shape[:2]

            # Calcula visibilidade média por grupo de região
            region_scores: Dict[str, float] = {}

            for region_name, indices in _POSE_REGION_MAP.items():
                vis_list = []
                in_frame_list = []
                for idx in indices:
                    if idx < len(landmarks):
                        lm = landmarks[idx]
                        vis = getattr(lm, "visibility", 0.0) or 0.0
                        vis_list.append(vis)
                        in_frame = 0.0 <= lm.x <= 1.0 and 0.0 <= lm.y <= 1.0
                        in_frame_list.append(1.0 if in_frame else 0.0)

                if not vis_list:
                    continue

                avg_vis = sum(vis_list) / len(vis_list)
                avg_in_frame = sum(in_frame_list) / len(in_frame_list)
                score = avg_vis * 0.6 + avg_in_frame * 0.4

                canonical = _SYMMETRIC_MAP.get(region_name, region_name)
                if canonical in region_scores:
                    region_scores[canonical] = max(region_scores[canonical], score)
                else:
                    region_scores[canonical] = score

            if not region_scores:
                return None, 0.0, {}

            # Identifica a região com landmarks mais centrais na imagem
            central_scores = self._centrality_scores(landmarks, h, w)
            for region, cscore in central_scores.items():
                if region in region_scores:
                    region_scores[region] = region_scores[region] * 0.5 + cscore * 0.5

            best_region = max(region_scores, key=region_scores.get)  # type: ignore[arg-type]
            best_score = region_scores[best_region]

            if best_score < 0.25:
                return None, 0.0, region_scores

            total = sum(region_scores.values()) or 1.0
            norm_probs = {k: v / total for k, v in region_scores.items()}

            return best_region, min(best_score, 0.95), norm_probs

        except Exception as e:
            logger.debug(f"MediaPipe PoseLandmarker erro: {e}")

        return None, 0.0, {}

    @staticmethod
    def _centrality_scores(landmarks, h: int, w: int) -> Dict[str, float]:
        """Calcula quão central cada grupo de landmarks está na imagem."""
        cx, cy = 0.5, 0.5
        region_centrality: Dict[str, float] = {}

        for region_name, indices in _POSE_REGION_MAP.items():
            dists = []
            for idx in indices:
                if idx < len(landmarks):
                    lm = landmarks[idx]
                    vis = getattr(lm, "visibility", 0.0) or 0.0
                    if vis > 0.1:
                        dist = ((lm.x - cx) ** 2 + (lm.y - cy) ** 2) ** 0.5
                        dists.append(1.0 - min(dist, 1.0))

            if dists:
                canonical = _SYMMETRIC_MAP.get(region_name, region_name)
                score = sum(dists) / len(dists)
                if canonical in region_centrality:
                    region_centrality[canonical] = max(region_centrality[canonical], score)
                else:
                    region_centrality[canonical] = score

        return region_centrality

    def close(self):
        """Libera recursos MediaPipe Tasks."""
        for obj in [self._hands, self._face, self._pose]:
            if obj is not None:
                try:
                    obj.close()
                except Exception:
                    pass
        self._hands = self._face = self._pose = None
        self._initialized = False

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
