#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
REDISUS - EXEMPLO: ANALISE ENSEMBLE MULTI-MODELO
===============================================================================

Demonstra o uso da camada adicional de IA para analise robusta de feridas.

Pipeline completo:
  1. Carrega imagem da ferida
  2. Executa classificacao standalone com cada modelo
  3. Executa ensemble (fusao de todos os modelos)
  4. Exibe resultados comparativos

Modelos utilizados:
  - DermaIntel ViT   : Classificacao de 7 tipos de ferida (fine-tuned)
  - MedSAM            : Segmentacao precisa (Segment Anything medico)
  - BiomedCLIP        : Analise zero-shot (classificacao, infeccao, severidade)
  - EfficientNet      : Classificador base REDISUS (5 classes etiologia)
  - U-Net             : Segmentador base REDISUS (tecidos)

Uso:
    python examples/ensemble_analysis_demo.py --image path/to/wound.jpg
    python examples/ensemble_analysis_demo.py --image path/to/wound.jpg --save
===============================================================================
"""

import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np

# Adiciona raiz do projeto ao path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def run_individual_models(image: np.ndarray):
    """Executa cada modelo individualmente e exibe resultados."""
    from src.ai_layer import DermaIntelClassifier, MedSAMSegmenter, BiomedCLIPAnalyzer

    print("=" * 60)
    print("  FASE 1: MODELOS INDIVIDUAIS")
    print("=" * 60)

    # --- DermaIntel ---
    print("\n[1/3] DermaIntel ViT (classificacao)")
    dermaintel = DermaIntelClassifier()
    dermaintel.load_model()
    result_di = dermaintel.classify(image)

    top = result_di.top_prediction
    print(f"  Predicao:   {top.class_name} ({top.confidence:.1%})")
    print(f"  Tempo:      {result_di.inference_time_ms:.0f}ms")
    print(f"  Modelo:     {'HuggingFace' if result_di.model_loaded else 'Simulacao'}")

    # Probabilidades mapeadas para REDISUS
    redisus_probs = result_di.get_redisus_probabilities()
    from src.core.config import ETIOLOGY_NAMES
    print("  Mapeamento REDISUS:")
    for cid in sorted(redisus_probs, key=redisus_probs.get, reverse=True):
        print(f"    {ETIOLOGY_NAMES[cid]}: {redisus_probs[cid]:.1%}")

    # --- MedSAM ---
    print("\n[2/3] MedSAM (segmentacao)")
    medsam = MedSAMSegmenter()
    medsam.load_model()
    result_ms = medsam.segment(image)

    print(f"  Area:         {result_ms.wound_area_pixels:,} pixels")
    print(f"  Perimetro:    {result_ms.wound_perimeter_pixels:.0f} pixels")
    print(f"  Circularidade: {result_ms.circularity:.3f}")
    print(f"  Tempo:        {result_ms.inference_time_ms:.0f}ms")
    print(f"  Modelo:       {'SAM' if result_ms.model_loaded else 'GrabCut (simulacao)'}")

    # --- BiomedCLIP ---
    print("\n[3/3] BiomedCLIP (zero-shot)")
    biomedclip = BiomedCLIPAnalyzer()
    biomedclip.load_model()
    result_bc = biomedclip.analyze(image)

    best_etiology = max(result_bc.etiology_probs, key=result_bc.etiology_probs.get)
    print(f"  Etiologia:     {ETIOLOGY_NAMES[best_etiology]} ({result_bc.etiology_probs[best_etiology]:.1%})")
    print(f"  Severidade:    {result_bc.severity_index:.2f}/1.00")
    print(f"  Risco infeccao: {result_bc.infection_risk:.1%}")
    print(f"  Tempo:         {result_bc.inference_time_ms:.0f}ms")
    print(f"  Modelo:        {'BiomedCLIP' if result_bc.model_loaded else 'Heuristica (simulacao)'}")

    return dermaintel, medsam, biomedclip


def run_ensemble(
    image: np.ndarray,
    dermaintel,
    medsam,
    biomedclip,
):
    """Executa o ensemble completo combinando todos os modelos."""
    from src.ai_layer import EnsembleOrchestrator
    from src.core.config import ETIOLOGY_NAMES

    print("\n" + "=" * 60)
    print("  FASE 2: ENSEMBLE MULTI-MODELO")
    print("=" * 60)

    # Cria orquestrador com instancias ja carregadas
    orchestrator = EnsembleOrchestrator(
        dermaintel=dermaintel,
        medsam=medsam,
        biomedclip=biomedclip,
    )
    # Modelos ja estao carregados, marca como loaded
    orchestrator._loaded = True

    # Simula probabilidades do EfficientNet (modelo base REDISUS)
    # Em producao, viriam do WoundAnalyzer.analyze()
    efficientnet_probs = {i: 0.2 for i in range(5)}  # uniforme como placeholder

    # Simula mascara U-Net como placeholder
    h, w = image.shape[:2]
    unet_mask = np.zeros((h, w), dtype=np.uint8)

    # Executa ensemble
    result = orchestrator.predict(
        image=image,
        efficientnet_probs=efficientnet_probs,
        unet_mask=unet_mask,
    )

    # Exibe resultados
    cls = result.classification
    print(f"\n  Etiologia (ensemble):  {cls.class_name}")
    print(f"  Confianca:             {cls.confidence:.1%}")
    print(f"  Modelos concordam:     {'SIM' if cls.agreement.models_agree else 'NAO'}")
    print(f"  Score concordancia:    {cls.agreement.agreement_score:.1%}")
    print(f"  Boost confianca:       {cls.agreement.confidence_boost:.2f}x")

    print("\n  Predicoes individuais:")
    for model_name, pred in cls.agreement.individual_predictions.items():
        print(f"    {model_name:15s} -> {pred}")

    print(f"\n  Probabilidades ensemble:")
    for cid in sorted(cls.all_probabilities, key=cls.all_probabilities.get, reverse=True):
        name = ETIOLOGY_NAMES.get(cid, f"Classe {cid}")
        print(f"    {name}: {cls.all_probabilities[cid]:.1%}")

    # Segmentacao
    if result.segmentation is not None:
        seg = result.segmentation
        print(f"\n  Segmentacao ensemble:")
        print(f"    Area ferida:    {seg.wound_area_pixels:,} pixels")
        print(f"    Circularidade:  {seg.circularity:.3f}")

    # BiomedCLIP extras
    print(f"\n  Severidade (BiomedCLIP): {result.severity_index:.2f}/1.00")
    print(f"  Risco infeccao:          {result.infection_risk:.1%}")

    print(f"\n  Tempo total ensemble:    {result.total_inference_time_ms:.0f}ms")
    print(f"  Modelos carregados:      {result.models_loaded}")

    return result


def create_visualization(
    image: np.ndarray,
    ensemble_result,
) -> np.ndarray:
    """Cria imagem de visualizacao com resultados do ensemble."""
    from src.core.config import ETIOLOGY_NAMES

    h, w = image.shape[:2]
    panel_w = 420
    canvas = np.zeros((max(h, 500), w + panel_w, 3), dtype=np.uint8)
    canvas[:h, :w] = image

    # Overlay de segmentacao se disponivel
    if ensemble_result.segmentation is not None:
        seg = ensemble_result.segmentation
        if seg.fused_mask is not None:
            mask = seg.fused_mask
            if mask.shape[:2] != (h, w):
                mask = cv2.resize(mask, (w, h), interpolation=cv2.INTER_NEAREST)
            overlay = image.copy()
            overlay[mask > 0] = (
                np.array(overlay[mask > 0], dtype=np.float32) * 0.6
                + np.array([0, 200, 0], dtype=np.float32) * 0.4
            ).astype(np.uint8)
            canvas[:h, :w] = overlay

    # Painel lateral
    panel = canvas[:, w:]
    panel[:] = (35, 35, 35)

    cls = ensemble_result.classification
    y = 30

    # Titulo
    cv2.putText(panel, "ENSEMBLE REDISUS", (15, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    y += 15
    cv2.line(panel, (15, y), (panel_w - 15, y), (80, 80, 80), 1)
    y += 30

    # Etiologia
    cv2.putText(panel, "ETIOLOGIA:", (15, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (180, 180, 180), 1)
    y += 28
    color = (0, 255, 0) if cls.confidence >= 0.7 else (0, 255, 255) if cls.confidence >= 0.5 else (0, 0, 255)
    cv2.putText(panel, cls.class_name, (15, y), cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2)
    y += 25
    cv2.putText(panel, f"Confianca: {cls.confidence:.1%}", (15, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (140, 140, 140), 1)
    y += 30

    # Concordancia
    agree_color = (0, 255, 0) if cls.agreement.models_agree else (0, 165, 255)
    agree_text = "UNANIME" if cls.agreement.models_agree else "DIVERGENTE"
    cv2.putText(panel, f"Modelos: {agree_text}", (15, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, agree_color, 1)
    y += 30

    # Predicoes individuais
    cv2.putText(panel, "Por modelo:", (15, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (160, 160, 160), 1)
    y += 22
    for model_name, pred in cls.agreement.individual_predictions.items():
        cv2.putText(panel, f"  {model_name}: {pred}", (15, y), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
        y += 20
    y += 15

    # Severidade e infeccao
    cv2.line(panel, (15, y), (panel_w - 15, y), (80, 80, 80), 1)
    y += 25
    cv2.putText(panel, f"Severidade: {ensemble_result.severity_index:.2f}/1.00", (15, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
    y += 25

    inf_color = (0, 0, 255) if ensemble_result.infection_risk > 0.5 else (0, 255, 0)
    cv2.putText(panel, f"Infeccao:   {ensemble_result.infection_risk:.1%}", (15, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, inf_color, 1)
    y += 25

    if ensemble_result.infection_risk > 0.5:
        cv2.putText(panel, "! ALERTA INFECCAO", (15, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2)
        y += 30

    # Segmentacao
    if ensemble_result.segmentation is not None:
        y += 10
        cv2.line(panel, (15, y), (panel_w - 15, y), (80, 80, 80), 1)
        y += 25
        cv2.putText(panel, "SEGMENTACAO:", (15, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)
        y += 25
        area = ensemble_result.segmentation.wound_area_pixels
        cv2.putText(panel, f"Area: {area:,} px", (15, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)
        y += 22
        circ = ensemble_result.segmentation.circularity
        cv2.putText(panel, f"Circularidade: {circ:.3f}", (15, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)

    return canvas


def main():
    parser = argparse.ArgumentParser(
        description="REDISUS - Demo Analise Ensemble Multi-Modelo"
    )
    parser.add_argument("--image", type=str, required=True, help="Caminho para imagem da ferida")
    parser.add_argument("--save", action="store_true", help="Salvar visualizacao em disco")
    parser.add_argument("--output", type=str, default=None, help="Caminho para salvar resultado")
    parser.add_argument("--show", action="store_true", help="Exibir janela com resultado")
    args = parser.parse_args()

    img_path = Path(args.image)
    if not img_path.exists():
        print(f"ERRO: Imagem nao encontrada: {img_path}")
        return

    print(f"Carregando imagem: {img_path}")
    image = cv2.imread(str(img_path))
    if image is None:
        print("ERRO: Nao foi possivel ler a imagem")
        return

    print(f"Tamanho: {image.shape[1]}x{image.shape[0]}")
    print()

    # Fase 1: modelos individuais
    di, ms, bc = run_individual_models(image)

    # Fase 2: ensemble
    ensemble_result = run_ensemble(image, di, ms, bc)

    # Visualizacao
    vis = create_visualization(image, ensemble_result)

    if args.save or args.output:
        out_path = args.output or f"output/ensemble_{img_path.stem}.png"
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(out_path, vis)
        print(f"\nVisualizacao salva em: {out_path}")

    if args.show:
        cv2.imshow("REDISUS Ensemble", vis)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    print("\nDemo concluida.")


if __name__ == "__main__":
    main()
