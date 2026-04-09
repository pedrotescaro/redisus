from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.monitoring.wound_progression import analyze_wound_photo_progression
from src.processing.clinical_wound_analyzer_core import ClinicalWoundAnalyzer


def main() -> int:
    parser = argparse.ArgumentParser(description="Compara duas ou mais fotos de uma ferida.")
    parser.add_argument("images", nargs="+", help="Fotos em ordem cronologica")
    parser.add_argument("--days-between-photos", type=float, default=7.0)
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    if len(args.images) < 2:
        parser.error("informe pelo menos duas imagens")

    result = analyze_wound_photo_progression(
        args.images,
        analyzer_factory=ClinicalWoundAnalyzer,
        days_between_photos=args.days_between_photos,
        progress_callback=print,
    )
    payload = result.to_dict()
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding="utf-8")
        print(f"Relatorio salvo em {output_path}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
