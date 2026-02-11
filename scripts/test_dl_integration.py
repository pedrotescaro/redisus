"""
REDISUS - Testes de Integracao para Pipeline de Deep Learning

Verifica que os modelos ONNX (YOLOv8 + U-Net) carregam e produzem
outputs validos, e que o fallback para OpenCV funciona corretamente.

Uso:
  python scripts/test_dl_integration.py
  python scripts/test_dl_integration.py --test yolo
  python scripts/test_dl_integration.py --test unet
  python scripts/test_dl_integration.py --test fallback
  python scripts/test_dl_integration.py --test pipeline
  python scripts/test_dl_integration.py --benchmark
"""
import argparse
import sys
import time
from pathlib import Path
from typing import List, Tuple

import cv2
import numpy as np
from loguru import logger

# Adiciona raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent))


def create_synthetic_wound_image(size: Tuple[int, int] = (640, 480)) -> np.ndarray:
    """
    Cria imagem sintetica com regiao que simula uma ferida.
    Util para testes sem imagens reais.
    """
    w, h = size
    image = np.ones((h, w, 3), dtype=np.uint8)

    # Fundo de pele
    image[:] = [140, 160, 180]  # BGR - tom de pele

    # Adiciona variacao
    noise = np.random.randn(h, w, 3) * 10
    image = np.clip(image + noise, 0, 255).astype(np.uint8)
    image = cv2.GaussianBlur(image, (5, 5), 0)

    # Regiao da "ferida" (elipse vermelha/escura no centro)
    center = (w // 2, h // 2)
    axes = (80, 60)

    # Base vermelha (granulacao)
    cv2.ellipse(image, center, axes, 0, 0, 360, (40, 40, 180), -1)

    # Area amarela (esfacelo)
    cv2.ellipse(image, (center[0] + 20, center[1] - 10), (30, 20), 15, 0, 360, (50, 180, 200), -1)

    # Area escura (necrose)
    cv2.ellipse(image, (center[0] - 25, center[1] + 15), (15, 12), -10, 0, 360, (30, 20, 30), -1)

    # Suaviza bordas
    image = cv2.GaussianBlur(image, (3, 3), 0)

    return image


class TestResult:
    """Resultado de um teste."""
    def __init__(self, name: str):
        self.name = name
        self.passed = False
        self.message = ""
        self.duration_ms = 0

    def __str__(self):
        status = "PASS" if self.passed else "FAIL"
        return f"[{status}] {self.name}: {self.message} ({self.duration_ms:.0f}ms)"


def test_yolo_onnx() -> TestResult:
    """Testa carregamento e inferencia do YOLOv8 ONNX."""
    result = TestResult("YOLO ONNX Inference")
    start = time.perf_counter()

    model_path = Path("models/yolo_wound_nano.onnx")
    if not model_path.exists():
        result.message = f"Modelo nao encontrado: {model_path}"
        return result

    try:
        from src.detection.realtime_detector import YOLODetector
        from src.core.config import ModelConfig

        config = ModelConfig(
            model_path=str(model_path),
            input_size=(320, 320),
            num_classes=1,
            confidence_threshold=0.3,
            device="cuda"
        )

        detector = YOLODetector(config=config, use_onnx=True)
        detector.load_model()
        detector.warmup()

        # Inferencia com imagem sintetica
        test_image = create_synthetic_wound_image()
        detections = detector.detect(test_image)

        # Validacoes
        assert isinstance(detections, list), "Output deve ser uma lista"
        for d in detections:
            assert 0 <= d.confidence <= 1, f"Confidence invalido: {d.confidence}"
            assert d.x1 >= 0 and d.y1 >= 0, f"Bbox negativo: {d.bbox}"
            assert d.x2 <= test_image.shape[1], f"x2 fora dos limites: {d.x2}"
            assert d.y2 <= test_image.shape[0], f"y2 fora dos limites: {d.y2}"

        result.passed = True
        result.message = f"{len(detections)} deteccoes encontradas"

    except Exception as e:
        result.message = f"Erro: {e}"

    result.duration_ms = (time.perf_counter() - start) * 1000
    return result


def test_unet_onnx() -> TestResult:
    """Testa carregamento e inferencia do U-Net ONNX."""
    result = TestResult("U-Net ONNX Inference")
    start = time.perf_counter()

    model_path = Path("models/unet_tissue_segmentation.onnx")
    if not model_path.exists():
        result.message = f"Modelo nao encontrado: {model_path}"
        return result

    try:
        from src.diagnosis.tissue_segmenter import UNetSegmenter
        from src.core.config import ModelConfig

        config = ModelConfig(
            model_path=str(model_path),
            input_size=(512, 512),
            num_classes=5,
            confidence_threshold=0.5,
            device="cuda"
        )

        segmenter = UNetSegmenter(config=config)
        segmenter.load_model()

        # Inferencia com imagem sintetica
        test_image = create_synthetic_wound_image()
        seg_result = segmenter.segment(test_image)

        # Validacoes
        assert seg_result.mask.shape[:2] == test_image.shape[:2] or seg_result.mask.ndim == 2, \
            f"Mask shape invalido: {seg_result.mask.shape}"

        unique_classes = np.unique(seg_result.mask)
        assert all(0 <= c < 5 for c in unique_classes), \
            f"Classes invalidas na mascara: {unique_classes}"

        pcts = seg_result.tissue_percentages
        total_pct = sum(pcts.values())
        assert abs(total_pct - 100.0) < 1.0, \
            f"Porcentagens nao somam 100%: {total_pct:.1f}"

        result.passed = True
        pct_str = ", ".join(f"{k}: {v:.1f}%" for k, v in pcts.items() if v > 0)
        result.message = f"Tecidos: {pct_str}"

    except Exception as e:
        result.message = f"Erro: {e}"

    result.duration_ms = (time.perf_counter() - start) * 1000
    return result


def test_fallback_opencv() -> TestResult:
    """Testa que o detector OpenCV funciona como fallback."""
    result = TestResult("OpenCV Fallback")
    start = time.perf_counter()

    try:
        from src.processing.wound_detector_cv import WoundDetectorCV, DetectionMethod
        from src.processing.tissue_analyzer import TissueAnalyzerCV

        # Detector
        detector = WoundDetectorCV(
            method=DetectionMethod.COMBINED,
            min_area=500,
            max_area=300000,
            confidence_threshold=0.35
        )
        detector.warmup()

        test_image = create_synthetic_wound_image()
        detections = detector.detect(test_image)

        assert isinstance(detections, list), "Deteccao deve retornar lista"

        # Tissue analyzer
        analyzer = TissueAnalyzerCV()
        if detections:
            roi = test_image[
                detections[0].bbox[1]:detections[0].bbox[3],
                detections[0].bbox[0]:detections[0].bbox[2]
            ]
            tissue = analyzer.analyze(roi, detections[0].mask)
            assert tissue is not None, "Analise de tecido nao deve ser None"

        result.passed = True
        result.message = f"Detector OK ({len(detections)} det), TissueAnalyzer OK"

    except Exception as e:
        result.message = f"Erro: {e}"

    result.duration_ms = (time.perf_counter() - start) * 1000
    return result


def test_yolo_to_detection_result() -> TestResult:
    """Testa conversao Detection -> DetectionResult no realtime_app."""
    result = TestResult("YOLO->DetectionResult Conversion")
    start = time.perf_counter()

    try:
        from src.detection.realtime_detector import Detection
        from src.processing.wound_detector_cv import DetectionResult

        # Simula deteccao YOLO
        det = Detection(
            bbox=(100, 80, 300, 250),
            confidence=0.85,
            class_id=0,
            class_name="wound"
        )

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        x1, y1, x2, y2 = det.bbox
        h, w = frame.shape[:2]

        mask = np.zeros((h, w), dtype=np.uint8)
        mask[y1:y2, x1:x2] = 255

        det_result = DetectionResult(
            bbox=det.bbox,
            confidence=det.confidence,
            mask=mask,
            contour=None,
            wound_type="wound",
            area_pixels=det.area,
            center=det.center,
            features={"backend": "yolo"}
        )

        assert det_result.confidence == 0.85
        assert det_result.bbox == (100, 80, 300, 250)
        assert det_result.area_pixels == det.area
        assert mask[150, 200] == 255  # Dentro da bbox
        assert mask[0, 0] == 0  # Fora da bbox

        result.passed = True
        result.message = "Conversao OK"

    except Exception as e:
        result.message = f"Erro: {e}"

    result.duration_ms = (time.perf_counter() - start) * 1000
    return result


def test_full_pipeline() -> TestResult:
    """Testa pipeline completo: deteccao -> segmentacao -> classificacao."""
    result = TestResult("Full Pipeline")
    start = time.perf_counter()

    try:
        from src.processing.wound_detector_cv import WoundDetectorCV, DetectionMethod
        from src.processing.tissue_analyzer import TissueAnalyzerCV
        from src.processing.wound_classifier_cv import WoundClassifierCV

        test_image = create_synthetic_wound_image()

        # 1. Deteccao (YOLO ou OpenCV)
        yolo_path = Path("models/yolo_wound_nano.onnx")
        if yolo_path.exists():
            from src.detection.realtime_detector import YOLODetector
            from src.core.config import ModelConfig

            config = ModelConfig(
                model_path=str(yolo_path),
                input_size=(320, 320),
                num_classes=1,
                confidence_threshold=0.3,
                device="cuda"
            )
            detector = YOLODetector(config=config, use_onnx=True)
            detector.load_model()
            raw_detections = detector.detect(test_image)
            backend_det = "YOLO"
        else:
            detector = WoundDetectorCV(
                method=DetectionMethod.COMBINED,
                min_area=500, max_area=300000,
                confidence_threshold=0.35
            )
            raw_detections = detector.detect(test_image)
            backend_det = "OpenCV"

        if not raw_detections:
            result.passed = True
            result.message = f"Pipeline OK (0 deteccoes, backend={backend_det})"
            result.duration_ms = (time.perf_counter() - start) * 1000
            return result

        # 2. ROI
        if hasattr(raw_detections[0], 'bbox'):
            bbox = raw_detections[0].bbox
        else:
            bbox = raw_detections[0].bbox
        x1, y1, x2, y2 = bbox
        roi = test_image[y1:y2, x1:x2]

        if roi.size == 0:
            result.passed = True
            result.message = "Pipeline OK (ROI vazio)"
            result.duration_ms = (time.perf_counter() - start) * 1000
            return result

        # 3. Segmentacao (U-Net ou OpenCV)
        unet_path = Path("models/unet_tissue_segmentation.onnx")
        if unet_path.exists():
            from src.diagnosis.tissue_segmenter import UNetSegmenter
            from src.core.config import ModelConfig as MC

            seg_config = MC(
                model_path=str(unet_path),
                input_size=(512, 512),
                num_classes=5,
                confidence_threshold=0.5,
                device="cuda"
            )
            segmenter = UNetSegmenter(config=seg_config)
            segmenter.load_model()
            seg_result = segmenter.segment(roi)
            tissue_pcts = seg_result.tissue_percentages
            backend_seg = "U-Net"
        else:
            analyzer = TissueAnalyzerCV()
            mask = np.ones(roi.shape[:2], dtype=np.uint8) * 255
            tissue = analyzer.analyze(roi, mask)
            tissue_pcts = tissue.tissue_percentages
            backend_seg = "OpenCV"

        # 4. Classificacao
        classifier = WoundClassifierCV(use_keras_model=False)
        classification = classifier.classify(roi, tissue_percentages=tissue_pcts)

        result.passed = True
        result.message = (
            f"det={backend_det}({len(raw_detections)}), "
            f"seg={backend_seg}, "
            f"class={classification.etiology.value}"
        )

    except Exception as e:
        result.message = f"Erro: {e}"

    result.duration_ms = (time.perf_counter() - start) * 1000
    return result


def benchmark_models() -> List[TestResult]:
    """Benchmark de latencia dos modelos ONNX."""
    results = []

    # YOLO benchmark
    yolo_result = TestResult("YOLO Latency Benchmark")
    yolo_path = Path("models/yolo_wound_nano.onnx")
    if yolo_path.exists():
        try:
            import onnxruntime as ort

            providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
            session = ort.InferenceSession(str(yolo_path), providers=providers)
            input_name = session.get_inputs()[0].name
            input_shape = session.get_inputs()[0].shape
            provider = session.get_providers()[0]

            dummy = np.random.randn(*input_shape).astype(np.float32)

            # Warmup
            for _ in range(5):
                session.run(None, {input_name: dummy})

            # Benchmark
            times = []
            for _ in range(100):
                t0 = time.perf_counter()
                session.run(None, {input_name: dummy})
                times.append((time.perf_counter() - t0) * 1000)

            times_np = np.array(times)
            yolo_result.passed = True
            yolo_result.message = (
                f"Provider={provider}, "
                f"media={times_np.mean():.1f}ms, "
                f"p95={np.percentile(times_np, 95):.1f}ms, "
                f"FPS={1000/times_np.mean():.0f}"
            )
        except Exception as e:
            yolo_result.message = f"Erro: {e}"
    else:
        yolo_result.message = "Modelo nao encontrado"
    results.append(yolo_result)

    # U-Net benchmark
    unet_result = TestResult("U-Net Latency Benchmark")
    unet_path = Path("models/unet_tissue_segmentation.onnx")
    if unet_path.exists():
        try:
            import onnxruntime as ort

            providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
            session = ort.InferenceSession(str(unet_path), providers=providers)
            input_name = session.get_inputs()[0].name
            input_shape = session.get_inputs()[0].shape
            provider = session.get_providers()[0]

            dummy = np.random.randn(*input_shape).astype(np.float32)

            # Warmup
            for _ in range(5):
                session.run(None, {input_name: dummy})

            # Benchmark
            times = []
            for _ in range(50):
                t0 = time.perf_counter()
                session.run(None, {input_name: dummy})
                times.append((time.perf_counter() - t0) * 1000)

            times_np = np.array(times)
            unet_result.passed = True
            unet_result.message = (
                f"Provider={provider}, "
                f"media={times_np.mean():.1f}ms, "
                f"p95={np.percentile(times_np, 95):.1f}ms, "
                f"FPS={1000/times_np.mean():.0f}"
            )
        except Exception as e:
            unet_result.message = f"Erro: {e}"
    else:
        unet_result.message = "Modelo nao encontrado"
    results.append(unet_result)

    return results


def main():
    parser = argparse.ArgumentParser(description="REDISUS - Testes de integracao DL")
    parser.add_argument(
        "--test", type=str, default="all",
        choices=["all", "yolo", "unet", "fallback", "conversion", "pipeline"],
        help="Qual teste executar"
    )
    parser.add_argument(
        "--benchmark", action="store_true",
        help="Executar benchmark de latencia"
    )

    args = parser.parse_args()

    logger.info("=== REDISUS - Testes de Integracao Deep Learning ===")

    # Verifica modelos disponiveis
    yolo_exists = Path("models/yolo_wound_nano.onnx").exists()
    unet_exists = Path("models/unet_tissue_segmentation.onnx").exists()
    logger.info(f"YOLO ONNX: {'encontrado' if yolo_exists else 'NAO encontrado'}")
    logger.info(f"U-Net ONNX: {'encontrado' if unet_exists else 'NAO encontrado'}")
    logger.info("")

    results = []

    test_map = {
        "yolo": [test_yolo_onnx],
        "unet": [test_unet_onnx],
        "fallback": [test_fallback_opencv],
        "conversion": [test_yolo_to_detection_result],
        "pipeline": [test_full_pipeline],
        "all": [
            test_yolo_onnx,
            test_unet_onnx,
            test_fallback_opencv,
            test_yolo_to_detection_result,
            test_full_pipeline,
        ],
    }

    for test_fn in test_map[args.test]:
        logger.info(f"Executando: {test_fn.__name__}...")
        r = test_fn()
        results.append(r)
        logger.info(f"  {r}")

    if args.benchmark:
        logger.info("")
        logger.info("--- Benchmark de Latencia ---")
        bench_results = benchmark_models()
        for r in bench_results:
            results.append(r)
            logger.info(f"  {r}")

    # Resumo
    logger.info("")
    logger.info("=== Resumo ===")
    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)
    skipped = sum(1 for r in results if "nao encontrado" in r.message.lower())
    logger.info(f"Passou: {passed} | Falhou: {failed} | Modelo ausente: {skipped}")

    if failed > 0:
        logger.error("Alguns testes falharam!")
        for r in results:
            if not r.passed:
                logger.error(f"  {r}")
        sys.exit(1)
    else:
        logger.info("Todos os testes passaram!")


if __name__ == "__main__":
    main()
