import { AlertCircle } from 'lucide-react';

import { missingFirebaseEnv } from '../../lib/firebase';
import { BrandLogo } from '../brand/BrandLogo';

export function FirebaseConfigError() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-heal-canvas px-4 py-10">
      <section className="w-full max-w-2xl rounded-[1.75rem] border border-heal-line bg-white p-8 shadow-soft">
        <BrandLogo />
        <div className="mt-8 flex gap-4 rounded-2xl bg-red-50 p-5 text-red-700">
          <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" />
          <div>
            <h1 className="text-lg font-black">Firebase não configurado</h1>
            <p className="mt-2 text-sm leading-6">
              Crie um arquivo <code className="font-bold">.env.local</code> a partir do <code className="font-bold">.env.example</code>.
              A aplicação não usa dados mockados nem fallback silencioso como banco principal.
            </p>
          </div>
        </div>
        <div className="mt-5 rounded-2xl border border-heal-line bg-slate-50 p-4">
          <p className="text-sm font-black text-heal-ink">Variáveis ausentes</p>
          <ul className="mt-3 grid gap-2 text-sm text-heal-muted sm:grid-cols-2">
            {missingFirebaseEnv.map(key => (
              <li key={key} className="rounded-xl bg-white px-3 py-2 font-mono text-xs">
                {key}
              </li>
            ))}
          </ul>
        </div>
      </section>
    </main>
  );
}
