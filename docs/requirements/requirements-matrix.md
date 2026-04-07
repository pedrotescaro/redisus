# Matriz de Requisitos e Entregas

## Recorte Escolhido

Com base no relatório trimestral do REDI-SUS, o foco prioritário deste repositório é:

- `PT2`: requisitos, arquitetura e contratos;
- `PT3`: coleta, rastreabilidade e base curada;
- `PT4`: modelos e benchmark;
- `PT5`: interface e jornada de uso.

## Matriz

| Trimestre | PT | Entrega do relatório | Estado atual no repo | Artefato canônico atual | Próximo fechamento |
|---|---|---|---|---|---|
| T1 | PT2 | Requisitos técnicos e clínicos | Parcial | `docs/requirements/requirements-matrix.md` | detalhar requisito por fluxo, risco e evidência |
| T2 | PT2 | Arquitetura conceitual e dicionário de dados | Parcial | `docs/architecture/system-architecture.md`, `docs/data/data-dictionary.md` | alinhar contrato único entre frontend, API e ML |
| T3 | PT3 | Protocolo de coleta e calibração | Inicial | `docs/data/collection-protocol.md` | transformar em checklist operacional de campo |
| T4 | PT3 | Base inicial curada com imagens rotuladas | Parcial | `docs/data/dataset-card.md` | gerar inventário, splits e relatório de curadoria |
| T4 | PT3 | Módulos de coleta e pipeline de ingestão | Parcial | `scripts/`, `dataset/`, `src/data/` | publicar fluxo executável e logs de QA |
| T4 | PT4 | Protótipos iniciais de IA e relatório de arquiteturas | Parcial | `ml/benchmarks/baseline_report.md`, `ml/model_cards/` | formalizar baseline e gaps de reprodutibilidade |
| T5 | PT3 | Base consolidada multicentro | Não iniciado | `data/manifests/` | depende de governança e consolidação externa |
| T5 | PT5 | Interface diagnóstica e jornadas validadas | Parcial | `web/redisus-frontend/`, `docs/product/user-journey.md` | fechar golden path e evidência de uso |
| T5 | PT7 | Gateway FHIR operacional | Exploratória | `src/interoperability/` | deixar para depois do backend oficial e contrato clínico estáveis |
| T6 | PT4 | Biblioteca federada de modelos | Não iniciado | `ml/registry/models.yaml` | depende de benchmark confiável e governança de publicação |
| T6 | PT5 | Protótipo funcional e usabilidade | Inicial | `docs/product/demo-script.md` | adicionar testes e coleta de feedback |
| T6 | PT6 | Início dos pilotos multicêntricos | Não iniciado | `docs/product/` e `docs/compliance/` | só após consolidação do core |
| T7 | PT4 | Sistema integrado com painel e validação | Não iniciado | `web/redisus-frontend/`, `src/dashboard/` | depende da unificação do backend |
| T7 | PT7 | Plataforma interoperável com rastreabilidade | Não iniciado | `src/interoperability/` | depende de eventos e auditoria formais |
| T8 | PT6 | Relatório final de validação e transferência | Não iniciado | `docs/research/` | resultado de fases posteriores |

## Critérios de Aceite Adotados

- rastreabilidade entre requisito, artefato e responsável;
- reprodutibilidade mínima da geração de resultado;
- documentação explícita de limitações;
- separação entre funcionalidade demonstrável e visão futura.
