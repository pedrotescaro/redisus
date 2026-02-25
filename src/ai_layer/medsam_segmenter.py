"""
REDISUS - MedSAM Segmenter
===========================

Integração com MedSAM (Medical Segment Anything Model):
  bowang-lab/MedSAM — Nature Communications 2024

Especificações:
  - Backbone: ViT-Base (SAM encoder)
  - Treinado em: 1.6M pares imagem-máscara médicas
  - Prompt: Bounding box (não requer pontos/texto)
  - Output: Máscara binária da região de interesse

Fallback: OpenCV GrabCut quando o modelo não está disponível.
"""
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
from loguru import logger


@dataclass
class MedSAMSegmentationResult:
    """Resultado da segmentação MedSAM."""
    mask: np.ndarray                # Binária (H, W), 0/1
    contours: List[np.ndarray]      # Contornos encontrados
    wound_area_pixels: int
    wound_perimeter_pixels: float
    circularity: float              # 4π·A / P²
    bounding_box: Tuple[int, int, int, int]   # (x1, y1, x2, y2)
    inference_time_ms: float
    model_loaded: bool = True

    def get_overlay(self, image: np.ndarray, color=(0, 255, 0), alpha=0.35) -> np.ndarray:
        """Overlay da máscara na imagem original."""
        overlay = image.copy()
        mask_bool = self.mask.astype(bool)
        if mask_bool.shape[:2] != image.shape[:2]:
            mask_resized = cv2.resize(
                self.mask, (image.shape[1], image.shape[0]),
                interpolation=cv2.INTER_NEAREST
            )
            mask_bool = mask_resized.astype(bool)
        overlay[mask_bool] = (
            np.array(overlay[mask_bool], dtype=np.float32) * (1 - alpha)
            + np.array(color, dtype=np.float32) * alpha
        ).astype(np.uint8)

        for cnt in self.contours:
            cv2.drawContours(overlay, [cnt], -1, color, 2)
        return overlay


class MedSAMSegmenter:
    """
    Segmentador de feridas com MedSAM.

    Usa bounding box como prompt. Se o modelo não estiver
    disponível, usa OpenCV GrabCut como fallback.
    """

    CHECKPOINT_NAME = "medsam_vit_b.pth"

    def __init__(self, checkpoint_path: Optional[str] = None):
        self._checkpoint_path = checkpoint_path
        self._predictor = None
        self._loaded = False

    # ------------------------------------------------------------------
    def load_model(self) -> bool:
        """Tenta carregar checkpoint do MedSAM."""
        try:
            import torch
            from segment_anything import sam_model_registry, SamPredictor

            ckpt = self._checkpoint_path
            if ckpt is None:
                from pathlib import Path
                candidates = [
                    Path("models") / self.CHECKPOINT_NAME,
                    Path(__file__).parent.parent.parent / "models" / self.CHECKPOINT_NAME,
                ]
                for c in candidates:
                    if c.exists():
                        ckpt = str(c)
                        break

            if ckpt is None or not Path(ckpt).exists():
                logger.warning("MedSAM: checkpoint não encontrado. Usando simulação GrabCut.")
                self._loaded = False
                return False

            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            sam = sam_model_registry["vit_b"](checkpoint=ckpt)
            sam.to(device)
            sam.eval()

            self._predictor = SamPredictor(sam)
            self._loaded = True
            logger.info(f"MedSAM: modelo carregado em {device}")
            return True

        except Exception as e:
            logger.warning(f"MedSAM: falha ao carregar ({e}). Usando simulação.")
            self._loaded = False
            return False

    # ------------------------------------------------------------------
    def segment(
        self,
        image: np.ndarray,
        bbox: Optional[Tuple[int, int, int, int]] = None
    ) -> MedSAMSegmentationResult:
        """
        Segmenta a ferida na imagem.

        Args:
            image: BGR (H, W, 3)
            bbox: (x1, y1, x2, y2) da região de interesse. Se None, usa imagem inteira.
        """
        h, w = image.shape[:2]
        if bbox is None:
            margin_x, margin_y = int(w * 0.1), int(h * 0.1)
            bbox = (margin_x, margin_y, w - margin_x, h - margin_y)

        if self._loaded:
            return self._infer(image, bbox)
        return self._simulate(image, bbox)

    # ------------------------------------------------------------------
    def _infer(
        self, image: np.ndarray, bbox: Tuple[int, int, int, int]
    ) -> MedSAMSegmentationResult:
        """Inferência real com MedSAM."""
        import torch

        start = time.perf_counter()
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        self._predictor.set_image(rgb)

        box_np = np.array(bbox).reshape(1, 4)
        box_tensor = torch.as_tensor(box_np, dtype=torch.float, device=self._predictor.device)
        transformed_box = self._predictor.transform.apply_boxes_torch(
            box_tensor, image.shape[:2]
        )

        masks, scores, _ = self._predictor.predict_torch(
            point_coords=None,
            point_labels=None,
            boxes=transformed_box,
            multimask_output=True,
        )

        best_idx = int(scores.argmax())
        mask = masks[0, best_idx].cpu().numpy().astype(np.uint8)

        elapsed_ms = (time.perf_counter() - start) * 1000
        return self._build_result(mask, bbox, elapsed_ms, model_loaded=True)

    # ------------------------------------------------------------------
    def _simulate(
        self, image: np.ndarray, bbox: Tuple[int, int, int, int]
    ) -> MedSAMSegmentationResult:
        """Simulação via GrabCut + heurística de cor."""
        start = time.perf_counter()
        h, w = image.shape[:2]

        x1, y1, x2, y2 = bbox
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)

        mask_gc = np.zeros((h, w), dtype=np.uint8)
        gc_rect = (x1, y1, x2 - x1, y2 - y1)

        bgd_model = np.zeros((1, 65), dtype=np.float64)
        fgd_model = np.zeros((1, 65), dtype=np.float64)

        try:
            cv2.grabCut(
                image, mask_gc, gc_rect,
                bgd_model, fgd_model,
                iterCount=5,
                mode=cv2.GC_INIT_WITH_RECT,
            )
            binary = np.where((mask_gc == cv2.GC_FGD) | (mask_gc == cv2.GC_PR_FGD), 1, 0).astype(np.uint8)
        except cv2.error:
            # Fallback: elipse inscrita no bbox
            binary = np.zeros((h, w), dtype=np.uint8)
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            rx, ry = (x2 - x1) // 3, (y2 - y1) // 3
            cv2.ellipse(binary, (cx, cy), (rx, ry), 0, 0, 360, 1, -1)

        # Refina com operações morfológicas
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

        elapsed_ms = (time.perf_counter() - start) * 1000
        return self._build_result(binary, bbox, elapsed_ms, model_loaded=False)

    # ------------------------------------------------------------------
    def _build_result(
        self,
        mask: np.ndarray,
        bbox: Tuple[int, int, int, int],
        elapsed_ms: float,
        model_loaded: bool,
    ) -> MedSAMSegmentationResult:
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        area = int(np.sum(mask > 0))
        perimeter = sum(cv2.arcLength(c, True) for c in contours) if contours else 0.0
        circularity = (4 * np.pi * area / (perimeter ** 2)) if perimeter > 0 else 0.0

        return MedSAMSegmentationResult(
            mask=mask,
            contours=list(contours),
            wound_area_pixels=area,
            wound_perimeter_pixels=perimeter,
            circularity=min(circularity, 1.0),
            bounding_box=bbox,
            inference_time_ms=elapsed_ms,
            model_loaded=model_loaded,
        )

    @property
    def is_loaded(self) -> bool:
        return self._loaded
