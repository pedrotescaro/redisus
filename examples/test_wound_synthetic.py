#!/usr/bin/env python3
"""Gera uma imagem sintetica de ferida para teste do ensemble."""
import cv2
import numpy as np
from pathlib import Path

def create_synthetic_wound(output_path: str = "examples/synthetic_wound.jpg"):
    """Cria imagem sintetica realista de ferida (480x640)."""
    h, w = 480, 640
    # Fundo pele (BGR)
    skin_color = np.array([180, 200, 220], dtype=np.uint8)
    image = np.full((h, w, 3), skin_color, dtype=np.uint8)

    # Variacao na pele
    noise = np.random.normal(0, 8, (h, w, 3)).astype(np.int16)
    image = np.clip(image.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    cx, cy = w // 2, h // 2

    # Borda perilesional (rosa avermelhado)
    cv2.ellipse(image, (cx, cy), (140, 100), 0, 0, 360, (160, 170, 210), -1)

    # Area da ferida - granulacao (vermelho)
    cv2.ellipse(image, (cx, cy), (100, 70), 0, 0, 360, (40, 40, 180), -1)

    # Esfacelo (amarelo) - regiao parcial
    cv2.ellipse(image, (cx - 20, cy + 10), (50, 30), 15, 0, 360, (80, 210, 220), -1)

    # Necrose (escuro) - pequena area
    cv2.ellipse(image, (cx + 30, cy - 15), (25, 18), -10, 0, 360, (20, 20, 30), -1)

    # Suaviza bordas
    image = cv2.GaussianBlur(image, (5, 5), 1.5)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(output_path, image)
    print(f"Imagem sintetica salva em: {output_path}")
    return output_path

if __name__ == "__main__":
    create_synthetic_wound()
