import os
import re
from pathlib import Path

# Paths relative to the project root
ROOT = Path("c:/Users/PEDRO/Documents/redisus")

FILES_TO_MERGE = [
    "src/processing/image_processor.py",
    "src/processing/preprocessing_filters.py",
    "src/processing/false_positive_filter.py",
    "src/processing/image_enhancer.py",
    "src/processing/roi_segmentation.py",
    "src/processing/tissue_analyzer.py",
    "src/processing/wound_classifier_cv.py",
    "src/processing/wound_detector_cv.py",
    "src/processing/dl_tissue_pipeline.py",
    "src/processing/clinical_wound_analyzer_core.py",
]

OUTPUT_FILE = ROOT / "heal_model_standalone.py"

def clean_imports_and_headers(content: str) -> str:
    lines = content.split('\n')
    cleaned_lines = []
    
    in_import_parens = False
    for line in lines:
        if line.startswith("# -*- coding"):
            continue
            
        if "from __future__ import" in line:
            continue
            
        # Strip local processing imports because they will be in the same file
        stripped_line = line.strip()
        if not in_import_parens and (stripped_line.startswith("from src.processing.") or stripped_line.startswith("import src.processing.")):
            if "(" in stripped_line and ")" not in stripped_line:
                in_import_parens = True
            continue
            
        if in_import_parens:
            if ")" in stripped_line:
                in_import_parens = False
            continue
            
        if not in_import_parens and stripped_line.startswith("from src.") and not stripped_line.startswith("from src.processing."):
            # For non-processing src imports, we'll also comment them out if they are multiline to avoid issues, or leave them.
            # But the issue was we deleted processing ones. For non-processing ones, let's keep them so they raise ImportError.
            pass

        # Strip PyQt6 imports completely
        if "PyQt6" in line:
            if "(" in stripped_line and ")" not in stripped_line:
                in_import_parens = True
            continue
            
        cleaned_lines.append(line)
        
    return '\n'.join(cleaned_lines)

def get_standard_imports():
    return """# -*- coding: utf-8 -*-
from __future__ import annotations
\"\"\"
======================================================================
1. README / DOCUMENTACAO
======================================================================
HEAL+ / REDISUS — Analisador Clínico de Feridas (Standalone)

Este script consolida o pipeline explicável de visão computacional 
para análise de feridas em um único arquivo. Ele atua como um motor 
autônomo e headless, sem dependências de PyQt6 ou infraestrutura web.

AVISO CLÍNICO E ÉTICO OBRIGATÓRIO:
Este script realiza uma análise assistiva/experimental para apoio, 
validação e discussão com especialista. Ele não substitui avaliação 
clínica, diagnóstico médico ou decisão terapêutica profissional.

DEPENDÊNCIAS (Python 3.9+ recomendado):
    pip install opencv-python numpy
    pip install torch torchvision (Opcional, apenas se for usar --use-dl)

COMO EXECUTAR:
    Exemplo imagem única:
      python heal_model_standalone.py --input "imagens/paciente1.jpg" --output "outputs/"

    Exemplo pasta de imagens:
      python heal_model_standalone.py --input "imagens_teste/" --output "outputs/"

    Exemplo com Deep Learning Opcional (se existirem modelos/checkpoints):
      python heal_model_standalone.py --input "imagens/" --output "outputs/" --use-dl

CORES DO MAPA DE TECIDOS:
    - Vermelho Intenso: Granulação (Tecido viável, cicatrização)
    - Amarelo/Bege: Esfacelo (Fibrina/Tecido desvitalizado aderido)
    - Preto/Marrom Escuro: Necrose (Escara de coagulação)
    - Rosa Claro: Epitelização (Fechamento e regeneração final)

======================================================================
2. IMPORTS
======================================================================
\"\"\"
import os
import sys
import io
import time
import json
import csv
import logging
import argparse
import traceback
from pathlib import Path
from typing import Dict, Optional, Tuple, List, Any, Mapping
from dataclasses import dataclass, field
import cv2
import numpy as np

# Torch is optional for DL pipeline
try:
    import torch
    from torchvision import transforms as _tv_transforms
    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False

try:
    from PIL import Image, ImageDraw, ImageFont
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# ======================================================================
# 3. DATACLASSES E 4. CONFIGURACOES CLINICAS (Incluidos da extracao)
# ======================================================================
"""

def get_cli_main():
    return """# ============================================================
# 11. CLI E 12. FUNCAO MAIN()
# ============================================================

def process_image(image_path: Path, output_dir: Path, analyzer: ClinicalWoundAnalyzer, csv_data_list: list):
    logger.info(f"Processando imagem: {image_path.name}")
    
    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError(f"Não foi possível ler a imagem: {image_path}")
        
    start_t = time.time()
    
    # Executa a análise completa
    report = analyzer.analyze(img)
    
    processing_time = (time.time() - start_t) * 1000
    
    # 1. Copia ou Redimensiona Original
    h, w = img.shape[:2]
    # Se ja foi redimensionado pelo analyzer (maior que 1024), usaremos o report.original
    out_orig_path = output_dir / f"{image_path.stem}_original.jpg"
    cv2.imwrite(str(out_orig_path), report.original)
    
    # Inicializa dict de output
    out_dict = {
        "nome_arquivo": image_path.name,
        "ferida_valida": report.is_valid_wound,
        "tempo_processamento_ms": processing_time,
        "observacoes_tecnicas": report.rejection_reason if not report.is_valid_wound else "Ferida processada com sucesso via Pipeline Explicável CV.",
        "area_estimada_pixels": report.wound_area_px,
        "tecido_predominante": "N/A",
        "score_visual_tecidual": 0.0,
        "percentual_granulacao": 0.0,
        "percentual_necrose": 0.0,
        "percentual_esfacelo": 0.0,
        "percentual_epitelizacao": 0.0,
        "caminhos_arquivos_gerados": {
            "original": str(out_orig_path)
        },
        "aviso_clinico": "Este script realiza uma análise assistiva/experimental para apoio, validação e discussão com especialista. Ele não substitui avaliação clínica, diagnóstico médico ou decisão terapêutica profissional."
    }
    
    if report.is_valid_wound:
        # Pega as mascaras geradas
        # 2. Mascara da ferida (ROI)
        roi_mask = report.segmentation_map  # Usa o tecido gerado ou mascara principal
        # Em ClinicalWoundAnalyzer, podemos n ter a mask exposta diretamente no objeto report
        # Entao extraimos da imagem de segmentação se precisar
        if report.roi and 'mask' in report.roi:
            mask_out = report.roi['mask']
        else:
            # Fallback pra encontrar a ROI apartir do original x overlay
            mask_out = np.zeros(report.original.shape[:2], dtype=np.uint8)
            if report.tissue_overlay is not None:
                mask_out = np.where(report.tissue_overlay != report.original, 255, 0).astype(np.uint8)[:,:,0]
        
        out_mask_path = output_dir / f"{image_path.stem}_roi_mask.png"
        cv2.imwrite(str(out_mask_path), mask_out)
        out_dict["caminhos_arquivos_gerados"]["mascara_roi"] = str(out_mask_path)
        
        # 3. Mapa de Tecidos
        if report.tissue_overlay is not None:
            out_tissue_path = output_dir / f"{image_path.stem}_tissue_map.png"
            cv2.imwrite(str(out_tissue_path), report.tissue_overlay)
            out_dict["caminhos_arquivos_gerados"]["mapa_tecidos"] = str(out_tissue_path)
            
        # 4. Overlay com contornos
        out_overlay_path = output_dir / f"{image_path.stem}_overlay.jpg"
        cv2.imwrite(str(out_overlay_path), report.tissue_overlay if report.tissue_overlay is not None else report.original)
        out_dict["caminhos_arquivos_gerados"]["overlay"] = str(out_overlay_path)
        
        maior_tecido = ""
        maior_pct = -1
        
        for t in report.tissues:
            pct = t.percentage
            if "Granula" in t.name:
                out_dict["percentual_granulacao"] = pct
            elif "Necrose" in t.name:
                out_dict["percentual_necrose"] = pct
            elif "Esfacelo" in t.name:
                out_dict["percentual_esfacelo"] = pct
            elif "Epitel" in t.name:
                out_dict["percentual_epitelizacao"] = pct
                
            if pct > maior_pct:
                maior_pct = pct
                maior_tecido = t.name
                
        out_dict["tecido_predominante"] = maior_tecido
        out_dict["score_visual_tecidual"] = report.health_score

    # 5. Salva Relatorio JSON
    out_json = output_dir / f"{image_path.stem}_report.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(out_dict, f, indent=4, ensure_ascii=False)
    out_dict["caminhos_arquivos_gerados"]["json"] = str(out_json)
        
    logger.info(f"Concluído: {image_path.name}")
    csv_data_list.append(out_dict)
    return True

def main():
    # ======================================================================
    # CONFIGURAÇÃO RÁPIDA (Altere aqui se não quiser usar linha de comando)
    # ======================================================================
    CAMINHO_DA_IMAGEM_OU_PASTA = "dataset/co2wounds-v2/imgs/IMG1000.jpg"
    PASTA_DE_SAIDA = "outputs"
    # ======================================================================
    
    # Se o usuario apenas clicou "Run" sem argumentos, abre janela para escolher a foto
    if len(sys.argv) == 1:
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw() # Oculta a janela principal
            root.attributes('-topmost', True) # Forca a janela a ficar na frente
            caminho_escolhido = filedialog.askopenfilename(
                title="HEAL+ | Selecione uma imagem de ferida para analisar",
                filetypes=[("Imagens", "*.jpg *.jpeg *.png *.webp *.tif *.tiff"), ("Todos", "*.*")]
            )
            if caminho_escolhido:
                CAMINHO_DA_IMAGEM_OU_PASTA = caminho_escolhido
        except Exception as e:
            logger.warning(f"Nao foi possivel abrir janela de selecao de arquivo: {e}")

    parser = argparse.ArgumentParser(description="HEAL+ / REDISUS Analisador de Feridas (Standalone)")
    parser.add_argument("--input", default=CAMINHO_DA_IMAGEM_OU_PASTA, help="Caminho para uma imagem ou pasta de imagens")
    parser.add_argument("--output", default=PASTA_DE_SAIDA, help="Pasta de destino para os resultados")
    parser.add_argument("--use-dl", action="store_true", help="Tentar usar o modelo Deep Learning opcional. Fara fallback automatico se falhar.")
    args = parser.parse_args()
    
    input_path = Path(args.input)
    output_path = Path(args.output)
    
    # Cria pasta de saída se nao existir
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Arquivo de log geral
    log_file = output_path / "processing_log.txt"
    file_handler = logging.FileHandler(str(log_file), encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    logging.getLogger().addHandler(file_handler)
    
    logger.info("="*50)
    logger.info("Iniciando HEAL+ Standalone Analyzer")
    logger.info("="*50)
    
    # Initialize Core Analyzer
    logger.info("Inicializando ClinicalWoundAnalyzer (Pipeline CV Explicável)...")
    analyzer = ClinicalWoundAnalyzer()
        
    if args.use_dl:
        # Checa se os modelos estao carregados
        if analyzer._dl_available or analyzer._resnet_available or analyzer._ensemble_available:
            logger.info("Modelos de Deep Learning carregados e ativos.")
        else:
            logger.warning("Pipeline DL indisponível. Usando pipeline explicável de visão computacional.")
            print("Pipeline DL indisponível. Usando pipeline explicável de visão computacional.")
    
    valid_exts = {'.jpg', '.jpeg', '.png', '.webp', '.tif', '.tiff'}
    files_to_process = []
    
    if input_path.is_file():
        if input_path.suffix.lower() in valid_exts:
            files_to_process.append(input_path)
        else:
            logger.error(f"Extensao de arquivo nao suportada: {input_path}")
            print(f"Extensao de arquivo nao suportada: {input_path}")
            return
    elif input_path.is_dir():
        for file in input_path.iterdir():
            if file.is_file() and file.suffix.lower() in valid_exts:
                files_to_process.append(file)
    else:
        logger.error(f"Caminho de entrada invalido: {input_path}")
        print(f"Caminho de entrada invalido: {input_path}")
        return
        
    if not files_to_process:
        logger.warning("Nenhuma imagem valida encontrada para processamento.")
        return

    csv_data_list = []
    
    for img_file in files_to_process:
        try:
            process_image(img_file, output_path, analyzer, csv_data_list)
        except Exception as e:
            error_msg = f"Erro ao processar imagem {img_file.name}: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            print(error_msg)
            
    # Salva CSV Consolidado
    csv_path = output_path / "resumo_resultados.csv"
    if csv_data_list:
        try:
            with open(csv_path, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "nome_arquivo", "ferida_valida", "tecido_predominante",
                    "percentual_granulacao", "percentual_necrose",
                    "percentual_esfacelo", "percentual_epitelizacao",
                    "area_estimada_pixels", "score_visual_tecidual", "tempo_processamento_ms", "observacoes_tecnicas"
                ], extrasaction='ignore')
                writer.writeheader()
                for row in csv_data_list:
                    writer.writerow(row)
            logger.info(f"Arquivo consolidado criado: {csv_path}")
            print(f"Arquivo consolidado criado: {csv_path}")
        except Exception as e:
            logger.error(f"Erro ao salvar CSV consolidado: {str(e)}")
            
    logger.info("Processamento finalizado.")

if __name__ == "__main__":
    main()
"""

def build():
    print(f"Building standalone model to {OUTPUT_FILE}")
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
        out.write(get_standard_imports())
        
        # Some global duplicated imports might need to be removed, but for now we rely on python ignoring duplicates
        
        for file_path in FILES_TO_MERGE:
            full_path = ROOT / file_path
            if not full_path.exists():
                print(f"Warning: File {file_path} not found. Skipping.")
                continue
                
            print(f"Merging {file_path}...")
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
                cleaned = clean_imports_and_headers(content)
                
                # Write a separator block
                out.write(f"\n# {'='*60}\n# Extracted from: {file_path}\n# {'='*60}\n\n")
                out.write(cleaned)
                out.write("\n")
                
        out.write(get_cli_main())
        
    print("Build successful.")

if __name__ == "__main__":
    build()
