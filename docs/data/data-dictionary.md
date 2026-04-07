# Dicionário de Dados

## Escopo

Este documento descreve as entidades clínicas e técnicas mais importantes já presentes no projeto.

## Entidades Principais

### Patient

Origem: `src/data/database.py`

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | string | identificador do paciente |
| `name` | string | nome ou identificador sintético |
| `birth_date` | string opcional | data de nascimento |
| `medical_record` | string opcional | prontuário ou referência interna |
| `notes` | string | observações livres |
| `created_at` | string | timestamp ISO |
| `metadata` | JSON | metadados adicionais |

### Wound Case

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | string | identificador do caso |
| `patient_id` | string | vínculo com paciente |
| `title` | string opcional | título do caso |
| `wound_type` | string opcional | tipo de ferida |
| `location` | string opcional | localização anatômica |
| `status` | string opcional | estado do caso |
| `opened_at` | string | abertura |
| `closed_at` | string opcional | encerramento |
| `metadata` | JSON | contexto adicional |

### Wound Evaluation

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | string | identificador da avaliação |
| `patient_id` | string | paciente |
| `case_id` | string opcional | caso clínico associado |
| `evaluation_date` | string | data da avaliação |
| `professional_name` | string opcional | profissional responsável |
| `wound_type` | string opcional | classificação informada |
| `wound_location` | string opcional | local anatômico |
| `clinical_description` | string opcional | observação clínica |
| `push_score` | float opcional | escala PUSH |
| `braden_score` | float opcional | escala Braden |
| `bwat_score` | float opcional | escala BWAT |
| `pain_score` | float opcional | dor autorreferida |
| `wound_area_cm2` | float opcional | área estimada |
| `depth_mm` | float opcional | profundidade |
| `tissue_composition` | JSON | composição tecidual |
| `timers_payload` | JSON | dados auxiliares |
| `metadata` | JSON | extensões locais |

### Wound Image

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | string | identificador da imagem |
| `evaluation_id` | string | vínculo com avaliação |
| `image_role` | string | papel da imagem no fluxo |
| `image_path` | string | caminho local ou lógico |
| `content_type` | string | mime type |
| `metadata` | JSON | nome original, flags etc. |
| `created_at` | string | timestamp ISO |

### AI Inference Run

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | string | job de inferência |
| `evaluation_id` | string | avaliação relacionada |
| `status` | string | `queued`, `running`, `completed`, `failed` |
| `use_fallback` | inteiro | indica fallback heurístico |
| `stage1_latency_ms` | inteiro opcional | latência estágio 1 |
| `stage2_latency_ms` | inteiro opcional | latência estágio 2 |
| `failure_reason` | string opcional | motivo da falha |
| `created_at` | string | criação |
| `updated_at` | string | atualização |

### AI Result

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | string | identificador do resultado |
| `run_id` | string | job associado |
| `etiology` | string | classe prevista |
| `confidence` | float | confiança principal |
| `tissue_percentages` | JSON | distribuição tecidual |
| `wound_area_cm2` | float opcional | área estimada |
| `diagnosis_summary` | string | resumo clínico |
| `recommendations` | JSON | recomendações |
| `payload` | JSON | payload completo |
| `created_at` | string | timestamp |

## Convenções Recomendadas

- usar timestamps ISO 8601;
- separar claramente campos clínicos, técnicos e de auditoria;
- padronizar classes clínicas antes de expor em API pública;
- manter identificadores sintéticos em ambientes de teste;
- documentar qualquer mapeamento para CID-10, SNOMED CT ou FHIR em camada específica de interoperabilidade.
