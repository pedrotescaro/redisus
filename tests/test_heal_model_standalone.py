import os
import json
import csv
import subprocess
import cv2
import numpy as np
import pytest
from pathlib import Path

# Constantes
SCRIPT_NAME = "heal_model_standalone.py"

@pytest.fixture
def temp_dir(tmp_path):
    """Retorna um diretorio temporario para os testes."""
    return tmp_path

def create_synthetic_wound(path: Path):
    """Cria uma imagem de ferida sintética e salva no caminho."""
    img = np.zeros((400, 400, 3), dtype=np.uint8)
    
    # Fundo (Pele saudavel)
    img[:] = (160, 190, 230) # BGR
    
    # Area de ferida principal (Esfacelo - Amarelado)
    cv2.circle(img, (200, 200), 100, (140, 200, 220), -1)
    
    # Necrose (Preto/Marrom escuro)
    cv2.circle(img, (180, 180), 30, (20, 30, 40), -1)
    
    # Granulacao (Vermelho)
    cv2.circle(img, (240, 220), 40, (40, 40, 180), -1)
    
    # Epitelizacao (Rosa/Esbranquicado nas bordas)
    cv2.circle(img, (130, 250), 20, (180, 180, 230), -1)
    
    cv2.imwrite(str(path), img)
    return path

def test_1_valid_image_execution(temp_dir):
    """Valida se o script roda corretamente com uma imagem valida sintetica."""
    img_path = temp_dir / "test_wound.jpg"
    out_dir = temp_dir / "outputs"
    create_synthetic_wound(img_path)
    
    cmd = [
        "python", SCRIPT_NAME,
        "--input", str(img_path),
        "--output", str(out_dir)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    assert result.returncode == 0, f"Script falhou: {result.stderr}"
    assert out_dir.exists()
    
    # Verifica arquivos gerados
    assert (out_dir / "test_wound_report.json").exists()
    assert (out_dir / "resumo_resultados.csv").exists()
    assert (out_dir / "test_wound_roi_mask.png").exists()
    assert (out_dir / "test_wound_tissue_map.png").exists()
    assert (out_dir / "test_wound_overlay.jpg").exists()

def test_2_multiple_images_execution(temp_dir):
    """Valida se o script roda com uma pasta cheia de imagens e salva varias linhas no CSV."""
    in_dir = temp_dir / "inputs"
    out_dir = temp_dir / "outputs"
    in_dir.mkdir()
    
    # Cria 3 imagens
    for i in range(3):
        create_synthetic_wound(in_dir / f"wound_{i}.jpg")
        
    cmd = [
        "python", SCRIPT_NAME,
        "--input", str(in_dir),
        "--output", str(out_dir)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0
    
    csv_path = out_dir / "resumo_resultados.csv"
    assert csv_path.exists()
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        
    assert len(rows) == 3, f"Esperado 3 imagens no CSV, encontrou {len(rows)}"
    
    for i in range(3):
        assert (out_dir / f"wound_{i}_report.json").exists()

def test_3_invalid_image(temp_dir):
    """Testa uma imagem invalida."""
    invalid_path = temp_dir / "invalid.jpg"
    with open(invalid_path, 'w') as f:
        f.write("Isto nao e uma imagem valida")
        
    out_dir = temp_dir / "outputs"
    
    cmd = [
        "python", SCRIPT_NAME,
        "--input", str(invalid_path),
        "--output", str(out_dir)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0 # Nao deve travar
    
    log_path = out_dir / "processing_log.txt"
    assert log_path.exists()
    with open(log_path, 'r') as f:
        log_content = f.read()
    
    assert "Erro ao processar imagem" in log_content

def test_4_nonexistent_input(temp_dir):
    """Testa caminho inexistente."""
    out_dir = temp_dir / "outputs"
    cmd = [
        "python", SCRIPT_NAME,
        "--input", str(temp_dir / "does_not_exist.jpg"),
        "--output", str(out_dir)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0 # O parser vai capturar, ou vai cair no else de path
    assert "Caminho de entrada invalido" in result.stdout or "Extensao de arquivo nao suportada" in result.stdout

def test_5_use_dl_fallback(temp_dir):
    """Testa o fallback do parametro --use-dl."""
    img_path = temp_dir / "wound_dl.jpg"
    out_dir = temp_dir / "outputs_dl"
    create_synthetic_wound(img_path)
    
    cmd = [
        "python", SCRIPT_NAME,
        "--input", str(img_path),
        "--output", str(out_dir),
        "--use-dl"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0
    assert "Pipeline DL indisponível. Usando pipeline explicável de visão computacional." in result.stdout
    assert (out_dir / "wound_dl_report.json").exists()

def test_6_mandatory_json_fields(temp_dir):
    """Verifica se todos os campos mandatorios estao presentes no JSON."""
    img_path = temp_dir / "wound_json.jpg"
    out_dir = temp_dir / "outputs_json"
    create_synthetic_wound(img_path)
    
    subprocess.run(["python", SCRIPT_NAME, "--input", str(img_path), "--output", str(out_dir)])
    
    json_path = out_dir / "wound_json_report.json"
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    mandatory_fields = [
        "nome_arquivo", "ferida_valida", "percentual_granulacao", "percentual_necrose",
        "percentual_esfacelo", "percentual_epitelizacao", "tecido_predominante",
        "area_estimada_pixels", "score_visual_tecidual", "observacoes_tecnicas",
        "tempo_processamento_ms", "caminhos_arquivos_gerados", "aviso_clinico"
    ]
    
    for field in mandatory_fields:
        assert field in data, f"Campo mandatorio ausente: {field}"

def test_7_mandatory_csv_columns(temp_dir):
    """Verifica colunas mandatorias no CSV."""
    img_path = temp_dir / "wound_csv.jpg"
    out_dir = temp_dir / "outputs_csv"
    create_synthetic_wound(img_path)
    
    subprocess.run(["python", SCRIPT_NAME, "--input", str(img_path), "--output", str(out_dir)])
    
    csv_path = out_dir / "resumo_resultados.csv"
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        headers = next(reader)
        
    mandatory_columns = [
        "nome_arquivo", "ferida_valida", "tecido_predominante", "percentual_granulacao",
        "percentual_necrose", "percentual_esfacelo", "percentual_epitelizacao",
        "area_estimada_pixels", "score_visual_tecidual", "tempo_processamento_ms"
    ]
    
    for col in mandatory_columns:
        assert col in headers, f"Coluna mandatoria ausente no CSV: {col}"

def test_8_clinical_warning(temp_dir):
    """Verifica aviso clinico e etico no JSON."""
    img_path = temp_dir / "wound_warning.jpg"
    out_dir = temp_dir / "outputs_warning"
    create_synthetic_wound(img_path)
    
    subprocess.run(["python", SCRIPT_NAME, "--input", str(img_path), "--output", str(out_dir)])
    
    json_path = out_dir / "wound_warning_report.json"
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    aviso = data["aviso_clinico"].lower()
    assert "não substitui avaliação clínica" in aviso or "não substitui" in aviso or "experimental" in aviso

def test_9_percentages_validation(temp_dir):
    """Testa se as porcentagens estao no intervalo [0, 100] e nao sao None."""
    img_path = temp_dir / "wound_pct.jpg"
    out_dir = temp_dir / "outputs_pct"
    create_synthetic_wound(img_path)
    
    subprocess.run(["python", SCRIPT_NAME, "--input", str(img_path), "--output", str(out_dir)])
    
    json_path = out_dir / "wound_pct_report.json"
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    for p_key in ["percentual_granulacao", "percentual_necrose", "percentual_esfacelo", "percentual_epitelizacao"]:
        val = data[p_key]
        assert isinstance(val, (int, float))
        assert 0.0 <= val <= 100.0

def test_10_cli_compatibility():
    """Valida argumentos obrigatorios da CLI."""
    cmd = ["python", SCRIPT_NAME, "--help"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0
    
    assert "--input" in result.stdout
    assert "--output" in result.stdout
    assert "--use-dl" in result.stdout
