# Estratégia de testes

O objetivo da suíte é proteger o fluxo clínico principal:

`paciente -> lesão -> imagem -> IA -> avaliação -> evolução -> plano -> acompanhamento`

## Perfis de teste

- `unit`: regras puras, validações, serialização e utilitários.
- `contract`: contratos HTTP, payloads de inferência, erros e schemas.
- `fhir`: recursos e bundles HL7 FHIR R4.
- `integration`: API, banco temporário, uploads e fluxo clínico.
- `smoke`: entrypoints mínimos usados pela CI.
- `security`: autenticação, autorização, RBAC e headers.
- `e2e`: jornadas completas.
- `ml`: testes que dependem de modelos, datasets ou treinamento.
- `slow`: testes longos ou sensíveis a ambiente.

## Comandos

```powershell
python -m ruff check apps packages src tests scripts main.py heal_platform.py realtime_app.py
python -m ruff check --select E,F,I,UP,B,SIM apps packages src tests scripts main.py heal_platform.py realtime_app.py
python -m ruff format --check apps packages src tests scripts main.py heal_platform.py realtime_app.py
python -m pytest
python -m pytest -m "not slow and not ml"
python -m pytest -m contract
python -m pytest -m fhir
python -m pytest tests/test_clinical_api_contracts.py tests/test_fhir_case_export_api.py tests/test_fhir_client.py tests/test_fhir_r4_layer.py tests/test_risk_stratification.py tests/test_official_api_factory.py tests/test_api_security.py -q
python -m pytest --cov=apps --cov=packages --cov=src/interoperability --cov=src/risk --cov-report=term-missing --cov-report=xml
```

## Cobertura

Meta inicial:

- 55% no smoke gate da CI apos ampliar contratos FHIR/API.
- 60% apos remover artefatos e estabilizar fixtures.
- 80% nos módulos críticos: segurança, domínio clínico, contratos FHIR e validação de payloads.

Cobertura baixa em código legado não deve bloquear a migração, mas código novo em API, segurança, FHIR e domínio clínico deve entrar com teste.

## Lint e formatação

O gate inicial da CI usa Ruff apenas para erros fatais de sintaxe/importação indefinida. O lint completo e a formatação ainda encontram dívida técnica histórica e devem ser tratados em PRs dedicados, para evitar um commit mecânico grande misturado com mudanças de governança.

## Dados de teste

Use fixtures sintéticas, imagens pequenas e bancos temporários. Dados clínicos reais, datasets completos e checkpoints não devem entrar em `tests/`.
