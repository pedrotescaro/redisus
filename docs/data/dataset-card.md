# Dataset Card

## Nome

HEAL+ / REDISUS - Base inicial de imagens de feridas

## Estado Atual

Dataset experimental em consolidação, com forte dependência do acervo público `Medetec` armazenado em `dataset/medetec/`.

## Fontes Conhecidas

- `dataset/medetec/metadata.json` registra URLs de origem, categorias e status de download;
- o repositório versiona mais de 1.200 arquivos dentro de `dataset/`, incluindo metadados e imagens.

## Uso Atual

- treinamento exploratório de classificadores;
- comparação de arquiteturas;
- protótipos de inferência;
- preparação de demos técnicas.

## Limitações Importantes

- não é uma base clínica multicêntrica validada;
- distribuição de classes é heterogênea;
- não há manifestos oficiais de split no repositório atual;
- parte das classes reflete categorias de origem do acervo, não taxonomia clínica final;
- o dataset não deve ser tratado como evidência suficiente para uso clínico.

## Riscos

- ruído de rotulagem;
- desequilíbrio entre classes;
- variação grande de iluminação e enquadramento;
- ausência de governança formal de curadoria multicentro;
- possível desalinhamento entre classes do dataset e classes do produto.

## Ações Prioritárias

1. gerar `data/manifests/dataset_v1.csv` com cada imagem e seus metadados principais;
2. publicar `data/manifests/splits_v1.json`;
3. documentar exclusões, duplicatas e classes consolidadas;
4. separar classes de pesquisa exploratória das classes clínicas oficiais;
5. formalizar licenças, permissões e limitações de uso.

## Saída Esperada

Um dataset tratável, auditável e reproduzível, apto para sustentar benchmark e model cards honestos.
