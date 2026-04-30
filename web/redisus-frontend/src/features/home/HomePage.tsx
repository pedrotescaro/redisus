import Image from "next/image";
import Link from "next/link";
import {
  Activity,
  ArrowRight,
  ArrowUpRight,
  BadgeCheck,
  BookOpenCheck,
  BrainCircuit,
  Camera,
  CheckCircle2,
  ClipboardList,
  Cpu,
  Database,
  FileText,
  Globe2,
  Layers3,
  LineChart,
  LockKeyhole,
  Network,
  ScanLine,
  ShieldCheck,
  Sparkles,
  Stethoscope,
  Target,
  UserRoundCheck,
  Workflow,
} from "lucide-react";

const navItems = [
  { label: "O projeto", href: "#projeto" },
  { label: "Plataforma", href: "#plataforma" },
  { label: "Fluxo", href: "#fluxo" },
  { label: "Tecnologia", href: "#tecnologia" },
  { label: "Instituições", href: "#instituicoes" },
];

const heroStats = [
  { value: "01", label: "Fluxo clínico centralizado" },
  { value: "ROI", label: "Imagens e evidências visuais" },
  { value: "IA", label: "Base preparada para análise assistida" },
  { value: "PDF", label: "Relatórios e histórico longitudinal" },
];

const clinicalFlow = [
  {
    icon: UserRoundCheck,
    title: "Cadastrar",
    text: "Organize pacientes, contatos, histórico e dados iniciais em uma experiência direta para a rotina clínica.",
  },
  {
    icon: ClipboardList,
    title: "Avaliar",
    text: "Registre sinais clínicos, evolução, dor, tecido, borda, umidade e observações com campos estruturados.",
  },
  {
    icon: ScanLine,
    title: "Marcar ROI",
    text: "Prepare imagens para comparação, análise visual e documentação da evolução da ferida ao longo do tempo.",
  },
  {
    icon: FileText,
    title: "Documentar",
    text: "Gere relatórios, consolide evidências e entregue uma visão mais clara para revisão, pesquisa e auditoria.",
  },
];

const platformHighlights = [
  {
    icon: Layers3,
    title: "Módulo acoplável",
    text: "Estrutura pensada para conversar com o ecossistema REDI-SUS sem virar uma aplicação isolada.",
  },
  {
    icon: Database,
    title: "Dados clínicos organizados",
    text: "Contratos para pacientes, lesões, imagens, avaliações, evolução e relatórios em um fluxo consistente.",
  },
  {
    icon: BrainCircuit,
    title: "Pronto para IA",
    text: "Base preparada para segmentação, classificação, comparação visual e apoio computacional no futuro.",
  },
  {
    icon: LockKeyhole,
    title: "Governança e acesso",
    text: "Arquitetura com foco em rastreabilidade, perfis de acesso e evolução segura da plataforma.",
  },
];

const techItems = [
  {
    icon: Globe2,
    label: "Interface web",
    value: "Next.js, React e TypeScript para uma experiência responsiva, rápida e escalável.",
  },
  {
    icon: Network,
    label: "Integração",
    value: "APIs e contratos clínicos preparados para conectar o módulo ao REDI-SUS.",
  },
  {
    icon: Cpu,
    label: "Camada analítica",
    value: "Base para visão computacional, ROI, segmentação, classificação e relatórios inteligentes.",
  },
  {
    icon: ShieldCheck,
    label: "Segurança",
    value: "RBAC, auditoria, separação de responsabilidades e cuidado com dados sensíveis de saúde.",
  },
];

const journeySteps = [
  {
    step: "01",
    title: "Entrada clínica",
    text: "O profissional registra o paciente, adiciona dados iniciais e cria a base do acompanhamento.",
  },
  {
    step: "02",
    title: "Imagem e avaliação",
    text: "A ferida é documentada com foto, ROI, sinais clínicos e observações do atendimento.",
  },
  {
    step: "03",
    title: "Comparativo de evolução",
    text: "O histórico permite visualizar mudanças, revisar condutas e acompanhar resposta ao tratamento.",
  },
  {
    step: "04",
    title: "Relatório e integração",
    text: "O caso vira evidência estruturada para relatório, auditoria, pesquisa e integração com a plataforma.",
  },
];

const institutionalLogos = [
  {
    name: "RNP",
    src: "/images/partners/rnp.png",
    alt: "Logo da RNP",
    width: 400,
    height: 125,
    className: "h-12 w-auto md:h-16",
  },
  {
    name: "Fatec Ferraz",
    src: "/images/partners/fatec-ferraz.png",
    alt: "Logotipo da Fatec Ferraz de Vasconcelos",
    width: 863,
    height: 544,
    className: "h-20 w-auto md:h-24",
  },
  {
    name: "Centro Paula Souza",
    src: "/images/partners/cps.svg",
    alt: "Logo do Centro Paula Souza",
    width: 122,
    height: 80,
    className: "h-16 w-auto md:h-20",
  },
];

export default function HomePage() {
  return (
    <div className="min-h-screen bg-[#f7faff] text-[#101828]">
      <nav className="fixed left-0 top-0 z-50 w-full border-b border-gray-200 bg-white/90 text-gray-900 shadow-sm backdrop-blur-2xl">
        <div className="mx-auto flex h-[76px] w-full max-w-7xl items-center justify-between px-5 md:px-8">
          <Link href="/" className="flex min-w-0 items-center gap-3">
            <Image
              src="/images/logo.png"
              alt="Heal+"
              width={54}
              height={54}
              priority
              className="h-12 w-12 shrink-0"
            />
            <div className="min-w-0 leading-none">
              <p className="text-2xl font-black text-[#3b82f6] font-headline">
                Heal+
              </p>
              <p className="mt-1 hidden text-[10px] font-extrabold uppercase tracking-[0.24em] text-gray-500 sm:block">
                REDI-SUS Module
              </p>
            </div>
          </Link>

          <div className="hidden items-center gap-7 lg:flex">
            {navItems.map((item) => (
              <a
                key={item.href}
                href={item.href}
                className="text-sm font-extrabold text-gray-600 transition-colors hover:text-[#3b82f6]"
              >
                {item.label}
              </a>
            ))}
          </div>

          <div className="flex items-center gap-2 sm:gap-3">
            <Link
              href="/login"
              className="hidden rounded-full px-4 py-2 text-sm font-extrabold text-gray-600 transition-colors hover:text-[#3b82f6] sm:inline-flex"
            >
              Entrar
            </Link>
            <Link
              href="/login"
              className="inline-flex items-center gap-2 rounded-full bg-[linear-gradient(135deg,#3b82f6,#73a8ff)] px-5 py-3 text-sm font-black text-white shadow-[0_12px_28px_rgba(59,130,246,0.34)] transition-transform hover:-translate-y-0.5"
            >
              Acessar
              <ArrowRight size={18} strokeWidth={3} />
            </Link>
          </div>
        </div>
      </nav>

      <main className="pt-[76px]">
        <section
          id="projeto"
          className="relative isolate overflow-hidden bg-[radial-gradient(circle_at_18%_12%,rgba(59,130,246,0.34),transparent_28%),radial-gradient(circle_at_86%_18%,rgba(115,168,255,0.22),transparent_24%),linear-gradient(135deg,#06101c_0%,#07111d_42%,#0d1b2e_100%)] text-white"
        >
          <div className="absolute inset-0 -z-10 bg-[radial-gradient(rgba(115,168,255,0.16)_1px,transparent_1px)] bg-[length:34px_34px] opacity-30" />
          <div className="absolute left-1/2 top-24 -z-10 h-80 w-80 -translate-x-1/2 rounded-full bg-[#3b82f6]/20 blur-3xl" />

          <div className="mx-auto grid min-h-[760px] max-w-7xl items-center gap-12 px-5 py-20 md:px-8 lg:grid-cols-[1.02fr_0.98fr]">
            <div className="max-w-3xl">
              <div className="inline-flex items-center gap-2 rounded-full border border-[#73a8ff]/25 bg-[#3b82f6]/12 px-4 py-2 text-xs font-black uppercase tracking-[0.18em] text-[#cfe3ff] shadow-[0_16px_45px_rgba(59,130,246,0.16)]">
                <Sparkles size={16} />
                App clínico | Inteligência aplicada | REDI-SUS
              </div>

              <h1 className="mt-7 max-w-5xl text-5xl font-black leading-[0.94] tracking-[-0.055em] font-headline md:text-7xl lg:text-[5.4rem]">
                Cuidado inteligente.
                <span className="block bg-[linear-gradient(135deg,#f8fbff_0%,#9fc8ff_44%,#3b82f6_100%)] bg-clip-text text-transparent">
                  Evolução visível.
                </span>
              </h1>

              <p className="mt-6 max-w-2xl text-lg font-medium leading-8 text-white/78 md:text-xl">
                O Heal+ transforma o acompanhamento de feridas em um fluxo
                claro: cadastro, avaliação, imagem, ROI, comparativo e relatório
                em uma base preparada para integrar o ecossistema REDI-SUS.
              </p>

              <div className="mt-9 flex flex-col gap-4 sm:flex-row">
                <Link
                  href="/login"
                  className="inline-flex items-center justify-center gap-2 rounded-full bg-[linear-gradient(135deg,#3b82f6,#73a8ff)] px-8 py-4 text-base font-black text-white shadow-[0_20px_42px_rgba(59,130,246,0.32)] transition-transform hover:-translate-y-0.5"
                >
                  Acessar área clínica
                  <ArrowRight size={20} strokeWidth={3} />
                </Link>
                <a
                  href="#plataforma"
                  className="inline-flex items-center justify-center gap-2 rounded-full border border-white/14 bg-white/[0.07] px-8 py-4 text-base font-black text-[#eef5ff] backdrop-blur-xl transition-colors hover:bg-white/[0.11]"
                >
                  Conhecer plataforma
                  <ArrowUpRight size={19} strokeWidth={3} />
                </a>
              </div>

              <div className="mt-10 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {heroStats.map((item) => (
                  <div
                    key={item.label}
                    className="rounded-3xl border border-white/10 bg-white/[0.06] p-4 backdrop-blur-xl"
                  >
                    <p className="text-2xl font-black text-[#73a8ff] font-headline">
                      {item.value}
                    </p>
                    <p className="mt-2 text-xs font-bold leading-5 text-white/64">
                      {item.label}
                    </p>
                  </div>
                ))}
              </div>
            </div>

            <div className="relative mt-12 flex w-full justify-center lg:mt-0 lg:justify-start">
              <Image
                src="/images/Hero imagem.png"
                alt="Heal+ Dashboard Preview"
                width={1000}
                height={800}
                className="h-auto w-full max-w-2xl rounded-2xl drop-shadow-2xl lg:max-w-none lg:w-[150%] xl:w-[160%] lg:translate-x-4 xl:translate-x-12 lg:rounded-l-2xl lg:rounded-r-none"
                priority
              />
            </div>
          </div>
        </section>

        <section className="border-y border-[#dbeafe] bg-white py-8">
          <div className="mx-auto grid max-w-7xl gap-4 px-5 md:grid-cols-4 md:px-8">
            {[
              "Pacientes em ordem",
              "Avaliação estruturada",
              "Comparativo fotográfico",
              "Relatórios exportáveis",
            ].map((item) => (
              <div key={item} className="flex items-center justify-center gap-2 rounded-2xl bg-[#f7faff] px-4 py-4 text-center text-sm font-black text-[#1d4ed8]">
                <BadgeCheck size={18} />
                {item}
              </div>
            ))}
          </div>
        </section>

        <section id="plataforma" className="bg-[#f7faff] py-24 text-[#101828]">
          <div className="mx-auto grid max-w-7xl gap-12 px-5 md:px-8 lg:grid-cols-[0.82fr_1.18fr]">
            <div>
              <p className="text-sm font-black uppercase tracking-[0.24em] text-[#3b82f6]">
                Plataforma
              </p>
              <h2 className="mt-4 text-4xl font-black leading-tight tracking-[-0.04em] font-headline md:text-5xl">
                Uma central clínica para acompanhar feridas com clareza.
              </h2>
              <p className="mt-5 text-lg leading-8 text-[#667085]">
                A Home precisa vender a ideia do produto antes de explicar a
                tecnologia. Por isso, o Heal+ aparece como uma solução real para
                reduzir retrabalho, organizar evidências e tornar a evolução mais visível.
              </p>
              <div className="mt-8 rounded-[2rem] border border-[#bfdbfe] bg-white p-5 shadow-[0_24px_60px_rgba(15,23,42,0.08)]">
                <div className="flex items-start gap-4">
                  <div className="rounded-2xl bg-[#3b82f6]/10 p-3 text-[#3b82f6]">
                    <Target size={28} />
                  </div>
                  <div>
                    <p className="text-xl font-black font-headline">Foco da experiência</p>
                    <p className="mt-2 text-sm leading-7 text-[#667085]">
                      Mostrar valor clínico rápido, sem deixar a página com cara
                      de documentação técnica ou tela genérica de sistema.
                    </p>
                  </div>
                </div>
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              {clinicalFlow.map((item) => (
                <article
                  key={item.title}
                  className="group rounded-[2rem] border border-[#dbeafe] bg-white p-6 shadow-[0_24px_70px_rgba(15,23,42,0.08)] transition-all hover:-translate-y-1 hover:border-[#93c5fd] hover:shadow-[0_30px_80px_rgba(59,130,246,0.16)]"
                >
                  <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#3b82f6]/10 text-[#3b82f6] transition-colors group-hover:bg-[#3b82f6] group-hover:text-white">
                    <item.icon size={26} />
                  </div>
                  <h3 className="mt-6 text-2xl font-black tracking-[-0.03em] font-headline">
                    {item.title}
                  </h3>
                  <p className="mt-3 text-sm leading-7 text-[#667085]">
                    {item.text}
                  </p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="fluxo" className="bg-white py-24 text-[#101828]">
          <div className="mx-auto max-w-7xl px-5 md:px-8">
            <div className="grid gap-8 lg:grid-cols-[0.9fr_1.1fr] lg:items-end">
              <div>
                <p className="text-sm font-black uppercase tracking-[0.24em] text-[#3b82f6]">
                  Fluxo do módulo
                </p>
                <h2 className="mt-4 text-4xl font-black leading-tight tracking-[-0.04em] font-headline md:text-5xl">
                  Do cadastro ao relatório, tudo segue uma sequência lógica.
                </h2>
              </div>
              <p className="text-lg leading-8 text-[#667085]">
                A tela fica mais forte quando mostra como o profissional usaria
                o Heal+ na prática. Esse bloco cria uma narrativa simples e mais
                próxima de uma landing de produto.
              </p>
            </div>

            <div className="mt-12 grid gap-4 lg:grid-cols-4">
              {journeySteps.map((item) => (
                <article
                  key={item.step}
                  className="relative overflow-hidden rounded-[2rem] border border-[#dbeafe] bg-[#f7faff] p-6"
                >
                  <div className="absolute -right-8 -top-8 h-28 w-28 rounded-full bg-[#3b82f6]/10" />
                  <p className="text-5xl font-black text-[#3b82f6] font-headline">
                    {item.step}
                  </p>
                  <h3 className="mt-7 text-xl font-black tracking-[-0.02em] font-headline">
                    {item.title}
                  </h3>
                  <p className="mt-3 text-sm leading-7 text-[#667085]">
                    {item.text}
                  </p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="relative overflow-hidden bg-[linear-gradient(135deg,#08111d_0%,#0b1728_100%)] py-24 text-white">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(59,130,246,0.28),transparent_28%),radial-gradient(circle_at_78%_30%,rgba(115,168,255,0.18),transparent_24%)]" />
          <div className="relative mx-auto max-w-7xl px-5 md:px-8">
            <div className="grid gap-10 lg:grid-cols-[0.9fr_1.1fr] lg:items-center">
              <div>
                <p className="text-sm font-black uppercase tracking-[0.24em] text-[#9fc8ff]">
                  Cluster REDI-SUS
                </p>
                <h2 className="mt-4 text-4xl font-black leading-tight tracking-[-0.04em] font-headline md:text-5xl">
                  Um bloco de saúde digital dentro de uma arquitetura maior.
                </h2>
                <p className="mt-5 text-lg leading-8 text-white/70">
                  A proposta combina uma identidade visual limpa com mensagens
                  fortes de confiança, integração e evolução clínica.
                </p>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                {platformHighlights.map((item) => (
                  <article
                    key={item.title}
                    className="rounded-[2rem] border border-white/10 bg-white/[0.07] p-6 backdrop-blur-xl"
                  >
                    <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#3b82f6]/18 text-[#9fc8ff]">
                      <item.icon size={26} />
                    </div>
                    <h3 className="mt-5 text-xl font-black tracking-[-0.02em] font-headline">
                      {item.title}
                    </h3>
                    <p className="mt-3 text-sm leading-7 text-white/62">
                      {item.text}
                    </p>
                  </article>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section id="tecnologia" className="bg-[#f7faff] py-24 text-[#101828]">
          <div className="mx-auto max-w-7xl px-5 md:px-8">
            <div className="mb-12 flex flex-col justify-between gap-6 md:flex-row md:items-end">
              <div>
                <p className="text-sm font-black uppercase tracking-[0.24em] text-[#3b82f6]">
                  Base técnica
                </p>
                <h2 className="mt-4 max-w-2xl text-4xl font-black leading-tight tracking-[-0.04em] font-headline md:text-5xl">
                  Tecnologia clara, segura e pronta para evoluir.
                </h2>
              </div>
              <Link
                href="/referencias"
                className="inline-flex items-center gap-2 rounded-full border border-[#bfdbfe] bg-white px-5 py-3 text-sm font-black text-[#2563eb] shadow-[0_16px_40px_rgba(15,23,42,0.06)] transition-transform hover:-translate-y-0.5"
              >
                Referências do projeto
                <BookOpenCheck size={18} />
              </Link>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              {techItems.map((item) => (
                <article
                  key={item.label}
                  className="rounded-[2rem] border border-[#dbeafe] bg-white p-6 shadow-[0_24px_70px_rgba(15,23,42,0.07)]"
                >
                  <div className="flex items-start gap-4">
                    <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-[#3b82f6]/10 text-[#3b82f6]">
                      <item.icon size={25} />
                    </div>
                    <div>
                      <p className="text-sm font-black uppercase tracking-[0.16em] text-[#3b82f6]">
                        {item.label}
                      </p>
                      <p className="mt-3 text-lg font-black leading-7 tracking-[-0.02em] font-headline">
                        {item.value}
                      </p>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="bg-[#f7faff] px-5 py-20 md:px-8">
          <div className="mx-auto max-w-7xl overflow-hidden rounded-[2.4rem] bg-[radial-gradient(circle_at_18%_20%,rgba(115,168,255,0.34),transparent_30%),linear-gradient(135deg,#06101c_0%,#0b1728_100%)] p-8 text-white shadow-[0_30px_90px_rgba(6,16,28,0.22)] md:p-12">
            <div className="grid gap-8 lg:grid-cols-[1fr_auto] lg:items-center">
              <div>
                <p className="text-sm font-black uppercase tracking-[0.24em] text-[#9fc8ff]">
                  Próximo passo
                </p>
                <h2 className="mt-4 max-w-3xl text-4xl font-black leading-tight tracking-[-0.04em] font-headline md:text-5xl">
                  Leve o acompanhamento de feridas para uma experiência mais clara, visual e segura.
                </h2>
              </div>
              <Link
                href="/login"
                className="inline-flex items-center justify-center gap-2 rounded-full bg-[linear-gradient(135deg,#3b82f6,#73a8ff)] px-8 py-4 text-base font-black text-white shadow-[0_20px_42px_rgba(59,130,246,0.32)] transition-transform hover:-translate-y-0.5"
              >
                Acessar módulo
                <ArrowRight size={20} strokeWidth={3} />
              </Link>
            </div>
          </div>
        </section>

        <section id="faq" className="bg-white py-24 text-[#101828]">
          <div className="mx-auto max-w-4xl px-5 md:px-8">
            <div className="text-center">
              <p className="text-sm font-black uppercase tracking-[0.24em] text-[#3b82f6]">
                Dúvidas Frequentes
              </p>
              <h2 className="mt-4 text-4xl font-black leading-tight tracking-[-0.04em] font-headline md:text-5xl">
                Tire suas dúvidas sobre o Heal+
              </h2>
            </div>
            <div className="mt-12 grid gap-4">
              {[
                {
                  question: "O Heal+ é gratuito?",
                  answer: "O Heal+ é um módulo integrado ao ambiente REDI-SUS e seu acesso é regulado pelas diretrizes do cluster parceiro."
                },
                {
                  question: "Preciso de um equipamento especial?",
                  answer: "Não. O registro de imagens pode ser realizado utilizando a câmera nativa de dispositivos móveis como tablets e smartphones da instituição."
                },
                {
                  question: "Os dados dos pacientes ficam seguros?",
                  answer: "Sim. A aplicação foi desenhada considerando LGPD, anonimização e RBAC (Role-Based Access Control) robustos."
                },
                {
                  question: "O módulo já faz diagnósticos por IA?",
                  answer: "No momento, preparamos a base da inteligência. Os modelos e segmentações estão em desenvolvimento, e a documentação serve de alicerce para tal."
                }
              ].map((faq, idx) => (
                <details key={idx} className="group rounded-[1.5rem] border border-[#dbeafe] bg-[#f7faff] p-6 open:bg-white open:shadow-[0_24px_70px_rgba(15,23,42,0.08)]">
                  <summary className="flex cursor-pointer items-center justify-between text-lg font-black font-headline">
                    {faq.question}
                    <span className="ml-4 transition-transform group-open:rotate-180 text-[#3b82f6]">
                      <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" className="lucide lucide-chevron-down"><path d="m6 9 6 6 6-6"/></svg>
                    </span>
                  </summary>
                  <p className="mt-4 text-sm leading-7 text-[#667085]">
                    {faq.answer}
                  </p>
                </details>
              ))}
            </div>
          </div>
        </section>
      </main>

      <footer className="relative overflow-hidden bg-[#06101c] text-white">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_16%_18%,rgba(59,130,246,0.16),transparent_22%),radial-gradient(circle_at_85%_22%,rgba(124,168,255,0.14),transparent_20%)]" />

        <div className="relative z-10 mx-auto max-w-7xl px-5 py-16 md:px-8">
          <div className="grid gap-10 border-b border-white/12 pb-12 lg:grid-cols-[0.8fr_1.2fr]">
            <div>
              <div className="flex items-center gap-3">
                <Image src="/images/logo.png" alt="Heal+" width={52} height={52} />
                <p className="text-4xl font-black text-[#73a8ff] font-headline">
                  Heal+
                </p>
              </div>
              <p className="mt-5 max-w-md text-sm font-medium leading-7 text-white/70">
                Módulo de saúde digital do cluster REDI-SUS para apoio à
                avaliação, acompanhamento e documentação de feridas crônicas.
              </p>
            </div>

            <div className="grid gap-8 sm:grid-cols-3">
              <div>
                <p className="text-sm font-black uppercase tracking-[0.2em] text-[#9fd0ff]">
                  Projeto
                </p>
                <a href="#projeto" className="mt-5 block text-lg font-black hover:text-[#9fd0ff]">
                  O projeto
                </a>
                <a href="#plataforma" className="mt-3 block text-lg font-black hover:text-[#9fd0ff]">
                  Plataforma
                </a>
              </div>
              <div>
                <p className="text-sm font-black uppercase tracking-[0.2em] text-[#9fd0ff]">
                  Tecnologia
                </p>
                <a href="#tecnologia" className="mt-5 block text-lg font-black hover:text-[#9fd0ff]">
                  Base técnica
                </a>
                <Link href="/referencias" className="mt-3 block text-lg font-black hover:text-[#9fd0ff]">
                  Referências
                </Link>
              </div>
              <div>
                <p className="text-sm font-black uppercase tracking-[0.2em] text-[#9fd0ff]">
                  Acesso
                </p>
                <Link href="/login" className="mt-5 block text-lg font-black hover:text-[#9fd0ff]">
                  Área clínica
                </Link>
                <a href="#instituicoes" className="mt-3 block text-lg font-black hover:text-[#9fd0ff]">
                  Instituições
                </a>
              </div>
            </div>
          </div>

          <div className="flex flex-col justify-between gap-5 pt-8 text-sm font-bold text-white/62 md:flex-row md:items-center">
            <p>&copy; {new Date().getFullYear()} HEAL+ REDI-SUS. Pesquisa aplicada em saúde digital.</p>
            <div className="flex flex-wrap gap-5">
              <a href="#projeto" className="hover:text-white">
                O projeto
              </a>
              <a href="#plataforma" className="hover:text-white">
                Plataforma
              </a>
              <Link href="/login" className="hover:text-white">
                Área clínica
              </Link>
            </div>
          </div>
        </div>
      </footer>

      <section
        id="instituicoes"
        aria-labelledby="institutional-support-title"
        className="border-t border-[#e5eefc] bg-white py-14 text-[#11113d]"
      >
        <div className="mx-auto max-w-7xl px-5 md:px-8">
          <div className="mx-auto max-w-3xl text-center">
      
          </div>

          <div className="mt-10">
            <div className="grid grid-cols-1 divide-y divide-[#dbeafe] md:grid-cols-4 md:divide-x md:divide-y-0">
              {institutionalLogos.map((logo) => (
                <div
                  key={logo.name}
                  className="flex min-h-[170px] items-center justify-center px-8 py-8"
                >
                  <Image
                    src={logo.src}
                    alt={logo.alt}
                    width={logo.width}
                    height={logo.height}
                    className={`${logo.className} object-contain`}
                  />
                </div>
              ))}

              <div className="flex min-h-[170px] items-center justify-center px-8 py-8">
                <div className="flex items-center gap-3">
                  <Image
                    src="/images/logo.png"
                    alt="Logo do Heal+"
                    width={76}
                    height={76}
                    className="h-16 w-16 md:h-20 md:w-20"
                  />
                  <span className="text-4xl font-black text-[#3b82f6] font-headline md:text-5xl">
                    Heal+
                  </span>
                </div>
              </div>
            </div>
          </div>

          <p className="mt-8 text-center text-sm font-medium text-[#667085]">
            Projeto desenvolvido com apoio institucional da RNP, Fatec Ferraz de Vasconcelos e Centro Paula Souza.
          </p>
        </div>
      </section>
    </div>
  );
}