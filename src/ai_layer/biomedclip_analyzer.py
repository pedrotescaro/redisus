"""
REDISUS - BiomedCLIP Zero-Shot Analyzer
========================================

Integração com BiomedCLIP (Microsoft Research):
  microsoft/BiomedCLIP-PubMedBERT_256-vit_base_patch16_224

Especificações:
  - Vision encoder: ViT-B/16 (86M params)
  - Text encoder: PubMedBERT (110M params)
  - Treinado em: PMC-15M (15 milhões de pares figura–legenda PubMed)
  - Capacidade: análise zero-shot com prompts clínicos em inglês

Dimensões de análise (via prompts):
  1. Etiologia da ferida (5 classes REDISUS)
  2. Composição tecidual (granulação, esfacelo, necrose, epitelização, mista)
  3. Severidade (leve, moderada, grave, crítica)
  4. Risco de infecção (infectada, limpa, biofilme, celulite)
"""
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
from loguru import logger


# =====================================================
# Prompts clínicos em inglês (BiomedCLIP treinou em PubMed)
# =====================================================

WOUND_ETIOLOGY_PROMPTS = {
    "a photograph of a venous leg ulcer with irregular borders": 0,
    "a clinical image of an arterial ulcer on a pale ischemic limb": 1,
    "a photograph of a diabetic foot ulcer neuropathic wound": 2,
    "a clinical photograph of a pressure injury decubitus ulcer": 3,
    "a surgical wound incision with suture or staple closure": 4,
}

WOUND_TISSUE_PROMPTS = [
    "wound bed with red granulation tissue healthy healing",
    "wound with yellow slough fibrinous tissue",
    "wound with black necrotic eschar tissue",
    "wound with pink epithelial tissue and wound margin advancing",
    "wound with mixed tissue types granulation and slough",
]

WOUND_SEVERITY_PROMPTS = [
    "a mild superficial wound with minimal tissue damage",
    "a moderate wound with partial tissue involvement",
    "a severe deep wound with significant tissue loss",
    "a critical wound with exposed underlying structures",
]

INFECTION_PROMPTS = [
    "an infected wound with purulent exudate erythema",
    "a clean wound with no signs of infection",
    "a wound with biofilm formation",
    "a wound with surrounding cellulitis and spreading erythema",
]


@dataclass
class BiomedCLIPResult:
    """Resultado completo da análise BiomedCLIP."""
    # Etiologia (probabilities mapeadas para REDISUS class IDs)
    etiology_probs: Dict[int, float]

    # Tecido dominante
    tissue_scores: Dict[str, float]

    # Severidade (0–1 index contínuo)
    severity_scores: List[float]
    severity_index: float          # 0 (leve) a 1 (crítico)

    # Infecção
    infection_scores: Dict[str, float]
    infection_risk: float          # 0 (limpa) a 1 (infectada)

    inference_time_ms: float
    model_loaded: bool = True


class BiomedCLIPAnalyzer:
    """
    Análise zero-shot de feridas com BiomedCLIP.

    Fallback: heurísticas de cor/textura quando o modelo não está disponível.
    """

    MODEL_ID = "microsoft/BiomedCLIP-PubMedBERT_256-vit_base_patch16_224"

    def __init__(self):
        self._model = None
        self._preprocess = None
        self._tokenizer = None
        self._device = None
        self._loaded = False

    # ------------------------------------------------------------------
    def load_model(self) -> bool:
        """Carrega BiomedCLIP via open_clip."""
        try:
            import torch
            import open_clip

            self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            logger.info(f"BiomedCLIP: carregando modelo em {self._device}…")

            model, preprocess_train, preprocess_val = open_clip.create_model_and_transforms(
                "hf-hub:microsoft/BiomedCLIP-PubMedBERT_256-vit_base_patch16_224",
                device=self._device,
            )
            self._tokenizer = open_clip.get_tokenizer(
                "hf-hub:microsoft/BiomedCLIP-PubMedBERT_256-vit_base_patch16_224"
            )

            model.eval()
            self._model = model
            self._preprocess = preprocess_val

            self._loaded = True
            logger.info("BiomedCLIP: modelo carregado com sucesso")
            return True

        except Exception as e:
            logger.warning(f"BiomedCLIP: falha ao carregar ({e}). Usando simulação.")
            self._loaded = False
            return False

    # ------------------------------------------------------------------
    def analyze(self, image: np.ndarray) -> BiomedCLIPResult:
        """Executa análise zero-shot completa."""
        if self._loaded:
            return self._infer(image)
        return self._simulate(image)

    # ------------------------------------------------------------------
    def _infer(self, image: np.ndarray) -> BiomedCLIPResult:
        """Inferência real com BiomedCLIP."""
        import torch
        from PIL import Image as PILImage

        start = time.perf_counter()
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        pil_img = PILImage.fromarray(rgb)
        img_tensor = self._preprocess(pil_img).unsqueeze(0).to(self._device)

        # Etiologia
        etiology_probs = self._zero_shot(
            img_tensor,
            list(WOUND_ETIOLOGY_PROMPTS.keys())
        )
        etiology_map: Dict[int, float] = {}
        for prompt, class_id in WOUND_ETIOLOGY_PROMPTS.items():
            idx = list(WOUND_ETIOLOGY_PROMPTS.keys()).index(prompt)
            etiology_map[class_id] = etiology_map.get(class_id, 0) + float(etiology_probs[idx])

        # Tecido
        tissue_scores_raw = self._zero_shot(img_tensor, WOUND_TISSUE_PROMPTS)
        tissue_labels = ["Granulação", "Esfacelo", "Necrose", "Epitelização", "Misto"]
        tissue_scores = {lbl: float(tissue_scores_raw[i]) for i, lbl in enumerate(tissue_labels)}

        # Severidade
        severity_raw = self._zero_shot(img_tensor, WOUND_SEVERITY_PROMPTS)
        severity_scores = [float(s) for s in severity_raw]
        severity_index = float(np.dot(severity_scores, [0.0, 0.33, 0.67, 1.0]))

        # Infecção
        infection_raw = self._zero_shot(img_tensor, INFECTION_PROMPTS)
        infection_labels = ["Infectada", "Limpa", "Biofilme", "Celulite"]
        infection_scores = {lbl: float(infection_raw[i]) for i, lbl in enumerate(infection_labels)}
        infected_score = infection_scores["Infectada"] + infection_scores.get("Celulite", 0)
        clean_score = infection_scores["Limpa"]
        infection_risk = infected_score / (infected_score + clean_score + 1e-8)

        elapsed_ms = (time.perf_counter() - start) * 1000

        return BiomedCLIPResult(
            etiology_probs=etiology_map,
            tissue_scores=tissue_scores,
            severity_scores=severity_scores,
            severity_index=severity_index,
            infection_scores=infection_scores,
            infection_risk=min(infection_risk, 1.0),
            inference_time_ms=elapsed_ms,
            model_loaded=True,
        )

    # ------------------------------------------------------------------
    def _zero_shot(self, img_tensor, prompts: List[str]) -> np.ndarray:
        """Executa classificação zero-shot dado imagem e prompts textuais."""
        import torch

        tokens = self._tokenizer(prompts).to(self._device)
        with torch.no_grad():
            img_feat = self._model.encode_image(img_tensor)
            txt_feat = self._model.encode_text(tokens)

            img_feat = img_feat / img_feat.norm(dim=-1, keepdim=True)
            txt_feat = txt_feat / txt_feat.norm(dim=-1, keepdim=True)

            similarity = (img_feat @ txt_feat.T).squeeze(0)
            probs = torch.softmax(similarity * 100, dim=0).cpu().numpy()
        return probs

    # ------------------------------------------------------------------
    def _simulate(self, image: np.ndarray) -> BiomedCLIPResult:
        """Simulação baseada em heurísticas de cor/textura."""
        start = time.perf_counter()

        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        h_ch, s_ch, v_ch = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        mean_h = float(np.mean(h_ch))
        mean_s = float(np.mean(s_ch))
        mean_v = float(np.mean(v_ch))
        tex_var = float(np.var(gray))

        # Etiologia simulada
        et = np.array([0.25, 0.15, 0.20, 0.25, 0.15], dtype=np.float32)
        if mean_h < 20 and mean_s > 100:
            et[0] += 0.3   # Venosa
        if mean_v > 150:
            et[1] += 0.2   # Arterial
        if 15 < mean_h < 35:
            et[2] += 0.25  # Diabética
        if mean_v < 100:
            et[3] += 0.3   # Pressão
        if tex_var < 1500:
            et[4] += 0.2   # Cirúrgica
        et = et / et.sum()
        etiology_probs = {i: float(et[i]) for i in range(5)}

        # Tecido simulado
        red_frac = float(np.mean(((h_ch <= 10) | (h_ch >= 170)) & (s_ch > 80) & (v_ch > 60)))
        yel_frac = float(np.mean((h_ch >= 15) & (h_ch <= 35) & (s_ch > 50)))
        dark_frac = float(np.mean(v_ch < 50))
        pink_frac = float(np.mean((h_ch <= 15) & (s_ch >= 20) & (s_ch <= 80) & (v_ch > 150)))
        tissue_scores = {
            "Granulação": red_frac,
            "Esfacelo": yel_frac,
            "Necrose": dark_frac,
            "Epitelização": pink_frac,
            "Misto": max(0.05, 1 - red_frac - yel_frac - dark_frac - pink_frac),
        }
        t_total = sum(tissue_scores.values()) or 1
        tissue_scores = {k: v / t_total for k, v in tissue_scores.items()}

        # Severidade simulada
        wound_frac = red_frac + yel_frac + dark_frac
        sev = np.array([
            max(0, 1 - wound_frac * 3),
            max(0, wound_frac - 0.1) * 2,
            dark_frac * 3,
            dark_frac * 5 if dark_frac > 0.2 else 0.05,
        ], dtype=np.float32)
        sev = sev / (sev.sum() + 1e-8)
        severity_scores = [float(s) for s in sev]
        severity_index = float(np.dot(sev, [0.0, 0.33, 0.67, 1.0]))

        # Infecção simulada
        green_frac = float(np.mean((h_ch >= 35) & (h_ch <= 85) & (s_ch > 50)))
        redness = float(np.mean(((h_ch <= 10) | (h_ch >= 160)) & (s_ch > 100)))
        infection_scores = {
            "Infectada": min(green_frac * 2 + redness * 0.5, 0.7),
            "Limpa": max(0.3, 1 - green_frac * 3 - redness),
            "Biofilme": min(green_frac * 3, 0.5),
            "Celulite": min(redness * 2, 0.4),
        }
        i_total = sum(infection_scores.values()) or 1
        infection_scores = {k: v / i_total for k, v in infection_scores.items()}
        infected = infection_scores["Infectada"] + infection_scores["Celulite"]
        clean = infection_scores["Limpa"]
        infection_risk = infected / (infected + clean + 1e-8)

        elapsed_ms = (time.perf_counter() - start) * 1000

        return BiomedCLIPResult(
            etiology_probs=etiology_probs,
            tissue_scores=tissue_scores,
            severity_scores=severity_scores,
            severity_index=min(severity_index, 1.0),
            infection_scores=infection_scores,
            infection_risk=min(infection_risk, 1.0),
            inference_time_ms=elapsed_ms,
            model_loaded=False,
        )

    @property
    def is_loaded(self) -> bool:
        return self._loaded
