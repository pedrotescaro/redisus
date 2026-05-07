# Changelog da revisão ABNT 2026

Data da revisão: 5 maio 2026.

## Arquivos-base utilizados

- `C:/Users/PEDRO/Downloads/relatorio_heal_redisus_final.pdf`
- `C:/Users/PEDRO/Downloads/introducao.docx`
- `C:/Users/PEDRO/Downloads/Modelo_Monografia_Ferraz_2024_v1.1 (10).docx` como fonte auxiliar de triagem histórica do HEAL, sem substituir o escopo atual.
- Repositório local `C:/Users/PEDRO/Documents/redisus`
- Fonte LaTeX relacionada: `docs/research/relatorio_resolucao_espacial_feridas_cronicas.tex`

## Introdução

- Substituída a introdução anterior por versão acadêmica baseada no DOCX fornecido.
- Incorporados os pontos sobre feridas crônicas, lesões por pressão, úlceras venosas, feridas cirúrgicas e pé diabético como problema de saúde pública.
- Incluída a demanda observada com apoio da profissional de enfermagem Caroline Paula Ribeiro Silvestre Tescaro.
- Acrescentada discussão sobre registros manuais, fotografias descentralizadas, documentação longitudinal, estomaterapia, fotografia digital e necessidade de armazenamento seguro.
- Reposicionado o HEAL+ como módulo do REDISUS/RNP, com IA descrita apenas como apoio assistivo futuro.

## Metodologia

- Reescrita a seção “Metodologia e uso de IA”.
- Incluída caracterização como pesquisa aplicada, desenvolvimento tecnológico e engenharia de requisitos em saúde digital.
- Acrescentada consulta documental aos materiais preliminares do HEAL de 2024/2025 apenas para recuperar requisitos históricos úteis, sem reposicionar o relatório atual como monografia antiga.
- Acrescentadas referências de engenharia de requisitos/software para sustentar a organização metodológica dos requisitos.
- Reescritos os trechos com aparência de inventário de fontes para linguagem de percurso metodológico, reduzindo marcas textuais de geração por IA.
- Atualizada a apresentação acadêmica para formato de Trabalho de Conclusão de Curso, com preâmbulo próprio, orientador, coorientador e resumo em português e inglês.
- Detalhadas fontes, etapas metodológicas e critérios de não superestimar resultados.
- Inserida figura metodológica com legenda e fonte.
- Reescrita a declaração de uso de IA generativa com foco em transparência, uso do Codex para apoio à geração de código do repositório, revisão de erros no documento, responsabilidade humana e não autoria da IA.
- Acrescentada explicação sobre citação indireta, citação direta curta e citação direta longa conforme a NBR 10520:2023.

## Citações e referências

- Criado `referencias.bib` em padrão BibTeX/ABNT.
- Padronizadas citações autor-data com `abntex2cite`.
- Adicionadas referências de Fernandes e Machado (2017) e Pressman e Maxim (2016) para fundamentar a engenharia de requisitos e a organização técnica do documento.
- Incluídas ou corrigidas referências de literatura científica, OMS, LGPD, ANPD, CNS 466/2012, CNS 510/2016, RNP, WCET e documentação local do projeto.
- A referência ANPD foi mantida como 2023 porque o próprio PDF “Tratamento de dados pessoais pelo Poder Público”, versão 2.0, informa publicação digital em junho de 2023.
- A referência antiga “COTA, 2025” não foi mantida no texto por não haver arquivo correspondente localizado no repositório inspecionado; foi substituída por RNP 2025 quando o assunto era a chamada pública, com pendência de validação humana se houver documento interno do Cluster.
- Removidas do corpo do texto as autocitações ao autor e ao próprio repositório; a descrição técnica permanece como análise do projeto, sem referência autor-data ao próprio repositório.

## ABNT e estrutura

- Criado novo arquivo `relatorio_heal_redisus_abnt_2026.tex` com classe `abntex2`.
- Ajustada a natureza do trabalho de "documento técnico-acadêmico" para "Trabalho de Conclusão de Curso".
- Gerada cópia final com nomenclatura de TCC: `tcc_heal_redisus_abnt_2026.tex` e `tcc_heal_redisus_abnt_2026.pdf`.
- Acrescentado resumo em inglês (`Abstract`) com palavras-chave em inglês.
- Padronizados títulos e subtítulos em tamanho 12 (`\normalsize`), fonte preta, com títulos primários em negrito e caixa alta.
- Removida a conversão automática de subseções para caixa alta; subseções secundárias e terciárias permanecem em caixa baixa/iniciais maiúsculas conforme a hierarquia ABNT.
- Ajustadas capa e folha de rosto para manter o título principal em tamanho 12, centralizado e posicionado no meio da página.
- Corrigida numeração progressiva: capítulos aparecem como `1`, `2`, `3`, sem `1.0`.
- Mantidos elementos pré-textuais: capa, folha de rosto, resumo, palavras-chave, lista de siglas, lista de figuras, lista de tabelas e sumário.
- Mantidos elementos textuais de 1 a 26.
- Mantidos apêndices A, B, C e D.
- Tabelas e figuras receberam legenda e fonte.
- Foram evitadas imagens clínicas reais; as imagens metodológicas são esquemáticas para reduzir risco de exposição de dado sensível.
- Ajustado o cabeçalho textual para remover indicação de capítulo, mantendo apenas paginação.
- Mantida a palavra "LaTeX" em fonte textual normal na declaração de uso de IA.

## Seções técnicas

- Atualizada leitura do estado real do repositório: backend Flask oficial, API clínica, frontend Next.js, ROI manual, camada FHIR R4, model cards e release `v0.1.0-alpha`.
- Diferenciados estados: Implementado, Parcialmente implementado, Planejado, Experimental, Fora do escopo inicial, Dependente de aprovação ética e Dependente de validação clínica.
- Aproveitados elementos coerentes do trabalho HEAL 2024/2025 para reforçar requisitos já alinhados ao escopo atual: histórico, relatórios, permissões, procedimentos, insumos, terapias aplicadas, acessibilidade e plano de cuidado.
- Incorporado resultado do relatório de resolução espacial: 80 x 80 como mínimo técnico interno do pipeline clássico e 224 x 224 como mínimo operacional recomendado.
- Registrado que o diretório `dataset/medetec` não apresentou imagens na inspeção local de 5 maio 2026; qualquer afirmação sobre Medetec deve ser verificada.
- Refeita a figura de redimensionamento e registro de evidências para melhorar legibilidade, fluxo visual, legenda e fonte.
- Acrescentada subseção sobre pré-processamento experimental com OpenCV, incluindo mediana, gaussiano, equalização em cinza, equalização colorida por luminância, CLAHE e combinações filtro + equalização.
- Registrada execução inicial sobre `examples/synthetic_wound.jpg`, com ressalva de que se trata de teste técnico de fumaça, não validação clínica.

## Pendências para validação humana

- Validar com orientador/professor se há documento interno do Cluster que justifique manter referência nominal a COTA, 2025.
- Confirmar licenças de uso de PIID, Medetec ou qualquer base pública antes de anexar imagens reais ao relatório.
- Validar clinicamente os requisitos com enfermeiro, médico, dermatologista ou estomaterapeuta.
- Revisar institucionalmente LGPD, TCLE, anonimização, retenção e descarte de dados.
- Submeter qualquer pesquisa com pacientes reais ao CEP/CONEP antes de coleta ou análise.
- Revisar se a instituição exige manual ABNT próprio além das NBRs citadas.

## Compilação

Comandos utilizados em `docs/research`:

```powershell
pdflatex -interaction=nonstopmode -halt-on-error relatorio_heal_redisus_abnt_2026.tex
bibtex relatorio_heal_redisus_abnt_2026
pdflatex -interaction=nonstopmode -halt-on-error relatorio_heal_redisus_abnt_2026.tex
pdflatex -interaction=nonstopmode -halt-on-error relatorio_heal_redisus_abnt_2026.tex
pdflatex -interaction=nonstopmode -halt-on-error relatorio_heal_redisus_abnt_2026.tex
```

Resultado: `docs/research/relatorio_heal_redisus_abnt_2026.pdf`.
