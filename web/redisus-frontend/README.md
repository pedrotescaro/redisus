# Redisus Frontend (Heal+)

Estrutura inicial do frontend web em Next.js com App Router, TypeScript e Tailwind para o modulo Heal+.

## Entregas desta iteracao

- Rotas principais configuradas (`/login`, `/dashboard`, `/evaluations/new`, `/comparison`, `/reports`).
- Login e cadastro via Firebase Auth (email/senha).
- Dashboard de pacientes com busca e CRUD em Firestore.
- Exportacao PDF basica do snapshot filtrado de pacientes.
- Servico separado para chamada da API externa de IA (placeholder para analise de imagem).

## Como rodar

1. Instale Node.js 20+.
2. Copie `.env.local.example` para `.env.local` e preencha as variaveis Firebase.
3. Instale dependencias:

```bash
npm install
```

4. Rode em modo desenvolvimento:

```bash
npm run dev
```

## Estrutura

- `src/app`: rotas do App Router
- `src/components`: componentes de UI e modulos de tela
- `src/services/firebase`: regras de acesso a Auth/Firestore
- `src/services/ai`: integracao com API externa de IA
- `src/types`: contratos TypeScript
