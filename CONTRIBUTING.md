# Guia de Contribuição — HEAL+ / REDISUS

Obrigado pelo interesse em contribuir com o **HEAL+/REDISUS**! Este documento descreve como colaborar com o projeto de forma organizada, segura e reprodutível.

---

## Índice

1. [Código de Conduta](#1-código-de-conduta)
2. [Pré-requisitos](#2-pré-requisitos)
3. [Configuração do Ambiente de Desenvolvimento](#3-configuração-do-ambiente-de-desenvolvimento)
4. [Fluxo de Trabalho (Git)](#4-fluxo-de-trabalho-git)
5. [Padrões de Código](#5-padrões-de-código)
6. [Convenções de Commit](#6-convenções-de-commit)
7. [Testes](#7-testes)
8. [Contribuições com Modelos e Dados](#8-contribuições-com-modelos-e-dados)
9. [Diretrizes Clínicas e Éticas](#9-diretrizes-clínicas-e-éticas)
10. [Estrutura de Módulos](#10-estrutura-de-módulos)
11. [Reportando Bugs e Sugerindo Features](#11-reportando-bugs-e-sugerindo-features)

---

## 1. Código de Conduta

- Trate todos os colaboradores com respeito e profissionalismo.
- Este é um projeto de **pesquisa em saúde** — decisões técnicas devem priorizar **segurança do paciente** e **reprodutibilidade científica** acima de conveniência de implementação.
- Dados de pacientes **nunca** devem ser incluídos no repositório, mesmo anonimizados — siga a LGPD (Lei Geral de Proteção de Dados) e as orientações do CEP (Comitê de Ética em Pesquisa).

---

## 2. Pré-requisitos

| Ferramenta | Versão Mínima | Notas |
|------------|---------------|-------|
| Python | 3.10+ | Recomendado: 3.11 |
| Git | 2.30+ | — |
| CUDA (opcional) | 11.8+ | Para treinamento com GPU NVIDIA |
| pip | 23.0+ | — |

---

## 3. Configuração do Ambiente de Desenvolvimento

```bash
# 1. Fork e clone
git clone https://github.com/SEU_USUARIO/redisus.git
cd redisus

# 2. Criar ambiente virtual
python -m venv .venv

# 3. Ativar
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Linux/macOS:
source .venv/bin/activate

# 4. Instalar dependências
pip install -r requirements.txt

# 5. Verificar instalação
pytest --co -q  # Lista os testes sem executar
```

### Verificação rápida

```bash
# Verificar que os módulos core importam corretamente
python -c "from src.core.config import config; print('Config OK:', config)"
python -c "from src.processing.tissue_analyzer import TissueAnalyzerCV; print('Tissue OK')"
```

---

## 4. Fluxo de Trabalho (Git)

Usamos o modelo **GitHub Flow** (simplificado):

```
main ─────────────────────────────────────────► (produção)
  │
  ├── feature/nome-da-feature ──► PR → Review → Merge
  ├── fix/descricao-do-bug ─────► PR → Review → Merge
  └── research/hipotese-xyz ────► PR → Review → Merge
```

### Passos

1. **Crie uma branch** a partir de `main`:
   ```bash
   git checkout -b feature/minha-contribuicao
   ```

2. **Faça commits atômicos** (veja Seção 6).

3. **Execute os testes** antes de abrir PR:
   ```bash
   pytest
   ```

4. **Abra um Pull Request** com:
   - Descrição clara do que foi alterado e **por quê**.
   - Referência à *issue* relacionada (se existir).
   - Screenshots ou métricas, se aplicável.

5. **Aguarde review** — pelo menos 1 aprovação é necessária.

### Branches protegidas

- `main`: Apenas via PR com *review* aprovado.

---

## 5. Padrões de Código

### Python

- **Style**: PEP 8.
- **Docstrings**: Google style, em português ou inglês (manter consistência dentro do módulo).
- **Type hints**: Obrigatórios em todas as funções públicas.
- **Imports**: Agrupados na ordem: stdlib → third-party → local.
- **Encoding**: UTF-8. Usar `text_renderer.py` para exibir texto em imagens (não `cv2.putText` para caracteres acentuados).

```python
def analyze_tissue(image: np.ndarray, mask: Optional[np.ndarray] = None) -> TissueResult:
    """
    Analisa composição tecidual da ferida.

    Args:
        image: Imagem BGR da ferida.
        mask: Máscara binária da ROI (opcional).

    Returns:
        TissueResult com percentuais por classe.
    """
```

### Nomes de variáveis e constantes

| Tipo | Convenção | Exemplo |
|------|-----------|---------|
| Classe | PascalCase | `WoundDetectorCV` |
| Função/método | snake_case | `detect_wound_bbox()` |
| Constante | UPPER_SNAKE_CASE | `TISSUE_HSV_RANGES` |
| Módulo | snake_case | `wound_detector_cv.py` |
| Branch | kebab-case com prefixo | `feature/grad-cam-overlay` |

---

## 6. Convenções de Commit

Usamos [Conventional Commits](https://www.conventionalcommits.org/):

```
<tipo>(<escopo>): <descrição curta>

[corpo opcional — explique o porquê]

[rodapé opcional — refs, breaking changes]
```

### Tipos

| Tipo | Uso |
|------|-----|
| `feat` | Nova funcionalidade |
| `fix` | Correção de bug |
| `docs` | Documentação |
| `refactor` | Refatoração sem mudança de comportamento |
| `test` | Adição ou correção de testes |
| `perf` | Melhoria de performance |
| `data` | Alterações em datasets, scraping, augmentação |
| `model` | Treinamento, exportação ou atualização de modelo |
| `clinical` | Alterações em escalas clínicas, protocolos, RAG |

### Exemplos

```
feat(detection): adicionar suporte a TFLite no realtime_detector

fix(tissue): corrigir range HSV de necrose para excluir campo cirúrgico azul

model(resnet50): retreinar estágio 2 com dataset medetec+fuseg

docs(readme): atualizar seção de métricas com resultados do benchmark

clinical(rag): adicionar protocolo de úlcera venosa (Cochrane 2012)
```

---

## 7. Testes

### Executar a suite completa

```bash
# Todos os testes
pytest

# Com cobertura
pytest --cov=src --cov-report=html

# Apenas um módulo específico
pytest tests/test_tissue_analyzer.py -v

# Apenas testes marcados como "rápidos"
pytest -m "not slow"
```

### Escrevendo testes

- Testes ficam em `tests/`.
- Nome do arquivo: `test_<modulo>.py`.
- Use `conftest.py` para fixtures compartilhadas.
- Testes de modelos DL devem ter a marca `@pytest.mark.slow` e verificar disponibilidade do modelo:

```python
import pytest

@pytest.mark.slow
def test_resnet50_inference():
    """Testa inferência do ResNet50 two-stage."""
    model_path = Path("models/wound_classifier/resnet50_stage1.pth")
    if not model_path.exists():
        pytest.skip("Modelo ResNet50 não disponível")
    # ...
```

### O que testar

| Módulo | O que testar | Prioridade |
|--------|-------------|------------|
| `processing/` | Ranges HSV, detecção de contorno, filtro de FP | Alta |
| `clinical/` | Cálculos de escalas (PUSH, Braden), intervalos de risco | Alta |
| `diagnosis/` | Formato de saída, serialização, fallbacks | Média |
| `detection/` | Formato de Detection, preprocessamento, fallback OpenCV | Média |
| `interoperability/` | Serialização FHIR, códigos SNOMED/LOINC/ICD-10 | Média |

---

## 8. Contribuições com Modelos e Dados

### Adicionando um novo dataset

1. Registre no `DATASETS_REGISTRY` em `src/training/prepare_wound_datasets.py`.
2. Documente a **fonte** (URL, paper, licença).
3. Padronize para o formato esperado (imagens + máscaras ou labels).
4. **Nunca** commite imagens no repositório — apenas scripts de download.
5. Atualize a seção "Rastreabilidade do Dataset" no README.

### Treinando ou atualizando um modelo

1. Documente os hiperparâmetros no commit.
2. Reporte métricas (Dice, IoU, F1, Accuracy) no PR.
3. Exporte para ONNX se possível.
4. Modelos treinados (`*.pth`, `*.onnx`) devem ser versionados via Git LFS ou hospedados externamente (nunca no repositório diretamente se > 50 MB).

### Data augmentation

- Siga as diretrizes de `scripts/medical_augmentation.py`.
- **Proibido**: Hue shift > ±5, RandomErasing, Cutout, MixUp forte.
- **Seguro**: Flips, rotação ±15°, zoom ±10%, ruído gaussiano leve, CLAHE.
- Sempre aplique augmentação apenas no **treino**, nunca na validação.

---

## 9. Diretrizes Clínicas e Éticas

Este não é um software comum — é uma ferramenta de **apoio ao diagnóstico clínico**. Contribuições que impactam a lógica de análise devem seguir:

### Requisitos obrigatórios

- [ ] **Não alterar ranges HSV clínicos** sem justificativa documentada (referência bibliográfica ou validação empírica com > 50 imagens).
- [ ] **Não remover filtros de falsos positivos** — eles existem para evitar diagnósticos incorretos.
- [ ] **Não modificar escalas clínicas** (PUSH, BWAT, Braden) — são instrumentos validados internacionalmente.
- [ ] **Incluir flags de review** (`needs_review=True`) quando a confiança do modelo for baixa (< 0.6).
- [ ] **Nunca** afirmar que o sistema substitui o profissional de saúde — sempre "auxílio ao diagnóstico".

### Dados de pacientes

- **Proibido** incluir imagens de pacientes reais no repositório.
- Use apenas datasets públicos com licença compatível.
- Se coletar dados em ambiente clínico, obtenha aprovação do CEP **antes** de iniciar.
- Siga a LGPD na manipulação de dados sensíveis.

### Níveis de evidência

Ao adicionar protocolos ao RAG (`src/rag/clinical_rag.py`), classifique a evidência segundo Oxford CEBM:

| Nível | Tipo de Estudo |
|-------|----------------|
| 1A | Revisão sistemática de RCTs |
| 1B | RCT individual |
| 2A–2B | Estudos de coorte |
| 3–4 | Séries/relatos de caso |
| 5 | Opinião de especialista |

---

## 10. Estrutura de Módulos

Ao criar novos módulos, siga a organização por camadas:

```
src/
├── ai_layer/        # Modelos de IA avançados (ensemble, zero-shot)
├── capture/         # Captura de vídeo/imagem
├── clinical/        # Escalas e instrumentos clínicos validados
├── core/            # Configurações e constantes
├── data/            # Persistência (SQLite, cache, exportação)
├── detection/       # Detecção em tempo real
├── diagnosis/       # Análise integrada
├── digital_twin/    # Gêmeo digital do paciente
├── interoperability/ # FHIR, DATASUS, e-SUS
├── monitoring/      # Monitoramento contínuo
├── patient/         # Gestão do paciente
├── presentation/    # UI e visualização
├── processing/      # Pipeline de processamento de imagem
├── rag/             # Base de conhecimento clínico
├── risk/            # Estratificação de risco
├── surveillance/    # Vigilância epidemiológica
├── training/        # Scripts de treinamento
├── treatment/       # Recomendação de tratamento
├── utils/           # Utilitários genéricos
└── validation/      # Framework de validação
```

### Regras

- Cada módulo tem seu `__init__.py` com exports explícitos.
- Dependências entre módulos devem ser **unidirecionais** (camada superior importa da inferior, nunca o contrário).
- Use `_safe_import()` para dependências opcionais (modelos pesados que podem não estar instalados).
- Fallbacks são obrigatórios para módulos de IA: se o modelo DL não carregar, use OpenCV como fallback.

---

## 11. Reportando Bugs e Sugerindo Features

### Bug Report

Ao abrir uma *issue* de bug, inclua:

1. **Descrição**: O que aconteceu vs. o que era esperado.
2. **Passos para reproduzir**: Comandos exatos.
3. **Ambiente**: SO, versão do Python, GPU (se aplicável).
4. **Logs**: Saída do terminal ou arquivo de log (`logs/`).
5. **Imagem de entrada** (se possível): Use uma imagem do Medetec como referência.

### Feature Request

1. **Motivação**: Por que essa feature é necessária? (Problema clínico, gap técnico, requisito de IC?)
2. **Proposta**: Descrição técnica da solução.
3. **Impacto**: Quais módulos são afetados?
4. **Métricas**: Como medir se a feature teve sucesso?

### Labels sugeridas

| Label | Descrição |
|-------|-----------|
| `bug` | Comportamento incorreto |
| `feature` | Nova funcionalidade |
| `clinical` | Impacta lógica clínica (requer revisão extra) |
| `model` | Treinamento / inferência de modelos |
| `docs` | Documentação |
| `research` | Exploração / hipótese de pesquisa |
| `good-first-issue` | Adequada para novos contribuidores |

---

## Dúvidas?

Abra uma *issue* com a label `question` ou entre em contato com os mantenedores do projeto.

---

<p align="center">
  <strong>HEAL+ / REDISUS</strong> — Cluster REDISUS — RNP/RUTE<br>
  Contribuições são bem-vindas!
</p>
