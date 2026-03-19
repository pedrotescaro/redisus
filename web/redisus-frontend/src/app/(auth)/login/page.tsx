import { LoginForm } from "@/components/auth/login-form";

export default function LoginPage() {
  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-10">
      <div className="grid w-full max-w-5xl overflow-hidden rounded-3xl bg-white shadow-soft lg:grid-cols-2">
        <section className="relative hidden bg-brand-700 p-10 text-white lg:block">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(255,255,255,0.2),transparent_50%)]" />
          <div className="relative z-10 flex h-full flex-col justify-between">
            <div>
              <span className="inline-flex rounded-full border border-white/35 px-3 py-1 text-xs font-medium tracking-[0.2em]">
                REDISUS HEAL+
              </span>
              <h1 className="mt-8 text-4xl font-semibold leading-tight text-white">
                Monitoramento inteligente de pacientes com feridas crônicas.
              </h1>
              <p className="mt-4 max-w-md text-base text-brand-100">
                Acesse seu painel clínico para registrar avaliações, acompanhar a evolução de lesões e integrar análise neural em instantes.
              </p>
            </div>
            <p className="text-sm font-medium text-brand-100">Ambiente seguro para equipes multiprofissionais.</p>
          </div>
        </section>
        <section className="flex flex-col justify-center p-8 md:p-14 bg-white">
          <LoginForm />
        </section>
      </div>
    </main>
  );
}
