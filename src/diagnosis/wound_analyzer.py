"""
REDISUS - Sistema de Diagnóstico de Feridas
Analisador de Feridas Integrado

Este módulo integra segmentação e classificação para análise completa.
Inclui EnhancedWoundAnalyzer com suporte a ensemble multi-modelo
(DermaIntel ViT + MedSAM + BiomedCLIP).
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import cv2
import numpy as np
from loguru import logger

from ..core.config import config, TISSUE_NAMES, ETIOLOGY_NAMES
from .tissue_segmenter import TissueSegmentationResult, UNetSegmenter, WoundAreaCalculator
from .etiology_classifier import EtiologyClassificationResult, EtiologyClassifier


@dataclass
class WoundAnalysisResult:
    """Resultado completo da análise de ferida"""
    # Resultados dos modelos
    segmentation: TissueSegmentationResult
    classification: EtiologyClassificationResult
    
    # Métricas calculadas
    wound_area_cm2: Optional[float]
    tissue_distribution: Dict[str, float]
    
    # Metadados
    image_size: Tuple[int, int]
    total_inference_time_ms: float
    
    def to_dict(self) -> Dict:
        """Converte resultado para dicionário (serialização)"""
        return {
            "etiology": {
                "primary": self.classification.primary_prediction.class_name,
                "confidence": round(self.classification.primary_prediction.confidence, 3),
                "description": self.classification.primary_prediction.description,
                "all_probabilities": self.classification.probabilities,
                "needs_review": self.classification.needs_review,
            },
            "segmentation": {
                "tissue_percentages": self.segmentation.tissue_percentages,
                "wound_area_pixels": self.segmentation.wound_area_pixels,
                "wound_area_cm2": self.wound_area_cm2,
            },
            "metadata": {
                "image_size": self.image_size,
                "inference_time_ms": round(self.total_inference_time_ms, 2),
            }
        }
    
    def get_summary(self) -> str:
        """Retorna resumo textual da análise"""
        lines = [
            "=" * 50,
            "ANÁLISE DE FERIDA - REDISUS",
            "=" * 50,
            "",
            "📋 ETIOLOGIA IDENTIFICADA:",
            f"   {self.classification.primary_prediction.class_name}",
            f"   Confiança: {self.classification.primary_prediction.confidence:.1%}",
            "",
            "📝 Descrição:",
            f"   {self.classification.primary_prediction.description}",
            "",
            "🔬 COMPOSIÇÃO TECIDUAL:",
        ]
        
        for tissue, percentage in self.segmentation.tissue_percentages.items():
            if percentage > 0.1:  # Só mostra tecidos com > 0.1%
                lines.append(f"   • {tissue}: {percentage:.1f}%")
        
        lines.extend([
            "",
            "📏 ÁREA DA FERIDA:",
            f"   {self.segmentation.wound_area_pixels:,} pixels",
        ])
        
        if self.wound_area_cm2:
            lines.append(f"   {self.wound_area_cm2:.2f} cm²")
        
        lines.extend([
            "",
            f"⏱️ Tempo de processamento: {self.total_inference_time_ms:.0f}ms",
            "=" * 50,
        ])
        
        if self.classification.needs_review:
            lines.insert(-1, "")
            lines.insert(-1, "⚠️ RECOMENDAÇÃO: Revisar classificação com especialista")
        
        return "\n".join(lines)


class WoundAnalyzer:
    """
    Analisador completo de feridas.
    
    Combina:
    - Segmentação de tecidos (U-Net)
    - Classificação de etiologia (EfficientNet)
    - Cálculo de área
    - Análise integrada
    
    Uso:
        analyzer = WoundAnalyzer()
        analyzer.load_models()
        
        result = analyzer.analyze(image)
        print(result.get_summary())
    """
    
    def __init__(
        self,
        segmenter: Optional[UNetSegmenter] = None,
        classifier: Optional[EtiologyClassifier] = None,
        parallel: bool = True
    ):
        """
        Args:
            segmenter: Instância do segmentador (ou cria novo)
            classifier: Instância do classificador (ou cria novo)
            parallel: Executar segmentação e classificação em paralelo
        """
        self.segmenter = segmenter or UNetSegmenter()
        self.classifier = classifier or EtiologyClassifier()
        self.parallel = parallel
        
        self._models_loaded = False
        
    def load_models(self):
        """Carrega todos os modelos"""
        logger.info("Carregando modelos de diagnóstico...")
        
        self.segmenter.load_model()
        self.classifier.load_model()
        
        self._models_loaded = True
        logger.info("Modelos carregados com sucesso")
    
    def analyze(
        self,
        image: np.ndarray,
        pixels_per_cm: Optional[float] = None
    ) -> WoundAnalysisResult:
        """
        Realiza análise completa de uma ferida.
        
        Args:
            image: Imagem BGR da ferida
            pixels_per_cm: Escala para cálculo de área em cm²
            
        Returns:
            WoundAnalysisResult com todos os resultados
        """
        if not self._models_loaded:
            self.load_models()
        
        image_size = (image.shape[1], image.shape[0])
        
        if self.parallel:
            # Execução paralela
            with ThreadPoolExecutor(max_workers=2) as executor:
                seg_future = executor.submit(self.segmenter.segment, image)
                cls_future = executor.submit(self.classifier.classify, image)
                
                segmentation = seg_future.result()
                classification = cls_future.result()
        else:
            # Execução sequencial
            segmentation = self.segmenter.segment(image)
            classification = self.classifier.classify(image)
        
        # Calcula área em cm² se escala disponível
        wound_area_cm2 = None
        if pixels_per_cm is not None:
            wound_area_cm2 = WoundAreaCalculator.calculate_area_cm2(
                segmentation.mask,
                pixels_per_cm
            )
        
        total_time = segmentation.inference_time_ms + classification.inference_time_ms
        
        return WoundAnalysisResult(
            segmentation=segmentation,
            classification=classification,
            wound_area_cm2=wound_area_cm2,
            tissue_distribution=segmentation.tissue_percentages,
            image_size=image_size,
            total_inference_time_ms=total_time
        )
    
    def analyze_with_visualization(
        self,
        image: np.ndarray,
        pixels_per_cm: Optional[float] = None
    ) -> Tuple[WoundAnalysisResult, np.ndarray]:
        """
        Analisa ferida e retorna visualização.
        
        Returns:
            (WoundAnalysisResult, imagem_visualização)
        """
        result = self.analyze(image, pixels_per_cm)
        
        # Cria visualização
        visualization = self._create_visualization(image, result)
        
        return result, visualization
    
    def _create_visualization(
        self,
        image: np.ndarray,
        result: WoundAnalysisResult
    ) -> np.ndarray:
        """Cria imagem de visualização com overlay e informações"""
        h, w = image.shape[:2]
        
        # Cria canvas maior para incluir informações
        info_width = 400
        canvas = np.zeros((h, w + info_width, 3), dtype=np.uint8)
        
        # Imagem original com overlay de segmentação
        overlay = result.segmentation.get_overlay(image, alpha=0.4)
        canvas[:, :w] = overlay
        
        # Painel de informações (fundo escuro)
        info_panel = canvas[:, w:]
        info_panel[:] = (40, 40, 40)
        
        # Título
        cv2.putText(
            info_panel,
            "ANALISE REDISUS",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2
        )
        
        # Linha separadora
        cv2.line(info_panel, (20, 55), (info_width - 20, 55), (100, 100, 100), 1)
        
        # Etiologia
        y = 90
        cv2.putText(
            info_panel,
            "ETIOLOGIA:",
            (20, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (200, 200, 200),
            1
        )
        
        y += 30
        etiology = result.classification.primary_prediction.class_name
        confidence = result.classification.primary_prediction.confidence
        
        # Cor baseada na confiança
        if confidence >= 0.7:
            color = (0, 255, 0)  # Verde
        elif confidence >= 0.5:
            color = (0, 255, 255)  # Amarelo
        else:
            color = (0, 0, 255)  # Vermelho
        
        cv2.putText(
            info_panel,
            etiology,
            (20, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            color,
            2
        )
        
        y += 25
        cv2.putText(
            info_panel,
            f"Confianca: {confidence:.1%}",
            (20, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (150, 150, 150),
            1
        )
        
        # Composição tecidual
        y += 50
        cv2.putText(
            info_panel,
            "TECIDOS:",
            (20, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (200, 200, 200),
            1
        )
        
        tissue_colors = {
            "Granulação": (0, 0, 255),
            "Esfacelo": (0, 255, 255),
            "Necrose": (128, 128, 128),
            "Pele Perilesional": (0, 255, 0),
        }
        
        for tissue, percentage in result.segmentation.tissue_percentages.items():
            if tissue == "Background" or percentage < 0.5:
                continue
            
            y += 25
            color = tissue_colors.get(tissue, (255, 255, 255))
            
            # Quadrado colorido
            cv2.rectangle(
                info_panel,
                (20, y - 12),
                (35, y + 3),
                color,
                -1
            )
            
            # Texto
            cv2.putText(
                info_panel,
                f"{tissue}: {percentage:.1f}%",
                (45, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1
            )
        
        # Área
        y += 50
        cv2.putText(
            info_panel,
            "AREA:",
            (20, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (200, 200, 200),
            1
        )
        
        y += 25
        area_text = f"{result.segmentation.wound_area_pixels:,} px"
        if result.wound_area_cm2:
            area_text += f" ({result.wound_area_cm2:.2f} cm2)"
        
        cv2.putText(
            info_panel,
            area_text,
            (20, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1
        )
        
        # Aviso se necessário
        if result.classification.needs_review:
            y += 50
            cv2.putText(
                info_panel,
                "! REVISAR COM ESPECIALISTA",
                (20, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 165, 255),
                1
            )
        
        return canvas


class EnhancedWoundAnalyzer(WoundAnalyzer):
    """
    Analisador de feridas aprimorado com ensemble multi-modelo.

    Adiciona camada de IA pré-treinada sobre o WoundAnalyzer base:
      - DermaIntel ViT (classificação)
      - MedSAM (segmentação)
      - BiomedCLIP (zero-shot: classificação + infecção + severidade)
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._ensemble = None
        self._ensemble_loaded = False

    def _load_ensemble(self):
        """Carrega modelos do ensemble (camada adicional)."""
        try:
            from ..ai_layer import (
                EnsembleOrchestrator,
                DermaIntelClassifier,
                MedSAMSegmenter,
                BiomedCLIPAnalyzer,
            )
            self._ensemble = EnsembleOrchestrator(
                dermaintel=DermaIntelClassifier(),
                medsam=MedSAMSegmenter(),
                biomedclip=BiomedCLIPAnalyzer(),
            )
            status = self._ensemble.load_all_models()
            self._ensemble_loaded = True
            logger.info(f"Ensemble carregado: {status}")
        except Exception as e:
            logger.warning(f"Ensemble indisponível: {e}")
            self._ensemble_loaded = False

    def analyze_ensemble(
        self,
        image: np.ndarray,
        pixels_per_cm: Optional[float] = None,
        bbox: Optional[tuple] = None,
    ):
        """
        Análise completa: base + ensemble.

        Returns:
            (WoundAnalysisResult, EnsembleResult ou None)
        """
        base_result = self.analyze(image, pixels_per_cm)

        if not self._ensemble_loaded:
            self._load_ensemble()

        ensemble_result = None
        if self._ensemble is not None:
            try:
                eff_probs = {
                    p.class_id: p.confidence
                    for p in base_result.classification.all_predictions
                }
                ensemble_result = self._ensemble.predict(
                    image=image,
                    bbox=bbox,
                    efficientnet_probs=eff_probs,
                    unet_mask=base_result.segmentation.mask,
                )
            except Exception as e:
                logger.error(f"Ensemble prediction error: {e}")

        return base_result, ensemble_result

    @property
    def ensemble_available(self) -> bool:
        return self._ensemble_loaded and self._ensemble is not None

    @property
    def models_status(self) -> Dict[str, bool]:
        if self._ensemble is None:
            return {}
        return {
            "dermaintel": self._ensemble.dermaintel.is_loaded,
            "medsam": self._ensemble.medsam.is_loaded,
            "biomedclip": self._ensemble.biomedclip.is_loaded,
        }
