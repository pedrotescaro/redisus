"""
REDISUS - Treinamento YOLOv8 para Deteccao de Feridas

Treina YOLOv8 Nano/Small para deteccao de feridas em tempo real.
Exporta modelo treinado para ONNX (inferencia via ONNX Runtime).

Dataset esperado no formato YOLO:
  dataset/yolo_wounds/
    train/images/ + train/labels/
    val/images/ + val/labels/

Uso:
  python scripts/train_yolo_wound.py
  python scripts/train_yolo_wound.py --model yolov8s.pt --imgsz 640 --epochs 150
  python scripts/train_yolo_wound.py --export-only --weights runs/detect/wound/weights/best.pt
"""
import argparse
import shutil
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

from loguru import logger


@dataclass
class YOLOTrainingConfig:
    """Configuracao de treinamento YOLOv8"""
    # Modelo
    model_size: str = "yolov8n.pt"  # yolov8n (nano), yolov8s (small)

    # Dataset
    data_yaml: str = "dataset/yolo_wounds/data.yaml"

    # Output
    output_dir: str = "runs/detect/wound"
    onnx_output: str = "models/yolo_wound_nano.onnx"

    # Treinamento
    imgsz: int = 320          # Match RealtimeConfig.detector.input_size
    epochs: int = 100
    batch_size: int = 16
    patience: int = 20        # Early stopping
    learning_rate: float = 0.01
    lrf: float = 0.01         # Final LR = lr0 * lrf

    # Augmentacao (conservativa para imagens medicas)
    # Hue MUITO baixo: cor de ferida e diagnostica
    # (vermelho=granulacao, amarelo=esfacelo, preto=necrose)
    hsv_h: float = 0.005      # Variacao de matiz minima
    hsv_s: float = 0.3        # Saturacao moderada
    hsv_v: float = 0.2        # Valor moderado

    # Geometricas (seguras - orientacao nao e diagnostica)
    mosaic: float = 1.0       # Mosaico (bom para datasets pequenos)
    mixup: float = 0.1        # Mixup leve
    flipud: float = 0.5       # Flip vertical
    fliplr: float = 0.5       # Flip horizontal
    scale: float = 0.3        # Variacao de escala
    degrees: float = 15.0     # Rotacao moderada

    # Hardware
    device: str = "0"         # GPU 0 (fallback CPU automatico)


def validate_dataset(data_yaml: str) -> bool:
    """
    Valida estrutura do dataset YOLO.

    Verifica:
    - data.yaml existe e contem campos obrigatorios
    - Diretorios train/val existem com imagens e labels
    - Labels estao no formato correto
    """
    import yaml

    yaml_path = Path(data_yaml)
    if not yaml_path.exists():
        logger.error(f"data.yaml nao encontrado: {data_yaml}")
        return False

    with open(yaml_path, encoding='utf-8') as f:
        data = yaml.safe_load(f)

    # Campos obrigatorios
    for field in ["path", "train", "val", "nc", "names"]:
        if field not in data:
            logger.error(f"Campo '{field}' ausente em data.yaml")
            return False

    base_path = Path(data["path"])

    # Verifica diretorios
    for split in ["train", "val"]:
        img_dir = base_path / data[split]
        label_dir = img_dir.parent / "labels"

        if not img_dir.exists():
            logger.error(f"Diretorio de imagens nao existe: {img_dir}")
            return False

        images = list(img_dir.glob("*.jpg")) + list(img_dir.glob("*.png")) + list(img_dir.glob("*.jpeg"))
        if not images:
            logger.error(f"Nenhuma imagem encontrada em: {img_dir}")
            return False

        if not label_dir.exists():
            logger.error(f"Diretorio de labels nao existe: {label_dir}")
            return False

        labels = list(label_dir.glob("*.txt"))
        if not labels:
            logger.error(f"Nenhum label encontrado em: {label_dir}")
            return False

        logger.info(f"[{split}] {len(images)} imagens, {len(labels)} labels")

        # Verifica formato de alguns labels
        errors = 0
        for label_file in labels[:5]:
            with open(label_file, encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    parts = line.strip().split()
                    if len(parts) != 5:
                        logger.warning(
                            f"Label invalido em {label_file.name}:{line_num} - "
                            f"esperado 5 valores, encontrado {len(parts)}"
                        )
                        errors += 1
                        continue
                    try:
                        class_id = int(parts[0])
                        coords = [float(x) for x in parts[1:]]
                        if class_id >= data["nc"]:
                            logger.warning(f"class_id {class_id} >= nc {data['nc']} em {label_file.name}")
                            errors += 1
                        if any(c < 0 or c > 1 for c in coords):
                            logger.warning(f"Coordenadas fora de [0,1] em {label_file.name}:{line_num}")
                            errors += 1
                    except ValueError:
                        logger.warning(f"Valores nao numericos em {label_file.name}:{line_num}")
                        errors += 1

        if errors > 0:
            logger.warning(f"[{split}] {errors} problemas encontrados nos labels verificados")

    logger.info("Dataset validado com sucesso")
    return True


def train(config: YOLOTrainingConfig):
    """
    Treina YOLOv8 para deteccao de feridas.

    Usa transfer learning a partir de checkpoint pre-treinado no COCO.
    """
    from ultralytics import YOLO

    logger.info(f"Carregando modelo base: {config.model_size}")
    model = YOLO(config.model_size)

    logger.info("Iniciando treinamento...")
    logger.info(f"  Dataset: {config.data_yaml}")
    logger.info(f"  Input: {config.imgsz}x{config.imgsz}")
    logger.info(f"  Epochs: {config.epochs}")
    logger.info(f"  Batch: {config.batch_size}")
    logger.info(f"  LR: {config.learning_rate}")

    results = model.train(
        data=config.data_yaml,
        epochs=config.epochs,
        imgsz=config.imgsz,
        batch=config.batch_size,
        patience=config.patience,
        lr0=config.learning_rate,
        lrf=config.lrf,
        # Augmentacao
        hsv_h=config.hsv_h,
        hsv_s=config.hsv_s,
        hsv_v=config.hsv_v,
        mosaic=config.mosaic,
        mixup=config.mixup,
        flipud=config.flipud,
        fliplr=config.fliplr,
        scale=config.scale,
        degrees=config.degrees,
        # Output
        project=config.output_dir,
        name="wound_yolov8",
        save=True,
        save_period=10,
        val=True,
        plots=True,
        device=config.device,
    )

    logger.info("Treinamento concluido")
    return results


def export_onnx(
    weights_path: str,
    config: YOLOTrainingConfig
) -> str:
    """
    Exporta modelo treinado para ONNX.

    Args:
        weights_path: Caminho para best.pt ou last.pt
        config: Configuracao (para imgsz e output path)

    Returns:
        Caminho do arquivo ONNX exportado
    """
    from ultralytics import YOLO

    weights = Path(weights_path)
    if not weights.exists():
        raise FileNotFoundError(f"Weights nao encontrados: {weights_path}")

    logger.info(f"Exportando {weights} para ONNX...")
    model = YOLO(str(weights))

    model.export(
        format="onnx",
        imgsz=config.imgsz,
        simplify=True,
        opset=12,
        dynamic=False,   # Shape estatico para inferencia mais rapida
        half=False,       # FP32 para compatibilidade
    )

    # O ultralytics salva o .onnx no mesmo diretorio do .pt
    exported_onnx = weights.with_suffix(".onnx")

    if not exported_onnx.exists():
        raise FileNotFoundError(f"ONNX exportado nao encontrado: {exported_onnx}")

    # Copia para destino final
    output_path = Path(config.onnx_output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(exported_onnx), str(output_path))

    logger.info(f"Modelo ONNX salvo em: {output_path}")
    logger.info(f"Tamanho: {output_path.stat().st_size / 1024 / 1024:.1f} MB")

    return str(output_path)


def evaluate(config: YOLOTrainingConfig, model_path: Optional[str] = None):
    """
    Avalia modelo no dataset de validacao.

    Args:
        config: Configuracao
        model_path: Caminho do modelo (ONNX ou .pt). Se None, usa onnx_output.
    """
    from ultralytics import YOLO

    path = model_path or config.onnx_output

    if not Path(path).exists():
        logger.error(f"Modelo nao encontrado: {path}")
        return None

    logger.info(f"Avaliando modelo: {path}")
    model = YOLO(path)

    metrics = model.val(
        data=config.data_yaml,
        imgsz=config.imgsz,
    )

    logger.info("=== Resultados da Avaliacao ===")
    logger.info(f"  mAP@0.5:      {metrics.box.map50:.4f}")
    logger.info(f"  mAP@0.5:0.95: {metrics.box.map:.4f}")
    logger.info(f"  Precision:     {metrics.box.mp:.4f}")
    logger.info(f"  Recall:        {metrics.box.mr:.4f}")

    return metrics


def benchmark_latency(config: YOLOTrainingConfig):
    """Mede latencia de inferencia do modelo ONNX."""
    import time
    import numpy as np

    onnx_path = Path(config.onnx_output)
    if not onnx_path.exists():
        logger.error(f"Modelo ONNX nao encontrado: {onnx_path}")
        return

    try:
        import onnxruntime as ort
    except ImportError:
        logger.error("onnxruntime nao instalado")
        return

    providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
    session = ort.InferenceSession(str(onnx_path), providers=providers)

    input_name = session.get_inputs()[0].name
    input_shape = session.get_inputs()[0].shape
    logger.info(f"Input shape: {input_shape}")
    logger.info(f"Provider: {session.get_providers()[0]}")

    # Dummy input
    dummy = np.random.randn(*input_shape).astype(np.float32)

    # Warmup
    for _ in range(5):
        session.run(None, {input_name: dummy})

    # Benchmark
    num_runs = 100
    times = []
    for _ in range(num_runs):
        start = time.perf_counter()
        session.run(None, {input_name: dummy})
        times.append((time.perf_counter() - start) * 1000)

    times_np = np.array(times)
    logger.info("=== Benchmark de Latencia ===")
    logger.info(f"  Media:  {times_np.mean():.1f} ms")
    logger.info(f"  P50:    {np.percentile(times_np, 50):.1f} ms")
    logger.info(f"  P95:    {np.percentile(times_np, 95):.1f} ms")
    logger.info(f"  P99:    {np.percentile(times_np, 99):.1f} ms")
    logger.info(f"  FPS:    {1000 / times_np.mean():.0f}")


def main():
    parser = argparse.ArgumentParser(
        description="REDISUS - Treinar YOLOv8 para deteccao de feridas"
    )

    parser.add_argument(
        "--model", type=str, default="yolov8n.pt",
        help="Modelo base (yolov8n.pt, yolov8s.pt)"
    )
    parser.add_argument(
        "--data", type=str, default="dataset/yolo_wounds/data.yaml",
        help="Caminho do data.yaml"
    )
    parser.add_argument(
        "--imgsz", type=int, default=320,
        help="Tamanho da imagem de entrada"
    )
    parser.add_argument(
        "--epochs", type=int, default=100,
        help="Numero de epochs"
    )
    parser.add_argument(
        "--batch", type=int, default=16,
        help="Tamanho do batch"
    )
    parser.add_argument(
        "--device", type=str, default="0",
        help="Device (0=GPU, cpu=CPU)"
    )
    parser.add_argument(
        "--export-only", action="store_true",
        help="Apenas exportar para ONNX (requer --weights)"
    )
    parser.add_argument(
        "--weights", type=str, default=None,
        help="Caminho dos weights para export/evaluate"
    )
    parser.add_argument(
        "--evaluate", action="store_true",
        help="Avaliar modelo apos treinamento"
    )
    parser.add_argument(
        "--benchmark", action="store_true",
        help="Benchmark de latencia do modelo ONNX"
    )
    parser.add_argument(
        "--skip-validation", action="store_true",
        help="Pular validacao do dataset"
    )

    args = parser.parse_args()

    config = YOLOTrainingConfig(
        model_size=args.model,
        data_yaml=args.data,
        imgsz=args.imgsz,
        epochs=args.epochs,
        batch_size=args.batch,
        device=args.device,
    )

    logger.info("=== REDISUS - Treinamento YOLOv8 ===")

    if args.export_only:
        # Apenas exportar
        weights = args.weights
        if not weights:
            # Tenta encontrar best.pt no output padrao
            default_best = Path(config.output_dir) / "wound_yolov8" / "weights" / "best.pt"
            if default_best.exists():
                weights = str(default_best)
            else:
                logger.error("Especifique --weights para exportar")
                return

        export_onnx(weights, config)

        if args.benchmark:
            benchmark_latency(config)
        return

    # Fluxo completo: validar -> treinar -> exportar -> avaliar

    # 1. Validar dataset
    if not args.skip_validation:
        if not validate_dataset(config.data_yaml):
            logger.error("Dataset invalido. Corrija os problemas acima.")
            return

    # 2. Treinar
    train(config)

    # 3. Exportar para ONNX
    best_pt = Path(config.output_dir) / "wound_yolov8" / "weights" / "best.pt"
    if best_pt.exists():
        export_onnx(str(best_pt), config)
    else:
        logger.warning(f"best.pt nao encontrado em {best_pt}")
        # Tenta last.pt
        last_pt = best_pt.parent / "last.pt"
        if last_pt.exists():
            export_onnx(str(last_pt), config)

    # 4. Avaliar
    if args.evaluate:
        evaluate(config)

    # 5. Benchmark
    if args.benchmark:
        benchmark_latency(config)

    logger.info("=== Pipeline Concluido ===")


if __name__ == "__main__":
    main()
