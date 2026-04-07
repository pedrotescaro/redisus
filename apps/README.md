# Apps

Esta pasta passa a concentrar os entrypoints canônicos do projeto.

## Estrutura

- `api/`: backend oficial do módulo de diagnóstico.
- `web/`: referência canônica do frontend durante a transição.
- `desktop/`: referência para a camada desktop legada.

Durante a migração, nem todo código foi movido fisicamente para cá. O objetivo imediato é consolidar pontos de entrada e reduzir ambiguidade arquitetural sem quebrar o runtime atual.
