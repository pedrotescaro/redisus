"""Quick test runner for U-Net training script."""
import sys
import os

# Force unbuffered output
os.environ['PYTHONUNBUFFERED'] = '1'

# Redirect loguru to stdout for capture
from loguru import logger
logger.remove()  # Remove default stderr handler
logger.add(sys.stdout, level="INFO")

# Now run the U-Net validation
sys.argv = [
    'train_unet_tissue.py',
    '--imgsz', '256',
    '--epochs', '2',        # Just 2 for testing
    '--batch', '4',
    '--lr', '5e-5',
    '--device', 'cpu',
]

print("=" * 50)
print("Testing U-Net training pipeline...")
print("=" * 50)

try:
    # Add parent dir to path so we can import from scripts/
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from train_unet_tissue import UNetTrainingConfig, validate_dataset

    config = UNetTrainingConfig(
        input_size=(256, 256),
        epochs=2,
        batch_size=4,
        learning_rate=5e-5,
        device="cpu",
    )

    print(f"Config: encoder={config.encoder}, size={config.input_size}, epochs={config.epochs}")
    print(f"Train dir: {config.train_dir}")
    print(f"Val dir: {config.val_dir}")

    result = validate_dataset(config)
    print(f"Dataset valid: {result}")

    if not result:
        print("\nDataset U-Net esta VAZIO.")
        print("O dataset tissue_segmentation requer anotacao MANUAL de mascaras.")
        print("Use ferramentas como LabelMe, CVAT ou Supervisely para criar")
        print("mascaras de segmentacao (valores 0-4 para cada classe de tecido).")
        print("\nO treinamento YOLO ja esta em andamento com sucesso!")

except Exception as e:
    print(f"ERRO: {e}")
    import traceback
    traceback.print_exc()
