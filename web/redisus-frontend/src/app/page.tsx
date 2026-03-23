import Link from "next/link";
import Image from "next/image";
import { ThemeToggle } from "@/components/theme-toggle";

const featureItems = [
  {
    icon: "auto_awesome",
    title: "Análise Inteligente",
    description:
      "Pipeline em dois estágios (detecção + diagnóstico) para apoiar a avaliação tecidual e etiológica de feridas crônicas.",
  },
  {
    icon: "description",
    title: "Laudo Clínico Estruturado",
    description:
      "Geração de relatório com composição tecidual, classificação e indicadores clínicos para apoiar conduta e rastreabilidade.",
  },
  {
    icon: "hub",
    title: "Plataforma Clínica Unificada",
    description:
      "Conexão entre avaliação, comparação e relatório clínico estruturado na jornada digital de feridas.",
  },
];

const benefits = [
  {
    icon: "schedule",
    title: "Padronização do Cuidado",
    text: "Reduz subjetividade na avaliação por imagem e apoia decisões clínicas mais consistentes entre equipes.",
  },
  {
    icon: "biotech",
    title: "Pesquisa Translacional",
    text: "Conecta pesquisa aplicada, validação multicêntrica e evolução tecnológica para uso real clínico.",
  },
  {
    icon: "rebase_edit",
    title: "Escalabilidade da Plataforma",
    text: "Arquitetura modular para evolução progressiva de integrações e serviços clínicos.",
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
                <p className="mt-0.5 text-[10px] font-bold uppercase tracking-widest text-on-surface-variant opacity-70">Plataforma Clínica</p>
            </div>
          </Link>

          <div className="hidden items-center gap-8 md:flex">
            <a
              href="#funcionalidades"
              className="group relative text-sm font-semibold text-on-surface-variant transition-colors hover:text-primary focus:text-primary focus:outline-none"
            >
              Funcionalidades
              <span className="absolute -bottom-1 left-0 h-0.5 w-full origin-left scale-x-0 bg-primary transition-transform duration-200 group-hover:scale-x-100 group-focus:scale-x-100" />
            </a>
            <a
              href="#beneficios"
              className="group relative text-sm font-semibold text-on-surface-variant transition-colors hover:text-primary focus:text-primary focus:outline-none"
            >
              Benefícios
              <span className="absolute -bottom-1 left-0 h-0.5 w-full origin-left scale-x-0 bg-primary transition-transform duration-200 group-hover:scale-x-100 group-focus:scale-x-100" />
            </a>
            <a
              href="#sobre"
              className="group relative text-sm font-semibold text-on-surface-variant transition-colors hover:text-primary focus:text-primary focus:outline-none"
            >
              Sobre
              <span className="absolute -bottom-1 left-0 h-0.5 w-full origin-left scale-x-0 bg-primary transition-transform duration-200 group-hover:scale-x-100 group-focus:scale-x-100" />
            </a>
          </div>

          <div className="flex items-center gap-3">
            <ThemeToggle />
            <Link
              href="/login"
              className="px-4 py-2 text-sm font-semibold text-on-surface-variant hover:text-on-surface transition-colors"
            >
              Login
            </Link>
            <Link
              href="/login"
              className="rounded-xl bg-primary-container px-5 py-2.5 text-sm font-bold text-on-primary-container shadow-ambient hover:brightness-110 transition-all"
            >
              Começar
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
              Pesquisa aplicada em saúde digital
            </div>
            <h1 className="mt-6 text-5xl font-extrabold tracking-tight font-headline md:text-7xl">
              HEAL+: <span className="text-primary">IA para avaliação de feridas</span>
            </h1>
            <p className="mx-auto mt-6 max-w-3xl text-lg leading-relaxed text-on-surface-variant md:text-xl">
              Plataforma de pesquisa para apoio ao diagnóstico e monitoramento de feridas crônicas, com visão
              computacional, modelos de deep learning e foco em interoperabilidade clínica incremental.
            </p>
            <div className="mt-8 flex flex-col items-center justify-center gap-4 sm:flex-row">
              <Link
                href="/login"
                className="w-full rounded-xl bg-primary-container px-10 py-4 text-center text-lg font-bold text-on-primary-container shadow-ambient sm:w-auto"
              >
                Acessar Plataforma
              </Link>
              <a
                href="#funcionalidades"
                className="w-full rounded-xl border border-outline-variant/20 px-10 py-4 text-center text-lg font-bold hover:bg-surface-container-low transition-colors sm:w-auto"
              >
                Ver Funcionalidades
              </a>
            </div>
          </div>

          <div className="relative z-10 mx-auto mt-14 w-full max-w-6xl">
            <div className="rounded-2xl bg-surface-container-low p-3 shadow-ambient ghost-border">
              <div className="flex h-[320px] items-center justify-center rounded-xl bg-gradient-to-br from-surface-container-high to-surface-container">
                <div className="text-center">
                  <span className="material-symbols-outlined text-6xl text-primary">monitoring</span>
                  <p className="mt-3 text-sm font-semibold tracking-wide text-on-surface-variant">
                    Dashboard clínico do HEAL+
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section id="funcionalidades" className="mx-auto max-w-7xl px-6 py-20">
          <div className="mb-12 space-y-3 text-center">
            <h2 className="text-3xl font-bold font-headline md:text-4xl">Tecnologia para Cuidado Baseado em Evidências</h2>
            <p className="mx-auto max-w-2xl text-on-surface-variant">
              Componentes alinhados ao escopo técnico-científico do projeto e à jornada clínica.
            </p>
          </div>

          <div className="grid gap-6 md:grid-cols-12">
            <article className="rounded-2xl bg-surface-container p-8 shadow-ambient ghost-border md:col-span-8">
              <div className="w-12 h-12 rounded-xl bg-primary/10 text-primary flex items-center justify-center">
                <span className="material-symbols-outlined">auto_awesome</span>
              </div>
              <h3 className="mt-5 text-2xl font-bold font-headline">Pipeline de IA em Dois Estágios</h3>
              <p className="mt-3 max-w-xl text-on-surface-variant">
                Detecção em tempo real para localização da lesão e diagnóstico aprofundado para segmentação,
                classificação e apoio à decisão clínica.
              </p>
              <div className="mt-8 rounded-xl bg-surface-container-high p-8">
                <p className="text-sm text-on-surface-variant">
                  YOLO, U-Net, ResNet/Ensemble, MedSAM e explicabilidade com Grad-CAM.
                </p>
              </div>
            </article>

            <article className="rounded-2xl bg-surface-container-low p-8 ghost-border md:col-span-4">
              <div className="w-12 h-12 rounded-xl bg-tertiary/10 text-tertiary flex items-center justify-center">
                <span className="material-symbols-outlined">description</span>
              </div>
              <h3 className="mt-5 text-2xl font-bold font-headline">Dados Clínicos Estruturados</h3>
              <p className="mt-3 text-on-surface-variant">
                Estrutura de dados canônica para rastreabilidade, comparação longitudinal e geração de laudos.
              </p>
              <div className="mt-6 space-y-2 border-t border-outline-variant/15 pt-4">
                <p className="text-xs uppercase tracking-widest text-primary">Modelo clínico versionado</p>
                <p className="text-xs uppercase tracking-widest text-primary">APIs REST + Relatórios</p>
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
              Plataforma acadêmica em evolução contínua
            </h2>
            <p className="mx-auto mt-5 max-w-2xl text-lg text-on-surface-variant">
              O HEAL+ está em nível TRL 4-5 e é destinado a pesquisa e apoio à decisão. Não substitui avaliação
              clínica profissional.
            </p>
            <div className="mt-10 flex flex-col justify-center gap-4 sm:flex-row">
              <Link
                href="/login"
                className="rounded-xl bg-primary-container px-12 py-4 text-lg font-bold text-on-primary-container"
              >
                Entrar no Sistema
              </Link>
              <Link
                href="/login"
                className="rounded-xl border border-outline-variant/30 px-12 py-4 text-lg font-bold hover:bg-surface-container-high transition-colors"
              >
                Ver Módulos Internos
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
              Módulo clínico para apoio ao diagnóstico, plano de cuidado e monitoramento.
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
              Benefícios
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
