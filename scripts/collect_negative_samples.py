#!/usr/bin/env python3
"""
HEAL+ — Coleta de Amostras Negativas para Treinamento YOLO

Este script captura frames da webcam que NÃO contêm feridas,
para usar como exemplos negativos no treinamento do modelo YOLO.

Tipos de negativos úteis:
  - Pele saudável (braços, mãos, pernas)
  - Rostos
  - Superfícies (mesas, roupas, pisos)
  - Objetos médicos (curativos limpos, luvas)

Uso:
  python scripts/collect_negative_samples.py --output dataset/negative_samples
  python scripts/collect_negative_samples.py --output dataset/negative_samples --camera 1
  python scripts/collect_negative_samples.py --augment  # Aumenta amostras existentes

Instruções:
  - Pressione ESPAÇO para capturar o frame atual
  - Pressione 'a' para ativar captura automática (1 frame/segundo)
  - Pressione 'q' para sair
  - Movimente a câmera mostrando pele saudável, rostos, objetos, superfícies
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


def collect_from_webcam(output_dir: Path, camera_id: int = 0):
    """Captura frames da webcam interativamente."""
    output_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(camera_id)
    if not cap.isOpened():
        print(f"[ERRO] Não foi possível abrir a câmera {camera_id}")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    # Conta arquivos existentes para continuar a numeração
    existing = list(output_dir.glob("neg_*.jpg"))
    counter = len(existing)
    auto_capture = False
    last_auto = 0.0

    print(f"\n{'='*60}")
    print(f"  HEAL+ Coleta de Amostras Negativas")
    print(f"{'='*60}")
    print(f"  Diretório: {output_dir}")
    print(f"  Imagens existentes: {counter}")
    print(f"  Camera: {camera_id}")
    print(f"")
    print(f"  [ESPAÇO] Capturar frame")
    print(f"  [A]      Captura automática (1/s)")
    print(f"  [Q]      Sair")
    print(f"{'='*60}\n")

    while True:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.01)
            continue

        display = frame.copy()
        h, w = display.shape[:2]

        # HUD
        cv2.rectangle(display, (8, 8), (350, 80), (0, 0, 0), -1)
        cv2.rectangle(display, (8, 8), (350, 80), (0, 200, 255), 1)
        mode = "AUTO" if auto_capture else "MANUAL"
        cv2.putText(display, f"NEGATIVAS  |  {mode}  |  #{counter}",
                     (14, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 255), 1)
        cv2.putText(display, "[ESPACO] Capturar  [A] Auto  [Q] Sair",
                     (14, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)

        cv2.imshow("HEAL+ Coleta de Negativos", display)

        # Captura automática
        if auto_capture and (time.time() - last_auto) >= 1.0:
            fname = output_dir / f"neg_{counter:05d}.jpg"
            cv2.imwrite(str(fname), frame)
            counter += 1
            last_auto = time.time()
            print(f"  [AUTO] Salvo: {fname.name}  (total: {counter})")

        key = cv2.waitKey(30) & 0xFF
        if key == ord('q'):
            break
        elif key == ord(' '):
            fname = output_dir / f"neg_{counter:05d}.jpg"
            cv2.imwrite(str(fname), frame)
            counter += 1
            print(f"  [MANUAL] Salvo: {fname.name}  (total: {counter})")
        elif key == ord('a'):
            auto_capture = not auto_capture
            state = "LIGADA" if auto_capture else "DESLIGADA"
            print(f"  Captura automática: {state}")

    cap.release()
    cv2.destroyAllWindows()
    print(f"\nTotal de amostras negativas: {counter}")


def augment_negatives(input_dir: Path, output_dir: Path = None, copies: int = 3):
    """
    Aumenta amostras negativas com transformações geométricas e de cor.

    Para cada imagem negativa, gera N cópias com variações:
    - Flip horizontal/vertical
    - Rotação aleatória
    - Ajuste de brilho/contraste
    - Crop aleatório
    - Gaussian blur leve
    """
    if output_dir is None:
        output_dir = input_dir

    images = list(input_dir.glob("neg_*.jpg")) + list(input_dir.glob("neg_*.png"))
    if not images:
        print(f"[AVISO] Nenhuma imagem negativa encontrada em {input_dir}")
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    counter = len(list(output_dir.glob("neg_aug_*.jpg")))

    print(f"\n  Aumentando {len(images)} imagens x {copies} cópias...")

    for img_path in images:
        img = cv2.imread(str(img_path))
        if img is None:
            continue

        for _ in range(copies):
            aug = img.copy()
            h, w = aug.shape[:2]

            # Flip aleatório
            flip = np.random.choice([-1, 0, 1, 2])
            if flip != 2:
                aug = cv2.flip(aug, flip)

            # Rotação aleatória (±15°)
            angle = np.random.uniform(-15, 15)
            M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
            aug = cv2.warpAffine(aug, M, (w, h), borderMode=cv2.BORDER_REFLECT)

            # Brilho/contraste
            alpha = np.random.uniform(0.8, 1.3)  # contraste
            beta = np.random.uniform(-20, 20)     # brilho
            aug = cv2.convertScaleAbs(aug, alpha=alpha, beta=beta)

            # Crop aleatório (85-100% do tamanho)
            crop_ratio = np.random.uniform(0.85, 1.0)
            ch, cw = int(h * crop_ratio), int(w * crop_ratio)
            cy = np.random.randint(0, h - ch + 1)
            cx = np.random.randint(0, w - cw + 1)
            aug = aug[cy:cy + ch, cx:cx + cw]
            aug = cv2.resize(aug, (w, h))

            # Blur leve (50% de chance)
            if np.random.random() > 0.5:
                ksize = np.random.choice([3, 5])
                aug = cv2.GaussianBlur(aug, (ksize, ksize), 0)

            fname = output_dir / f"neg_aug_{counter:05d}.jpg"
            cv2.imwrite(str(fname), aug)
            counter += 1

    print(f"  Total de augmentações geradas: {counter}")


def create_yolo_negative_labels(image_dir: Path, label_dir: Path):
    """
    Cria arquivos .txt vazios para cada imagem negativa (formato YOLO).

    No YOLO, um .txt vazio significa "sem objetos nesta imagem" —
    isso ensina o modelo a NÃO detectar nada nesses frames.
    """
    label_dir.mkdir(parents=True, exist_ok=True)
    images = (
        list(image_dir.glob("neg_*.jpg"))
        + list(image_dir.glob("neg_*.png"))
        + list(image_dir.glob("neg_aug_*.jpg"))
    )

    count = 0
    for img_path in images:
        label_path = label_dir / f"{img_path.stem}.txt"
        if not label_path.exists():
            label_path.touch()  # Arquivo vazio = sem detecções
            count += 1

    print(f"\n  Labels vazios criados: {count}")
    print(f"  Diretório: {label_dir}")
    print(f"\n  Próximo passo: copie as imagens para dataset/yolo_wounds/images/train/")
    print(f"  e os labels para dataset/yolo_wounds/labels/train/")


def main():
    parser = argparse.ArgumentParser(
        description="HEAL+ — Coleta e Augmentação de Amostras Negativas"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="dataset/negative_samples",
        help="Diretório de saída para as imagens (default: dataset/negative_samples)",
    )
    parser.add_argument(
        "--camera", "-c",
        type=int,
        default=0,
        help="ID da câmera (default: 0)",
    )
    parser.add_argument(
        "--augment",
        action="store_true",
        help="Apenas aumenta amostras negativas existentes (sem webcam)",
    )
    parser.add_argument(
        "--copies",
        type=int,
        default=3,
        help="Número de cópias por imagem na augmentação (default: 3)",
    )
    parser.add_argument(
        "--labels",
        action="store_true",
        help="Gera labels YOLO vazios para as amostras negativas",
    )
    args = parser.parse_args()

    output_dir = Path(args.output)

    if args.labels:
        label_dir = output_dir.parent / "yolo_wounds" / "labels" / "train"
        create_yolo_negative_labels(output_dir, label_dir)
    elif args.augment:
        augment_negatives(output_dir, copies=args.copies)
    else:
        collect_from_webcam(output_dir, camera_id=args.camera)

        # Pergunta se quer aumentar
        resp = input("\nDeseja aumentar as amostras com augmentação? [s/N] ").strip().lower()
        if resp == 's':
            augment_negatives(output_dir, copies=args.copies)

        # Pergunta se quer gerar labels
        resp = input("Gerar labels YOLO vazios? [s/N] ").strip().lower()
        if resp == 's':
            label_dir = output_dir.parent / "yolo_wounds" / "labels" / "train"
            create_yolo_negative_labels(output_dir, label_dir)


if __name__ == "__main__":
    main()
