# HEAL Analyzer AI Strategy

## Objetivo

Evoluir o HEAL Analyzer de uma leitura isolada de imagem para uma camada assistiva longitudinal, usando imagem da ferida, ROI manual, dados clinicos estruturados da avaliacao, dados minimos do paciente e historico evolutivo.

O resultado deve apoiar o profissional de saude. Ele nao deve produzir diagnostico definitivo, indicar tratamento automatico ou substituir exame fisico, protocolos institucionais e julgamento clinico.

## Dados Usados

- Imagem original da ferida armazenada no Firebase Storage.
- ROI manual normalizada entre 0 e 1.
- Metadados da imagem e qualidade fotografica.
- Dados estruturados da avaliacao: regiao, tipo de lesao, dor, exsudato, bordas, pele ao redor, sinais marcados, TIMERS e observacoes.
- Historico anterior do mesmo paciente e, quando possivel, da mesma regiao/ferida.
- Resultado assistivo anterior quando existir.

Dados diretamente identificaveis, como telefone e e-mail, nao devem ser usados para treinamento nem exibidos no resultado analitico salvo.

## Formato de ROI

As ROIs devem permanecer proporcionais a imagem, independentes do tamanho renderizado:

```json
{
  "id": "roi-uuid",
  "label": "Ferida principal",
  "type": "wound_area",
  "points": [
    { "x": 0.32, "y": 0.41 },
    { "x": 0.35, "y": 0.45 }
  ],
  "normalized": true,
  "createdAt": "iso-date",
  "updatedAt": "iso-date",
  "createdBy": "uid"
}
```

Esse formato permite reconstruir poligonos, gerar mascaras binarizadas e preservar anotacoes supervisionadas para modelos futuros.

## Pipeline Atual

1. Carregar paciente, avaliacao, imagem, ROI e historico autorizado pelo `uid`.
2. Reutilizar ROI salva da avaliacao quando existir.
3. Permitir criar ROI no HEAL Analyzer com o mesmo componente usado na avaliacao.
4. Aplicar filtros antes da inferencia: mediana, gaussiano e equalizacao de histograma.
5. Avaliar qualidade da imagem: resolucao, brilho, contraste e nitidez aproximada.
6. Extrair sinais visuais simples dentro da ROI: faixas avermelhadas, amareladas, escurecidas, esbranquicadas e mistas.
7. Aplicar regras clinicas assistivas explicaveis.
8. Comparar com avaliacao anterior relacionada.
9. Salvar resultado estruturado em Firestore com versao de algoritmo, versao de ROI, autor e data.

## Estrategia de Treinamento Futuro

- Usar ROIs manuais como anotacoes supervisionadas para segmentacao da ferida.
- Gerar mascaras internas a partir dos pontos normalizados.
- Separar imagem original, imagem filtrada, ROI, mascara e metadados clinicos.
- Criar dataset interno anonimizado, sem nome, telefone, e-mail ou identificadores diretos.
- Usar datasets publicos quando possivel para pre-treinamento e validacao externa.
- Priorizar CO2Wounds-V2 para o primeiro baseline academico de segmentacao ferida vs fundo, mantendo uso estritamente experimental/nao comercial por causa das licencas CC BY-NC 3.0 e CC BY-NC-ND declaradas nas fontes oficiais.
- Testar resolucoes como 224x224, 512x512 e imagem original redimensionada.
- Comparar perda de detalhe, ruido visual e desempenho entre resolucoes.
- Separar modelo de segmentacao da ferida de modelos de tecido/classificacao assistiva.
- Avaliar arquiteturas como U-Net, DeepLabV3 e variantes leves para ambiente clinico.
- Registrar metricas como Dice, IoU, sensibilidade, especificidade, calibracao de confianca e taxa de revisao profissional.
- Manter trilha de auditoria dos resultados e da versao do modelo.

## Limitacoes e Cuidados Eticos

- A IA nao deve afirmar infeccao, necrose ou diagnostico como certeza.
- Linguagem deve usar termos como "pode sugerir", "merece atencao", "compativel com" e "validar profissionalmente".
- Baixa qualidade da imagem, ausencia de ROI e campos clinicos incompletos devem reduzir confianca e gerar alerta.
- Dados LGPD sensiveis exigem minimizacao, controle de acesso por usuario, rastreabilidade e anonimização para pesquisa.
- Treinamento com dados identificaveis e proibido sem base legal, governanca e processo formal de anonimização.

## Proximos Passos

- Criar export anonimizado de imagens, mascaras e metadados clinicos.
- Adicionar audit log dedicado para execucoes do Analyzer.
- Persistir resultado anterior resumido no card de historico.
- Adicionar revisao profissional do resultado para criar labels de qualidade.
- Implementar pipeline offline de treinamento e validacao com versionamento de dataset/modelo.
