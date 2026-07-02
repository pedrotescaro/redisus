import { zodResolver } from '@hookform/resolvers/zod';
import { Building2, Phone, Rocket, Stethoscope, Palette } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { Navigate, useNavigate } from 'react-router-dom';

import { useAuth } from '../../app/providers/AuthProvider';
import { BrandLogo } from '../../components/brand/BrandLogo';
import { updateUserProfile } from './authService';
import { onboardingSchema, type OnboardingFormValues } from './authSchema';

const areaOptions = ['Enfermagem', 'Medicina', 'Fisioterapia', 'Nutrição', 'Podologia', 'Outra área'];
const themeOptions = ['light', 'dark'];

export function OnboardingPage() {
  const { user, profile, loading } = useAuth();
  const navigate = useNavigate();
  
  const {
    register,
    reset,
    handleSubmit,
    formState: { errors, isSubmitting }
  } = useForm<OnboardingFormValues>({
    resolver: zodResolver(onboardingSchema),
    defaultValues: {
      professionalName: '',
      professionalArea: '',
      clinicName: '',
      phone: '',
      theme: 'light'
    }
  });

  useEffect(() => {
    reset({
      professionalName: profile?.displayName || user?.displayName || '',
      professionalArea: profile?.professionalArea || '',
      clinicName: profile?.clinicName || '',
      phone: profile?.phone || '',
      theme: profile?.settings?.theme || 'light'
    });
  }, [profile, reset, user]);

  if (!loading && !user) return <Navigate to="/login" replace />;
  if (profile?.onboardingCompleted) return <Navigate to="/dashboard" replace />;

  const onSubmit = async (values: OnboardingFormValues) => {
    if (!user) return;
    try {
      await updateUserProfile(user.uid, {
        displayName: values.professionalName,
        professionalArea: values.professionalArea,
        clinicName: values.clinicName || '',
        phone: values.phone || '',
        onboardingCompleted: true,
        settings: {
          ...(profile?.settings || {
            notificationsEnabled: true,
            emailNotificationsEnabled: true,
            agendaRemindersEnabled: true,
            hideEmailPreview: false,
            showProfilePhoto: true
          }),
          theme: values.theme
        }
      });
      navigate('/dashboard', { replace: true });
    } catch (err: any) {
      alert('Erro ao salvar perfil: ' + (err.message || String(err)));
    }
  };

  const particleParams = [
    { left: 12, delay: 0.5, duration: 9, size: 3.5 },
    { left: 34, delay: 2.1, duration: 14, size: 2.1 },
    { left: 56, delay: 4.8, duration: 11, size: 4.2 },
    { left: 78, delay: 1.2, duration: 8.5, size: 3.0 },
    { left: 23, delay: 8.4, duration: 15, size: 2.5 },
    { left: 45, delay: 10.1, duration: 12.5, size: 3.8 },
    { left: 67, delay: 6.2, duration: 10, size: 4.5 },
    { left: 89, delay: 3.7, duration: 13, size: 2.8 }
  ];

  return (
    <div className="heal-onboarding-page dark">
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@400;500;600;700;800;900&display=swap');

        .heal-onboarding-page * { margin: 0; padding: 0; box-sizing: border-box; }

        .heal-onboarding-page {
          --heal: #41B6E6;
          --heal-light: #6cd6ff;
          --heal-bright: #41B6E6;
          --heal-deep: #0077a3;
          --heal-glow: rgba(65, 182, 230, 0.4);
          --bg: #050608;
          --bg-elevated: #0f1115;
          --bg-hover: #16181d;
          --border: #23262d;
          --border-strong: #2f3338;
          --text: #f2f4f7;
          --text-secondary: #8b9099;
          --text-muted: #5a5f68;

          background: var(--bg);
          color: var(--text);
          font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
          min-height: 100vh;
          width: 100%;
          overflow-x: hidden;
          -webkit-font-smoothing: antialiased;
          position: relative;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 2.5rem 1rem;
        }

        /* Ambient background glow */
        .heal-onboarding-page::before {
          content: '';
          position: fixed;
          inset: 0;
          background:
            radial-gradient(ellipse 80% 60% at 50% 50%, rgba(65, 182, 230, 0.08), transparent 60%);
          pointer-events: none;
          z-index: 0;
        }

        /* Floating particles */
        .heal-onboarding-page .particles {
          position: absolute;
          inset: 0;
          pointer-events: none;
          z-index: 0;
          overflow: hidden;
        }

        .heal-onboarding-page .particle {
          position: absolute;
          width: 3px;
          height: 3px;
          background: var(--heal-bright);
          border-radius: 50%;
          box-shadow: 0 0 8px var(--heal-glow);
          animation: float-up linear infinite;
          opacity: 0;
        }

        @keyframes float-up {
          0% { transform: translateY(100vh) translateX(0); opacity: 0; }
          10% { opacity: 0.6; }
          50% { transform: translateY(50vh) translateX(20px); }
          90% { opacity: 0.6; }
          100% { transform: translateY(-100px) translateX(-20px); opacity: 0; }
        }

        .heal-onboarding-page .onboarding-card {
          width: 100%;
          max-width: 640px;
          background: var(--bg-elevated);
          border: 1px solid var(--border);
          border-radius: 20px;
          padding: 3rem 2.5rem;
          box-shadow: 0 20px 50px rgba(0, 0, 0, 0.4);
          z-index: 1;
          position: relative;
        }

        .heal-onboarding-page .top-bar {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 2rem;
        }

        .heal-onboarding-page .subtitle-tag {
          display: inline-flex;
          align-items: center;
          gap: 0.5rem;
          padding: 0.38rem 0.85rem;
          background: rgba(65, 182, 230, 0.1);
          border: 1px solid rgba(65, 182, 230, 0.25);
          border-radius: 9999px;
          font-size: 0.78rem;
          color: var(--heal-light);
          margin-bottom: 0.8rem;
          font-weight: 500;
        }

        .heal-onboarding-page .pulse-dot {
          width: 7px;
          height: 7px;
          background: var(--heal-bright);
          border-radius: 50%;
          animation: live-pulse 1.6s ease-in-out infinite;
          box-shadow: 0 0 8px var(--heal-bright);
        }

        @keyframes live-pulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.4; transform: scale(0.8); }
        }

        .heal-onboarding-page h1 {
          font-size: 2.2rem;
          font-weight: 800;
          line-height: 1.2;
          margin-bottom: 0.75rem;
          letter-spacing: -0.03em;
          font-family: 'Space Grotesk', sans-serif;
        }

        .heal-onboarding-page .description {
          font-size: 0.95rem;
          color: var(--text-secondary);
          line-height: 1.6;
          margin-bottom: 2.5rem;
        }

        .heal-onboarding-page .form-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 1.5rem;
        }

        .heal-onboarding-page .col-span-2 {
          grid-column: span 2;
        }

        .heal-onboarding-page .input-group {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }

        .heal-onboarding-page .input-label {
          font-size: 0.88rem;
          font-weight: 600;
          color: var(--text);
        }

        .heal-onboarding-page .input-wrapper {
          position: relative;
          display: flex;
          align-items: center;
        }

        .heal-onboarding-page .input-icon {
          position: absolute;
          left: 1rem;
          color: var(--text-muted);
          pointer-events: none;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .heal-onboarding-page .input-wrapper input,
        .heal-onboarding-page .input-wrapper select {
          width: 100%;
          padding: 0.78rem 1rem 0.78rem 2.75rem;
          background: var(--bg);
          border: 1px solid var(--border-strong);
          border-radius: 10px;
          color: var(--text);
          font-size: 0.95rem;
          font-family: inherit;
          transition: all 0.2s;
          appearance: none;
        }

        .heal-onboarding-page .input-wrapper select {
          background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%238b9099' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E");
          background-repeat: no-repeat;
          background-position: right 1rem center;
          background-size: 1.1rem;
          cursor: pointer;
        }

        .heal-onboarding-page .input-wrapper input:focus,
        .heal-onboarding-page .input-wrapper select:focus {
          outline: none;
          border-color: var(--heal);
          box-shadow: 0 0 0 3px rgba(65, 182, 230, 0.15);
        }

        .heal-onboarding-page .error-msg {
          font-size: 0.8rem;
          color: #ff6b6b;
          font-weight: 500;
          margin-top: 0.2rem;
        }

        .heal-onboarding-page .btn-submit {
          width: 100%;
          padding: 0.9rem 1.5rem;
          border-radius: 9999px;
          border: none;
          background: linear-gradient(135deg, var(--heal), #35a3d0);
          color: #ffffff;
          font-size: 1rem;
          font-weight: 750;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 0.6rem;
          transition: all 0.2s;
          margin-top: 1rem;
          box-shadow: 0 4px 15px rgba(65, 182, 230, 0.15);
        }

        .heal-onboarding-page .btn-submit:hover:not(:disabled) {
          background: linear-gradient(135deg, #5fc3ed, #35a3d0);
          transform: translateY(-1.5px);
          box-shadow: 0 8px 24px rgba(65, 182, 230, 0.3);
        }

        .heal-onboarding-page .btn-submit:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }
      `}</style>

      {/* Floating particles background */}
      <div className="particles">
        {particleParams.map((p, idx) => (
          <div
            key={idx}
            className="particle"
            style={{
              left: `${p.left}%`,
              animationDelay: `${p.delay}s`,
              animationDuration: `${p.duration}s`,
              width: `${p.size}px`,
              height: `${p.size}px`
            }}
          />
        ))}
      </div>

      <div className="onboarding-card">
        <div className="top-bar">
          <BrandLogo />
          <span className="subtitle-tag">
            <span className="pulse-dot" />
            Configuração Inicial
          </span>
        </div>

        <h1>Comece com seu perfil profissional</h1>
        <p className="description">
          Esses dados aparecem no perfil, relatórios e assinatura clínica. Você pode editar depois.
        </p>

        <form onSubmit={handleSubmit(onSubmit)} className="form-grid">
          <div className="input-group col-span-2">
            <label className="input-label">Nome profissional</label>
            <div className="input-wrapper">
              <span className="input-icon">
                <Stethoscope size={18} />
              </span>
              <input
                type="text"
                placeholder="Ex: Dr. Pedro Tescaro"
                {...register('professionalName')}
              />
            </div>
            {errors.professionalName?.message && (
              <span className="error-msg">{errors.professionalName.message}</span>
            )}
          </div>

          <div className="input-group">
            <label className="input-label">Área de atuação</label>
            <div className="input-wrapper">
              <span className="input-icon">
                <Palette size={18} />
              </span>
              <select {...register('professionalArea')}>
                <option value="">Selecione...</option>
                {areaOptions.map(opt => (
                  <option key={opt} value={opt}>
                    {opt}
                  </option>
                ))}
              </select>
            </div>
            {errors.professionalArea?.message && (
              <span className="error-msg">{errors.professionalArea.message}</span>
            )}
          </div>

          <div className="input-group">
            <label className="input-label">Preferência de tema</label>
            <div className="input-wrapper">
              <span className="input-icon">
                <Palette size={18} />
              </span>
              <select {...register('theme')}>
                {themeOptions.map(opt => (
                  <option key={opt} value={opt}>
                    {opt === 'light' ? 'Claro (Light)' : 'Escuro (Dark)'}
                  </option>
                ))}
              </select>
            </div>
            {errors.theme?.message && (
              <span className="error-msg">{errors.theme.message}</span>
            )}
          </div>

          <div className="input-group">
            <label className="input-label">Instituição ou clínica</label>
            <div className="input-wrapper">
              <span className="input-icon">
                <Building2 size={18} />
              </span>
              <input
                type="text"
                placeholder="Ex: Hospital das Clínicas"
                {...register('clinicName')}
              />
            </div>
          </div>

          <div className="input-group">
            <label className="input-label">Telefone</label>
            <div className="input-wrapper">
              <span className="input-icon">
                <Phone size={18} />
              </span>
              <input
                type="tel"
                placeholder="Ex: (11) 99999-9999"
                {...register('phone')}
              />
            </div>
          </div>

          <div className="col-span-2">
            <button
              type="submit"
              className="btn-submit"
              disabled={isSubmitting}
            >
              <Rocket size={18} />
              {isSubmitting ? 'Salvando...' : 'Começar agora'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
