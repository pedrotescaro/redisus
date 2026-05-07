# Experimentos de Pré-processamento com OpenCV para Análise de Feridas por IA

## 1. Objetivo

Este experimento implementa uma etapa controlada de pré-processamento de imagens com OpenCV antes da análise por IA do HEAL+ / REDISUS. O objetivo é observar, de forma empírica, se filtros passa-baixa e equalização de histograma alteram a detecção da ferida, a ROI, a segmentação tecidual, a classificação e demais saídas do analisador.

Esta etapa é experimental e não substitui o fluxo principal do sistema.

## 2. Justificativa

A professora Márcia orientou testar filtros antes da análise com IA para avaliar se a padronização visual da imagem pode influenciar os resultados. Em imagens clínicas, ruído, variação de iluminação, contraste baixo e textura da pele podem afetar a resposta de algoritmos de detecção, segmentação e classificação.

Filtros passa-baixa, como mediana e gaussiano, podem reduzir ruídos, mas também podem suavizar bordas e remover detalhes importantes da ferida. A equalização de histograma pode melhorar contraste, mas também pode intensificar artefatos. Por isso, nenhum filtro deve ser adotado como padrão antes de validação comparativa.

## 3. Biblioteca utilizada

O experimento usa OpenCV em Python:

```python
import cv2
```

Também são usados `numpy` e módulos da biblioteca padrão para manipulação de arquivos e geração de CSV. Quando `matplotlib` está instalado, ele é usado para gerar grades visuais; quando não está disponível, o script usa um fallback com OpenCV puro. O projeto já declara OpenCV em `requirements.txt` e `requirements-ci.txt`.

## 4. Filtros aplicados

As funções ficam em `src/processing/preprocessing_filters.py`.

- Mediana: `cv2.medianBlur()`.
- Gaussiano: `cv2.GaussianBlur()`.
- Equalização global em cinza: `cv2.equalizeHist()` após conversão BGR para escala de cinza.
- Equalização global colorida: equalização apenas do canal de luminância no espaço YCrCb.
- CLAHE colorido: equalização adaptativa no canal L do espaço LAB com `cv2.createCLAHE()`.
- Combinações: mediana + equalização, gaussiano + equalização, mediana + CLAHE e gaussiano + CLAHE.

Para imagens coloridas, a equalização é aplicada sobre luminância para reduzir distorção artificial das cores da ferida.

## 5. Metodologia dos testes

O script `scripts/run_preprocessing_experiments.py` recebe uma pasta de imagens, gera variantes processadas e executa o analisador clínico do projeto quando disponível.

Para cada imagem, são geradas as versões:

- `original`
- `median`
- `gaussian`
- `equalized_gray`
- `equalized_color`
- `clahe_color`
- `median_equalized`
- `gaussian_equalized`
- `median_clahe`
- `gaussian_clahe`

O pipeline principal não é alterado. A análise por IA é chamada apenas dentro do script experimental, para comparar a resposta do sistema frente a cada transformação.

## 6. Organização das imagens

Saída padrão:

```text
outputs/preprocessing_experiments/
  original/
  median/
  gaussian/
  equalized_gray/
  equalized_color/
  clahe_color/
  median_equalized/
  gaussian_equalized/
  median_clahe/
  gaussian_clahe/
  reports/
    preprocessing_results.csv
    comparison_grids/
```

As imagens originais de entrada não são sobrescritas.

## 7. Resultados esperados

O arquivo `preprocessing_results.csv` registra uma linha por imagem e por método. Campos mínimos:

- `image_name`
- `preprocessing_method`
- `image_resolution`
- `model_used`
- `confidence_score`
- `detected_area`
- `roi_count`
- `predicted_class`
- `processing_time_ms`
- `notes`

Quando uma métrica não existe no pipeline atual, o campo é preenchido como `not_available`. Isso evita inventar confiança, área, classe ou qualquer resultado não produzido pelo analisador.

## 8. Como interpretar os resultados

A comparação deve observar se cada filtro melhora, piora ou mantém:

- detecção da ferida;
- ROI gerada;
- segmentação;
- classificação de tecido;
- classificação de estágio, se disponível;
- área detectada;
- confiança, se o modelo fornecer;
- presença de falsos positivos visuais;
- perda de bordas ou detalhes finos.

Diferenças entre métodos devem ser interpretadas com cautela. Um filtro pode melhorar contraste visual e, ao mesmo tempo, prejudicar a cor ou a textura usada pela IA.

## 9. Limitações

Este experimento não comprova melhoria clínica. Ele apenas permite comparar a influência de pré-processamentos sobre o pipeline atual.

Limitações principais:

- ausência de validação clínica formal;
- dependência da qualidade e origem das imagens de teste;
- risco de alteração de cores clinicamente relevantes;
- métricas ausentes quando o pipeline não fornece confiança ou classe específica;
- impossibilidade de generalizar resultados a pacientes reais sem CEP/CONEP, TCLE e governança LGPD.

## 10. Próximos passos

- Rodar o script em subconjuntos controlados de imagens públicas licenciadas.
- Comparar visualmente as grades geradas.
- Discutir os resultados com orientação/professor e profissionais da saúde.
- Definir, se houver evidência, qual filtro merece estudo mais amplo.
- Manter o pré-processamento como opcional até validação técnica e clínica.

## Como executar

Instalar dependências, se necessário:

```powershell
pip install opencv-python numpy matplotlib
```

Executar com uma pasta de imagens:

```powershell
python scripts/run_preprocessing_experiments.py `
  --input examples `
  --output outputs/preprocessing_experiments
```

Para uma execução rápida sem IA:

```powershell
python scripts/run_preprocessing_experiments.py `
  --input examples `
  --output outputs/preprocessing_experiments `
  --skip-ai
```

Para limitar a quantidade de imagens:

```powershell
python scripts/run_preprocessing_experiments.py `
  --input dataset/piid/raw `
  --output outputs/preprocessing_experiments `
  --max-images 5
```

Não usar imagens reais de pacientes sem aprovação ética, TCLE e plano de proteção de dados.
