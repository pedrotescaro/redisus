# Secure Backend Guidelines

## Regra-mãe

O backend nunca confia no frontend.

## Regras obrigatórias

- validar tudo no backend, mesmo que o frontend já valide
- nunca usar `role`, `status`, `generated_by`, `id` ou timestamps enviados pelo cliente
- nunca autorizar acesso a recurso apenas porque a UI esconde a ação
- nunca enriquecer prompt de IA com contexto clínico sem checagem de acesso
- nunca salvar upload sem validar conteúdo real, tamanho e formato

## Auth

- toda rota `/api/` sensível exige token válido no backend
- se o provedor de autenticação falhar, o backend falha fechado
- `CORS` não é controle de autorização

## Authz

- toda leitura, escrita, exclusão e exportação deve validar ownership/escopo
- `patient_id`, `evaluation_id`, `job_id`, `report_id` e `conversation_id` devem ser revalidados no servidor
- recursos agregados devem ser `admin-only` ou explicitamente filtrados por escopo

## Payloads

- usar schemas explícitos
- rejeitar campos extras
- ranges clínicos devem ser validados no backend
- IDs de sistema são gerados no servidor

## Uploads

- aceitar apenas formatos suportados
- validar assinatura real do arquivo
- limitar bytes e megapixels
- salvar nome gerado no servidor
- remover metadados sensíveis no re-encode

## IA aplicada à saúde

- minimizar dados enviados a terceiros
- não enviar prontuário completo quando um resumo técnico basta
- registrar quem solicitou, quando e qual contexto foi enviado
- separar claramente modo demo de modo clínico
