# Validation Rules

## `POST /api/v1/evaluations`

Campos aceitos:

- `patient_id`
- `case_id`
- `evaluation_date`
- `wound_type`
- `wound_location`
- `clinical_description`
- `push_score`
- `braden_score`
- `bwat_score`
- `pain_score`
- `wound_area_cm2`
- `depth_mm`
- `tissue_composition`
- `timers_payload`

Campos bloqueados:

- `id`
- `created_at`
- `updated_at`
- `professional`
- `professional_name` vindo do cliente
- `generated_by`
- `status`
- `metadata` arbitrário

## `POST /api/v1/evaluations/<evaluation_id>/images`

Form fields aceitos:

- `image`
- `imageRole`

Regras:

- extensões suportadas: `.jpg`, `.png`, `.webp`
- MIME declarado deve bater com o conteúdo
- imagem deve ser válida após `Pillow.verify()`
- tamanho máximo e megapixels são controlados por env
- qualquer campo extra retorna `400`

## `POST /api/v1/reports/generate`

Campos aceitos:

- `patient_id`
- `case_id`
- `report_type`

Campos bloqueados:

- `professional`
- `generated_by`
- `id`

## `POST /api/v1/ai-chat`

Campos aceitos:

- `message`
- `conversation_id`
- `context.patient_id`

Regras:

- `context.patient_id` só é processado após checagem de acesso
- o backend não injeta prontuário bruto no prompt por padrão
- `conversation_id` deve pertencer ao mesmo usuário, salvo admin
