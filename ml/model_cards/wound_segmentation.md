# Model Card - Wound Segmentation Small U-Net v2

## Identificacao

- tarefa: segmentacao binaria `ferida` versus `fundo`;
- arquitetura: `small_unet_gn_v2`, com GroupNorm para batches pequenos;
- entrada do benchmark local: 128 x 128 com letterbox, sem deformar a imagem;
- status: experimental, nao validado clinicamente;
- artefato local: `ml/outputs/co2wounds_v2_unet_v2_final/best_small_unet.pt`;
- artefatos e imagens permanecem fora do Git.

## Dados e governanca

- fonte: CO2Wounds-V2, DOI `10.17632/s2w7rjwz49.2`;
- escopo: pesquisa academica e prototipo nao comercial;
- a pagina Mendeley v2 informa CC BY-NC 3.0 e o repositorio dos autores informa
  CC BY-NC-ND; este projeto aplica a leitura mais restritiva;
- 607 registros rotulados originais;
- 581 imagens de conteudo unico apos auditoria;
- 23 grupos de fotos duplicadas tiveram suas mascaras unidas;
- 8 grupos originalmente cruzavam treino e validacao e foram mantidos apenas
  na validacao;
- split final: 461 imagens de treino e 120 de validacao;
- nenhum hash exato cruza os splits apos a limpeza;
- os arquivos publicos nao expoem identificador de paciente, portanto a
  separacao por paciente nao pode ser comprovada.

## Metricas do benchmark local

As metricas devem ser preenchidas a partir de
`ml/outputs/co2wounds_v2_unet_v2_final/final_metrics.json`. O criterio de
selecao e Dice macro por imagem; o limiar e escolhido apenas na validacao.

- melhor epoch: 8 de 8;
- Dice macro de validacao: 0,6253;
- IoU macro de validacao: 0,4900;
- Dice agregado por pixel: 0,7014;
- precision/recall agregados: 0,7069 / 0,6960;
- false positive rate / false negative rate: 0,0230 / 0,3040;
- limiar de decisao selecionado na validacao: 0,60.

Esses numeros sao validacao interna, nao validacao clinica ou externa.

## Uso pretendido

- pesquisa de delimitacao de ferida dentro de uma ROI revisada;
- geracao de mascara e overlay para avaliacao humana;
- benchmark reproduzivel de segmentacao ferida/fundo.

## Usos proibidos

- diagnostico, estadiamento ou prescricao autonoma;
- estimativa de infeccao apenas por fotografia;
- uso comercial sem autorizacao compativel com todos os dados;
- substituir a ROI/revisao de profissional em caso de baixa confianca;
- afirmar desempenho para etiologias, tons de pele, cameras ou servicos nao
  representados no conjunto.

## Salvaguardas do runtime

- habilitacao explicita por variavel de ambiente;
- aceite explicito de checkpoint nao comercial;
- abstencao para mascara vazia, grande demais ou de baixa confianca;
- fallback rastreavel para ROI manual/visao computacional classica;
- exposicao de versao, threshold, cobertura e entropia no relatorio;
- preservacao da ROI manual como limite maximo da predicao.

## Proximos requisitos para qualquer claim clinico

1. teste externo congelado e multicentrico, separado por paciente;
2. avaliacao por etiologia, tom de pele, dispositivo e condicao de captura;
3. estudo prospectivo com especialistas e analise de erros;
4. calibracao e limites de abstencao definidos no conjunto de validacao;
5. governanca LGPD, consentimento, seguranca e caminho regulatorio aplicavel.
