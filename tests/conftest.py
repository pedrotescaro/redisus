"""
HEAL/REDISUS — Fixtures compartilhados para testes unitários.
"""
import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Imagens sintéticas
# ---------------------------------------------------------------------------

@pytest.fixture
def black_frame():
    """Frame 480x640 totalmente preto (BGR)."""
    return np.zeros((480, 640, 3), dtype=np.uint8)


@pytest.fixture
def white_frame():
    """Frame 480x640 totalmente branco (BGR)."""
    return np.ones((480, 640, 3), dtype=np.uint8) * 255


@pytest.fixture
def red_wound_frame():
    """
    Frame com um 'wound' vermelho (granulação) no centro.
    Fundo bege (pele), círculo vermelho ~100px raio.
    """
    frame = np.full((480, 640, 3), (180, 200, 220), dtype=np.uint8)  # pele BGR
    # Desenha círculo vermelho (BGR: 0, 0, 200)
    import cv2
    cv2.circle(frame, (320, 240), 100, (0, 0, 200), -1)
    return frame


@pytest.fixture
def dark_necrosis_frame():
    """
    Frame com região escura (necrose) no centro.
    Fundo bege, círculo preto/marrom ~80px raio.
    """
    frame = np.full((480, 640, 3), (180, 200, 220), dtype=np.uint8)
    import cv2
    cv2.circle(frame, (320, 240), 80, (20, 20, 30), -1)
    return frame


@pytest.fixture
def yellow_slough_frame():
    """
    Frame com tecido amarelo (esfacelo) no centro.
    """
    frame = np.full((480, 640, 3), (180, 200, 220), dtype=np.uint8)
    import cv2
    cv2.circle(frame, (320, 240), 90, (80, 220, 220), -1)  # amarelo BGR
    return frame


@pytest.fixture
def wound_mask_center():
    """Máscara binária com círculo central (255) ~ raio 100."""
    import cv2
    mask = np.zeros((480, 640), dtype=np.uint8)
    cv2.circle(mask, (320, 240), 100, 255, -1)
    return mask


@pytest.fixture
def small_rgb_image():
    """Imagem 64x64 RGB aleatória (para testes leves)."""
    rng = np.random.default_rng(42)
    return rng.integers(0, 255, (64, 64, 3), dtype=np.uint8)


# ---------------------------------------------------------------------------
# Dados de paciente / ferida para testes
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_tissue_percentages():
    """Porcentagens de tecido típicas para ferida venosa em cicatrização."""
    return {
        "Granulação": 55.0,
        "Esfacelo": 20.0,
        "Necrose": 5.0,
        "Pele Perilesional": 15.0,
        "Background": 5.0,
    }


@pytest.fixture
def high_necrosis_tissue():
    """Porcentagens com necrose dominante."""
    return {
        "Granulação": 10.0,
        "Esfacelo": 15.0,
        "Necrose": 55.0,
        "Pele Perilesional": 15.0,
        "Background": 5.0,
    }


@pytest.fixture
def sample_wound_data():
    """Dados de ferida para teste de risk scoring."""
    return {
        "area_cm2": 25.0,
        "tissue_percentages": {
            "Necrose": 15.0,
            "Esfacelo": 20.0,
            "Granulação": 40.0,
        },
        "wound_age_days": 60,
        "infection_signs": False,
    }


@pytest.fixture
def sample_patient_data():
    """Dados do paciente para teste de risk scoring."""
    return {
        "age": 72,
        "smoking": False,
        "treatment_adherence": 0.85,
        "comorbidities": {
            "diabetes": True,
            "venous_insufficiency": True,
            "arterial_disease": False,
            "immobility": False,
            "malnutrition": False,
            "immunosuppression": False,
        },
    }
