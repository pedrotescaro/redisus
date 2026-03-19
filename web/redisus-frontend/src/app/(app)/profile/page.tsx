"use client";

import { useEffect, useState } from "react";
import { onAuthStateChanged, type User } from "firebase/auth";
import { auth } from "@/lib/firebase";

export default function ProfilePage() {
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (authUser) => {
      setUser(authUser);
    });
    return () => unsubscribe();
  }, []);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-extrabold font-headline text-on-surface">
          Perfil
        </h1>
        <p className="text-on-surface-variant mt-1">
          Gerencie suas informações pessoais
        </p>
      </div>

      {/* Profile Card */}
      <div className="bg-surface-container-low rounded-xl p-8 border border-outline-variant/5">
        <div className="flex items-start gap-6">
          {/* Avatar */}
          <div className="w-24 h-24 rounded-full bg-primary/10 flex items-center justify-center text-primary flex-shrink-0 border-4 border-primary-container/20">
            {user?.photoURL ? (
              <img
                src={user.photoURL}
                alt="Profile"
                className="w-full h-full rounded-full object-cover"
              />
            ) : (
              <span className="material-symbols-outlined text-5xl">
                person
              </span>
            )}
          </div>

          {/* Info */}
          <div className="flex-grow">
            <h2 className="text-2xl font-bold font-headline text-on-surface">
              {user?.displayName || user?.email?.split("@")[0] || "Usuário"}
            </h2>
            <p className="text-on-surface-variant mt-1">{user?.email}</p>
            <div className="flex items-center gap-2 mt-3">
              <span className="text-xs font-bold text-primary bg-primary/10 px-3 py-1 rounded-full">
                Profissional de Saúde
              </span>
              {user?.emailVerified && (
                <span className="text-xs font-bold text-tertiary bg-tertiary/10 px-3 py-1 rounded-full flex items-center gap-1">
                  <span className="material-symbols-outlined text-sm">
                    verified
                  </span>
                  Verificado
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="mt-8 pt-8 border-t border-outline-variant/10 grid gap-6 md:grid-cols-2">
          <div>
            <p className="text-xs font-bold uppercase tracking-wider text-gray-500 mb-2">
              ID da Conta
            </p>
            <p className="text-on-surface font-mono text-sm bg-surface-container-high px-4 py-2 rounded-lg">
              {user?.uid?.slice(0, 20)}...
            </p>
          </div>
          <div>
            <p className="text-xs font-bold uppercase tracking-wider text-gray-500 mb-2">
              Último Login
            </p>
            <p className="text-on-surface text-sm bg-surface-container-high px-4 py-2 rounded-lg">
              {user?.metadata?.lastSignInTime
                ? new Date(user.metadata.lastSignInTime).toLocaleDateString(
                    "pt-BR",
                    {
                      day: "2-digit",
                      month: "long",
                      year: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    }
                  )
                : "N/A"}
            </p>
          </div>
        </div>
      </div>

      {/* Coming Soon Features */}
      <section className="bg-surface-container-low rounded-xl p-12 text-center border border-dashed border-outline-variant/20">
        <div className="max-w-md mx-auto space-y-4">
          <div className="w-16 h-16 bg-surface-container-high rounded-full flex items-center justify-center mx-auto mb-4">
            <span className="material-symbols-outlined text-3xl text-gray-600">
              build
            </span>
          </div>
          <h3 className="text-xl font-bold font-headline">
            Mais opções em breve
          </h3>
          <p className="text-on-surface-variant font-body text-sm">
            Edição de perfil, upload de foto, configurações de notificações e
            preferências de acessibilidade serão adicionadas em breve.
          </p>
        </div>
      </section>
    </div>
  );
}
