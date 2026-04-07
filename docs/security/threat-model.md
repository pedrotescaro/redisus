# Threat Model

## Ativos críticos

- dados de pacientes
- imagens clínicas
- relatórios estruturados
- resultados de IA
- tokens, service accounts e credenciais

## Fronteiras de confiança

- `frontend` é não confiável por definição
- `proxy Next.js` não substitui autenticação/autorização do backend
- `Firebase client SDK` não substitui backend como fonte de verdade
- `provedores de IA` são terceiros e recebem apenas contexto mínimo

## Atores de ameaça

- usuário autenticado malicioso
- usuário não autenticado tentando enumeração
- operador interno com acesso excessivo
- automação abusiva contra endpoints caros
- vazamento operacional de segredo ou artefato

## Ameaças prioritárias

1. IDOR trocando `patient_id`, `evaluation_id`, `report_id`, `conversation_id`
2. bypass do frontend via `curl`, Postman ou app modificado
3. upload malicioso para exaustão de memória/CPU
4. adulteração de payload com `id`, `generated_by`, `status` ou campos extras
5. vazamento de contexto clínico para IA de terceiros
6. exposição de dados por storage/SQLite/relatórios sem proteção adequada

## Controles obrigatórios

- autenticação server-side em toda rota sensível
- autorização server-side por recurso
- schema estrito com `extra=forbid`
- validação real de imagem e limite de tamanho
- rate limit por usuário/IP e endpoint
- trilha de auditoria de leitura, escrita e exportação
