#!/usr/bin/env python3
"""
REDISUS — Launcher de Re-treinamento

Script simples para re-treinar o classificador de feridas com as
melhorias v2 (consolidação de classes, EfficientNetB3, 3 fases).

Uso:
    python retrain.py                  # Treinamento completo (3 fases)
    python retrain.py --fast           # Apenas fase 1 (rápido)
    python retrain.py --epochs 60      # Custom épocas
"""
import subprocess
import sys
from pathlib import Path

def main():
    script = Path(__file__).parent / "scripts" / "train_improved.py"
    
    if not script.exists():
        print(f"Erro: Script de treinamento não encontrado: {script}")
        sys.exit(1)
    
    # Passa argumentos
    args = [sys.executable, str(script)]
    
    if "--fast" in sys.argv:
        args.extend(["--no-fine-tune", "--epochs", "20"])
        sys.argv.remove("--fast")
    
    # Passa outros argumentos
    extra = [a for a in sys.argv[1:] if a != "--fast"]
    args.extend(extra)
    
    print("=" * 60)
    print("REDISUS — Re-treinamento do Classificador v2")
    print("=" * 60)
    print(f"Script: {script}")
    print(f"Comando: {' '.join(args)}")
    print("=" * 60)
    
    result = subprocess.run(args, cwd=str(Path(__file__).parent))
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
