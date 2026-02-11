"""
REDISUS - Treinamento U-Net para Segmentacao de Tecidos

Treina U-Net com encoder EfficientNet-B0 para segmentacao semantica
de tecidos em feridas (5 classes).

Dataset esperado:
  dataset/tissue_segmentation/
    train/
      images/   (*.jpg, *.png)
      masks/    (*.png - single channel, valores 0-4)
    val/
      images/
      masks/

Classes:
  0: Background
  1: Granulacao (tecido saudavel, vermelho)
  2: Esfacelo (amarelo/branco)
  3: Necrose (preto)
  4: Pele perilesional

Uso:
  python scripts/train_unet_tissue.py
  python scripts/train_unet_tissue.py --encoder efficientnet-b2 --imgsz 512 --epochs 100
  python scripts/train_unet_tissue.py --export-only --weights runs/segment/tissue/best_model.pt
"""
import argparse
import json
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
from loguru import logger

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import Dataset, DataLoader
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    logger.warning("PyTorch nao disponivel")

try:
    import segmentation_models_pytorch as smp
    HAS_SMP = True
except ImportError:
    HAS_SMP = False
    logger.warning("segmentation-models-pytorch nao disponivel")

try:
    import albumentations as A
    from albumentations.pytorch import ToTensorV2
    HAS_ALBUM = True
except ImportError:
    HAS_ALBUM = False
    logger.warning("albumentations nao disponivel")


@dataclass
class UNetTrainingConfig:
    """Configuracao de treinamento U-Net"""
    # Dataset
    train_dir: str = "dataset/tissue_segmentation/train"
    val_dir: str = "dataset/tissue_segmentation/val"

    # Output
    output_dir: str = "runs/segment/tissue"
    onnx_output: str = "models/unet_tissue_segmentation.onnx"

    # Modelo
    encoder: str = "efficientnet-b0"
    encoder_weights: str = "imagenet"
    input_size: Tuple[int, int] = (512, 512)  # Match DiagnosisConfig.segmenter
    num_classes: int = 5

    # Treinamento
    epochs: int = 80
    batch_size: int = 8
    learning_rate: float = 1e-4
    weight_decay: float = 1e-4
    patience: int = 15           # Early stopping
    num_workers: int = 4

    # Loss - pesos por classe (background subrepresentado, necrose rara)
    class_weights: List[float] = field(default_factory=lambda: [0.5, 1.5, 1.5, 2.0, 0.8])

    # Nomes das classes
    class_names: List[str] = field(default_factory=lambda: [
        "Background", "Granulacao", "Esfacelo", "Necrose", "Perilesional"
    ])

    # Hardware
    device: str = "cuda"


class WoundSegmentationDataset(Dataset):
    """Dataset PyTorch para segmentacao de tecidos."""

    VALID_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}

    def __init__(
        self,
        image_dir: str,
        mask_dir: str,
        transform=None,
        num_classes: int = 5
    ):
        self.image_dir = Path(image_dir)
        self.mask_dir = Path(mask_dir)
        self.transform = transform
        self.num_classes = num_classes

        # Encontra pares imagem/mascara
        self.image_paths = sorted([
            p for p in self.image_dir.iterdir()
            if p.suffix.lower() in self.VALID_EXTENSIONS
        ])

        # Verifica mascaras correspondentes
        self.pairs = []
        for img_path in self.image_paths:
            # Tenta .png primeiro, depois mesmo sufixo
            mask_path = self.mask_dir / (img_path.stem + ".png")
            if not mask_path.exists():
                mask_path = self.mask_dir / img_path.name
            if mask_path.exists():
                self.pairs.append((img_path, mask_path))

        if len(self.pairs) < len(self.image_paths):
            missing = len(self.image_paths) - len(self.pairs)
            logger.warning(f"{missing} imagens sem mascara correspondente")

        logger.info(f"Dataset: {len(self.pairs)} pares imagem/mascara em {image_dir}")

    def __len__(self):
        return len(self.pairs)

    def __getitem__(self, idx):
        img_path, mask_path = self.pairs[idx]

        # Carrega imagem (BGR -> RGB)
        image = cv2.imread(str(img_path))
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # Carrega mascara (single channel, valores 0-4)
        mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)

        # Garante valores validos na mascara
        mask = np.clip(mask, 0, self.num_classes - 1)

        if self.transform:
            augmented = self.transform(image=image, mask=mask)
            image = augmented["image"]
            mask = augmented["mask"]

        return image, mask.long()


def create_augmentations(config: UNetTrainingConfig):
    """
    Pipeline de augmentacao com albumentations.

    Filosofia: conservativa para imagens medicas.
    - Geometricas sao seguras (orientacao nao e diagnostica)
    - Cor MUITO conservativa (vermelho=granulacao, amarelo=esfacelo)
    - ElasticTransform simula deformacao natural de tecidos
    """
    train_transform = A.Compose([
        A.Resize(config.input_size[0], config.input_size[1]),
        # Geometricas (seguras)
        A.HorizontalFlip(p=0.5),
        A.VerticalFlip(p=0.5),
        A.RandomRotate90(p=0.5),
        A.ShiftScaleRotate(
            shift_limit=0.05,
            scale_limit=0.1,
            rotate_limit=15,
            border_mode=cv2.BORDER_REFLECT,
            p=0.5
        ),
        A.ElasticTransform(alpha=30, sigma=6, p=0.3),
        # Cor (MUITO conservativa)
        A.RandomBrightnessContrast(
            brightness_limit=0.1,
            contrast_limit=0.1,
            p=0.3
        ),
        A.GaussNoise(var_limit=(5, 20), p=0.3),
        A.GaussianBlur(blur_limit=(3, 5), p=0.2),
        # Normalizacao ImageNet (encoder pre-treinado)
        A.Normalize(
            mean=(0.485, 0.456, 0.406),
            std=(0.229, 0.224, 0.225)
        ),
        ToTensorV2(),
    ])

    val_transform = A.Compose([
        A.Resize(config.input_size[0], config.input_size[1]),
        A.Normalize(
            mean=(0.485, 0.456, 0.406),
            std=(0.229, 0.224, 0.225)
        ),
        ToTensorV2(),
    ])

    return train_transform, val_transform


def build_model(config: UNetTrainingConfig):
    """Constroi U-Net com encoder EfficientNet-B0."""
    model = smp.Unet(
        encoder_name=config.encoder,
        encoder_weights=config.encoder_weights,
        in_channels=3,
        classes=config.num_classes,
        activation=None,  # Logits crus; softmax no pos-processamento
    )
    return model


def create_loss_function(config: UNetTrainingConfig, device):
    """
    Loss combinada: CrossEntropy + Dice.

    - CrossEntropy com pesos por classe (lida com desbalanceamento)
    - DiceLoss intrinsecamente lida com classes raras
    """
    class_weights = torch.tensor(config.class_weights, dtype=torch.float32).to(device)
    ce_loss = nn.CrossEntropyLoss(weight=class_weights)
    dice_loss = smp.losses.DiceLoss(mode="multiclass", classes=config.num_classes)

    def combined_loss(pred, target):
        return 0.5 * ce_loss(pred, target) + 0.5 * dice_loss(pred, target)

    return combined_loss


def compute_iou(pred_mask: np.ndarray, true_mask: np.ndarray, num_classes: int) -> np.ndarray:
    """Calcula IoU por classe."""
    iou_per_class = np.zeros(num_classes)

    for c in range(num_classes):
        pred_c = (pred_mask == c)
        true_c = (true_mask == c)

        intersection = np.logical_and(pred_c, true_c).sum()
        union = np.logical_or(pred_c, true_c).sum()

        if union > 0:
            iou_per_class[c] = intersection / union
        else:
            iou_per_class[c] = float("nan")  # Classe ausente

    return iou_per_class


def train_one_epoch(model, dataloader, optimizer, loss_fn, device):
    """Treina uma epoch."""
    model.train()
    total_loss = 0
    num_batches = 0

    for images, masks in dataloader:
        images = images.to(device)
        masks = masks.to(device)

        optimizer.zero_grad()
        predictions = model(images)  # (B, C, H, W)
        loss = loss_fn(predictions, masks)
        loss.backward()
        optimizer.step()

        total_loss += loss.item()
        num_batches += 1

    return total_loss / max(num_batches, 1)


def validate(model, dataloader, loss_fn, device, num_classes):
    """Validacao com loss e IoU por classe."""
    model.eval()
    total_loss = 0
    num_batches = 0
    all_iou = []

    with torch.no_grad():
        for images, masks in dataloader:
            images = images.to(device)
            masks = masks.to(device)

            predictions = model(images)
            loss = loss_fn(predictions, masks)
            total_loss += loss.item()
            num_batches += 1

            # IoU
            pred_classes = predictions.argmax(dim=1).cpu().numpy()
            true_classes = masks.cpu().numpy()

            for i in range(pred_classes.shape[0]):
                iou = compute_iou(pred_classes[i], true_classes[i], num_classes)
                all_iou.append(iou)

    # Media IoU por classe (ignora NaN)
    all_iou = np.array(all_iou)
    mean_iou_per_class = np.nanmean(all_iou, axis=0)

    return total_loss / max(num_batches, 1), mean_iou_per_class


def validate_dataset(config: UNetTrainingConfig) -> bool:
    """Valida estrutura do dataset de segmentacao."""
    for split_name, split_dir in [("train", config.train_dir), ("val", config.val_dir)]:
        img_dir = Path(split_dir) / "images"
        mask_dir = Path(split_dir) / "masks"

        if not img_dir.exists():
            logger.error(f"[{split_name}] Diretorio de imagens nao existe: {img_dir}")
            return False

        if not mask_dir.exists():
            logger.error(f"[{split_name}] Diretorio de mascaras nao existe: {mask_dir}")
            return False

        images = list(img_dir.glob("*"))
        masks = list(mask_dir.glob("*"))
        logger.info(f"[{split_name}] {len(images)} imagens, {len(masks)} mascaras")

        if not images:
            logger.error(f"[{split_name}] Nenhuma imagem encontrada")
            return False

        # Verifica formato de uma mascara
        if masks:
            sample_mask = cv2.imread(str(masks[0]), cv2.IMREAD_GRAYSCALE)
            if sample_mask is not None:
                unique_vals = np.unique(sample_mask)
                logger.info(f"[{split_name}] Valores unicos na mascara: {unique_vals}")
                if any(v >= config.num_classes for v in unique_vals):
                    logger.warning(
                        f"[{split_name}] Mascara contem valores >= {config.num_classes}: {unique_vals}"
                    )

    logger.info("Dataset validado com sucesso")
    return True


def train_model(config: UNetTrainingConfig):
    """Pipeline completo de treinamento."""
    if not HAS_TORCH:
        raise RuntimeError("PyTorch necessario")
    if not HAS_SMP:
        raise RuntimeError("segmentation-models-pytorch necessario")
    if not HAS_ALBUM:
        raise RuntimeError("albumentations necessario")

    device = torch.device(
        "cuda" if config.device == "cuda" and torch.cuda.is_available()
        else "cpu"
    )
    logger.info(f"Device: {device}")

    # 1. Modelo
    model = build_model(config).to(device)
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    logger.info(f"Parametros: {total_params:,} total, {trainable_params:,} treinaveis")

    # 2. Datasets
    train_transform, val_transform = create_augmentations(config)

    train_dataset = WoundSegmentationDataset(
        image_dir=str(Path(config.train_dir) / "images"),
        mask_dir=str(Path(config.train_dir) / "masks"),
        transform=train_transform,
        num_classes=config.num_classes,
    )
    val_dataset = WoundSegmentationDataset(
        image_dir=str(Path(config.val_dir) / "images"),
        mask_dir=str(Path(config.val_dir) / "masks"),
        transform=val_transform,
        num_classes=config.num_classes,
    )

    train_loader = DataLoader(
        train_dataset,
        batch_size=config.batch_size,
        shuffle=True,
        num_workers=config.num_workers,
        pin_memory=True,
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=config.batch_size,
        shuffle=False,
        num_workers=config.num_workers,
        pin_memory=True,
    )

    # 3. Optimizer, scheduler, loss
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=config.learning_rate,
        weight_decay=config.weight_decay,
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=config.epochs
    )
    loss_fn = create_loss_function(config, device)

    # 4. Diretorios de saida
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 5. Training loop
    best_val_loss = float("inf")
    patience_counter = 0
    history = {"train_loss": [], "val_loss": [], "mean_iou": [], "lr": []}

    logger.info("Iniciando treinamento...")
    logger.info(f"  Encoder: {config.encoder}")
    logger.info(f"  Input: {config.input_size}")
    logger.info(f"  Epochs: {config.epochs}")
    logger.info(f"  Batch: {config.batch_size}")
    logger.info(f"  LR: {config.learning_rate}")
    logger.info(f"  Train: {len(train_dataset)} amostras")
    logger.info(f"  Val: {len(val_dataset)} amostras")

    for epoch in range(config.epochs):
        epoch_start = time.time()

        # Train
        train_loss = train_one_epoch(model, train_loader, optimizer, loss_fn, device)

        # Validate
        val_loss, iou_per_class = validate(model, val_loader, loss_fn, device, config.num_classes)

        # Scheduler
        scheduler.step()
        current_lr = optimizer.param_groups[0]["lr"]

        # Mean IoU (sem background)
        tissue_iou = iou_per_class[1:]  # Exclui background
        mean_iou = float(np.nanmean(tissue_iou))

        elapsed = time.time() - epoch_start

        # Log
        iou_str = " | ".join(
            f"{config.class_names[i]}: {iou_per_class[i]:.3f}"
            for i in range(config.num_classes)
            if not np.isnan(iou_per_class[i])
        )
        logger.info(
            f"Epoch {epoch + 1}/{config.epochs} "
            f"[{elapsed:.0f}s] "
            f"train_loss={train_loss:.4f} "
            f"val_loss={val_loss:.4f} "
            f"mIoU={mean_iou:.4f} "
            f"lr={current_lr:.2e}"
        )
        logger.info(f"  IoU: {iou_str}")

        # Historico
        history["train_loss"].append(train_loss)
        history["val_loss"].append(val_loss)
        history["mean_iou"].append(mean_iou)
        history["lr"].append(current_lr)

        # Checkpoint
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
            torch.save(model.state_dict(), output_dir / "best_model.pt")
            logger.info(f"  Novo melhor modelo salvo (val_loss={val_loss:.4f})")
        else:
            patience_counter += 1

        # Checkpoint periodico
        if (epoch + 1) % 10 == 0:
            torch.save(model.state_dict(), output_dir / f"checkpoint_epoch_{epoch + 1}.pt")

        # Early stopping
        if patience_counter >= config.patience:
            logger.info(f"Early stopping na epoch {epoch + 1} (patience={config.patience})")
            break

    # Salva historico
    with open(output_dir / "training_history.json", "w") as f:
        json.dump(history, f, indent=2)

    # Salva modelo final
    torch.save(model.state_dict(), output_dir / "last_model.pt")

    logger.info(f"Treinamento concluido. Melhor val_loss: {best_val_loss:.4f}")
    return model, history


def export_onnx(
    weights_path: str,
    config: UNetTrainingConfig
) -> str:
    """
    Exporta modelo treinado para ONNX.

    Args:
        weights_path: Caminho para .pt (state_dict)
        config: Configuracao

    Returns:
        Caminho do arquivo ONNX
    """
    device = torch.device("cpu")  # Export em CPU para compatibilidade

    # Reconstroi modelo e carrega weights
    model = build_model(config).to(device)
    state_dict = torch.load(weights_path, map_location=device)
    model.load_state_dict(state_dict)
    model.eval()

    # Dummy input
    dummy_input = torch.randn(1, 3, *config.input_size).to(device)

    # Export
    output_path = Path(config.onnx_output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Exportando para ONNX: {output_path}")

    torch.onnx.export(
        model,
        dummy_input,
        str(output_path),
        opset_version=12,
        input_names=["input"],
        output_names=["output"],
        dynamic_axes=None,  # Shape estatico para inferencia mais rapida
    )

    # Verifica com ONNX Runtime
    try:
        import onnxruntime as ort

        session = ort.InferenceSession(str(output_path))
        test_input = dummy_input.numpy()
        output = session.run(None, {"input": test_input})[0]

        expected_shape = (1, config.num_classes, *config.input_size)
        assert output.shape == expected_shape, (
            f"Shape inesperado: {output.shape}, esperado: {expected_shape}"
        )
        logger.info(f"Verificacao ONNX OK - output shape: {output.shape}")

    except ImportError:
        logger.warning("onnxruntime nao disponivel para verificacao")

    file_size = output_path.stat().st_size / 1024 / 1024
    logger.info(f"Modelo ONNX salvo: {output_path} ({file_size:.1f} MB)")

    return str(output_path)


def benchmark_latency(config: UNetTrainingConfig):
    """Benchmark de latencia ONNX."""
    onnx_path = Path(config.onnx_output)
    if not onnx_path.exists():
        logger.error(f"Modelo ONNX nao encontrado: {onnx_path}")
        return

    try:
        import onnxruntime as ort
    except ImportError:
        logger.error("onnxruntime nao instalado")
        return

    providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    session = ort.InferenceSession(str(onnx_path), providers=providers)

    input_name = session.get_inputs()[0].name
    dummy = np.random.randn(1, 3, *config.input_size).astype(np.float32)

    logger.info(f"Provider: {session.get_providers()[0]}")

    # Warmup
    for _ in range(5):
        session.run(None, {input_name: dummy})

    # Benchmark
    times = []
    for _ in range(50):
        start = time.perf_counter()
        session.run(None, {input_name: dummy})
        times.append((time.perf_counter() - start) * 1000)

    times_np = np.array(times)
    logger.info("=== Benchmark de Latencia ===")
    logger.info(f"  Media:  {times_np.mean():.1f} ms")
    logger.info(f"  P50:    {np.percentile(times_np, 50):.1f} ms")
    logger.info(f"  P95:    {np.percentile(times_np, 95):.1f} ms")
    logger.info(f"  FPS:    {1000 / times_np.mean():.0f}")


def main():
    parser = argparse.ArgumentParser(
        description="REDISUS - Treinar U-Net para segmentacao de tecidos"
    )

    parser.add_argument(
        "--encoder", type=str, default="efficientnet-b0",
        help="Encoder backbone (efficientnet-b0, efficientnet-b2, resnet34)"
    )
    parser.add_argument(
        "--imgsz", type=int, default=512,
        help="Tamanho da imagem de entrada"
    )
    parser.add_argument(
        "--epochs", type=int, default=80,
        help="Numero de epochs"
    )
    parser.add_argument(
        "--batch", type=int, default=8,
        help="Tamanho do batch"
    )
    parser.add_argument(
        "--lr", type=float, default=1e-4,
        help="Learning rate"
    )
    parser.add_argument(
        "--device", type=str, default="cuda",
        help="Device (cuda, cpu)"
    )
    parser.add_argument(
        "--train-dir", type=str, default="dataset/tissue_segmentation/train",
        help="Diretorio de treino"
    )
    parser.add_argument(
        "--val-dir", type=str, default="dataset/tissue_segmentation/val",
        help="Diretorio de validacao"
    )
    parser.add_argument(
        "--export-only", action="store_true",
        help="Apenas exportar para ONNX (requer --weights)"
    )
    parser.add_argument(
        "--weights", type=str, default=None,
        help="Caminho dos weights para export"
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

    config = UNetTrainingConfig(
        encoder=args.encoder,
        input_size=(args.imgsz, args.imgsz),
        epochs=args.epochs,
        batch_size=args.batch,
        learning_rate=args.lr,
        device=args.device,
        train_dir=args.train_dir,
        val_dir=args.val_dir,
    )

    logger.info("=== REDISUS - Treinamento U-Net ===")

    if args.export_only:
        weights = args.weights
        if not weights:
            default_best = Path(config.output_dir) / "best_model.pt"
            if default_best.exists():
                weights = str(default_best)
            else:
                logger.error("Especifique --weights para exportar")
                return

        export_onnx(weights, config)

        if args.benchmark:
            benchmark_latency(config)
        return

    # Fluxo completo

    # 1. Validar dataset
    if not args.skip_validation:
        if not validate_dataset(config):
            logger.error("Dataset invalido. Corrija os problemas acima.")
            return

    # 2. Treinar
    model, history = train_model(config)

    # 3. Exportar para ONNX
    best_path = Path(config.output_dir) / "best_model.pt"
    if best_path.exists():
        export_onnx(str(best_path), config)
    else:
        logger.warning("best_model.pt nao encontrado, exportando last_model.pt")
        last_path = Path(config.output_dir) / "last_model.pt"
        if last_path.exists():
            export_onnx(str(last_path), config)

    # 4. Benchmark
    if args.benchmark:
        benchmark_latency(config)

    logger.info("=== Pipeline Concluido ===")


if __name__ == "__main__":
    main()
