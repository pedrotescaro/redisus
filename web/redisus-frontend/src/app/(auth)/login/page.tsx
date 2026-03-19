import Image from "next/image";
import { LoginForm } from "@/components/auth/login-form";

export default function LoginPage() {
  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-10 bg-surface">
      <div className="grid w-full max-w-5xl overflow-hidden rounded-2xl bg-surface-container-lowest shadow-2xl lg:grid-cols-2 border border-outline-variant/10">
        <section className="relative hidden bg-gradient-to-br from-primary-container to-primary-container/80 p-10 text-on-primary-container lg:block">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(255,255,255,0.15),transparent_50%)]" />
          <div className="absolute -right-32 -bottom-32 w-96 h-96 bg-primary/20 rounded-full blur-[100px]"></div>
          <div className="relative z-10 flex h-full flex-col justify-between">
            <div>
              <div className="flex items-center gap-3 mb-8">
                <Image
                  src="/images/logo.png"
                  alt="Heal+ Logo"
                  width={72}
                  height={72}
                  className="drop-shadow-lg"
                />
                <span className="inline-flex rounded-full border border-white/25 px-4 py-1.5 text-xs font-bold tracking-[0.2em] bg-white/10">
                  REDISUS HEAL+
                </span>
              </div>
              <h1 className="text-4xl font-extrabold leading-tight font-headline">
                Monitoramento inteligente de pacientes com feridas crônicas.
              </h1>
              <p className="mt-4 max-w-md text-base opacity-90 font-body">
                Acesse seu painel clínico para registrar avaliações, acompanhar
                a evolução de lesões e integrar análise neural em instantes.
              </p>
            </div>
            <p className="text-sm font-semibold opacity-80">
              Ambiente seguro para equipes multiprofissionais.
            </p>
          </div>
        </section>
        <section className="flex flex-col justify-center p-8 md:p-14 bg-surface-container-lowest">
          <LoginForm />
        </section>
      </div>
    </main>
  );
}
