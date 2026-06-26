import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import {
  UserRound,
  Sun,
  Moon,
  Bell,
  LogOut,
  ChevronRight,
  ArrowLeft,
  Search,
  X,
  Upload,
  Check,
  AlertCircle,
  Mail,
  Building2,
  Phone,
  Briefcase
} from 'lucide-react';

import { useAuth } from '../../app/providers/AuthProvider';
import { useTheme } from '../../app/providers/ThemeProvider';
import { Input } from '../../components/ui/input';
import { logout } from '../auth/authService';
import {
  profileSchema,
  type ProfileFormValues,
  updateProfileData,
  uploadProfilePhoto,
  updateSettings
} from '../profile/profileService';

export function SettingsPage() {
  const { user, profile } = useAuth();
  const { theme, setTheme } = useTheme();
  const navigate = useNavigate();
  const settings = profile?.settings;

  // State management matching DevDeck
  const [activeTab, setActiveTab] = useState<'sua-conta' | 'aparencia' | 'preferencias' | 'acoes'>('sua-conta');
  const [mobileShowDetails, setMobileShowDetails] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  // Save profile states
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [updating, setUpdating] = useState(false);
  const [uploadingPhoto, setUploadingPhoto] = useState(false);
  const [photoError, setPhotoError] = useState('');

  const {
    register,
    reset,
    handleSubmit,
    formState: { errors }
  } = useForm<ProfileFormValues>({
    resolver: zodResolver(profileSchema),
    defaultValues: { displayName: '', email: '', professionalArea: '', clinicName: '', phone: '' }
  });

  useEffect(() => {
    reset({
      displayName: profile?.displayName || user?.displayName || '',
      email: profile?.email || user?.email || '',
      professionalArea: profile?.professionalArea || '',
      clinicName: profile?.clinicName || '',
      phone: profile?.phone || ''
    });
  }, [profile, reset, user]);

  const changeTheme = (nextTheme: 'light' | 'dark') => {
    setTheme(nextTheme);
    if (user) {
      void updateSettings(user.uid, { theme: nextTheme });
    }
  };

  const handleLogout = async () => {
    await logout();
    navigate('/login', { replace: true });
  };

  const saveSetting = (key: string, value: boolean | string) => {
    if (user) void updateSettings(user.uid, { [key]: value });
  };

  const onSubmit = async (values: ProfileFormValues) => {
    if (!user) return;
    setUpdating(true);
    setError(null);
    setSuccess(false);

    try {
      await updateProfileData(user.uid, values);
      setSuccess(true);
      setTimeout(() => setSuccess(false), 5000);
    } catch (err) {
      console.error(err);
      setError('Erro ao atualizar perfil.');
    } finally {
      setUpdating(false);
    }
  };

  const handlePhoto = async (fileList: FileList | null) => {
    if (!user || !fileList?.[0]) return;
    setPhotoError('');
    setSuccess(false);
    try {
      setUploadingPhoto(true);
      await uploadProfilePhoto(user.uid, fileList[0]);
      setSuccess(true);
      setTimeout(() => setSuccess(false), 5000);
    } catch (err) {
      setPhotoError(err instanceof Error ? err.message : 'Não foi possível enviar a foto.');
    } finally {
      setUploadingPhoto(false);
    }
  };

  const tabs = [
    {
      id: 'sua-conta',
      title: 'Sua conta',
      description: 'Edite seu nome, e-mail visual, área de atuação, clínica, telefone e foto.',
      icon: UserRound,
      keywords: ['sua conta', 'perfil', 'nome', 'email', 'telefone', 'foto', 'clinica', 'atuacao', 'profissional', 'avatar']
    },
    {
      id: 'aparencia',
      title: 'Aparência',
      description: 'Personalize a exibição visual da plataforma (Modo Claro vs Modo Escuro).',
      icon: Sun,
      keywords: ['aparencia', 'tema', 'claro', 'escuro', 'light', 'dark', 'visual', 'sincronizada']
    },
    {
      id: 'preferencias',
      title: 'Preferências rápidas',
      description: 'Notificações, lembretes de agenda e exibição de foto/e-mail.',
      icon: Bell,
      keywords: ['preferencias', 'notificacoes', 'foto', 'email', 'lembretes', 'agenda', 'rapidas', 'toggles']
    },
    {
      id: 'acoes',
      title: 'Ações da conta',
      description: 'Encerre sua sessão ativa no dispositivo ou faça logout do sistema.',
      icon: LogOut,
      keywords: ['acoes', 'sair', 'logout', 'deslogar', 'encerrar', 'sessao', 'conta']
    }
  ];

  const filteredTabs = tabs.filter(
    (tab) =>
      tab.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      tab.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      tab.keywords.some((keyword) => keyword.includes(searchQuery.toLowerCase()))
  );

  return (
    <div className="flex flex-col md:flex-row min-h-screen w-full bg-white dark:bg-[#0c0c0e] antialiased">
      {/* Central Settings List Column */}
      <div
        className={`w-full md:w-[320px] lg:w-[350px] border-r border-heal-line/75 dark:border-zinc-800/80 flex-shrink-0 flex flex-col bg-slate-50/10 dark:bg-zinc-950/10 ${
          mobileShowDetails ? 'hidden md:flex' : 'flex'
        }`}
      >
        <div className="sticky top-0 z-30 bg-white/95 dark:bg-[#0c0c0e]/95 backdrop-blur-md border-b border-heal-line/60 dark:border-zinc-800/60 px-4 py-3 flex items-center gap-4 shrink-0 select-none">
          <div className="min-w-0">
            <h1 className="text-heal-ink dark:text-white text-base font-extrabold tracking-tight leading-tight">
              Configurações
            </h1>
            <p className="text-heal-muted dark:text-zinc-500 text-[10px] uppercase font-bold tracking-wider mt-0.5">
              Preferências e conta do profissional
            </p>
          </div>
        </div>

        {/* Search Box */}
        <div className="p-3 border-b border-heal-line/50 dark:border-zinc-800/50">
          <div className="relative flex items-center bg-white dark:bg-[#131316]/50 border border-heal-line dark:border-zinc-800 rounded-xl px-3 py-2.5 focus-within:border-heal-blue/85 transition-all">
            <Search className="w-4 h-4 text-heal-muted mr-2 flex-shrink-0" />
            <input
              type="text"
              placeholder="Buscar configuração"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-transparent text-xs text-heal-ink dark:text-white focus:outline-none placeholder-heal-muted/70"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                className="text-heal-muted hover:text-heal-ink dark:hover:text-white cursor-pointer"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>

        {/* Categories List */}
        <div className="flex-grow overflow-y-auto pb-4 divide-y divide-heal-line/30 dark:divide-zinc-800/30">
          {filteredTabs.length === 0 ? (
            <div className="p-6 text-center text-xs text-heal-muted font-bold">
              Nenhuma configuração encontrada
            </div>
          ) : (
            filteredTabs.map((tab) => {
              const TabIcon = tab.icon;
              const isSelected = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => {
                    setActiveTab(tab.id as any);
                    setMobileShowDetails(true);
                  }}
                  className={`w-full flex items-center justify-between p-4 text-left transition-colors relative cursor-pointer ${
                    isSelected
                      ? 'bg-slate-50 dark:bg-zinc-900/40 text-heal-blue dark:text-blue-400 font-bold'
                      : 'text-heal-muted dark:text-zinc-400 hover:bg-slate-50 dark:hover:bg-zinc-900/20 hover:text-heal-ink dark:hover:text-white'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <TabIcon
                      className={`w-4.5 h-4.5 ${isSelected ? 'text-heal-blue dark:text-blue-400' : 'text-heal-muted dark:text-zinc-400'}`}
                    />
                    <div className="space-y-0.5">
                      <span className="text-xs font-bold tracking-wide block">{tab.title}</span>
                      <span className="text-[10px] text-heal-muted dark:text-zinc-500 font-semibold block md:hidden lg:block leading-tight">
                        {tab.description}
                      </span>
                    </div>
                  </div>
                  <ChevronRight className="w-4 h-4 text-heal-muted/60" />

                  {isSelected && (
                    <div className="absolute right-0 top-0 bottom-0 w-[3px] bg-heal-blue" />
                  )}
                </button>
              );
            })
          )}
        </div>
      </div>

      {/* Right-hand Detail Panel Column */}
      <div
        className={`flex-grow flex flex-col min-w-0 bg-white dark:bg-[#0c0c0e] ${
          !mobileShowDetails ? 'hidden md:flex' : 'flex'
        }`}
      >
        {/* Panel Header */}
        <div className="p-4 border-b border-heal-line/75 dark:border-zinc-800/80 flex items-center gap-3 sticky top-0 z-10 bg-white dark:bg-[#0c0c0e]">
          <button
            type="button"
            onClick={() => setMobileShowDetails(false)}
            className="md:hidden p-1.5 hover:bg-slate-50 dark:hover:bg-zinc-900/50 rounded-xl text-heal-muted dark:text-zinc-400 hover:text-heal-ink dark:hover:text-white transition-colors cursor-pointer"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <h2 className="text-base font-black text-heal-ink dark:text-white">
            {tabs.find((t) => t.id === activeTab)?.title}
          </h2>
        </div>

        {/* Panel Scrollable Content */}
        <div className="flex-grow overflow-y-auto px-4 py-6 md:px-6 space-y-6 max-w-2xl w-full pb-8">
          {activeTab === 'sua-conta' && (
            <div className="space-y-6">
              <div>
                <h3 className="text-xs font-bold text-heal-muted dark:text-zinc-400 uppercase tracking-wider mb-1">
                  Informações Clínicas & Perfil
                </h3>
                <p className="text-xs text-heal-muted dark:text-zinc-500 leading-relaxed">
                  Atualize seus dados profissionais e de contato que ficarão visíveis para seus pacientes e colegas.
                </p>
              </div>

              {success && (
                <div className="rounded-xl bg-emerald-50/70 dark:bg-emerald-950/20 border border-emerald-200/50 dark:border-emerald-950/50 p-3.5 text-xs font-bold text-emerald-700 dark:text-emerald-300 flex items-center gap-2 animate-fade-in">
                  <Check className="w-4 h-4 shrink-0" />
                  <span>Perfil atualizado com sucesso!</span>
                </div>
              )}

              {error && (
                <div className="rounded-xl bg-red-50/70 dark:bg-red-950/20 border border-red-200/50 dark:border-red-950/50 p-3.5 text-xs font-bold text-red-700 dark:text-red-300 flex items-center gap-2 animate-fade-in">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>{error}</span>
                </div>
              )}

              <div className="space-y-5">
                {/* Photo Upload Section */}
                <div>
                  <label className="block text-[11px] font-bold text-heal-muted dark:text-zinc-400 uppercase tracking-wider mb-2">
                    Foto de Perfil
                  </label>
                  <div className="flex items-center gap-4">
                    <div className="flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-xl bg-heal-softBlue/60 text-heal-blue dark:bg-blue-950/40 ring-2 ring-heal-blue/20">
                      {profile?.photoURL ? (
                        <img src={profile.photoURL} alt="" className="h-full w-full object-cover" />
                      ) : (
                        <UserRound className="h-7 w-7 text-heal-blue" />
                      )}
                    </div>
                    <div className="space-y-2">
                      <input
                        type="file"
                        accept="image/*"
                        onChange={e => void handlePhoto(e.target.files)}
                        className="hidden"
                        id="settings-photo-upload"
                        disabled={uploadingPhoto}
                      />
                      <label
                        htmlFor="settings-photo-upload"
                        className="inline-flex items-center gap-1.5 px-4 py-2 border border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 hover:bg-slate-50 dark:hover:bg-zinc-850 text-heal-ink dark:text-white rounded-full text-xs font-bold transition-all cursor-pointer active:scale-95 select-none"
                      >
                        <Upload className="w-3.5 h-3.5 text-heal-muted" />
                        {uploadingPhoto ? 'Enviando...' : 'Alterar Foto de Perfil'}
                      </label>
                      {photoError && (
                        <p className="text-xs text-red-500 font-medium">{photoError}</p>
                      )}
                    </div>
                  </div>
                </div>

                <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
                  <Input
                    label="Nome"
                    error={errors.displayName?.message}
                    icon={<UserRound className="w-4 h-4 text-heal-muted" />}
                    {...register('displayName')}
                  />

                  <Input
                    label="E-mail visual"
                    type="email"
                    error={errors.email?.message}
                    icon={<Mail className="w-4 h-4 text-heal-muted" />}
                    {...register('email')}
                  />

                  <Input
                    label="Área de atuação"
                    error={errors.professionalArea?.message}
                    icon={<Briefcase className="w-4 h-4 text-heal-muted" />}
                    {...register('professionalArea')}
                  />

                  <Input
                    label="Instituição ou clínica"
                    error={errors.clinicName?.message}
                    icon={<Building2 className="w-4 h-4 text-heal-muted" />}
                    {...register('clinicName')}
                  />

                  <Input
                    label="Telefone"
                    error={errors.phone?.message}
                    icon={<Phone className="w-4 h-4 text-heal-muted" />}
                    {...register('phone')}
                  />

                  <div className="flex justify-end pt-4 border-t border-heal-line/60 dark:border-zinc-800/60">
                    <button
                      type="submit"
                      disabled={updating}
                      className="bg-heal-blue text-white text-xs font-bold px-5 py-2.5 rounded-xl transition-colors hover:bg-blue-600 disabled:opacity-50 cursor-pointer shadow-md shadow-blue-500/10"
                    >
                      {updating ? 'Salvando...' : 'Salvar Alterações'}
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}

          {activeTab === 'aparencia' && (
            <div className="space-y-6">
              <div>
                <h3 className="text-xs font-bold text-heal-muted dark:text-zinc-400 uppercase tracking-wider mb-1">
                  Aparência da Plataforma
                </h3>
                <p className="text-xs text-heal-muted dark:text-zinc-500 leading-relaxed">
                  Escolha a sua preferência de exibição visual para navegar na plataforma.
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {/* Dark Theme Card */}
                <button
                  type="button"
                  onClick={() => changeTheme('dark')}
                  className={`flex flex-col items-center gap-3 p-4 rounded-xl border transition-all duration-200 text-left cursor-pointer ${
                    theme === 'dark'
                      ? 'border-heal-blue bg-heal-blue/[0.03] text-heal-ink dark:text-white shadow-[0_0_15px_rgba(59,130,246,0.05)]'
                      : 'border-slate-200 dark:border-zinc-800 bg-slate-50/50 dark:bg-zinc-950/40 text-heal-muted dark:text-zinc-400 hover:border-slate-300 dark:hover:border-zinc-700 hover:text-heal-ink dark:hover:text-white'
                  }`}
                >
                  <div className="flex items-center justify-between w-full">
                    <Moon
                      className={`w-5 h-5 ${theme === 'dark' ? 'text-heal-blue' : 'text-heal-muted dark:text-zinc-400'}`}
                    />
                    {theme === 'dark' && <span className="w-2 h-2 rounded-full bg-heal-blue" />}
                  </div>
                  <div className="w-full">
                    <p className="text-xs font-bold">Modo Escuro</p>
                    <p className="text-[10px] text-heal-muted dark:text-zinc-500 mt-0.5 font-semibold leading-normal">
                      Foco na leitura clínica e menor fadiga ocular.
                    </p>
                  </div>
                </button>

                {/* Light Theme Card */}
                <button
                  type="button"
                  onClick={() => changeTheme('light')}
                  className={`flex flex-col items-center gap-3 p-4 rounded-xl border transition-all duration-200 text-left cursor-pointer ${
                    theme === 'light'
                      ? 'border-heal-blue bg-heal-blue/[0.03] text-heal-ink dark:text-white shadow-[0_0_15px_rgba(59,130,246,0.05)]'
                      : 'border-slate-200 dark:border-zinc-800 bg-slate-50/50 dark:bg-zinc-950/40 text-heal-muted dark:text-zinc-400 hover:border-slate-300 dark:hover:border-zinc-700 hover:text-heal-ink dark:hover:text-white'
                  }`}
                >
                  <div className="flex items-center justify-between w-full">
                    <Sun
                      className={`w-5 h-5 ${theme === 'light' ? 'text-heal-blue' : 'text-heal-muted dark:text-zinc-400'}`}
                    />
                    {theme === 'light' && <span className="w-2 h-2 rounded-full bg-heal-blue" />}
                  </div>
                  <div className="w-full">
                    <p className="text-xs font-bold">Modo Claro</p>
                    <p className="text-[10px] text-heal-muted dark:text-zinc-500 mt-0.5 font-semibold leading-normal">
                      Estilo limpo e alto contraste de leitura.
                    </p>
                  </div>
                </button>
              </div>
            </div>
          )}

          {activeTab === 'preferencias' && (
            <div className="space-y-6">
              <div>
                <h3 className="text-xs font-bold text-heal-muted dark:text-zinc-400 uppercase tracking-wider mb-1">
                  Preferências Rápidas
                </h3>
                <p className="text-xs text-heal-muted dark:text-zinc-500 leading-relaxed">
                  Ative ou desative as preferências de exibição e avisos do sistema.
                </p>
              </div>

              <div className="space-y-4">
                <PreferenceToggle
                  label="Notificações gerais"
                  checked={settings?.notificationsEnabled ?? true}
                  onChange={value => saveSetting('notificationsEnabled', value)}
                />
                <PreferenceToggle
                  label="Mostrar foto de perfil"
                  checked={settings?.showProfilePhoto ?? true}
                  onChange={value => saveSetting('showProfilePhoto', value)}
                />
                <PreferenceToggle
                  label="Ocultar e-mail no topo"
                  checked={settings?.hideEmailPreview ?? false}
                  onChange={value => saveSetting('hideEmailPreview', value)}
                />
                <PreferenceToggle
                  label="Lembretes da agenda"
                  checked={settings?.agendaRemindersEnabled ?? true}
                  onChange={value => saveSetting('agendaRemindersEnabled', value)}
                />
              </div>
            </div>
          )}

          {activeTab === 'acoes' && (
            <div className="space-y-6">
              <div>
                <h3 className="text-xs font-bold text-red-500 uppercase tracking-wider mb-1">
                  Ações da Conta
                </h3>
                <p className="text-xs text-heal-muted dark:text-zinc-400 leading-relaxed">
                  Gerencie sua sessão ativa e encerre seu acesso de forma segura.
                </p>
              </div>

              <div className="bg-slate-50 dark:bg-zinc-950/40 border border-slate-200 dark:border-zinc-800/80 rounded-xl p-6 space-y-4 backdrop-blur-sm shadow-sm animate-fade-in">
                <p className="text-heal-muted dark:text-zinc-500 text-xs leading-relaxed font-semibold">
                  Para trocar de conta ou sair do Heal+, utilize o botão abaixo para encerrar a sessão de forma segura.
                </p>
                <button
                  type="button"
                  onClick={() => void handleLogout()}
                  className="rounded-xl border border-red-500/20 bg-red-500/5 hover:bg-red-500/15 text-red-500 text-xs font-bold px-5 py-3 transition-colors cursor-pointer flex items-center justify-center gap-2 select-none"
                >
                  <LogOut className="w-3.5 h-3.5" />
                  Sair da Conta (Logout)
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function PreferenceToggle({
  label,
  checked,
  onChange
}: {
  label: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <div className="flex justify-between items-center bg-slate-50/50 dark:bg-zinc-950/20 border border-slate-200 dark:border-zinc-800/80 rounded-xl p-4 text-xs font-bold tracking-wide backdrop-blur-sm shadow-sm select-none">
      <span className="text-heal-ink dark:text-white flex items-center gap-2">
        {label}
      </span>
      <button
        type="button"
        onClick={() => onChange(!checked)}
        className={`px-4 py-2 rounded-xl border text-[10px] font-extrabold uppercase tracking-wider transition-all duration-200 active:scale-[0.97] cursor-pointer ${
          checked
            ? 'bg-heal-blue border-blue-600 text-white shadow-md shadow-blue-500/10 hover:bg-blue-600'
            : 'bg-white dark:bg-zinc-900 border-slate-200 dark:border-zinc-800 text-heal-muted dark:text-zinc-400 hover:text-heal-ink dark:hover:text-white hover:bg-slate-50 dark:hover:bg-zinc-850'
        }`}
      >
        {checked ? 'LIGADO' : 'DESLIGADO'}
      </button>
    </div>
  );
}

