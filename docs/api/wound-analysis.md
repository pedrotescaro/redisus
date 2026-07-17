# HEAL+ Wound Analysis API

O recurso canônico de análise é `POST /api/v1/wound-analyses`. Ele aceita uma
imagem com ou sem `patient_id`/`evaluation_id`, persiste o resultado e permite
consulta posterior por `analysis_id`.

## Endpoints

- `POST /api/v1/wound-analyses` cria uma análise e responde `201 Created`.
- `GET /api/v1/wound-analyses/{analysis_id}` consulta o recurso persistido.
- `GET /api/v1/wound-analyses/capabilities` descreve runtime, entradas, saídas,
  limitações e referências metodológicas.
- `POST /api/v1/analyze` é legado e permanece apenas por compatibilidade.

O contrato OpenAPI completo está em [openapi.yaml](./openapi.yaml).

## Exemplo local

Com `CLINICAL_API_REQUIRE_AUTH=0` apenas no ambiente local:

```powershell
curl.exe -X POST http://127.0.0.1:5000/api/v1/wound-analyses `
  -H "Idempotency-Key: heal-local-00000001" `
  -F "image=@C:\caminho\ferida.png"
```

Em ambiente autenticado, adicione `Authorization: Bearer <firebase-jwt>`. Para
vincular o resultado, envie `patient_id` ou `evaluation_id` como campos multipart.
Quando `evaluation_id` é informado, a API deriva e valida o paciente associado.

## Idempotência e rastreabilidade

`Idempotency-Key` aceita de 8 a 128 caracteres seguros. Repetir a mesma chave com
o mesmo conteúdo retorna `200` e `X-Idempotent-Replay: true`. Reutilizá-la com
imagem, ROI ou contexto diferente retorna `409`. Toda resposta contém
`X-Request-ID`; erros usam `application/problem+json` conforme RFC 9457.

Cada resultado informa o modo de execução, componentes disponíveis, avisos,
hash SHA-256 da entrada, versão do contrato e versão do motor. O endpoint canônico
não usa um modelo generativo como substituto silencioso do analisador clínico.

## Uso clínico

O resultado é apoio à decisão e requer revisão de profissional habilitado. A API
expõe limitações de imagem, escala e inferência em cada recurso. Fotografia isolada
não confirma etiologia nem define conduta, e área em pixels não equivale a cm² sem
uma referência física calibrada.
