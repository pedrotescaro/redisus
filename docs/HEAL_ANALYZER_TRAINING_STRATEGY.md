# HEAL Analyzer Training Strategy

## Problema atual

O HEAL Analyzer nao deve tratar qualquer imagem como imagem de ferida. O risco observado vem de uma falha arquitetural comum: usar segmentacao/heuristica visual generica e depois traduzir cores de pele, roupa, fundo, rosto ou objetos em termos clinicos como se fossem tecido de ferida.

No estado atual do projeto, a interface web carrega imagem e ROI no `AnalyzerWorkbench`, usa o canvas `WoundRoiCanvas`, salva ROI no Firestore e chama um servico assistivo. O backend legado possui analisadores de cor/forma e modelos/fallbacks, mas a classificacao tecidual pode cair em heuristicas. Portanto, ate existir modelo treinado e validado especificamente para feridas, o frontend deve bloquear classificacao tecidual e exibir analise limitada.

## Por que o modelo errava

- A ROI manual era usada como mascara de area analisavel, mas nao como prova de que havia ferida.
- Tons de roupa, fundo, pele integra, sombra, cabelo, campo cirurgico e objetos podiam acionar faixas de cor parecidas com classes teciduais.
- A segmentacao por cor/HSV nao distingue semanticamente "ferida" de "objeto colorido".
- Resultado de fallback ou heuristica era apresentado com linguagem clinica forte demais.
- Nao havia gate obrigatorio para imagem/ROI invalida antes da classificacao.

## Segmentacao generica vs segmentacao de feridas

Segmentacao generica encontra objetos, pessoas, pele, roupas ou regioes salientes. Segmentacao de feridas precisa aprender o limite anatomico-clinico da lesao e separar leito de ferida, pele perilesional, fundo e artefatos. Um modelo treinado em pessoas ou objetos nao deve ser usado para inferir tecido de ferida.

## Arquitetura segura

Ordem obrigatoria:

1. Carregar imagem clinica.
2. Criar/carregar ROI manual normalizada entre 0 e 1.
3. Recortar a imagem pela ROI, independente do tamanho renderizado na tela.
4. Validar qualidade da imagem.
5. Validar se a ROI contem evidencia visual suficiente de ferida.
6. Detectar ferida no recorte.
7. Segmentar ferida vs fundo.
8. Classificar tecido somente se houver modelo treinado/validado e confianca suficiente.
9. Gerar contexto clinico assistivo, sem diagnostico definitivo.

Thresholds iniciais:

- `woundLikelihood < 0.60`: bloquear analise visual.
- `segmentation.confidence < 0.70`: mostrar analise limitada.
- ROI ausente: bloquear analise visual.
- ROI muito pequena ou grande: pedir nova marcacao.
- Imagem ruim: permitir apenas analise limitada.
- Fallback, mock ou heuristica: nao exibir classificacao tecidual.

## Datasets publicos avaliados

| Dataset | Uso recomendado | Licenca/termos | Observacao |
| --- | --- | --- | --- |
| FUSeg - Foot Ulcer Segmentation Challenge | Segmentacao de ulcera de pe, ferida vs fundo | Acesso via Grand Challenge/GitHub; verificar termos antes de uso comercial | O desafio informa imagens desidentificadas e objetivo de segmentar feridas em fotos clinicas. A publicacao descreve 1.210 imagens e mascaras pixel-a-pixel. Fontes: [Grand Challenge](https://fusc.grand-challenge.org/FUSeg-2021/), [MDPI](https://www.mdpi.com/2078-2489/15/3/140). |
| AZH Wound Dataset / UWM wound-segmentation | Segmentacao inicial de feridas/ulceras | Publicado em GitHub com permissao da clinica; checar ausencia/presenca de arquivo LICENSE antes de uso comercial | Dataset anotado por profissionais, ligado ao trabalho de segmentacao de feridas da UWM. Fonte: [uwm-bigdata/wound-segmentation](https://github.com/uwm-bigdata/wound-segmentation). |
| WoundDB / Chronic Wounds Multimodal Image Database | Avaliacao multimodal, contornos manuais, validacao externa | CC BY 4.0 segundo os termos oficiais | Inclui fotos RGB, termicas, 3D/profundidade e contornos manuais. Fontes: [WoundDB](https://chronicwounddatabase.eu/), [Terms](https://chronicwounddatabase.eu/Terms). |
| CO2Wounds-V2 | Pesquisa/educacao em segmentacao de feridas cronicas | Licenca depende da fonte/versao: Kaggle lista CC BY-NC 3.0; Mendeley v1 lista CC BY 4.0; paper/dataset v2 menciona restricoes NC/ND em algumas fontes | Nao usar comercialmente ate resolver a licenca da versao exata e obter autorizacao quando necessario. Fontes: [Kaggle](https://www.kaggle.com/datasets/orvile/leprosy-chronic-wound-images-co2wounds-v2), [Mendeley](https://data.mendeley.com/datasets/s2w7rjwz49/1). |
| PIID - Pressure Injury Images Dataset | Classificacao de estagios de lesao por pressao | Repositorio publico; licenca explicita nao evidente no README | 1.091 imagens RGB 299x299, estagios 1 a 4. Nao usar como dataset principal de segmentacao sem mascaras. Fonte: [GitHub PIID](https://github.com/FU-MedicalAI/PIID). |
| Medetec Wound Database | Material complementar/validacao visual | Verificar termos no site antes de treino ou redistribuicao | Base pequena, qualidade variavel, nem sempre com mascaras; boa para teste externo, nao para treino principal sem revisao. Fonte: [Medetec](https://www.medetec.co.uk/files/medetec-image-databases.html). |
| WoundSeg | Segmentacao diversa de tipos de ferida | Paper WACV; confirmar disponibilidade e termos do dataset antes de uso | Dataset de 8 tipos de ferida proposto no WSNet; bom alvo futuro se acesso/licenca forem claros. Fonte: [WACV/CVF](https://openaccess.thecvf.com/content/WACV2023/html/Oota_WSNet_Towards_an_Effective_Method_for_Wound_Image_Segmentation_WACV_2023_paper.html). |

## Estrategia de treinamento

Fase 1: segmentacao ferida vs fundo.

- Comecar com U-Net com encoder pre-treinado, DeepLabV3+ e SegFormer leve.
- Treinar com FUSeg/AZH/WoundDB quando a licenca permitir.
- Separar treino, validacao, teste interno e teste externo por paciente/fonte quando possivel.
- Usar augmentations clinicamente plausiveis: iluminacao, contraste, rotacao leve, blur moderado, compressao JPEG.
- Evitar augmentations que criem tecido falso ou alterem cor clinica de modo irreal.

Fase 2: validador de entrada.

- Treinar classificador binario/multiclasse: `wound_roi`, `intact_skin`, `face/person`, `clothing`, `background/object`, `instrument/gauze`.
- Usar negativos internos revisados e datasets publicos licenciados para negativos nao clinicos quando permitido.
- Otimizar falso positivo baixo em imagens sem ferida.

Fase 3: classificacao tecidual.

- So iniciar depois que segmentacao da area de ferida for confiavel.
- Exigir rotulos de tecido pixel-a-pixel ou patches revisados por especialista.
- Classes iniciais: `granulation`, `slough_fibrin`, `necrosis`, `epithelial`, `unknown`.
- Incluir `unknown` para baixa confianca.

Fase 4: contexto clinico.

- Integrar dor, exsudato, etiologia, localizacao, bordas, pele perilesional e historico.
- Produzir alertas assistivos, nunca diagnostico definitivo.

## Metricas obrigatorias

Segmentacao:

- Dice coefficient.
- IoU/Jaccard.
- Precision.
- Recall.
- F1-score.
- False Positive Rate.
- False Negative Rate.

Validacao assistiva:

- Taxa de imagens bloqueadas corretamente.
- Taxa de falso positivo em imagem sem ferida.
- Taxa de ROI invalida detectada.
- Confianca media por classe.
- Calibracao: ECE/Brier score quando houver probabilidades.

## LGPD, etica e seguranca

- Feridas e dados clinicos sao dados pessoais sensiveis.
- Usar minimizacao: nao exportar nome, telefone, e-mail, CPF, endereco, data real ou metadados EXIF identificaveis.
- Exportar apenas dados autorizados por consentimento/base legal e aprovacao institucional.
- Separar imagem clinica de identificadores em armazenamento.
- Exigir revisao profissional para rotulos internos.
- Registrar versao de dataset, modelo, thresholds e responsavel pela revisao.
- Permitir retirada de consentimento quando aplicavel.

## ROIs manuais como dataset futuro

Formato recomendado:

```json
{
  "id": "roi-uuid",
  "patientId": "patient-id",
  "assessmentId": "assessment-id",
  "imageId": "image-id",
  "roiPoints": [{ "x": 0.31, "y": 0.42 }],
  "normalized": true,
  "label": "wound_area",
  "verifiedByProfessional": false,
  "createdAt": "2026-05-07T00:00:00.000Z",
  "createdBy": "uid",
  "consentForResearch": false,
  "anonymizedExportReady": false
}
```

Nao exportar se:

- nao houver consentimento/autorizacao;
- houver rosto, documento, tatuagem identificavel, cracha, nome ou metadados sensiveis;
- nao houver revisao profissional;
- a ROI pegar roupa, fundo, instrumentos ou pele saudavel predominante;
- o caso nao estiver anonimizado.

Exportacao futura:

- imagem anonimizada;
- mascara binaria gerada da ROI;
- metadados clinicos minimos;
- tipo de ferida e regiao anatomica quando revisados;
- data relativa, nao data real;
- nenhum dado identificavel.

## Criterio de liberacao

O HEAL Analyzer so deve exibir classificacao tecidual quando:

- ha ROI valida;
- a imagem passa por qualidade minima;
- o validador indica ferida com `woundLikelihood >= 0.60`;
- o modelo de segmentacao validado atinge confianca adequada;
- o modelo de tecido esta treinado, versionado, testado em dados externos e habilitado;
- o resultado inclui disclaimer assistivo e exige validacao profissional.

Sem isso, mostrar apenas:

> A imagem analisada nao apresenta evidencia visual suficiente de ferida na ROI marcada. Para evitar resultado incorreto, o sistema nao gerou classificacao de tecido.
