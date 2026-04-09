from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.training.pressure_injury_stage_training import (
    PressureInjuryTrainingConfig,
    ensure_pressure_injury_layout,
    prepare_pressure_injury_manifest,
    train_pressure_injury_stage_classifier,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Pipeline LP-only para preparar e treinar classificador de estagio de lesao por pressao (PIID)."
    )
    parser.add_argument("--dataset-dir", default="dataset/piid/raw", help="Diretorio raw com pastas stage_1..stage_4.")
    parser.add_argument("--manifest", default="dataset/piid/manifests/piid_lp_split.json", help="Caminho do manifesto JSON.")
    parser.add_argument("--output-dir", default="models/pressure_injury_stage_classifier", help="Diretorio de saida dos artefatos.")
    parser.add_argument("--batch-size", type=int, default=16, help="Batch size do treino.")
    parser.add_argument("--epochs", type=int, default=35, help="Numero de epocas.")
    parser.add_argument("--focal-gamma", type=float, default=1.5, help="Foco em exemplos dificeis; 0 desliga focal loss.")
    parser.add_argument("--label-smoothing", type=float, default=0.03, help="Suavizacao leve dos rotulos.")
    parser.add_argument("--stage3-loss-multiplier", type=float, default=1.35, help="Peso extra para stage_3.")
    parser.add_argument("--stage4-loss-multiplier", type=float, default=1.10, help="Peso extra para stage_4.")
    parser.add_argument("--stage34-sampler-multiplier", type=float, default=1.20, help="Amostragem extra para stage_3/stage_4.")
    parser.add_argument("--init-layout", action="store_true", help="Cria as pastas locais esperadas para o PIID.")
    parser.add_argument("--prepare-only", action="store_true", help="Somente valida o dataset e gera o manifesto.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config = PressureInjuryTrainingConfig(
        raw_dataset_dir=args.dataset_dir,
        manifest_path=args.manifest,
        output_dir=args.output_dir,
        batch_size=args.batch_size,
        epochs=args.epochs,
        focal_gamma=args.focal_gamma,
        label_smoothing=args.label_smoothing,
        stage3_loss_multiplier=args.stage3_loss_multiplier,
        stage4_loss_multiplier=args.stage4_loss_multiplier,
        stage34_sampler_multiplier=args.stage34_sampler_multiplier,
    )

    if args.init_layout:
        layout = ensure_pressure_injury_layout(config)
        print(json.dumps({key: str(value) for key, value in layout.items()}, ensure_ascii=False, indent=2))
        if args.prepare_only:
            return 0

    try:
        if args.prepare_only:
            manifest_path = prepare_pressure_injury_manifest(config)
            print(json.dumps({"manifest_path": str(manifest_path)}, ensure_ascii=False, indent=2))
            return 0

        result = train_pressure_injury_stage_classifier(config)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {
                    "error": "pressure_injury_training_unavailable",
                    "detail": str(exc),
                    "next_steps": [
                        "Coloque imagens do PIID em dataset/piid/raw/stage_1..stage_4.",
                        "Instale PyTorch/torchvision antes do treino real.",
                        "Rode novamente com --prepare-only para gerar o manifesto.",
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
