# Heal+ Web

Versao web do Heal+ reconstruida em React + TypeScript + Vite + Firebase. O app usa Firebase Auth, Cloud Firestore e Firebase Storage como fonte real de dados. Nao ha banco mockado como origem principal.

## Stack

- React, TypeScript, Vite e React Router
- Tailwind CSS e Lucide React
- React Hook Form + Zod
- Firebase JS SDK modular: Auth, Firestore, Storage e App Check opcional
- Vitest + React Testing Library
- Firebase Emulator Suite para regras
- Playwright opcional para E2E

## Funcionalidades

- Cadastro, login, recuperacao de senha, logout e rotas protegidas
- Perfil em `users/{uid}` com foto no Storage
- Dashboard com pacientes ativos, avaliacoes, agenda e arquivados
- CRUD de pacientes em `users/{uid}/patients/{patientId}`
- Avaliacoes em `users/{uid}/patients/{patientId}/evaluations/{evaluationId}`
- Upload de fotos para Storage e metadados no Firestore
- Editor de ROI web com poligono e caneta fina, coordenadas normalizadas
- Relatorio imprimivel ou salvavel como PDF pelo navegador
- Comparativo de duas avaliacoes reais
- Agenda em `users/{uid}/appointments/{appointmentId}`
- Assistente local sem IA externa, baseado nos dados carregados do Firestore

## Configuracao Firebase

1. Crie um projeto no Firebase.
2. Ative Authentication com e-mail/senha.
3. Ative Cloud Firestore.
4. Ative Firebase Storage.
5. Copie `.env.example` para `.env.local`.
6. Preencha as variaveis `VITE_FIREBASE_*`.

Observacao sobre Storage: para projetos criados ou configurados a partir de 30/10/2024, o Firebase exige o plano Blaze para criar o bucket padrao. Se o bucket informado em `VITE_FIREBASE_STORAGE_BUCKET` ainda nao existir, a avaliacao sera salva no Firestore sem imagens e o app exibira um aviso.

Nunca coloque chaves privadas, service accounts ou segredos no codigo. As chaves web do Firebase nao sao segredo, mas devem ficar em variaveis de ambiente.

Sem `.env.local`, o app usa uma configuracao `demo-healplus` apenas para renderizar a interface e rodar smoke tests. Para autenticar, persistir dados e fazer upload de verdade, configure Firebase real ou ligue os emuladores.

## Variaveis

```bash
VITE_FIREBASE_API_KEY=
VITE_FIREBASE_AUTH_DOMAIN=
VITE_FIREBASE_PROJECT_ID=
VITE_FIREBASE_STORAGE_BUCKET=
VITE_FIREBASE_MESSAGING_SENDER_ID=
VITE_FIREBASE_APP_ID=
VITE_FIREBASE_MEASUREMENT_ID=
VITE_USE_FIREBASE_EMULATORS=false
VITE_RECAPTCHA_ENTERPRISE_SITE_KEY=
VITE_APPCHECK_DEBUG_TOKEN=
VITE_MAX_IMAGE_UPLOAD_MB=10
```

App Check e opcional. Se `VITE_RECAPTCHA_ENTERPRISE_SITE_KEY` existir e emuladores estiverem desligados, o app inicializa App Check com reCAPTCHA Enterprise.

## Rodar localmente

```bash
npm install
npm run dev
```

Abra `http://127.0.0.1:5173`.

Para usar emuladores:

```bash
cp .env.example .env.local
# defina VITE_USE_FIREBASE_EMULATORS=true
npm run firebase:emulators
```

## Testes

```bash
npm run test
npm run test:coverage
npm run test:rules
npm run test:e2e
```

`test:rules` usa `firebase emulators:exec` com Firestore e Storage. Os testes cobrem:
O Firebase CLI atual exige Java 21; o script `test:rules` tenta localizar automaticamente um JRE/JDK 21 local antes de subir os emuladores.

- Validacoes de login, paciente e avaliacao
- Normalizacao e area estimada de ROI
- Componentes principais
- Regras de Firestore: autenticado, anonimo, isolamento por usuario e avaliacao no paciente correto
- Regras de Storage: imagem no proprio path, bloqueio entre usuarios e bloqueio de arquivo nao imagem

## Modelo de dados

```text
users/{uid}
  displayName
  email
  photoURL
  role: "professional"
  settings

users/{uid}/patients/{patientId}
  name
  phone
  email
  birthDate
  notes
  archived
  createdAt
  updatedAt

users/{uid}/patients/{patientId}/evaluations/{evaluationId}
  patientId
  patientName
  date
  woundLocation
  woundEtiology
  painLevel
  exudateAmount
  exudateType
  borderCharacteristics
  periwoundSkin
  infectionSigns
  timers
  comorbidities
  medications
  notes
  images[]

users/{uid}/appointments/{appointmentId}
  patientId
  patientName
  date
  time
  type
  status
  notes
```

## Segurança

- `firestore.rules` nega tudo por padrao.
- Cada usuario so acessa `users/{uid}` quando `request.auth.uid == uid`.
- Documentos de paciente, avaliacao e agenda validam campos essenciais.
- `storage.rules` aceita somente imagens no path do proprio usuario.
- Upload limitado a 10 MB por regra e por validacao no cliente.
- Segredos nao ficam no repositorio.

## Checklist de apresentacao

- Criar usuario novo pelo cadastro.
- Confirmar documento em `users/{uid}`.
- Fazer login e abrir dashboard protegido.
- Criar paciente e mostrar documento no Firestore.
- Criar avaliacao vinculada ao paciente.
- Enviar foto real e confirmar arquivo no Storage.
- Desenhar ROI e confirmar coordenadas salvas no Firestore.
- Gerar relatorio e salvar como PDF pelo print do navegador.
- Criar segunda avaliacao e abrir comparativo.
- Criar atendimento na agenda e ver no dashboard.
- Rodar `npm run test` e `npm run test:rules`.
- Mostrar tentativa bloqueada de usuario A acessando usuario B nos testes de regras.
