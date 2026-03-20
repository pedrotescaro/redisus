"use client";

import { useEffect, useState } from "react";
import { onAuthStateChanged, type User, updateProfile } from "firebase/auth";
import { getDownloadURL, ref, uploadBytes } from "firebase/storage";
import { auth, storage } from "@/lib/firebase";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function ProfilePage() {
  const [user, setUser] = useState<User | null>(null);
  const [displayName, setDisplayName] = useState("");
  const [savingName, setSavingName] = useState(false);
  const [uploadingPhoto, setUploadingPhoto] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (authUser) => {
      setUser(authUser);
      setDisplayName(authUser?.displayName ?? "");
    });
    return () => unsubscribe();
  }, []);

  const handleUpdateProfile = async () => {
    if (!auth.currentUser) return;
    setSavingName(true);
    setStatusMessage(null);
    try {
      await updateProfile(auth.currentUser, { displayName: displayName.trim() });
      setStatusMessage("Nome de perfil atualizado com sucesso.");
    } catch {
      setStatusMessage("Nao foi possivel atualizar o nome do perfil.");
    } finally {
      setSavingName(false);
    }
  };

  const handlePhotoUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file || !auth.currentUser) return;

    setUploadingPhoto(true);
    setStatusMessage(null);
    try {
      const avatarRef = ref(storage, `avatars/${auth.currentUser.uid}/${Date.now()}-${file.name}`);
      await uploadBytes(avatarRef, file, { contentType: file.type });
      const photoURL = await getDownloadURL(avatarRef);
      await updateProfile(auth.currentUser, { photoURL });
      setStatusMessage("Foto de perfil atualizada com sucesso.");
    } catch {
      setStatusMessage("Nao foi possivel enviar a foto de perfil.");
    } finally {
      setUploadingPhoto(false);
    }
  };

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
            <div className="mt-4 flex items-center gap-3">
              <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg bg-surface-container-high px-3 py-2 text-sm">
                <span className="material-symbols-outlined text-base">photo_camera</span>
                {uploadingPhoto ? "Enviando..." : "Trocar foto"}
                <input
                  type="file"
                  accept="image/*"
                  className="hidden"
                  disabled={uploadingPhoto}
                  onChange={(event) => void handlePhotoUpload(event)}
                />
              </label>
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

        <div className="mt-8 pt-8 border-t border-outline-variant/10 space-y-4">
          <p className="text-xs font-bold uppercase tracking-wider text-gray-500">Editar perfil</p>
          <div className="grid gap-3 md:grid-cols-[1fr_auto]">
            <Input
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              placeholder="Digite seu nome de exibicao"
            />
            <Button
              type="button"
              onClick={() => void handleUpdateProfile()}
              disabled={savingName || !displayName.trim()}
            >
              {savingName ? "Salvando..." : "Salvar nome"}
            </Button>
          </div>
        </div>
      </div>

      <section className="bg-surface-container-low rounded-xl p-6 border border-outline-variant/10">
        <h3 className="text-xl font-bold font-headline">Preferencias da conta</h3>
        <p className="text-on-surface-variant text-sm mt-1">
          Configure notificacoes e acessibilidade na pagina de configuracoes.
        </p>
      </section>

      {statusMessage && (
        <div className="rounded-xl bg-primary/10 text-primary px-4 py-3 text-sm font-medium">
          {statusMessage}
        </div>
      )}
    </div>
  );
}
