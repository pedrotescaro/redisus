import Link from "next/link";
import Image from "next/image";

const featureItems = [
  {
    icon: "auto_awesome",
    title: "Analise Inteligente",
    description:
      "Medicao de feridas baseada em imagem com suporte de IA para avaliar tecido, profundidade e evolucao clinica.",
  },
  {
    icon: "description",
    title: "Relatorios Automaticos",
    description:
      "Gere documentos clinicos em segundos, com padrao para auditoria e exportacao PDF.",
  },
  {
    icon: "manage_search",
    title: "Hub de Busca IA",
    description:
      "Busque informacoes em historicos e condutas com linguagem natural em um unico painel.",
  },
];

const benefits = [
  {
    icon: "schedule",
    title: "Tempo de Cuidado",
    text: "Reduza tarefas manuais e aumente o foco no paciente durante toda a jornada de tratamento.",
  },
  {
    icon: "biotech",
    title: "Precisao Clinica",
    text: "Padronize avaliacao e reduza subjetividade com dados mais consistentes e rastreaveis.",
  },
  {
    icon: "rebase_edit",
    title: "Workflow Simplificado",
    text: "Experiencia fluida que se adapta a rotina de clinicas, hospitais e equipes multiprofissionais.",
  },
];

export default function HomePage() {
  return (
    <div className="min-h-screen bg-surface text-on-surface">
      <nav className="fixed top-0 z-50 w-full bg-surface/80 backdrop-blur-xl shadow-ambient">
        <div className="mx-auto flex h-16 w-full max-w-7xl items-center justify-between px-6">
          <Link href="/" className="group flex items-center gap-2">
            <Image
              src="/images/logo.png"
              alt="Heal+ Logo"
              width={56}
              height={56}
              className="transition-transform group-hover:scale-105"
            />
            <div className="-ml-1">
              <h1 className="text-2xl font-extrabold leading-none tracking-tight text-primary font-headline">
                Heal+
              </h1>
              <p className="mt-0.5 text-[10px] font-bold uppercase tracking-widest text-on-surface-variant opacity-70">
                 REDI-SUS
              </p>
            </div>
          </Link>

          <div className="hidden items-center gap-8 md:flex">
            <a href="#funcionalidades" className="text-sm font-semibold text-primary">
              Funcionalidades
            </a>
            <a
              href="#beneficios"
              className="text-sm font-semibold text-on-surface-variant hover:text-on-surface transition-colors"
            >
              Beneficios
            </a>
            <a
              href="#sobre"
              className="text-sm font-semibold text-on-surface-variant hover:text-on-surface transition-colors"
            >
              Sobre
            </a>
          </div>

          <div className="flex items-center gap-3">
            <Link
              href="/login"
              className="px-4 py-2 text-sm font-semibold text-on-surface-variant hover:text-on-surface transition-colors"
            >
              Login
            </Link>
            <Link
              href="/login"
              className="rounded-xl bg-primary-container px-5 py-2.5 text-sm font-bold text-on-primary-container shadow-ambient"
            >
              Comecar
            </Link>
          </div>
        </div>
      </nav>

      <main className="pt-24">
        <section id="sobre" className="relative overflow-hidden px-6 pb-16 pt-10">
          <div className="pointer-events-none absolute left-1/2 top-1/2 h-[420px] w-[800px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-primary/10 blur-[120px]" />
          <div className="relative z-10 mx-auto max-w-5xl text-center">
            <div className="inline-flex items-center gap-2 rounded-full bg-surface-container-high px-4 py-1.5 text-xs font-bold uppercase tracking-widest text-primary ghost-border">
              <span className="material-symbols-outlined text-sm">auto_awesome</span>
              A proxima geracao de cuidado clinico
            </div>
            <h1 className="mt-6 text-5xl font-extrabold tracking-tight font-headline md:text-7xl">
              A Revolucao na Gestao de <span className="text-primary">Feridas com IA</span>
            </h1>
            <p className="mx-auto mt-6 max-w-3xl text-lg leading-relaxed text-on-surface-variant md:text-xl">
              Otimize o cuidado clinico, automatize relatorios e melhore desfechos com o modulo Heal+ dentro do
              ecossistema Redi-SUS.
            </p>
            <div className="mt-8 flex flex-col items-center justify-center gap-4 sm:flex-row">
              <Link
                href="/login"
                className="w-full rounded-xl bg-primary-container px-10 py-4 text-center text-lg font-bold text-on-primary-container shadow-ambient sm:w-auto"
              >
                Comecar Gratis
              </Link>
              <a
                href="#funcionalidades"
                className="w-full rounded-xl border border-outline-variant/20 px-10 py-4 text-center text-lg font-bold hover:bg-surface-container-low transition-colors sm:w-auto"
              >
                Ver Demonstracao
              </a>
            </div>
          </div>

          <div className="relative z-10 mx-auto mt-14 w-full max-w-6xl">
            <div className="rounded-2xl bg-surface-container-low p-3 shadow-ambient ghost-border">
              <div className="flex h-[320px] items-center justify-center rounded-xl bg-gradient-to-br from-surface-container-high to-surface-container">
                <div className="text-center">
                  <span className="material-symbols-outlined text-6xl text-primary">monitoring</span>
                  <p className="mt-3 text-sm font-semibold tracking-wide text-on-surface-variant">
                    Dashboard Clinico Heal+ no Redi-SUS
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section id="funcionalidades" className="mx-auto max-w-7xl px-6 py-20">
          <div className="mb-12 space-y-3 text-center">
            <h2 className="text-3xl font-bold font-headline md:text-4xl">Tecnologia que Salva Vidas</h2>
            <p className="mx-auto max-w-2xl text-on-surface-variant">
              Ferramentas de precisao desenhadas para a realidade do profissional de saude moderno.
            </p>
          </div>

          <div className="grid gap-6 md:grid-cols-12">
            <article className="rounded-2xl bg-surface-container p-8 shadow-ambient ghost-border md:col-span-8">
              <div className="w-12 h-12 rounded-xl bg-primary/10 text-primary flex items-center justify-center">
                <span className="material-symbols-outlined">auto_awesome</span>
              </div>
              <h3 className="mt-5 text-2xl font-bold font-headline">Analise Inteligente</h3>
              <p className="mt-3 max-w-xl text-on-surface-variant">
                Medicao de feridas com apoio de IA para avaliar padroes de cicatrizacao e apoiar decisoes baseadas em
                evidencias.
              </p>
              <div className="mt-8 rounded-xl bg-surface-container-high p-8">
                <p className="text-sm text-on-surface-variant">Visao assistida para acompanhamento longitudinal.</p>
              </div>
            </article>

            <article className="rounded-2xl bg-surface-container-low p-8 ghost-border md:col-span-4">
              <div className="w-12 h-12 rounded-xl bg-tertiary/10 text-tertiary flex items-center justify-center">
                <span className="material-symbols-outlined">description</span>
              </div>
              <h3 className="mt-5 text-2xl font-bold font-headline">Relatorios Automaticos</h3>
              <p className="mt-3 text-on-surface-variant">
                Gere documentacao clinica completa em segundos, pronta para auditoria e compartilhamento.
              </p>
              <div className="mt-6 space-y-2 border-t border-outline-variant/15 pt-4">
                <p className="text-xs uppercase tracking-widest text-primary">Padronizacao TISS/TUSS</p>
                <p className="text-xs uppercase tracking-widest text-primary">Exportacao PDF</p>
              </div>
            </article>

            {featureItems.map((item) => (
              <article key={item.title} className="rounded-2xl bg-surface-container p-8 ghost-border md:col-span-4">
                <div className="w-12 h-12 rounded-xl bg-primary/10 text-primary flex items-center justify-center">
                  <span className="material-symbols-outlined">{item.icon}</span>
                </div>
                <h3 className="mt-5 text-xl font-bold font-headline">{item.title}</h3>
                <p className="mt-2 text-on-surface-variant">{item.description}</p>
              </article>
            ))}
          </div>
        </section>

        <section id="beneficios" className="bg-surface-container-low py-20">
          <div className="mx-auto grid max-w-7xl gap-10 px-6 md:grid-cols-3">
            {benefits.map((benefit) => (
              <article key={benefit.title}>
                <span className="material-symbols-outlined text-4xl text-primary">{benefit.icon}</span>
                <h4 className="mt-4 text-xl font-bold font-headline">{benefit.title}</h4>
                <p className="mt-2 text-sm leading-relaxed text-on-surface-variant">{benefit.text}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="px-6 py-24">
          <div className="mx-auto max-w-4xl rounded-2xl border border-outline-variant/10 bg-surface-container/50 p-12 text-center shadow-ambient">
            <h2 className="text-3xl font-extrabold font-headline md:text-5xl">
              Pronto para elevar o padrao do seu cuidado clinico?
            </h2>
            <p className="mx-auto mt-5 max-w-2xl text-lg text-on-surface-variant">
              Junte-se a equipes que estao transformando a gestao de feridas com o Heal+ no Redi-SUS.
            </p>
            <div className="mt-10 flex flex-col justify-center gap-4 sm:flex-row">
              <Link
                href="/login"
                className="rounded-xl bg-primary-container px-12 py-4 text-lg font-bold text-on-primary-container"
              >
                Agendar Demonstracao
              </Link>
              <Link
                href="/login"
                className="rounded-xl border border-outline-variant/30 px-12 py-4 text-lg font-bold hover:bg-surface-container-high transition-colors"
              >
                Falar com Especialista
              </Link>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-outline-variant/10 bg-surface py-10">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-6 px-6 md:flex-row">
          <div>
            <p className="text-lg font-bold font-headline text-primary">Heal+</p>
            <p className="text-xs uppercase tracking-widest text-on-surface-variant">
              Modulo Redi-SUS para cuidado clinico e gestao de feridas.
            </p>
          </div>
          <div className="flex flex-wrap justify-center gap-6 text-xs uppercase tracking-widest text-on-surface-variant">
            <a href="#sobre" className="hover:text-on-surface transition-colors">
              Sobre
            </a>
            <a href="#funcionalidades" className="hover:text-on-surface transition-colors">
              Funcionalidades
            </a>
            <a href="#beneficios" className="hover:text-on-surface transition-colors">
              Beneficios
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
