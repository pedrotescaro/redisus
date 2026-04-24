# Security Policy

## Escopo

Este repositório trata de software para apoio ao diagnóstico e pode lidar com dados clínicos, imagens sensíveis e integrações com serviços externos. Segurança e privacidade não são opcionais.

## Regra crítica

O backend nunca deve confiar no frontend.

## Regras imediatas

- nunca versionar credenciais, chaves de API ou service accounts;
- nunca subir imagens de pacientes reais para o Git;
- nunca usar dados clínicos identificáveis em exemplos, screenshots ou testes;
- nunca versionar checkpoints, bancos locais, runs de treino ou datasets completos;
- manter arquivos `.env`, `.env.local` e equivalentes apenas no ambiente local;
- preferir IDs sintéticos e datasets públicos ou explicitamente autorizados.

## Documentos operacionais

- `docs/security/threat-model.md`
- `docs/security/secure-backend-guidelines.md`
- `docs/security/validation-rules.md`
- `docs/security/data-classification.md`
- `docs/security/incident-response.md`
- `docs/data/artifact-policy.md`

## Reporte de vulnerabilidades

Se você identificar uma vulnerabilidade:

1. não abra issue pública com detalhes sensíveis;
2. envie a descrição, o impacto e os passos de reprodução ao mantenedor do projeto;
3. aguarde alinhamento antes de divulgar publicamente.

## Áreas sensíveis

- integrações com Firebase e autenticação;
- armazenamento de imagens e relatórios;
- tokens de IA generativa;
- rastreabilidade de eventos clínicos;
- dados pessoais e sensíveis regulados pela LGPD.

## Hardening prioritário

- remover segredos do workspace versionável;
- centralizar o contrato de ambiente em exemplos seguros;
- adicionar verificação de segredos no CI;
- manter Artifact Guard ativo para impedir dados, modelos e bancos rastreados em PRs;
- restringir CORS e validar autenticação por ambiente;
- formalizar política de retenção e anonimização de dados.

## Controles automatizados

- Dependabot deve abrir PRs semanais para GitHub Actions, Python e frontend.
- CodeQL deve rodar em pull requests, pushes na `main` e agenda semanal.
- Gitleaks deve bloquear segredos reais em pull requests, pushes e varreduras semanais.
- Falhas de seguranca nao devem ser tratadas como advisory sem decisao explicita do mantenedor.
- Falsos positivos precisam ser registrados em `.gitleaks.toml` com escopo estreito e justificativa.
