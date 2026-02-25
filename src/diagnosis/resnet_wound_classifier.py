# -*- coding: utf-8 -*-
"""
HEAL+ / REDISUS — Classificador de Feridas ResNet50 em Dois Estágios
=====================================================================

Implementação do pipeline de classificação baseado no notebook de treinamento
(wounds_classifier_resnet50_semAugmentation.ipynb).

Arquitetura de Dois Estágios:
  Estágio 1: Normal vs. Ferida (classificação binária)
  Estágio 2: Tipo de Ferida (Diabetic Wounds, Pressure Wounds, Venous Wounds)

Modelo base: ResNet50 (ImageNet, transfer learning)
Entrada: 224×224, normalização ImageNet
Explainabilidade: Grad-CAM sobre layer4

Uso:
    classifier = TwoStageWoundClassifier()
    result = classifier.predict(image_bgr)
    heatmap = classifier.grad_cam(image_bgr)
"""

import os
import json
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Torch imports (com fallback gracioso)
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torchvision import models, transforms
    from PIL import Image
    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False
    logger.warning("PyTorch não disponível. Classificador ResNet50 desabilitado.")


# ============================================================
# DATACLASSES DE RESULTADO
# ============================================================

@dataclass
class StageOnePrediction:
    """Resultado do Estágio 1 (Normal vs. Ferida)."""
    is_wound: bool
    confidence: float
    probabilities: Dict[str, float] = field(default_factory=dict)
    # Probabilities: {'Normal': 0.05, 'Wound': 0.95}


@dataclass
class StageTwoPrediction:
    """Resultado do Estágio 2 (Tipo de Ferida)."""
    wound_type: str          # 'Diabetic Wounds', 'Pressure Wounds', 'Venous Wounds'
    wound_type_pt: str       # Nome em português
    confidence: float
    probabilities: Dict[str, float] = field(default_factory=dict)
    top_predictions: List[Dict] = field(default_factory=list)


@dataclass
class TwoStageResult:
    """Resultado completo da classificação de dois estágios."""
    # Estágio 1
    stage1: StageOnePrediction = None
    # Estágio 2 (None se Estágio 1 classificou como Normal)
    stage2: Optional[StageTwoPrediction] = None
    # Grad-CAM heatmap (opcional)
    grad_cam_heatmap: Optional[np.ndarray] = None
    grad_cam_overlay: Optional[np.ndarray] = None
    # Classificação final consolidada
    final_class: str = ""
    final_class_pt: str = ""
    final_confidence: float = 0.0
    # Flags
    is_wound: bool = False
    model_available: bool = False
    # Confiança e revisão (baseado no notebook wounds_classifier_embeddings.ipynb)
    needs_expert_review: bool = False
    confidence_level: str = ""       # "very_high", "high", "moderate", "low"
    confidence_entropy: float = 0.0  # Entropia da distribuição
    confidence_margin: float = 0.0   # Margem entre top-2 classes

    def to_dict(self) -> Dict:
        """Serializa para dicionário."""
        result = {
            "is_wound": self.is_wound,
            "final_class": self.final_class,
            "final_class_pt": self.final_class_pt,
            "final_confidence": self.final_confidence,
            "model_available": self.model_available,
            "needs_expert_review": self.needs_expert_review,
            "confidence_level": self.confidence_level,
            "confidence_entropy": round(self.confidence_entropy, 4),
            "confidence_margin": round(self.confidence_margin, 4),
        }
        if self.stage1:
            result["stage1"] = {
                "is_wound": self.stage1.is_wound,
                "confidence": self.stage1.confidence,
                "probabilities": self.stage1.probabilities,
            }
        if self.stage2:
            result["stage2"] = {
                "wound_type": self.stage2.wound_type,
                "wound_type_pt": self.stage2.wound_type_pt,
                "confidence": self.stage2.confidence,
                "probabilities": self.stage2.probabilities,
                "top_predictions": self.stage2.top_predictions,
            }
        return result


# ============================================================
# MAPEAMENTOS CLÍNICOS
# ============================================================

# Nomes do notebook → Nomes clínicos em pt-BR
WOUND_TYPE_PT = {
    "Normal": "Pele Normal / Saudável",
    "Wound": "Ferida Identificada",
    "Diabetic Wounds": "Ferida Diabética (Pé Diabético)",
    "Pressure Wounds": "Lesão por Pressão",
    "Venous Wounds": "Úlcera Venosa",
}

# Mapeamento de tipos de ferida → etiologia do sistema
WOUND_TO_ETIOLOGY = {
    "Diabetic Wounds": "diabetic_foot",
    "Pressure Wounds": "pressure_injury",
    "Venous Wounds": "venous_ulcer",
}

# Ações clínicas por tipo de ferida
WOUND_CLINICAL_ACTIONS = {
    "Diabetic Wounds": (
        "Ferida diabética identificada. Avaliar neuropatia periférica, "
        "perfusão vascular (ITB), controle glicêmico (HbA1c). "
        "Indicar descarregamento do membro (palmilhas, gesso de contato total). "
        "Desbridamento conforme necessidade. Monitorar sinais de infecção."
    ),
    "Pressure Wounds": (
        "Lesão por pressão identificada. Classificar estágio (I-IV). "
        "Implementar protocolo de reposicionamento (a cada 2h). "
        "Avaliar superfície de apoio (colchão pneumático). "
        "Otimizar nutrição (proteínas, zinco, vitamina C). "
        "Monitorar Escala de Braden periodicamente."
    ),
    "Venous Wounds": (
        "Úlcera venosa identificada. Avaliar insuficiência venosa (eco-Doppler). "
        "Indicar terapia compressiva (bandagem ou meia elástica) se ITB > 0.8. "
        "Controlar edema. Manter leito úmido com coberturas adequadas "
        "(espuma, alginato). Elevar membros inferiores."
    ),
}

# Confiança mínima para cada estágio
STAGE1_CONFIDENCE_THRESHOLD = 0.60
STAGE2_CONFIDENCE_THRESHOLD = 0.45

# Threshold de confiança para revisão especialista (do notebook embeddings)
EXPERT_REVIEW_THRESHOLD = 0.80
HIGH_CONFIDENCE_THRESHOLD = 0.95  # Predições de alta confiança (melhor precision)


# ============================================================
# GRAD-CAM
# ============================================================

class GradCAM:
    """
    Extractor de Grad-CAM para visualização de ativações.
    
    Gera mapa de calor que indica quais regiões da imagem o modelo
    usou para fazer a predição — essencial para explicabilidade clínica.
    """

    def __init__(self, model, target_layer):
        self.model = model
        self.target_layer = target_layer
        self.gradients = None
        self.activations = None
        self._hooks = []

        # Registra hooks
        self._hooks.append(
            target_layer.register_forward_hook(self._save_activation)
        )
        self._hooks.append(
            target_layer.register_full_backward_hook(self._save_gradient)
        )

    def _save_activation(self, module, input, output):
        self.activations = output.detach()

    def _save_gradient(self, module, grad_in, grad_out):
        self.gradients = grad_out[0].detach()

    def __call__(self, x, class_idx=None):
        """
        Gera mapa Grad-CAM.
        
        Args:
            x: Tensor [1, 3, H, W] normalizado
            class_idx: Índice da classe alvo (None = classe predita)
            
        Returns:
            (cam, predicted_class_idx, confidence)
        """
        self.model.eval()
        output = self.model(x)
        probs = F.softmax(output, dim=1)
        confidence, predicted_class = torch.max(probs, 1)

        if class_idx is None:
            class_idx = predicted_class.item()

        self.model.zero_grad()
        one_hot = torch.zeros_like(output)
        one_hot[0][class_idx] = 1
        output.backward(gradient=one_hot, retain_graph=True)

        gradients = self.gradients.cpu().numpy()[0]
        activations = self.activations.cpu().numpy()[0]

        # Pesos = média global dos gradientes por canal
        weights = np.mean(gradients, axis=(1, 2))

        # Combinação ponderada
        cam = np.zeros(activations.shape[1:], dtype=np.float32)
        for i, w in enumerate(weights):
            cam += w * activations[i]

        # ReLU + normalização
        cam = np.maximum(cam, 0)
        if cam.max() > 0:
            cam = cam / cam.max()

        # Redimensiona para tamanho da imagem de entrada
        cam = cv2.resize(cam, (x.shape[3], x.shape[2]))

        return cam, class_idx, confidence.item()

    def remove_hooks(self):
        """Remove hooks registrados (limpeza de memória)."""
        for hook in self._hooks:
            hook.remove()
        self._hooks.clear()


# ============================================================
# CLASSIFICADOR DE DOIS ESTÁGIOS
# ============================================================

class TwoStageWoundClassifier:
    """
    Classificador de feridas em dois estágios usando ResNet50.
    
    Estágio 1: Detecta se a imagem contém uma ferida (Normal vs. Wound)
    Estágio 2: Classifica o tipo de ferida (Diabetic, Pressure, Venous)
    
    Baseado no notebook wounds_classifier_resnet50_semAugmentation.ipynb
    """

    # Classes do modelo
    STAGE1_CLASSES = ['Normal', 'Wound']
    STAGE2_CLASSES = ['Diabetic Wounds', 'Pressure Wounds', 'Venous Wounds']

    # Normalização ImageNet (padrão ResNet50)
    IMAGENET_MEAN = [0.485, 0.456, 0.406]
    IMAGENET_STD = [0.229, 0.224, 0.225]
    INPUT_SIZE = 224

    def __init__(
        self,
        stage1_path: Optional[str] = None,
        stage2_path: Optional[str] = None,
        device: Optional[str] = None,
    ):
        """
        Args:
            stage1_path: Caminho para pesos do modelo estágio 1 (.pth)
            stage2_path: Caminho para pesos do modelo estágio 2 (.pth)
            device: 'cuda' ou 'cpu' (auto-detecção se None)
        """
        self.available = False
        self.stage1_available = False
        self.stage2_available = False
        self._model_s1 = None
        self._model_s2 = None
        self._device = None
        self._transform = None

        if not _TORCH_AVAILABLE:
            logger.warning("PyTorch não instalado — classificador desabilitado")
            return

        # Device
        if device:
            self._device = torch.device(device)
        else:
            self._device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

        logger.info(f"[ResNet50] Dispositivo: {self._device}")

        # Transform de inferência (mesmo do notebook)
        self._transform = transforms.Compose([
            transforms.Resize((self.INPUT_SIZE, self.INPUT_SIZE)),
            transforms.ToTensor(),
            transforms.Normalize(self.IMAGENET_MEAN, self.IMAGENET_STD),
        ])

        # Carrega modelos
        self._load_models(stage1_path, stage2_path)

    def _build_resnet50(self, num_classes: int, use_mlp_head: bool = True) -> nn.Module:
        """
        Constrói ResNet50 com cabeça personalizada.
        
        Baseado no SimpleMLPClassifier do notebook wounds_classifier_embeddings.ipynb:
        MLP com 2 camadas ocultas, ReLU, Dropout para melhor robustez.
        
        Args:
            num_classes: Número de classes de saída
            use_mlp_head: Se True, usa MLP head; se False, usa linear simples
                          (compatibilidade com pesos antigos)
        """
        model = models.resnet50(weights=None)  # Sem pretrained (vamos carregar pesos)
        num_ftrs = model.fc.in_features  # 2048 para ResNet50
        
        if use_mlp_head:
            # MLP Head inspirado no notebook (SimpleMLPClassifier)
            # 2 camadas ocultas com dropout progressivo para regularização
            hidden_size = 256
            dropout_rate = 0.25
            model.fc = nn.Sequential(
                nn.Linear(num_ftrs, hidden_size),
                nn.BatchNorm1d(hidden_size),
                nn.ReLU(inplace=True),
                nn.Dropout(dropout_rate),
                nn.Linear(hidden_size, hidden_size),
                nn.BatchNorm1d(hidden_size),
                nn.ReLU(inplace=True),
                nn.Dropout(dropout_rate * 0.5),  # Dropout menor na 2ª camada
                nn.Linear(hidden_size, num_classes),
            )
            logger.info(f"[ResNet50] MLP head: {num_ftrs}→{hidden_size}→{hidden_size}→{num_classes} (dropout={dropout_rate})")
        else:
            # Head linear simples (compatibilidade com pesos legados)
            model.fc = nn.Linear(num_ftrs, num_classes)
        
        return model

    def _load_models(self, stage1_path: Optional[str], stage2_path: Optional[str]):
        """Tenta carregar ambos os modelos."""
        base_dir = Path(__file__).resolve().parent.parent.parent

        # Caminhos de busca para Estágio 1
        s1_candidates = [
            stage1_path,
            str(base_dir / "models" / "wound_classifier_v2" / "modelo_estagio1.pth"),
            str(base_dir / "models" / "resnet50" / "modelo_estagio1.pth"),
            str(base_dir / "modelo_estagio1.pth"),
        ]

        # Caminhos de busca para Estágio 2
        s2_candidates = [
            stage2_path,
            str(base_dir / "models" / "wound_classifier_v2" / "modelo_estagio2_semAugmentation.pth"),
            str(base_dir / "models" / "wound_classifier_v2" / "modelo_estagio2.pth"),
            str(base_dir / "models" / "resnet50" / "modelo_estagio2_semAugmentation.pth"),
            str(base_dir / "models" / "resnet50" / "modelo_estagio2.pth"),
            str(base_dir / "modelo_estagio2_semAugmentation.pth"),
            str(base_dir / "modelo_estagio2.pth"),
        ]

        # Carrega Estágio 1
        for path in s1_candidates:
            if path and os.path.exists(path):
                try:
                    # Tenta MLP head primeiro, fallback para linear
                    self._model_s1 = self._build_resnet50(len(self.STAGE1_CLASSES), use_mlp_head=True)
                    state_dict = torch.load(path, map_location=self._device, weights_only=True)
                    try:
                        self._model_s1.load_state_dict(state_dict)
                    except RuntimeError:
                        # Pesos antigos com head linear — reconstruir sem MLP
                        logger.info("[ResNet50] Pesos S1 legados detectados, usando head linear")
                        self._model_s1 = self._build_resnet50(len(self.STAGE1_CLASSES), use_mlp_head=False)
                        self._model_s1.load_state_dict(state_dict)
                    self._model_s1.to(self._device)
                    self._model_s1.eval()
                    self.stage1_available = True
                    logger.info(f"[ResNet50] Estágio 1 carregado: {Path(path).name}")
                    break
                except Exception as e:
                    logger.warning(f"[ResNet50] Erro ao carregar estágio 1 ({path}): {e}")
                    self._model_s1 = None

        # Carrega Estágio 2
        for path in s2_candidates:
            if path and os.path.exists(path):
                try:
                    # Tenta MLP head primeiro, fallback para linear
                    self._model_s2 = self._build_resnet50(len(self.STAGE2_CLASSES), use_mlp_head=True)
                    state_dict = torch.load(path, map_location=self._device, weights_only=True)
                    try:
                        self._model_s2.load_state_dict(state_dict)
                    except RuntimeError:
                        # Pesos antigos com head linear — reconstruir sem MLP
                        logger.info("[ResNet50] Pesos S2 legados detectados, usando head linear")
                        self._model_s2 = self._build_resnet50(len(self.STAGE2_CLASSES), use_mlp_head=False)
                        self._model_s2.load_state_dict(state_dict)
                    self._model_s2.to(self._device)
                    self._model_s2.eval()
                    self.stage2_available = True
                    logger.info(f"[ResNet50] Estágio 2 carregado: {Path(path).name}")
                    break
                except Exception as e:
                    logger.warning(f"[ResNet50] Erro ao carregar estágio 2 ({path}): {e}")
                    self._model_s2 = None

        self.available = self.stage1_available or self.stage2_available

        if self.available:
            status = []
            if self.stage1_available:
                status.append("S1(Normal/Ferida)")
            if self.stage2_available:
                status.append("S2(Tipo)")
            logger.info(f"[ResNet50] Classificador ativo: {' + '.join(status)}")
        else:
            logger.info("[ResNet50] Nenhum modelo encontrado — classificador por heurística")

    def _preprocess(self, image_bgr: np.ndarray) -> 'torch.Tensor':
        """
        Pré-processa uma imagem BGR do OpenCV para tensor PyTorch.
        
        Args:
            image_bgr: Imagem no formato BGR (OpenCV)
            
        Returns:
            Tensor [1, 3, 224, 224] normalizado
        """
        # BGR → RGB → PIL
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(image_rgb)

        # Aplica transforms
        tensor = self._transform(pil_image)
        tensor = tensor.unsqueeze(0)  # Batch dimension
        return tensor.to(self._device)

    def _predict_with_tta(
        self, model: nn.Module, tensor: 'torch.Tensor', num_classes: int
    ) -> Tuple[np.ndarray, int, float]:
        """
        Predição com Test-Time Augmentation aprimorada.
        
        Inclui as 4 variações originais (flips) mais 2 variações de
        brilho/contraste sutis para maior robustez nas predições,
        totalizando 6 augmentações.
        
        Returns:
            (probabilities_array, predicted_class_idx, confidence)
        """
        model.eval()
        with torch.no_grad():
            predictions = []

            # Original
            out = F.softmax(model(tensor), dim=1)
            predictions.append(out)

            # Horizontal flip
            out = F.softmax(model(torch.flip(tensor, [3])), dim=1)
            predictions.append(out)

            # Vertical flip
            out = F.softmax(model(torch.flip(tensor, [2])), dim=1)
            predictions.append(out)

            # Both flips
            out = F.softmax(model(torch.flip(tensor, [2, 3])), dim=1)
            predictions.append(out)

            # Leve aumento de brilho (+5%) — variação sutil para robustez
            bright = torch.clamp(tensor * 1.05, 0, 1)
            out = F.softmax(model(bright), dim=1)
            predictions.append(out)

            # Leve redução de brilho (-5%)
            dark = torch.clamp(tensor * 0.95, 0, 1)
            out = F.softmax(model(dark), dim=1)
            predictions.append(out)

            # Média das 6 predições
            avg_probs = torch.stack(predictions).mean(dim=0).squeeze(0).cpu().numpy()

        pred_idx = int(np.argmax(avg_probs))
        confidence = float(avg_probs[pred_idx])
        return avg_probs, pred_idx, confidence

    def predict(
        self,
        image_bgr: np.ndarray,
        use_tta: bool = True,
        generate_gradcam: bool = False,
        confidence_threshold: float = None,
    ) -> TwoStageResult:
        """
        Pipeline completo de classificação em dois estágios.
        
        Inclui avaliação de confiança baseada no notebook
        wounds_classifier_embeddings.ipynb (filtragem por threshold,
        entropia, e margem entre top-2 classes).
        
        Args:
            image_bgr: Imagem BGR do OpenCV
            use_tta: Usar Test-Time Augmentation (6 augmentações)
            generate_gradcam: Gerar mapa Grad-CAM para explicabilidade
            confidence_threshold: Threshold customizado (default: EXPERT_REVIEW_THRESHOLD)
            
        Returns:
            TwoStageResult com classificação, confiança calibrada, e Grad-CAM
        """
        review_threshold = confidence_threshold or EXPERT_REVIEW_THRESHOLD
        result = TwoStageResult(model_available=self.available)

        if not self.available or not _TORCH_AVAILABLE:
            return result

        try:
            tensor = self._preprocess(image_bgr)
        except Exception as e:
            logger.error(f"[ResNet50] Erro no pré-processamento: {e}")
            return result

        # ── ESTÁGIO 1: Normal vs. Ferida ──
        if self.stage1_available and self._model_s1 is not None:
            try:
                if use_tta:
                    probs_s1, pred_idx_s1, conf_s1 = self._predict_with_tta(
                        self._model_s1, tensor, len(self.STAGE1_CLASSES)
                    )
                else:
                    self._model_s1.eval()
                    with torch.no_grad():
                        out = F.softmax(self._model_s1(tensor), dim=1)
                        probs_s1 = out.squeeze(0).cpu().numpy()
                        pred_idx_s1 = int(np.argmax(probs_s1))
                        conf_s1 = float(probs_s1[pred_idx_s1])

                is_wound = pred_idx_s1 == 1  # 0=Normal, 1=Wound
                result.stage1 = StageOnePrediction(
                    is_wound=is_wound,
                    confidence=conf_s1,
                    probabilities={
                        cls: float(probs_s1[i])
                        for i, cls in enumerate(self.STAGE1_CLASSES)
                    },
                )
                result.is_wound = is_wound

                if not is_wound:
                    result.final_class = "Normal"
                    result.final_class_pt = WOUND_TYPE_PT["Normal"]
                    result.final_confidence = conf_s1
                    result.needs_expert_review = conf_s1 < review_threshold
                    self._set_confidence_metrics(result, probs_s1)
                    return result

            except Exception as e:
                logger.error(f"[ResNet50] Erro no Estágio 1: {e}")
                # Assume que é ferida e continua para estágio 2
                result.is_wound = True
        else:
            # Sem modelo S1, assume ferida e prossegue
            result.is_wound = True

        # ── ESTÁGIO 2: Tipo de Ferida ──
        if self.stage2_available and self._model_s2 is not None:
            try:
                if use_tta:
                    probs_s2, pred_idx_s2, conf_s2 = self._predict_with_tta(
                        self._model_s2, tensor, len(self.STAGE2_CLASSES)
                    )
                else:
                    self._model_s2.eval()
                    with torch.no_grad():
                        out = F.softmax(self._model_s2(tensor), dim=1)
                        probs_s2 = out.squeeze(0).cpu().numpy()
                        pred_idx_s2 = int(np.argmax(probs_s2))
                        conf_s2 = float(probs_s2[pred_idx_s2])

                wound_type = self.STAGE2_CLASSES[pred_idx_s2]

                # Top predictions ordenadas por confiança
                sorted_indices = np.argsort(probs_s2)[::-1]
                top_preds = []
                for idx in sorted_indices:
                    cls_name = self.STAGE2_CLASSES[idx]
                    top_preds.append({
                        "class": cls_name,
                        "class_pt": WOUND_TYPE_PT.get(cls_name, cls_name),
                        "confidence": float(probs_s2[idx]),
                        "clinical_action": WOUND_CLINICAL_ACTIONS.get(cls_name, ""),
                    })

                result.stage2 = StageTwoPrediction(
                    wound_type=wound_type,
                    wound_type_pt=WOUND_TYPE_PT.get(wound_type, wound_type),
                    confidence=conf_s2,
                    probabilities={
                        cls: float(probs_s2[i])
                        for i, cls in enumerate(self.STAGE2_CLASSES)
                    },
                    top_predictions=top_preds,
                )

                result.final_class = wound_type
                result.final_class_pt = WOUND_TYPE_PT.get(wound_type, wound_type)
                result.final_confidence = conf_s2

                # ── Avaliação de confiança (do notebook embeddings) ──
                result.needs_expert_review = conf_s2 < review_threshold
                self._set_confidence_metrics(result, probs_s2)

                if result.needs_expert_review:
                    logger.info(
                        f"[ResNet50] Revisão recomendada: {wound_type} "
                        f"(conf={conf_s2:.3f} < {review_threshold:.2f})"
                    )

            except Exception as e:
                logger.error(f"[ResNet50] Erro no Estágio 2: {e}")
                result.final_class = "Wound"
                result.final_class_pt = WOUND_TYPE_PT["Wound"]
                result.final_confidence = result.stage1.confidence if result.stage1 else 0.5
                result.needs_expert_review = True
        else:
            result.final_class = "Wound"
            result.final_class_pt = WOUND_TYPE_PT["Wound"]
            result.final_confidence = result.stage1.confidence if result.stage1 else 0.5
            result.needs_expert_review = True

        # ── GRAD-CAM (opcional) ──
        if generate_gradcam:
            try:
                result.grad_cam_heatmap, result.grad_cam_overlay = \
                    self._generate_gradcam(image_bgr, tensor)
            except Exception as e:
                logger.warning(f"[ResNet50] Erro no Grad-CAM: {e}")

        return result

    @staticmethod
    def _set_confidence_metrics(result: 'TwoStageResult', probs: np.ndarray):
        """
        Define métricas de confiança no resultado.
        
        Baseado nas técnicas do notebook wounds_classifier_embeddings.ipynb:
        - Entropia normalizada (incerteza da distribuição)
        - Margem entre top-2 classes (dispersão)
        - Nível de confiança categórico
        """
        # Entropia normalizada
        eps = 1e-10
        probs_clipped = np.clip(probs, eps, 1.0)
        entropy = -np.sum(probs_clipped * np.log(probs_clipped))
        max_entropy = np.log(len(probs))
        if max_entropy > 0:
            entropy /= max_entropy
        result.confidence_entropy = float(entropy)

        # Margem entre top-2
        if len(probs) >= 2:
            sorted_p = np.sort(probs)[::-1]
            result.confidence_margin = float(sorted_p[0] - sorted_p[1])
        else:
            result.confidence_margin = 1.0

        # Nível categórico
        conf = result.final_confidence
        if conf >= HIGH_CONFIDENCE_THRESHOLD:
            result.confidence_level = "very_high"
        elif conf >= EXPERT_REVIEW_THRESHOLD:
            result.confidence_level = "high"
        elif conf >= STAGE1_CONFIDENCE_THRESHOLD:
            result.confidence_level = "moderate"
        else:
            result.confidence_level = "low"

    def _generate_gradcam(
        self,
        image_bgr: np.ndarray,
        tensor: 'torch.Tensor',
    ) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """
        Gera visualização Grad-CAM para o modelo mais relevante.
        
        Usa o modelo S2 se disponível (classificação mais detalhada),
        senão usa S1.
        
        Returns:
            (heatmap_normalized, overlay_bgr)
        """
        if not _TORCH_AVAILABLE:
            return None, None

        # Escolhe modelo e target layer (layer4 do ResNet50)
        if self.stage2_available and self._model_s2 is not None:
            model = self._model_s2
        elif self.stage1_available and self._model_s1 is not None:
            model = self._model_s1
        else:
            return None, None

        target_layer = model.layer4

        # Habilita gradientes temporariamente
        tensor_grad = tensor.clone().requires_grad_(True)

        grad_cam = GradCAM(model, target_layer)
        try:
            cam, pred_idx, confidence = grad_cam(tensor_grad)
        finally:
            grad_cam.remove_hooks()

        # Heatmap colorido
        heatmap_colored = cv2.applyColorMap(
            np.uint8(255 * cam), cv2.COLORMAP_JET
        )

        # Overlay na imagem original redimensionada
        image_resized = cv2.resize(image_bgr, (self.INPUT_SIZE, self.INPUT_SIZE))
        overlay = cv2.addWeighted(image_resized, 0.6, heatmap_colored, 0.4, 0)

        return cam, overlay

    def predict_stage1_only(self, image_bgr: np.ndarray) -> StageOnePrediction:
        """
        Executa apenas o Estágio 1 (Normal vs Ferida).
        Útil para triagem rápida.
        """
        if not self.stage1_available or self._model_s1 is None:
            return StageOnePrediction(is_wound=True, confidence=0.5)

        tensor = self._preprocess(image_bgr)
        probs, pred_idx, conf = self._predict_with_tta(
            self._model_s1, tensor, len(self.STAGE1_CLASSES)
        )

        return StageOnePrediction(
            is_wound=(pred_idx == 1),
            confidence=conf,
            probabilities={
                cls: float(probs[i])
                for i, cls in enumerate(self.STAGE1_CLASSES)
            },
        )

    def predict_stage2_only(self, image_bgr: np.ndarray) -> StageTwoPrediction:
        """
        Executa apenas o Estágio 2 (Tipo de Ferida).
        Assume que a imagem já é uma ferida confirmada.
        """
        if not self.stage2_available or self._model_s2 is None:
            return StageTwoPrediction(
                wound_type="Unknown",
                wound_type_pt="Desconhecido",
                confidence=0.0,
            )

        tensor = self._preprocess(image_bgr)
        probs, pred_idx, conf = self._predict_with_tta(
            self._model_s2, tensor, len(self.STAGE2_CLASSES)
        )

        wound_type = self.STAGE2_CLASSES[pred_idx]
        sorted_indices = np.argsort(probs)[::-1]
        top_preds = []
        for idx in sorted_indices:
            cls_name = self.STAGE2_CLASSES[idx]
            top_preds.append({
                "class": cls_name,
                "class_pt": WOUND_TYPE_PT.get(cls_name, cls_name),
                "confidence": float(probs[idx]),
            })

        return StageTwoPrediction(
            wound_type=wound_type,
            wound_type_pt=WOUND_TYPE_PT.get(wound_type, wound_type),
            confidence=conf,
            probabilities={
                cls: float(probs[i])
                for i, cls in enumerate(self.STAGE2_CLASSES)
            },
            top_predictions=top_preds,
        )

    def get_clinical_action(self, wound_type: str) -> str:
        """Retorna ação clínica recomendada para o tipo de ferida."""
        return WOUND_CLINICAL_ACTIONS.get(wound_type, "")

    def get_status(self) -> Dict:
        """Status do classificador para diagnóstico."""
        return {
            "available": self.available,
            "stage1_available": self.stage1_available,
            "stage2_available": self.stage2_available,
            "device": str(self._device) if self._device else "N/A",
            "model": "ResNet50 (Two-Stage)",
            "stage1_classes": self.STAGE1_CLASSES,
            "stage2_classes": self.STAGE2_CLASSES,
            "input_size": self.INPUT_SIZE,
            "tta": "4-flip (H, V, HV)",
            "explainability": "Grad-CAM (layer4)",
        }


# ============================================================
# FACTORY
# ============================================================

def create_two_stage_classifier(
    stage1_path: Optional[str] = None,
    stage2_path: Optional[str] = None,
) -> TwoStageWoundClassifier:
    """
    Cria instância do classificador de dois estágios.
    
    Busca automaticamente os modelos nos diretórios padrão.
    """
    return TwoStageWoundClassifier(
        stage1_path=stage1_path,
        stage2_path=stage2_path,
    )
