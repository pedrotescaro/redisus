# LGPD e Privacidade

## Princípio

O projeto lida com contexto potencialmente sensível de saúde. Portanto, qualquer imagem clínica, identificador de paciente ou metadado associado deve ser tratado como dado sensível.

## Regras Operacionais

- não versionar dados reais de pacientes;
- usar identificadores sintéticos em testes e demos;
- separar ambientes de desenvolvimento e dados de pesquisa autorizados;
- manter evidência de consentimento e base legal fora do código-fonte;
- evitar screenshots com dados identificáveis.

## Medidas Prioritárias

- centralizar política de anonimização;
- mapear retenção de dados;
- revisar storage e controle de acesso;
- auditar integrações com Firebase e relatórios exportáveis.

## Situação Atual

- o repositório já contém mecanismos úteis de documentação e persistência;
- ainda falta um pacote formal de governança de dados para pilotos e integração institucional.
