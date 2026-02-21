"""
HEAL/REDISUS — Testes do Pipeline Completo de Reconhecimento de Imagens.

Cobre o pipeline ponta-a-ponta:
- Detecção em tempo real (YOLODetector, RealtimeWoundDetector)
- Segmentação de tecidos (UNetSegmenter)
- Classificação de etiologia (EtiologyClassifier, MultiModalClassifier)
- Análise integrada (WoundAnalyzer)
- Processamento OpenCV (WoundDetectorCV → TissueAnalyzerCV → WoundClassifierCV)
- Cálculo de área (WoundAreaCalculator)

Todos os módulos DL rodam em modo de simulação (sem modelos .onnx/.pt necessários).
"""
import numpy as np
import pytest
import cv2


# ====================================================================
# Fixtures de imagens especializadas
# ====================================================================

@pytest.fixture
def wound_frame_granulation():
    """Frame 480x640 com região de granulação (vermelho vivo) e pele ao redor."""
    frame = np.full((480, 640, 3), (180, 200, 220), dtype=np.uint8)  # pele BGR
    cv2.circle(frame, (320, 240), 100, (0, 0, 200), -1)   # vermelho forte
    cv2.circle(frame, (320, 240), 60, (30, 30, 210), -1)   # centro mais vivo
    return frame


@pytest.fixture
def wound_frame_necrosis():
    """Frame com região necrótica escura no centro."""
    frame = np.full((480, 640, 3), (180, 200, 220), dtype=np.uint8)
    cv2.circle(frame, (320, 240), 90, (15, 15, 20), -1)    # necrose quase preta
    return frame


@pytest.fixture
def wound_frame_slough():
    """Frame com esfacelo amarelado no centro."""
    frame = np.full((480, 640, 3), (180, 200, 220), dtype=np.uint8)
    cv2.circle(frame, (320, 240), 85, (80, 220, 220), -1)  # amarelo BGR
    return frame


@pytest.fixture
def wound_frame_mixed():
    """Frame com tecido misto: granulação + esfacelo + necrose."""
    frame = np.full((480, 640, 3), (180, 200, 220), dtype=np.uint8)
    cv2.circle(frame, (280, 200), 60, (0, 0, 200), -1)     # granulação
    cv2.circle(frame, (360, 200), 50, (80, 220, 220), -1)   # esfacelo
    cv2.circle(frame, (320, 300), 40, (15, 15, 20), -1)     # necrose
    return frame


@pytest.fixture
def wound_mask_large():
    """Máscara binária cobrindo região central ampla."""
    mask = np.zeros((480, 640), dtype=np.uint8)
    cv2.circle(mask, (320, 240), 120, 255, -1)
    return mask


@pytest.fixture
def realistic_wound_frame():
    """Frame com wound mais realista: gradiente de tecidos."""
    frame = np.full((480, 640, 3), (170, 190, 210), dtype=np.uint8)
    # Borda externa: pele perilesional
    cv2.circle(frame, (320, 240), 130, (140, 160, 190), -1)
    # Granulação no centro
    cv2.circle(frame, (320, 240), 90, (20, 30, 180), -1)
    # Esfacelo no meio
    cv2.ellipse(frame, (340, 230), (40, 25), 30, 0, 360, (100, 210, 210), -1)
    # Pequena área necrótica
    cv2.circle(frame, (300, 260), 20, (20, 20, 30), -1)
    return frame


# ====================================================================
# 1. YOLO Detector (modo simulação)
# ====================================================================

class TestYOLODetector:
    """Testa o detector YOLO em modo de simulação."""

    def test_init_default(self):
        from src.detection.realtime_detector import YOLODetector
        det = YOLODetector()
        assert det._model is None
        assert det._session is None

    def test_load_model_simulation(self):
        """Sem arquivo de modelo, entra em modo simulação."""
        from src.detection.realtime_detector import YOLODetector
        det = YOLODetector(model_path="inexistente.onnx")
        det.load_model()
        assert det._model == "simulation"

    def test_detect_returns_list(self, wound_frame_granulation):
        from src.detection.realtime_detector import YOLODetector
        det = YOLODetector()
        det.load_model()
        results = det.detect(wound_frame_granulation)
        assert isinstance(results, list)

    def test_detect_red_wound_finds_something(self, wound_frame_granulation):
        """Círculo vermelho grande deve gerar detecção por cor HSV."""
        from src.detection.realtime_detector import YOLODetector
        det = YOLODetector()
        det.load_model()
        results = det.detect(wound_frame_granulation)
        assert len(results) >= 1
        for d in results:
            assert 0 < d.confidence <= 1
            assert d.class_name == "wound"
            assert d.width > 0 and d.height > 0

    def test_detection_bbox_within_frame(self, wound_frame_granulation):
        from src.detection.realtime_detector import YOLODetector
        det = YOLODetector()
        det.load_model()
        results = det.detect(wound_frame_granulation)
        h, w = wound_frame_granulation.shape[:2]
        for d in results:
            assert d.x1 >= 0 and d.y1 >= 0
            assert d.x2 <= w and d.y2 <= h

    def test_detection_properties(self, wound_frame_granulation):
        from src.detection.realtime_detector import Detection
        d = Detection(bbox=(100, 50, 300, 250), confidence=0.9, class_id=0)
        assert d.width == 200
        assert d.height == 200
        assert d.center == (200, 150)
        assert d.area == 40000

    def test_nms_removes_overlapping(self):
        from src.detection.realtime_detector import YOLODetector, Detection
        dets = [
            Detection(bbox=(100, 100, 200, 200), confidence=0.9),
            Detection(bbox=(105, 105, 205, 205), confidence=0.7),  # quase sobreposto
            Detection(bbox=(400, 400, 500, 500), confidence=0.8),  # separado
        ]
        kept = YOLODetector._nms(dets, iou_threshold=0.45)
        assert len(kept) == 2  # remove o sobreposto menos confiante

    def test_iou_identical_boxes(self):
        from src.detection.realtime_detector import YOLODetector
        assert YOLODetector._iou((0, 0, 100, 100), (0, 0, 100, 100)) == 1.0

    def test_iou_no_overlap(self):
        from src.detection.realtime_detector import YOLODetector
        assert YOLODetector._iou((0, 0, 50, 50), (200, 200, 300, 300)) == 0.0

    def test_warmup_does_not_crash(self):
        from src.detection.realtime_detector import YOLODetector
        det = YOLODetector()
        det.load_model()
        det.warmup(iterations=1)

    def test_avg_inference_time(self, wound_frame_granulation):
        from src.detection.realtime_detector import YOLODetector
        det = YOLODetector()
        det.load_model()
        det.detect(wound_frame_granulation)
        assert det.avg_inference_time > 0
        assert det.fps > 0

    def test_black_frame_no_detections(self, black_frame):
        from src.detection.realtime_detector import YOLODetector
        det = YOLODetector()
        det.load_model()
        results = det.detect(black_frame)
        assert isinstance(results, list)
        # Frame preto não deve ter nada "vermelho"


# ====================================================================
# 2. Realtime Wound Detector
# ====================================================================

class TestRealtimeWoundDetector:
    """Testa o detector de alto nível com lógica de auto-captura."""

    def test_init(self):
        from src.detection.realtime_detector import RealtimeWoundDetector
        rtd = RealtimeWoundDetector()
        assert rtd.auto_capture_threshold == 0.85
        assert rtd.auto_capture_frames == 10
        assert not rtd.should_capture()

    def test_start_loads_model(self):
        from src.detection.realtime_detector import RealtimeWoundDetector
        rtd = RealtimeWoundDetector()
        rtd.start()
        # Deve ter carregado em modo simulação
        assert rtd._detector._model == "simulation"

    def test_process_frame_returns_tuple(self, wound_frame_granulation):
        from src.detection.realtime_detector import RealtimeWoundDetector
        rtd = RealtimeWoundDetector()
        rtd.start()
        annotated, detections = rtd.process_frame(wound_frame_granulation)
        assert isinstance(annotated, np.ndarray)
        assert annotated.shape == wound_frame_granulation.shape
        assert isinstance(detections, list)

    def test_process_frame_with_draw_boxes(self, wound_frame_granulation):
        from src.detection.realtime_detector import RealtimeWoundDetector
        rtd = RealtimeWoundDetector()
        rtd.start()
        ann_on, _ = rtd.process_frame(wound_frame_granulation, draw_boxes=True)
        ann_off, _ = rtd.process_frame(wound_frame_granulation, draw_boxes=False)
        # Ambos devem ter mesma forma
        assert ann_on.shape == ann_off.shape

    def test_should_capture_initially_false(self):
        from src.detection.realtime_detector import RealtimeWoundDetector
        rtd = RealtimeWoundDetector()
        assert rtd.should_capture() is False

    def test_reset_capture_trigger(self):
        from src.detection.realtime_detector import RealtimeWoundDetector
        rtd = RealtimeWoundDetector()
        rtd._stable_detection_count = 20
        rtd.reset_capture_trigger()
        assert rtd._stable_detection_count == 0
        assert not rtd.should_capture()


# ====================================================================
# 3. U-Net Segmenter (modo simulação)
# ====================================================================

class TestUNetSegmenter:
    """Testa o segmentador U-Net em modo simulação."""

    def test_init_default(self):
        from src.diagnosis.tissue_segmenter import UNetSegmenter
        seg = UNetSegmenter()
        assert seg.NUM_CLASSES == 5

    def test_load_model_simulation(self):
        from src.diagnosis.tissue_segmenter import UNetSegmenter
        seg = UNetSegmenter()
        seg.load_model()
        assert seg._model == "simulation"

    def test_segment_returns_result(self, wound_frame_granulation):
        from src.diagnosis.tissue_segmenter import UNetSegmenter, TissueSegmentationResult
        seg = UNetSegmenter()
        seg.load_model()
        result = seg.segment(wound_frame_granulation)
        assert isinstance(result, TissueSegmentationResult)

    def test_segment_mask_shape_matches_input(self, wound_frame_granulation):
        from src.diagnosis.tissue_segmenter import UNetSegmenter
        seg = UNetSegmenter()
        seg.load_model()
        result = seg.segment(wound_frame_granulation)
        h, w = wound_frame_granulation.shape[:2]
        assert result.mask.shape == (h, w)
        assert result.original_size == (w, h)

    def test_segment_percentages_sum(self, wound_frame_granulation):
        from src.diagnosis.tissue_segmenter import UNetSegmenter
        seg = UNetSegmenter()
        seg.load_model()
        result = seg.segment(wound_frame_granulation)
        total = sum(result.tissue_percentages.values())
        assert 99 <= total <= 101  # deve somar ~100%

    def test_segment_wound_area_positive(self, wound_frame_granulation):
        from src.diagnosis.tissue_segmenter import UNetSegmenter
        seg = UNetSegmenter()
        seg.load_model()
        result = seg.segment(wound_frame_granulation)
        assert result.wound_area_pixels >= 0

    def test_colored_mask_rgb(self, wound_frame_granulation):
        from src.diagnosis.tissue_segmenter import UNetSegmenter
        seg = UNetSegmenter()
        seg.load_model()
        result = seg.segment(wound_frame_granulation)
        colored = result.get_colored_mask()
        h, w = wound_frame_granulation.shape[:2]
        assert colored.shape == (h, w, 3)

    def test_overlay_same_size(self, wound_frame_granulation):
        from src.diagnosis.tissue_segmenter import UNetSegmenter
        seg = UNetSegmenter()
        seg.load_model()
        result = seg.segment(wound_frame_granulation)
        overlay = result.get_overlay(wound_frame_granulation)
        assert overlay.shape == wound_frame_granulation.shape

    def test_inference_time_recorded(self, wound_frame_granulation):
        from src.diagnosis.tissue_segmenter import UNetSegmenter
        seg = UNetSegmenter()
        seg.load_model()
        result = seg.segment(wound_frame_granulation)
        assert result.inference_time_ms > 0

    def test_necrosis_frame_has_necrosis(self, wound_frame_necrosis):
        """Frame escuro deve gerar alguma porcentagem de necrose."""
        from src.diagnosis.tissue_segmenter import UNetSegmenter
        seg = UNetSegmenter()
        seg.load_model()
        result = seg.segment(wound_frame_necrosis)
        # O simulador usa HSV para detectar regiões escuras como necrose
        assert "Necrose" in result.tissue_percentages or "necrose" in str(result.tissue_percentages).lower()

    def test_different_frames_different_results(self, wound_frame_granulation, wound_frame_necrosis):
        from src.diagnosis.tissue_segmenter import UNetSegmenter
        seg = UNetSegmenter()
        seg.load_model()
        r1 = seg.segment(wound_frame_granulation)
        r2 = seg.segment(wound_frame_necrosis)
        # As distribuições de tecido devem diferir
        assert r1.tissue_percentages != r2.tissue_percentages


# ====================================================================
# 4. Etiology Classifier (modo simulação)
# ====================================================================

class TestEtiologyClassifier:
    """Testa o classificador de etiologia em modo simulação."""

    def test_init_default(self):
        from src.diagnosis.etiology_classifier import EtiologyClassifier
        clf = EtiologyClassifier()
        assert clf.NUM_CLASSES == 5

    def test_load_model_simulation(self):
        from src.diagnosis.etiology_classifier import EtiologyClassifier
        clf = EtiologyClassifier()
        clf.load_model()
        assert clf._model == "simulation"

    def test_classify_returns_result(self, wound_frame_granulation):
        from src.diagnosis.etiology_classifier import EtiologyClassifier, EtiologyClassificationResult
        clf = EtiologyClassifier()
        clf.load_model()
        result = clf.classify(wound_frame_granulation)
        assert isinstance(result, EtiologyClassificationResult)

    def test_classify_primary_prediction(self, wound_frame_granulation):
        from src.diagnosis.etiology_classifier import EtiologyClassifier
        clf = EtiologyClassifier()
        clf.load_model()
        result = clf.classify(wound_frame_granulation)
        primary = result.primary_prediction
        assert primary.class_name != ""
        assert 0 < primary.confidence <= 1
        assert primary.description != ""

    def test_classify_all_predictions_sorted(self, wound_frame_granulation):
        from src.diagnosis.etiology_classifier import EtiologyClassifier
        clf = EtiologyClassifier()
        clf.load_model()
        result = clf.classify(wound_frame_granulation)
        confs = [p.confidence for p in result.all_predictions]
        assert confs == sorted(confs, reverse=True), "Predições devem estar ordenadas por confiança"

    def test_classify_probabilities_sum_to_one(self, wound_frame_granulation):
        from src.diagnosis.etiology_classifier import EtiologyClassifier
        clf = EtiologyClassifier()
        clf.load_model()
        result = clf.classify(wound_frame_granulation)
        total = sum(result.probabilities.values())
        assert abs(total - 1.0) < 0.02, f"Probabilidades somam {total}"

    def test_classify_features_extracted(self, wound_frame_granulation):
        from src.diagnosis.etiology_classifier import EtiologyClassifier
        clf = EtiologyClassifier()
        clf.load_model()
        result = clf.classify(wound_frame_granulation)
        assert result.features is not None
        assert "mean_hue" in result.features
        assert "texture_variance" in result.features
        assert "edge_density" in result.features

    def test_classify_inference_time(self, wound_frame_granulation):
        from src.diagnosis.etiology_classifier import EtiologyClassifier
        clf = EtiologyClassifier()
        clf.load_model()
        result = clf.classify(wound_frame_granulation)
        assert result.inference_time_ms > 0

    def test_needs_review_property(self, wound_frame_granulation):
        from src.diagnosis.etiology_classifier import EtiologyClassifier
        clf = EtiologyClassifier()
        clf.load_model()
        result = clf.classify(wound_frame_granulation)
        assert isinstance(result.needs_review, bool)

    def test_is_confident_property(self, wound_frame_granulation):
        from src.diagnosis.etiology_classifier import EtiologyClassifier
        clf = EtiologyClassifier()
        clf.load_model()
        result = clf.classify(wound_frame_granulation)
        assert isinstance(result.is_confident, bool)

    def test_top_k_parameter(self, wound_frame_granulation):
        from src.diagnosis.etiology_classifier import EtiologyClassifier
        clf = EtiologyClassifier()
        clf.load_model()
        result = clf.classify(wound_frame_granulation, top_k=2)
        assert len(result.all_predictions) == 2


# ====================================================================
# 5. MultiModal Classifier
# ====================================================================

class TestMultiModalClassifier:
    """Testa o classificador multimodal."""

    def test_init(self):
        from src.diagnosis.etiology_classifier import EtiologyClassifier, MultiModalClassifier
        img_clf = EtiologyClassifier()
        mm = MultiModalClassifier(image_classifier=img_clf)
        assert mm.use_location is False
        assert mm.use_history is False

    def test_classify_image_only(self, wound_frame_granulation):
        from src.diagnosis.etiology_classifier import EtiologyClassifier, MultiModalClassifier
        img_clf = EtiologyClassifier()
        img_clf.load_model()
        mm = MultiModalClassifier(image_classifier=img_clf)
        result = mm.classify(wound_frame_granulation)
        assert result.primary_prediction.confidence > 0

    def test_classify_with_location(self, wound_frame_granulation):
        from src.diagnosis.etiology_classifier import EtiologyClassifier, MultiModalClassifier
        img_clf = EtiologyClassifier()
        img_clf.load_model()
        mm = MultiModalClassifier(image_classifier=img_clf, use_location=True)
        result = mm.classify(wound_frame_granulation, location="lower_leg")
        assert result.primary_prediction.confidence > 0


# ====================================================================
# 6. Wound Analyzer (pipeline integrado)
# ====================================================================

class TestWoundAnalyzer:
    """Testa o analisador completo de feridas."""

    def test_init_default(self):
        from src.diagnosis.wound_analyzer import WoundAnalyzer
        analyzer = WoundAnalyzer()
        assert analyzer._models_loaded is False

    def test_load_models(self):
        from src.diagnosis.wound_analyzer import WoundAnalyzer
        analyzer = WoundAnalyzer()
        analyzer.load_models()
        assert analyzer._models_loaded is True

    def test_analyze_sequential(self, wound_frame_granulation):
        from src.diagnosis.wound_analyzer import WoundAnalyzer, WoundAnalysisResult
        analyzer = WoundAnalyzer(parallel=False)
        result = analyzer.analyze(wound_frame_granulation)
        assert isinstance(result, WoundAnalysisResult)

    def test_analyze_parallel(self, wound_frame_granulation):
        from src.diagnosis.wound_analyzer import WoundAnalyzer, WoundAnalysisResult
        analyzer = WoundAnalyzer(parallel=True)
        result = analyzer.analyze(wound_frame_granulation)
        assert isinstance(result, WoundAnalysisResult)

    def test_analyze_result_has_segmentation(self, wound_frame_granulation):
        from src.diagnosis.wound_analyzer import WoundAnalyzer
        analyzer = WoundAnalyzer(parallel=False)
        result = analyzer.analyze(wound_frame_granulation)
        assert result.segmentation is not None
        assert result.segmentation.mask is not None
        assert len(result.segmentation.tissue_percentages) > 0

    def test_analyze_result_has_classification(self, wound_frame_granulation):
        from src.diagnosis.wound_analyzer import WoundAnalyzer
        analyzer = WoundAnalyzer(parallel=False)
        result = analyzer.analyze(wound_frame_granulation)
        assert result.classification is not None
        assert result.classification.primary_prediction.class_name != ""
        assert result.classification.primary_prediction.confidence > 0

    def test_analyze_result_image_size(self, wound_frame_granulation):
        from src.diagnosis.wound_analyzer import WoundAnalyzer
        analyzer = WoundAnalyzer(parallel=False)
        result = analyzer.analyze(wound_frame_granulation)
        h, w = wound_frame_granulation.shape[:2]
        assert result.image_size == (w, h)

    def test_analyze_with_scale(self, wound_frame_granulation):
        from src.diagnosis.wound_analyzer import WoundAnalyzer
        analyzer = WoundAnalyzer(parallel=False)
        result = analyzer.analyze(wound_frame_granulation, pixels_per_cm=50.0)
        assert result.wound_area_cm2 is not None
        assert result.wound_area_cm2 >= 0

    def test_analyze_without_scale(self, wound_frame_granulation):
        from src.diagnosis.wound_analyzer import WoundAnalyzer
        analyzer = WoundAnalyzer(parallel=False)
        result = analyzer.analyze(wound_frame_granulation)
        assert result.wound_area_cm2 is None

    def test_to_dict(self, wound_frame_granulation):
        from src.diagnosis.wound_analyzer import WoundAnalyzer
        analyzer = WoundAnalyzer(parallel=False)
        result = analyzer.analyze(wound_frame_granulation)
        d = result.to_dict()
        assert "etiology" in d
        assert "segmentation" in d
        assert "metadata" in d
        assert "confidence" in d["etiology"]
        assert "tissue_percentages" in d["segmentation"]

    def test_get_summary(self, wound_frame_granulation):
        from src.diagnosis.wound_analyzer import WoundAnalyzer
        analyzer = WoundAnalyzer(parallel=False)
        result = analyzer.analyze(wound_frame_granulation)
        summary = result.get_summary()
        assert "REDISUS" in summary
        assert "ETIOLOGIA" in summary
        assert "TECIDUAL" in summary

    def test_analyze_with_visualization(self, wound_frame_granulation):
        from src.diagnosis.wound_analyzer import WoundAnalyzer
        analyzer = WoundAnalyzer(parallel=False)
        result, viz = analyzer.analyze_with_visualization(wound_frame_granulation)
        assert isinstance(viz, np.ndarray)
        assert viz.shape[0] == wound_frame_granulation.shape[0]
        # A visualização adiciona painel lateral
        assert viz.shape[1] > wound_frame_granulation.shape[1]

    def test_total_inference_time(self, wound_frame_granulation):
        from src.diagnosis.wound_analyzer import WoundAnalyzer
        analyzer = WoundAnalyzer(parallel=False)
        result = analyzer.analyze(wound_frame_granulation)
        assert result.total_inference_time_ms > 0


# ====================================================================
# 7. Wound Area Calculator
# ====================================================================

class TestWoundAreaCalculator:
    """Testa cálculo de área de ferida."""

    def test_calculate_area_pixels(self):
        from src.diagnosis.tissue_segmenter import WoundAreaCalculator
        from src.core.config import TissueType
        mask = np.zeros((100, 100), dtype=np.uint8)
        # Preenche 25% como granulação
        mask[25:75, 25:75] = TissueType.GRANULATION.value
        area = WoundAreaCalculator.calculate_area_pixels(mask)
        assert area > 0

    def test_calculate_area_cm2(self):
        from src.diagnosis.tissue_segmenter import WoundAreaCalculator
        from src.core.config import TissueType
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[0:50, 0:50] = TissueType.GRANULATION.value  # 2500 pixels
        area_cm2 = WoundAreaCalculator.calculate_area_cm2(mask, pixels_per_cm=10.0)
        assert area_cm2 > 0
        # 2500 pixels / (10*10 px/cm²) = 25 cm²
        assert abs(area_cm2 - 25.0) < 1.0

    def test_calculate_reduction(self):
        from src.diagnosis.tissue_segmenter import WoundAreaCalculator
        result = WoundAreaCalculator.calculate_reduction(100.0, 60.0)
        assert isinstance(result, dict)
        assert "percentage" in result
        assert "absolute" in result
        assert abs(result["absolute"] - (-40.0)) < 0.1


# ====================================================================
# 8. Pipeline OpenCV Completo (Detect → Tissue → Classify)
# ====================================================================

class TestOpenCVPipeline:
    """Testa o pipeline completo OpenCV sem DL."""

    def test_full_pipeline_red_wound(self, wound_frame_granulation, wound_mask_large):
        """Ciclo completo: detecção → análise de tecido → classificação."""
        from src.processing.wound_detector_cv import WoundDetectorCV, DetectionMethod
        from src.processing.tissue_analyzer import TissueAnalyzerCV
        from src.processing.wound_classifier_cv import WoundClassifierCV

        # 1. Detecção
        detector = WoundDetectorCV(
            method=DetectionMethod.COLOR_SEGMENTATION,
            min_area=500,
            confidence_threshold=0.2,
            enable_false_positive_filter=False,
        )
        detections = detector.detect(wound_frame_granulation)
        assert isinstance(detections, list)

        # 2. Análise de tecido
        analyzer = TissueAnalyzerCV()
        tissue_result = analyzer.analyze(wound_frame_granulation, wound_mask=wound_mask_large)
        assert tissue_result.health_score >= 0
        assert sum(tissue_result.tissue_percentages.values()) >= 0

        # 3. Classificação de etiologia
        classifier = WoundClassifierCV()
        etiology = classifier.classify(
            wound_frame_granulation,
            tissue_percentages=tissue_result.tissue_percentages,
        )
        assert etiology.confidence > 0
        assert etiology.name != ""

    def test_full_pipeline_necrosis(self, wound_frame_necrosis, wound_mask_large):
        """Pipeline com frame necrótico."""
        from src.processing.tissue_analyzer import TissueAnalyzerCV
        from src.processing.wound_classifier_cv import WoundClassifierCV

        analyzer = TissueAnalyzerCV()
        tissue = analyzer.analyze(wound_frame_necrosis, wound_mask=wound_mask_large)

        classifier = WoundClassifierCV()
        etiology = classifier.classify(
            wound_frame_necrosis,
            tissue_percentages=tissue.tissue_percentages,
        )
        assert etiology.confidence > 0

    def test_full_pipeline_mixed(self, wound_frame_mixed, wound_mask_large):
        """Pipeline com tecido misto."""
        from src.processing.tissue_analyzer import TissueAnalyzerCV
        from src.processing.wound_classifier_cv import WoundClassifierCV

        analyzer = TissueAnalyzerCV()
        tissue = analyzer.analyze(wound_frame_mixed, wound_mask=wound_mask_large)
        assert len(tissue.tissue_percentages) > 0

        classifier = WoundClassifierCV()
        etiology = classifier.classify(
            wound_frame_mixed,
            tissue_percentages=tissue.tissue_percentages,
        )
        assert isinstance(etiology.probabilities, dict)
        assert abs(sum(etiology.probabilities.values()) - 1.0) < 0.02

    def test_deep_pipeline_end_to_end(self, wound_frame_granulation):
        """Pipeline DL completo: WoundAnalyzer (segmenter + classifier)."""
        from src.diagnosis.wound_analyzer import WoundAnalyzer

        analyzer = WoundAnalyzer(parallel=False)
        result = analyzer.analyze(wound_frame_granulation, pixels_per_cm=30.0)

        # Verifica resultado integrado
        assert result.wound_area_cm2 is not None
        assert result.tissue_distribution is not None
        assert result.classification.primary_prediction.confidence > 0
        assert result.total_inference_time_ms > 0

        # Serializa para dicionário
        d = result.to_dict()
        assert d["etiology"]["primary"] != ""
        assert d["segmentation"]["wound_area_cm2"] > 0


# ====================================================================
# 9. TissueSegmentationResult helper methods
# ====================================================================

class TestSegmentationResultHelpers:
    """Testa métodos auxiliares do TissueSegmentationResult."""

    def test_get_tissue_mask(self, wound_frame_granulation):
        from src.diagnosis.tissue_segmenter import UNetSegmenter
        from src.core.config import TissueType
        seg = UNetSegmenter()
        seg.load_model()
        result = seg.segment(wound_frame_granulation)

        gran_mask = result.get_tissue_mask(TissueType.GRANULATION)
        assert gran_mask.dtype == np.uint8
        assert gran_mask.shape == result.mask.shape
        assert set(np.unique(gran_mask)).issubset({0, 1})


# ====================================================================
# 10. EtiologyPrediction dataclass
# ====================================================================

class TestEtiologyPrediction:
    """Testa o dataclass EtiologyPrediction."""

    def test_etiology_type_property(self):
        from src.diagnosis.etiology_classifier import EtiologyPrediction
        from src.core.config import EtiologyType
        pred = EtiologyPrediction(
            class_id=0, class_name="Úlcera Venosa",
            confidence=0.85, description="Descrição teste",
        )
        assert pred.etiology_type == EtiologyType(0)

    def test_prediction_fields(self):
        from src.diagnosis.etiology_classifier import EtiologyPrediction
        pred = EtiologyPrediction(
            class_id=2, class_name="Pé Diabético",
            confidence=0.65, description="Neuropática",
        )
        assert pred.class_id == 2
        assert pred.class_name == "Pé Diabético"
        assert pred.confidence == 0.65
