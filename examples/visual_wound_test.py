"""
REDISUS — Teste Visual de Reconhecimento de Imagens de Feridas
===============================================================

Carrega imagens REAIS do dataset Medetec, executa o pipeline completo
(Detecção → Segmentação → Classificação) e serve os resultados
num dashboard web para visualização no navegador.

Uso:
    python examples/visual_wound_test.py
    Depois abra http://localhost:5050
"""
import sys
import base64
import io
import time
from pathlib import Path

import cv2
import numpy as np

# Path setup
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flask import Flask, render_template_string

# ============================================================
# Módulos do projeto
# ============================================================
from src.processing.wound_detector_cv import WoundDetectorCV, DetectionMethod
from src.processing.tissue_analyzer import TissueAnalyzerCV
from src.processing.wound_classifier_cv import WoundClassifierCV
from src.diagnosis.wound_analyzer import WoundAnalyzer
from src.diagnosis.tissue_segmenter import UNetSegmenter
from src.diagnosis.etiology_classifier import EtiologyClassifier

# ============================================================
# Busca imagens reais no dataset
# ============================================================
DATASET_ROOT = Path(__file__).resolve().parent.parent / "dataset" / "medetec"

# Seleciona 1 imagem de cada categoria relevante
TARGET_CATEGORIES = [
    "pressure_ulcers_1",
    "diabetic_foot_ulcers",
    "venous_arterial_ulcers_1",
    "burns",
    "abdominal_wounds",
    "necrotic_toes",
    "malignant_wounds",
]


def find_sample_images(max_per_category=1):
    """Encontra imagens de amostra no dataset."""
    samples = []
    for cat in TARGET_CATEGORIES:
        cat_dir = DATASET_ROOT / cat
        if not cat_dir.exists():
            continue
        imgs = sorted(cat_dir.glob("*.jpg"))[:max_per_category]
        for img in imgs:
            samples.append((cat, img))
    # Se não achou as categorias alvo, pega qualquer imagem
    if not samples:
        for img in sorted(DATASET_ROOT.rglob("*.jpg"))[:7]:
            samples.append((img.parent.name, img))
    return samples


def image_to_base64(img: np.ndarray) -> str:
    """Converte imagem OpenCV para base64 para embedding no HTML."""
    _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return base64.b64encode(buf).decode("utf-8")


# ============================================================
# Pipeline de análise
# ============================================================
def analyze_image(image_path: Path):
    """Executa o pipeline completo numa imagem real."""
    img = cv2.imread(str(image_path))
    if img is None:
        return None

    results = {"path": str(image_path), "category": image_path.parent.name}
    t0 = time.perf_counter()

    # Redimensiona se muito grande
    h, w = img.shape[:2]
    if max(h, w) > 800:
        scale = 800 / max(h, w)
        img = cv2.resize(img, (int(w * scale), int(h * scale)))
    results["image_size"] = f"{img.shape[1]}x{img.shape[0]}"
    results["original_b64"] = image_to_base64(img)

    # --- 1. Detecção OpenCV ---
    detector = WoundDetectorCV(
        method=DetectionMethod.COMBINED,
        min_area=300,
        confidence_threshold=0.25,
        enable_false_positive_filter=False,
    )
    detections = detector.detect(img)
    results["num_detections"] = len(detections)

    # Desenha bboxes (bbox = x1, y1, x2, y2)
    det_img = img.copy()
    for det in detections:
        x1, y1, x2, y2 = det.bbox
        conf = det.confidence
        cv2.rectangle(det_img, (x1, y1), (x2, y2), (0, 255, 0), 2)
        label = f"Ferida {conf:.0%}"
        cv2.putText(det_img, label, (x1, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
    results["detection_b64"] = image_to_base64(det_img)
    results["detections"] = [
        {"bbox": d.bbox, "confidence": f"{d.confidence:.1%}", "type": d.wound_type}
        for d in detections
    ]

    # --- 2. Segmentação de tecidos (U-Net simulação) ---
    segmenter = UNetSegmenter()
    segmenter.load_model()
    seg_result = segmenter.segment(img)
    results["tissue_percentages"] = {k: f"{v:.1f}%" for k, v in seg_result.tissue_percentages.items()}
    results["wound_area_px"] = seg_result.wound_area_pixels

    # Mapa colorido + overlay
    colored_mask = seg_result.get_colored_mask()
    overlay = seg_result.get_overlay(img, alpha=0.45)
    results["segmentation_b64"] = image_to_base64(colored_mask)
    results["overlay_b64"] = image_to_base64(overlay)

    # --- 3. Análise de tecidos OpenCV ---
    tissue_analyzer = TissueAnalyzerCV()
    # Cria máscara da maior detecção (ou imagem toda)
    if detections:
        mask = np.zeros(img.shape[:2], dtype=np.uint8)
        for det in detections:
            x1, y1, x2, y2 = det.bbox
            mask[y1:y2, x1:x2] = 255
    else:
        mask = np.ones(img.shape[:2], dtype=np.uint8) * 255
    tissue_cv = tissue_analyzer.analyze(img, wound_mask=mask)
    results["tissue_cv"] = {k.name if hasattr(k, 'name') else str(k): f"{v:.1f}%" for k, v in tissue_cv.tissue_percentages.items()}
    results["health_score"] = f"{tissue_cv.health_score:.1f}"

    # --- 4. Classificação de etiologia ---
    classifier_dl = EtiologyClassifier()
    classifier_dl.load_model()
    etiology_result = classifier_dl.classify(img)
    results["etiology_primary"] = etiology_result.primary_prediction.class_name
    results["etiology_confidence"] = f"{etiology_result.primary_prediction.confidence:.1%}"
    results["etiology_description"] = etiology_result.primary_prediction.description
    results["etiology_all"] = [
        {"name": p.class_name, "conf": f"{p.confidence:.1%}"}
        for p in etiology_result.all_predictions
    ]
    results["needs_review"] = etiology_result.needs_review

    # --- 5. Classificação heurística OpenCV ---
    classifier_cv = WoundClassifierCV()
    etiology_cv = classifier_cv.classify(img, tissue_percentages=tissue_cv.tissue_percentages)
    results["etiology_cv"] = etiology_cv.name
    results["etiology_cv_conf"] = f"{etiology_cv.confidence:.1%}"

    # --- 6. WoundAnalyzer integrado (segmentação + classificação DL) ---
    analyzer = WoundAnalyzer(parallel=False)
    full_result = analyzer.analyze(img, pixels_per_cm=30.0)
    results["wound_area_cm2"] = f"{full_result.wound_area_cm2:.1f}" if full_result.wound_area_cm2 else "N/A"
    results["total_time_ms"] = f"{full_result.total_inference_time_ms:.0f}"

    # Visualização integrada
    _, viz = analyzer.analyze_with_visualization(img)
    results["visualization_b64"] = image_to_base64(viz)

    elapsed = (time.perf_counter() - t0) * 1000
    results["pipeline_time_ms"] = f"{elapsed:.0f}"

    return results


# ============================================================
# Template HTML
# ============================================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>REDISUS — Teste Visual de Reconhecimento de Feridas</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: 'Inter', sans-serif;
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%);
    color: #e2e8f0;
    min-height: 100vh;
}
.header {
    background: rgba(15,23,42,0.95);
    border-bottom: 1px solid rgba(56,189,248,0.2);
    padding: 1.5rem 2rem;
    text-align: center;
}
.header h1 {
    font-size: 1.8rem;
    background: linear-gradient(135deg, #38bdf8, #818cf8);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0.3rem;
}
.header p { color: #94a3b8; font-size: 0.9rem; }
.summary-bar {
    display: flex; justify-content: center; gap: 2rem;
    padding: 1rem 2rem;
    background: rgba(30,41,59,0.8);
    border-bottom: 1px solid rgba(56,189,248,0.1);
    flex-wrap: wrap;
}
.summary-item {
    text-align: center;
    padding: 0.5rem 1.2rem;
    background: rgba(56,189,248,0.08);
    border-radius: 8px;
    border: 1px solid rgba(56,189,248,0.15);
}
.summary-item .val { font-size: 1.4rem; font-weight: 700; color: #38bdf8; }
.summary-item .lbl { font-size: 0.75rem; color: #94a3b8; text-transform: uppercase; }
.container { max-width: 1400px; margin: 0 auto; padding: 1.5rem; }
.wound-card {
    background: rgba(30,41,59,0.7);
    border: 1px solid rgba(56,189,248,0.12);
    border-radius: 16px;
    margin-bottom: 2rem;
    overflow: hidden;
    backdrop-filter: blur(8px);
}
.wound-card-header {
    padding: 1rem 1.5rem;
    background: linear-gradient(135deg, rgba(56,189,248,0.15), rgba(129,140,248,0.1));
    border-bottom: 1px solid rgba(56,189,248,0.15);
    display: flex; justify-content: space-between; align-items: center;
    flex-wrap: wrap; gap: 0.5rem;
}
.wound-card-header h2 { font-size: 1.15rem; font-weight: 600; color: #f1f5f9; }
.badge {
    display: inline-block; padding: 0.25rem 0.75rem;
    border-radius: 20px; font-size: 0.75rem; font-weight: 600;
}
.badge-review { background: rgba(251,191,36,0.2); color: #fbbf24; border: 1px solid rgba(251,191,36,0.3); }
.badge-ok { background: rgba(34,197,94,0.2); color: #22c55e; border: 1px solid rgba(34,197,94,0.3); }
.images-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 1rem;
    padding: 1.2rem;
}
.img-panel { text-align: center; }
.img-panel img {
    width: 100%; border-radius: 8px;
    border: 1px solid rgba(56,189,248,0.1);
    transition: transform 0.2s;
    cursor: pointer;
}
.img-panel img:hover { transform: scale(1.03); }
.img-panel .caption {
    font-size: 0.78rem; color: #94a3b8; margin-top: 0.4rem;
    text-transform: uppercase; letter-spacing: 0.05em;
}
.results-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: 1rem;
    padding: 0 1.2rem 1.2rem;
}
.result-box {
    background: rgba(15,23,42,0.5);
    border: 1px solid rgba(56,189,248,0.1);
    border-radius: 10px;
    padding: 1rem;
}
.result-box h3 {
    font-size: 0.85rem; color: #38bdf8;
    text-transform: uppercase; letter-spacing: 0.05em;
    margin-bottom: 0.6rem;
    border-bottom: 1px solid rgba(56,189,248,0.1);
    padding-bottom: 0.4rem;
}
.result-box .row { display: flex; justify-content: space-between; padding: 0.2rem 0; font-size: 0.85rem; }
.result-box .row .k { color: #94a3b8; }
.result-box .row .v { color: #f1f5f9; font-weight: 500; }
.bar-container { background: rgba(15,23,42,0.8); border-radius: 4px; height: 10px; margin-top: 2px; overflow: hidden; }
.bar { height: 100%; border-radius: 4px; }
.bar-gran { background: linear-gradient(90deg, #ef4444, #dc2626); }
.bar-slough { background: linear-gradient(90deg, #eab308, #ca8a04); }
.bar-necro { background: linear-gradient(90deg, #6b7280, #4b5563); }
.bar-peri { background: linear-gradient(90deg, #38bdf8, #0ea5e9); }
.bar-bg { background: linear-gradient(90deg, #22c55e, #16a34a); }
.etiology-list { list-style: none; }
.etiology-list li {
    display: flex; justify-content: space-between;
    padding: 0.3rem 0; font-size: 0.85rem;
    border-bottom: 1px solid rgba(56,189,248,0.05);
}
.etiology-list li:first-child { font-weight: 600; color: #38bdf8; }
.footer {
    text-align: center; padding: 2rem;
    color: #64748b; font-size: 0.8rem;
}
</style>
</head>
<body>
<div class="header">
    <h1>REDISUS — Teste Visual de Reconhecimento de Feridas</h1>
    <p>Pipeline completo: Detecção → Segmentação de Tecidos → Classificação Etiológica</p>
</div>

<div class="summary-bar">
    <div class="summary-item">
        <div class="val">{{ results|length }}</div>
        <div class="lbl">Imagens Analisadas</div>
    </div>
    <div class="summary-item">
        <div class="val">{{ total_detections }}</div>
        <div class="lbl">Feridas Detectadas</div>
    </div>
    <div class="summary-item">
        <div class="val">{{ categories|length }}</div>
        <div class="lbl">Categorias</div>
    </div>
    <div class="summary-item">
        <div class="val">{{ avg_time }}ms</div>
        <div class="lbl">Tempo Médio</div>
    </div>
</div>

<div class="container">
{% for r in results %}
<div class="wound-card">
    <div class="wound-card-header">
        <h2>{{ r.category | replace('_', ' ') | title }}</h2>
        <div>
            <span class="badge {{ 'badge-review' if r.needs_review else 'badge-ok' }}">
                {{ 'Revisão Necessária' if r.needs_review else 'Confiante' }}
            </span>
            <span style="margin-left:0.5rem; font-size:0.8rem; color:#94a3b8;">
                {{ r.image_size }} · {{ r.pipeline_time_ms }}ms · {{ r.num_detections }} detecção(ões)
            </span>
        </div>
    </div>
    
    <div class="images-grid">
        <div class="img-panel">
            <img src="data:image/jpeg;base64,{{ r.original_b64 }}" alt="Original">
            <div class="caption">Imagem Original</div>
        </div>
        <div class="img-panel">
            <img src="data:image/jpeg;base64,{{ r.detection_b64 }}" alt="Detecção">
            <div class="caption">Detecção de Feridas</div>
        </div>
        <div class="img-panel">
            <img src="data:image/jpeg;base64,{{ r.overlay_b64 }}" alt="Segmentação">
            <div class="caption">Segmentação Tecidual (Overlay)</div>
        </div>
        <div class="img-panel">
            <img src="data:image/jpeg;base64,{{ r.visualization_b64 }}" alt="Análise Integrada">
            <div class="caption">Análise Integrada (WoundAnalyzer)</div>
        </div>
    </div>
    
    <div class="results-grid">
        <div class="result-box">
            <h3>🔬 Composição Tecidual (U-Net)</h3>
            {% for tissue, pct in r.tissue_percentages.items() %}
            <div class="row">
                <span class="k">{{ tissue }}</span>
                <span class="v">{{ pct }}</span>
            </div>
            <div class="bar-container">
                <div class="bar {% if 'Granul' in tissue %}bar-gran{% elif 'Esfacelo' in tissue or 'Slough' in tissue %}bar-slough{% elif 'Necro' in tissue %}bar-necro{% elif 'Peri' in tissue %}bar-peri{% else %}bar-bg{% endif %}" style="width: {{ pct }}"></div>
            </div>
            {% endfor %}
            <div class="row" style="margin-top:0.5rem; border-top:1px solid rgba(56,189,248,0.1); padding-top:0.4rem;">
                <span class="k">Área da Ferida</span>
                <span class="v">{{ r.wound_area_px }} px · {{ r.wound_area_cm2 }} cm²</span>
            </div>
        </div>
        
        <div class="result-box">
            <h3>🏥 Classificação Etiológica (DL)</h3>
            <div class="row">
                <span class="k">Etiologia</span>
                <span class="v" style="color:#38bdf8;">{{ r.etiology_primary }}</span>
            </div>
            <div class="row">
                <span class="k">Confiança</span>
                <span class="v">{{ r.etiology_confidence }}</span>
            </div>
            <div class="row" style="font-size:0.8rem; color:#94a3b8; margin-bottom:0.5rem;">
                <span>{{ r.etiology_description }}</span>
            </div>
            <ul class="etiology-list">
            {% for e in r.etiology_all %}
                <li><span>{{ e.name }}</span><span>{{ e.conf }}</span></li>
            {% endfor %}
            </ul>
        </div>
        
        <div class="result-box">
            <h3>📊 Análise OpenCV (Heurística)</h3>
            <div class="row">
                <span class="k">Etiologia (CV)</span>
                <span class="v">{{ r.etiology_cv }}</span>
            </div>
            <div class="row">
                <span class="k">Confiança (CV)</span>
                <span class="v">{{ r.etiology_cv_conf }}</span>
            </div>
            <div class="row">
                <span class="k">Score de Saúde</span>
                <span class="v">{{ r.health_score }} / 100</span>
            </div>
            {% for tissue, pct in r.tissue_cv.items() %}
            <div class="row">
                <span class="k">{{ tissue }}</span>
                <span class="v">{{ pct }}</span>
            </div>
            {% endfor %}
        </div>
    </div>
</div>
{% endfor %}
</div>

<div class="footer">
    HEAL/REDISUS — Plataforma Nacional de Saúde Digital · Cluster REDISUS — RNP/RUTE<br>
    Pipeline: WoundDetectorCV + UNetSegmenter (sim.) + EtiologyClassifier (sim.) + WoundAnalyzer
</div>
</body>
</html>
"""

# ============================================================
# Flask App
# ============================================================
app = Flask(__name__)


@app.route("/")
def index():
    samples = find_sample_images(max_per_category=1)
    print(f"\n{'='*60}")
    print(f"  Analisando {len(samples)} imagens reais de feridas...")
    print(f"{'='*60}\n")

    results = []
    for cat, img_path in samples:
        print(f"  → Processando: {cat} / {img_path.name} ...", end=" ", flush=True)
        r = analyze_image(img_path)
        if r:
            results.append(r)
            print(f"OK ({r['pipeline_time_ms']}ms, {r['num_detections']} detecções)")
        else:
            print("FALHA ao carregar")

    total_det = sum(r["num_detections"] for r in results)
    categories = set(r["category"] for r in results)
    times = [float(r["pipeline_time_ms"]) for r in results]
    avg_t = f"{sum(times)/len(times):.0f}" if times else "0"

    print(f"\n  ✓ {len(results)} imagens processadas, {total_det} detecções\n")

    return render_template_string(
        HTML_TEMPLATE,
        results=results,
        total_detections=total_det,
        categories=categories,
        avg_time=avg_t,
    )


if __name__ == "__main__":
    print()
    print("=" * 60)
    print("  REDISUS — Teste Visual de Reconhecimento de Feridas")
    print("  Pipeline: Detecção → Segmentação → Classificação")
    print("=" * 60)
    print()
    print("  Abra no navegador: http://localhost:5050")
    print()
    app.run(host="127.0.0.1", port=5050, debug=False)
