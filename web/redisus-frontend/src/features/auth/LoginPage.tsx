import { useState, useEffect } from "react";
import { Link, Navigate } from "react-router-dom";
import { useAuth } from "../../app/providers/AuthProvider";
import { useTheme } from "../../app/providers/ThemeProvider";
import {
  friendlyAuthError,
  resetPassword,
  signInWithEmail,
  signInWithGoogle,
  signUpWithEmail,
} from "./authService";

const authTranslations = {
  pt: {
    subtitle: "Plataforma de apoio ao diagnóstico de feridas",
    loginTitle: "Entrar no Heal+",
    registerTitle: "Criar sua conta",
    actionLogin: "Entrar",
    actionRegister: "Criar conta",
    emailLabel: "E-mail clínico",
    emailPlaceholder: "exemplo@instituicao.org",
    passwordLabel: "Senha",
    passwordPlaceholder: "••••••••",
    forgotPassword: "Esqueceu sua senha?",
    googleBtn: "Acessar com o Google",
    switchRegister: "Novo na plataforma?",
    switchRegisterLink: "Crie sua conta",
    switchLogin: "Já possui uma conta?",
    switchLoginLink: "Entre agora",
    phoneBtn: "Continuar com telefone",
    appleBtn: "Continuar com a Apple",
    recuperarSenha: "E-mail de recuperação enviado!",
    insiraEmail: "Insira o e-mail para recuperar a senha",
    loginSucesso: "Login efetuado com sucesso!",
    cadastroSucesso: "Cadastro efetuado com sucesso!",
    orText: "ou",
    woundsLabel: "Feridas em acompanhamento",
    healingLabel: "Taxa de cicatrização",
    qrTitle: "Baixe o app",
    qrSub: "Escaneie o QR Code",
    termsText: "Ao inscrever-se, você concorda com os ",
    termsLink: "Termos de Serviço",
    termsText2: " e a ",
    privacyLink: "Política de Privacidade",
    termsText3: ", incluindo o ",
    cookiesLink: "Uso de Cookies",
    termsText4: ". A Heal+ é uma plataforma de apoio ao diagnóstico e acompanhamento longitudinal de feridas — suas análises não substituem a avaliação clínica de um profissional de saúde.",
    processando: "Processando...",
    conectando: "Conectando...",
    toastPt: "Idioma: Português (BR)",
    toastEn: "Language: English (US)",
    forgotPasswordLabel: "Esqueceu a senha?",
    acessoGoogle: "Login via Google efetuado!",
    acessoTelefone: "Acesso via telefone em desenvolvimento...",
    acessoApple: "Acesso via Apple ID em desenvolvimento...",
  },
  en: {
    subtitle: "Wound diagnostics support platform",
    loginTitle: "Sign In to Heal+",
    registerTitle: "Create your account",
    actionLogin: "Sign In",
    actionRegister: "Create account",
    emailLabel: "Clinical Email",
    emailPlaceholder: "example@institution.org",
    passwordLabel: "Password",
    passwordPlaceholder: "••••••••",
    forgotPassword: "Forgot password?",
    googleBtn: "Access with Google",
    switchRegister: "New to the platform?",
    switchRegisterLink: "Create your account",
    switchLogin: "Already have an account?",
    switchLoginLink: "Sign in now",
    phoneBtn: "Continue with Phone",
    appleBtn: "Continue with Apple",
    recuperarSenha: "Recovery email sent!",
    insiraEmail: "Enter email to recover password",
    loginSucesso: "Login successful!",
    cadastroSucesso: "Account created successfully!",
    orText: "or",
    woundsLabel: "Wounds tracked",
    healingLabel: "Healing rate",
    qrTitle: "Download the app",
    qrSub: "Scan the QR Code",
    termsText: "By signing up, you agree to the ",
    termsLink: "Terms of Service",
    termsText2: " and the ",
    privacyLink: "Privacy Policy",
    termsText3: ", including ",
    cookiesLink: "Cookie Use",
    termsText4: ". Heal+ is a diagnostics and longitudinal monitoring support platform — its analyses do not replace clinical evaluation by a healthcare professional.",
    processando: "Processing...",
    conectando: "Connecting...",
    toastPt: "Idioma: Português (BR)",
    toastEn: "Language: English (US)",
    forgotPasswordLabel: "Forgot password?",
    acessoGoogle: "Logged in via Google!",
    acessoTelefone: "Phone access in development...",
    acessoApple: "Apple ID access in development...",
  }
};

export function LoginPage() {
  const { user } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const [lang, setLang] = useState<"pt" | "en">("pt");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<"login" | "register">("login");
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resetSent, setResetSent] = useState(false);

  // Custom Toast State
  const [toastMsg, setToastMsg] = useState<string | null>(null);
  const [showToast, setShowToast] = useState(false);
  const [toastTimeoutId, setToastTimeoutId] = useState<any>(null);

  const triggerToast = (msg: string) => {
    if (toastTimeoutId) clearTimeout(toastTimeoutId);
    setToastMsg(msg);
    setShowToast(true);
    const id = setTimeout(() => {
      setShowToast(false);
    }, 2800);
    setToastTimeoutId(id);
  };

  const t = (key: keyof typeof authTranslations.pt) => {
    return authTranslations[lang][key] || authTranslations.pt[key];
  };

  // Stats Counters Animation
  const [stat1, setStat1] = useState(0);
  const [stat2, setStat2] = useState(0);

  useEffect(() => {
    let startTimestamp: number | null = null;
    const duration = 2000;

    const step = (timestamp: number) => {
      if (!startTimestamp) startTimestamp = timestamp;
      const progress = Math.min((timestamp - startTimestamp) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);

      setStat1(Math.floor(0 + (12847 - 0) * eased));
      setStat2(parseFloat((0 + (87.3 - 0) * eased).toFixed(1)));

      if (progress < 1) {
        window.requestAnimationFrame(step);
      }
    };

    const timer = setTimeout(() => {
      window.requestAnimationFrame(step);
    }, 400);

    return () => {
      clearTimeout(timer);
    };
  }, []);

  if (user) return <Navigate to="/dashboard" replace />;

  const title = mode === "login" ? t("loginTitle") : t("registerTitle");
  const actionLabel = mode === "login" ? t("actionLogin") : t("actionRegister");

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setResetSent(false);

    try {
      if (mode === "login") {
        await signInWithEmail(email, password);
        triggerToast(t("loginSucesso"));
      } else {
        const name = email.split("@")[0] || "Profissional";
        await signUpWithEmail(name, email, password);
        triggerToast(t("cadastroSucesso"));
      }
    } catch (err) {
      const friendlyErr = friendlyAuthError(err);
      setError(friendlyErr);
      triggerToast(friendlyErr);
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleSignIn = async () => {
    setGoogleLoading(true);
    setError(null);
    setResetSent(false);

    try {
      await signInWithGoogle();
      triggerToast(t("acessoGoogle"));
    } catch (err) {
      const friendlyErr = friendlyAuthError(err);
      setError(friendlyErr);
      triggerToast(friendlyErr);
    } finally {
      setGoogleLoading(false);
    }
  };

  const handleResetPassword = async () => {
    setError(null);
    setResetSent(false);

    if (!email) {
      setError(lang === "pt" ? "Por favor, preencha o campo de e-mail antes para recuperar a senha." : "Please fill in the email field first to recover password.");
      triggerToast(t("insiraEmail"));
      return;
    }

    setLoading(true);
    try {
      await resetPassword(email);
      setResetSent(true);
      triggerToast(t("recuperarSenha"));
    } catch (err) {
      const friendlyErr = friendlyAuthError(err);
      setError(friendlyErr);
      triggerToast(friendlyErr);
    } finally {
      setLoading(false);
    }
  };

  // Generate 24 static random values once for the particles to keep SSR/hydration stable
  const particleParams = [
    { left: 12, delay: 0.5, duration: 9, size: 3.5 },
    { left: 34, delay: 2.1, duration: 14, size: 2.1 },
    { left: 56, delay: 4.8, duration: 11, size: 4.2 },
    { left: 78, delay: 1.2, duration: 8.5, size: 3.0 },
    { left: 23, delay: 8.4, duration: 15, size: 2.5 },
    { left: 45, delay: 10.1, duration: 12.5, size: 3.8 },
    { left: 67, delay: 6.2, duration: 10, size: 4.5 },
    { left: 89, delay: 3.7, duration: 13, size: 2.8 },
    { left: 15, delay: 5.5, duration: 11.5, size: 3.2 },
    { left: 38, delay: 9.3, duration: 14.5, size: 2.4 },
    { left: 59, delay: 1.8, duration: 9.5, size: 4.0 },
    { left: 82, delay: 7.1, duration: 12, size: 3.1 },
    { left: 8, delay: 11.2, duration: 16, size: 2.2 },
    { left: 29, delay: 3.0, duration: 10.5, size: 3.6 },
    { left: 51, delay: 5.9, duration: 13.5, size: 2.7 },
    { left: 73, delay: 0.2, duration: 8.0, size: 4.8 },
    { left: 95, delay: 9.8, duration: 15.5, size: 2.0 },
    { left: 20, delay: 4.1, duration: 12, size: 3.4 },
    { left: 42, delay: 7.6, duration: 9, size: 4.1 },
    { left: 64, delay: 11.9, duration: 14, size: 2.9 },
    { left: 86, delay: 2.5, duration: 11, size: 3.7 },
    { left: 30, delay: 6.7, duration: 13, size: 2.6 },
    { left: 52, delay: 8.8, duration: 10.5, size: 4.4 },
    { left: 74, delay: 1.5, duration: 12, size: 3.3 }
  ];

  return (
    <div className={`heal-login-page ${theme === "dark" ? "dark" : ""}`}>
      <Link
        to="/"
        className="back-btn-absolute"
        aria-label="Voltar para a página inicial"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
          <line x1="19" y1="12" x2="5" y2="12"></line>
          <polyline points="12 19 5 12 12 5"></polyline>
        </svg>
      </Link>

      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@400;500;600;700;800;900&display=swap');

        .heal-login-page * { margin: 0; padding: 0; box-sizing: border-box; }

        .heal-login-page {
          --heal: #41B6E6;
          --heal-light: #6cd6ff;
          --heal-bright: #41B6E6;
          --heal-deep: #0077a3;
          --heal-glow: rgba(65, 182, 230, 0.4);

          background: var(--bg);
          color: var(--text);
          font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
          min-height: 100vh;
          width: 100%;
          overflow-x: hidden;
          -webkit-font-smoothing: antialiased;
          position: relative;
        }

        .heal-login-page:not(.dark) {
          --bg: #ffffff;
          --bg-elevated: #f8fbfd;
          --bg-hover: #f1f7fa;
          --border: #e2e8f0;
          --border-strong: #cbd5e1;
          --text: #0f172a;
          --text-secondary: #475569;
          --text-muted: #94a3b8;
        }

        .heal-login-page.dark {
          --bg: #050608;
          --bg-elevated: #0f1115;
          --bg-hover: #16181d;
          --border: #23262d;
          --border-strong: #2f3338;
          --text: #f2f4f7;
          --text-secondary: #8b9099;
          --text-muted: #5a5f68;
        }

        /* Ambient background glow */
        .heal-login-page::before {
          content: '';
          position: fixed;
          inset: 0;
          background:
            radial-gradient(ellipse 80% 60% at 75% 50%, rgba(65, 182, 230, 0.12), transparent 60%),
            radial-gradient(ellipse 60% 50% at 25% 80%, rgba(65, 182, 230, 0.06), transparent 50%);
          pointer-events: none;
          z-index: 0;
        }

        .heal-login-page .login-container {
          display: grid;
          grid-template-columns: 1.05fr 1fr;
          min-height: 100vh;
          position: relative;
          z-index: 1;
        }

        /* ============ LEFT: LOGIN ============ */
        .heal-login-page .login-side {
          padding: 2.25rem 2rem;
          display: flex;
          flex-direction: column;
          justify-content: center;
          max-width: 450px;
          margin: 0 auto;
          width: 100%;
          position: relative;
        }

        .heal-login-page .top-bar {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 1.25rem;
        }

        .heal-login-page .brand {
          display: flex;
          align-items: center;
          text-decoration: none;
          width: fit-content;
        }

        .heal-login-page .brand-logo {
          height: 2.2rem;
          width: auto;
          object-fit: contain;
          transition: transform 300ms ease;
        }
        .heal-login-page .brand:hover .brand-logo {
          transform: scale(1.05);
        }

        .heal-login-page .back-btn-absolute {
          position: absolute;
          top: 1.85rem;
          left: 1.85rem;
          z-index: 100;
          display: flex;
          align-items: center;
          justify-content: center;
          width: 2.2rem;
          height: 2.2rem;
          border-radius: 50%;
          border: 1px solid var(--border-strong);
          color: var(--text);
          background: var(--bg);
          transition: all 0.2s;
          cursor: pointer;
          text-decoration: none;
        }

        .heal-login-page .back-btn-absolute:hover {
          background: var(--bg-hover);
          border-color: var(--heal);
          color: var(--heal);
        }

        .heal-login-page .lang-btn,
        .heal-login-page .theme-toggle-btn {
          background: transparent;
          border: 1px solid var(--border-strong);
          color: var(--text);
          cursor: pointer;
          transition: all 0.2s;
          font-family: inherit;
        }

        .heal-login-page .lang-btn {
          padding: 0.42rem 0.85rem;
          border-radius: 9999px;
          font-size: 0.82rem;
          font-weight: 500;
          display: flex;
          align-items: center;
          gap: 0.4rem;
        }

        .heal-login-page .lang-btn:hover,
        .heal-login-page .theme-toggle-btn:hover {
          background: var(--bg-hover);
          border-color: var(--heal);
        }

        .heal-login-page h1 {
          font-size: 2.8rem;
          font-weight: 800;
          line-height: 1.15;
          margin-bottom: 1rem;
          letter-spacing: -0.04em;
        }

        .heal-login-page .accent-text {
          background: linear-gradient(135deg, var(--heal-bright), var(--heal));
          -webkit-background-clip: text;
          background-clip: text;
          color: transparent;
          position: relative;
        }

        .heal-login-page .subtitle-tag {
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
          width: fit-content;
        }

        .heal-login-page .pulse-dot {
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

        .heal-login-page .auth-buttons {
          display: flex;
          flex-direction: column;
          gap: 0.6rem;
          margin-bottom: 0.8rem;
        }

        .heal-login-page .btn {
          width: 100%;
          padding: 0.72rem 1.25rem;
          border-radius: 9999px;
          border: 1px solid var(--border-strong);
          background: var(--bg);
          color: var(--text);
          font-size: 0.92rem;
          font-weight: 600;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 0.6rem;
          transition: all 0.2s;
          font-family: inherit;
        }

        .heal-login-page .btn:hover {
          background: var(--bg-hover);
          border-color: var(--text-muted);
        }

        .heal-login-page .btn svg {
          width: 18px;
          height: 18px;
          flex-shrink: 0;
        }

        .heal-login-page .divider {
          display: flex;
          align-items: center;
          gap: 1rem;
          margin: 0.8rem 0;
          color: var(--text-muted);
          font-size: 0.85rem;
          font-weight: 500;
        }

        .heal-login-page .divider::before,
        .heal-login-page .divider::after {
          content: '';
          flex: 1;
          height: 1px;
          background: var(--border);
        }

        .heal-login-page .input-group {
          margin-bottom: 0.55rem;
          position: relative;
        }

        .heal-login-page .input-group input {
          width: 100%;
          padding: 0.78rem 1rem;
          background: var(--bg);
          border: 1px solid var(--border-strong);
          border-radius: 8px;
          color: var(--text);
          font-size: 0.95rem;
          font-family: inherit;
          transition: all 0.2s;
        }

        .heal-login-page .input-group input:focus {
          outline: none;
          border-color: var(--heal);
          box-shadow: 0 0 0 3px rgba(65, 182, 230, 0.15);
        }

        .heal-login-page .btn-primary {
          background: linear-gradient(135deg, var(--heal), #35a3d0);
          color: #ffffff;
          border: none;
          font-weight: 750;
        }

        .heal-login-page .btn-primary:hover {
          background: linear-gradient(135deg, #5fc3ed, #35a3d0);
          transform: translateY(-1px);
          box-shadow: 0 8px 24px rgba(65, 182, 230, 0.25);
        }

        .heal-login-page .terms {
          font-size: 0.75rem;
          color: var(--text-secondary);
          line-height: 1.5;
          margin-top: 1rem;
        }

        .heal-login-page .terms a {
          color: var(--heal-light);
          text-decoration: none;
        }

        .heal-login-page .terms a:hover { text-decoration: underline; }

        /* ============ RIGHT: LOGO SIDE ============ */
        .heal-login-page .logo-side {
          display: flex;
          align-items: center;
          justify-content: center;
          position: relative;
          overflow: hidden;
          padding: 2rem;
          background: linear-gradient(135deg, transparent, rgba(65, 182, 230, 0.04));
          border-left: 1px solid var(--border);
        }

        /* Grid pattern background */
        .heal-login-page .grid-bg {
          position: absolute;
          inset: 0;
          background-image:
            linear-gradient(rgba(65, 182, 230, 0.04) 1px, transparent 1px),
            linear-gradient(90deg, rgba(65, 182, 230, 0.04) 1px, transparent 1px);
          background-size: 40px 40px;
          mask-image: radial-gradient(ellipse 60% 70% at center, black 30%, transparent 80%);
          -webkit-mask-image: radial-gradient(ellipse 60% 70% at center, black 30%, transparent 80%);
          pointer-events: none;
        }

        /* ECG line background */
        .heal-login-page .ecg-bg {
          position: absolute;
          inset: 0;
          pointer-events: none;
          opacity: 0.5;
        }

        .heal-login-page .ecg-svg {
          width: 100%;
          height: 100%;
        }

        .heal-login-page .ecg-path {
          fill: none;
          stroke: var(--heal);
          stroke-width: 2;
          stroke-linecap: round;
          stroke-linejoin: round;
          filter: drop-shadow(0 0 6px var(--heal-glow));
          stroke-dasharray: 1200;
          stroke-dashoffset: 1200;
          animation: ecg-draw 4s linear infinite;
        }

        @keyframes ecg-draw {
          0% { stroke-dashoffset: 1200; }
          50% { stroke-dashoffset: 0; }
          100% { stroke-dashoffset: -1200; }
        }

        /* Floating particles */
        .heal-login-page .particles {
          position: absolute;
          inset: 0;
          pointer-events: none;
        }

        .heal-login-page .particle {
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

        /* Big logo */
        .heal-login-page .big-logo-wrap {
          position: relative;
          width: 100%;
          max-width: 520px;
          aspect-ratio: 1;
          z-index: 2;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .heal-login-page .pulse-rings {
          position: absolute;
          inset: -8%;
          pointer-events: none;
        }

        .heal-login-page .pulse-ring {
          position: absolute;
          inset: 0;
          border: 2px solid var(--heal);
          border-radius: 32% 68% 47% 53% / 53% 47% 53% 47%;
          opacity: 0;
          animation: pulse-out 3.5s ease-out infinite;
        }

        .heal-login-page .pulse-ring:nth-child(2) { animation-delay: 1.2s; }
        .heal-login-page .pulse-ring:nth-child(3) { animation-delay: 2.4s; }

        @keyframes pulse-out {
          0% {
            opacity: 0.5;
            transform: scale(0.85) rotate(0deg);
          }
          100% {
            opacity: 0;
            transform: scale(1.3) rotate(180deg);
          }
        }

        .heal-login-page .big-logo {
          width: 72%;
          height: 72%;
          object-fit: contain;
          animation: breathe 5s ease-in-out infinite;
          filter: drop-shadow(0 20px 60px rgba(65, 182, 230, 0.35));
        }

        @keyframes breathe {
          0%, 100% { transform: scale(1) rotate(0deg); }
          50% { transform: scale(1.025) rotate(0.5deg); }
        }

        /* Bandage dot pulse */
        .heal-login-page .bandage-dot {
          transform-origin: center;
          transform-box: fill-box;
          animation: dot-pulse 2.4s ease-in-out infinite;
        }

        .heal-login-page .bandage-dot:nth-child(1) { animation-delay: 0s; }
        .heal-login-page .bandage-dot:nth-child(2) { animation-delay: 0.2s; }
        .heal-login-page .bandage-dot:nth-child(3) { animation-delay: 0.4s; }
        .heal-login-page .bandage-dot:nth-child(4) { animation-delay: 0.6s; }
        .heal-login-page .bandage-dot:nth-child(5) { animation-delay: 0.8s; }
        .heal-login-page .bandage-dot:nth-child(6) { animation-delay: 1s; }

        @keyframes dot-pulse {
          0%, 100% { opacity: 1; r: 13; }
          50% { opacity: 0.5; r: 10; }
        }

        /* Watermark text */
        .heal-login-page .watermark {
          position: absolute;
          bottom: -2%;
          left: 50%;
          transform: translateX(-50%);
          font-family: 'Space Grotesk', sans-serif;
          font-size: 4.5rem;
          font-weight: 700;
          color: rgba(65, 182, 230, 0.08);
          letter-spacing: -0.05em;
          z-index: 1;
          pointer-events: none;
          white-space: nowrap;
        }

        /* Stats overlay */
        .heal-login-page .stats-overlay {
          position: absolute;
          top: 2rem;
          left: 2rem;
          display: flex;
          flex-direction: column;
          gap: 0.7rem;
          z-index: 3;
        }

        .heal-login-page .stat {
          background: var(--bg-elevated);
          backdrop-filter: blur(12px);
          -webkit-backdrop-filter: blur(12px);
          border: 1px solid var(--border-strong);
          padding: 0.75rem 1rem;
          border-radius: 12px;
          font-size: 0.72rem;
          display: flex;
          align-items: center;
          gap: 0.7rem;
          min-width: 180px;
        }

        .heal-login-page .stat-icon {
          width: 28px;
          height: 28px;
          border-radius: 8px;
          background: rgba(65, 182, 230, 0.15);
          display: flex;
          align-items: center;
          justify-content: center;
          color: var(--heal-bright);
          flex-shrink: 0;
        }

        .heal-login-page .stat-content { display: flex; flex-direction: column; }

        .heal-login-page .stat-value {
          font-size: 1.05rem;
          font-weight: 700;
          color: var(--text);
          line-height: 1.1;
          font-family: 'Space Grotesk', sans-serif;
        }

        .heal-login-page .stat-label {
          color: var(--text-secondary);
          font-size: 0.7rem;
          margin-top: 0.1rem;
        }

        /* QR section */
        .heal-login-page .qr-section {
          position: absolute;
          bottom: 2rem;
          right: 2rem;
          display: flex;
          align-items: center;
          gap: 1rem;
          background: var(--bg-elevated);
          backdrop-filter: blur(12px);
          -webkit-backdrop-filter: blur(12px);
          border: 1px solid var(--border-strong);
          padding: 0.85rem 1.1rem;
          border-radius: 14px;
          z-index: 3;
        }

        .heal-login-page .qr-text {
          font-size: 0.82rem;
          line-height: 1.3;
          max-width: 160px;
        }

        .heal-login-page .qr-text strong {
          color: var(--text);
          display: block;
          margin-bottom: 0.15rem;
          font-weight: 700;
        }

        .heal-login-page .qr-text span {
          color: var(--text-secondary);
          font-size: 0.75rem;
        }

        .heal-login-page .qr-code {
          width: 76px;
          height: 76px;
          background: white;
          padding: 4px;
          border-radius: 8px;
          flex-shrink: 0;
        }

        /* Bottom ECG strip */
        .heal-login-page .ecg-strip {
          position: absolute;
          bottom: 0;
          left: 0;
          right: 0;
          height: 60px;
          overflow: hidden;
          opacity: 0.3;
          pointer-events: none;
          z-index: 1;
        }

        .heal-login-page .ecg-strip svg {
          width: 200%;
          height: 100%;
          animation: scroll-ecg 8s linear infinite;
        }

        @keyframes scroll-ecg {
          0% { transform: translateX(0); }
          100% { transform: translateX(-50%); }
        }

        /* Toast */
        .heal-login-page .toast {
          position: fixed;
          top: 1.5rem;
          left: 50%;
          transform: translateX(-50%) translateY(-200%);
          background: var(--bg-elevated);
          border: 1px solid var(--heal);
          color: var(--text);
          padding: 0.9rem 1.4rem;
          border-radius: 12px;
          z-index: 1000;
          transition: transform 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
          display: flex;
          align-items: center;
          gap: 0.7rem;
          box-shadow: 0 12px 40px rgba(65, 182, 230, 0.25);
          font-size: 0.9rem;
          font-weight: 500;
        }

        .heal-login-page .toast.show { transform: translateX(-50%) translateY(0); }

        .heal-login-page .toast svg {
          color: var(--heal-bright);
          width: 20px;
          height: 20px;
          flex-shrink: 0;
        }

        /* Responsive */
        @media (max-width: 1024px) {
          .heal-login-page .stats-overlay,
          .heal-login-page .qr-section {
            display: none;
          }
          .heal-login-page .login-container {
            grid-template-columns: 1.05fr 1fr;
          }
          .heal-login-page h1 {
            font-size: 2.3rem;
          }
        }

        @media (max-width: 768px) {
          .heal-login-page .login-container {
            grid-template-columns: 1fr;
          }
          .heal-login-page .logo-side {
            display: none;
          }
          .heal-login-page h1 {
            font-size: 2.2rem;
          }
          .heal-login-page .login-side {
            padding: 1.5rem 1.25rem;
            max-width: 420px;
          }
          .heal-login-page .back-btn-absolute {
            top: 1rem;
            left: 1rem;
          }
        }

        @media (max-width: 480px) {
          .heal-login-page h1 {
            font-size: 1.8rem;
            margin-bottom: 1rem;
          }
          .heal-login-page .login-side {
            padding: 1.25rem 0.8rem;
          }
          .heal-login-page .top-bar {
            margin-bottom: 1rem;
          }
        }

        /* Focus accessibility */
        .heal-login-page *:focus-visible {
          outline: 2px solid var(--heal);
          outline-offset: 2px;
        }

        /* Reduced motion */
        @media (prefers-reduced-motion: reduce) {
          .heal-login-page *, .heal-login-page *::before, .heal-login-page *::after {
            animation-duration: 0.01ms !important;
            animation-iteration-count: 1 !important;
            transition-duration: 0.01ms !important;
          }
        }
      `}</style>

      <div className="login-container">
        {/* ====== LEFT: LOGIN FORM ====== */}
        <div className="login-side">
          <div className="top-bar">
            <div className="brand" style={{ display: "flex", alignItems: "center" }}>
              <Link to="/">
                <img
                  className="brand-logo"
                  src="/images/Logo_final_modobranco.png"
                  alt="Heal+"
                />
              </Link>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <button
                type="button"
                className="lang-btn"
                onClick={() => {
                  const nextLang = lang === "pt" ? "en" : "pt";
                  setLang(nextLang);
                  triggerToast(nextLang === "pt" ? t("toastPt") : t("toastEn"));
                }}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10"/>
                  <path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
                </svg>
                {lang === "pt" ? "Português" : "English"}
              </button>

              <button
                type="button"
                onClick={toggleTheme}
                className="theme-toggle-btn"
                style={{
                  width: "2.1rem",
                  height: "2.1rem",
                  borderRadius: "50%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
                aria-label="Alternar Tema"
              >
                {theme === "dark" ? (
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#41B6E6" strokeWidth="2.5">
                    <circle cx="12" cy="12" r="5"/>
                    <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>
                  </svg>
                ) : (
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
                  </svg>
                )}
              </button>
            </div>
          </div>

          <div className="subtitle-tag">
            <span className="pulse-dot"></span>
            {t("subtitle")}
          </div>

          <h1>
            Cuidado inteligente.<br />
            <span className="accent-text">Acesso seguro.</span>
          </h1>

          <div className="auth-buttons">
            <button
              type="button"
              className="btn"
              onClick={() => triggerToast(t("acessoTelefone"))}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>
              </svg>
              {t("phoneBtn")}
            </button>
            <button
              type="button"
              className="btn"
              disabled={googleLoading || loading}
              onClick={handleGoogleSignIn}
            >
              <svg viewBox="0 0 24 24">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
              </svg>
              {googleLoading ? t("conectando") : t("googleBtn")}
            </button>
            <button
              type="button"
              className="btn"
              onClick={() => triggerToast(t("acessoApple"))}
            >
              <svg viewBox="0 0 24 24" fill="currentColor">
                <path d="M17.05 20.28c-.98.95-2.05.8-3.08.35-1.09-.46-2.09-.48-3.24 0-1.44.62-2.2.44-3.06-.35C2.79 15.25 3.51 7.59 9.05 7.31c1.35.07 2.29.74 3.08.8 1.18-.24 2.31-.93 3.57-.84 1.51.12 2.65.72 3.4 1.8-3.12 1.87-2.38 5.98.48 7.13-.57 1.5-1.31 2.99-2.54 4.09l.01-.01zM12.03 7.25c-.15-2.23 1.66-4.07 3.74-4.25.29 2.58-2.34 4.5-3.74 4.25z"/>
              </svg>
              {t("appleBtn")}
            </button>
          </div>

          <div className="divider">{t("orText")}</div>

          <form onSubmit={handleSubmit} className="w-full">
            <div className="input-group">
              <input
                type="email"
                placeholder={t("emailPlaceholder")}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                aria-label="E-mail"
              />
            </div>

            <div className="input-group">
              <input
                type="password"
                placeholder={t("passwordPlaceholder")}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                aria-label="Senha"
              />
            </div>

            {mode === "login" && (
              <div className="flex justify-end" style={{ marginTop: "-0.4rem", marginBottom: "0.6rem" }}>
                <button
                  type="button"
                  onClick={handleResetPassword}
                  className="text-[10.5px] font-bold uppercase tracking-[0.16em] text-[#41B6E6] hover:text-[#5fc3ed] transition-colors disabled:opacity-50"
                  disabled={loading}
                >
                  {t("forgotPasswordLabel")}
                </button>
              </div>
            )}

            {error && (
              <div style={{
                color: "#ff6b6b",
                background: "rgba(255,107,107,0.1)",
                border: "1px solid rgba(255,107,107,0.2)",
                borderRadius: "6px",
                padding: "0.75rem",
                fontSize: "0.85rem",
                marginBottom: "0.6rem",
                textAlign: "center"
              }}>
                {error}
              </div>
            )}

            {resetSent && (
              <div style={{
                color: "#4ecdc4",
                background: "rgba(78,205,196,0.1)",
                border: "1px solid rgba(78,205,196,0.2)",
                borderRadius: "6px",
                padding: "0.75rem",
                fontSize: "0.85rem",
                marginBottom: "0.6rem",
                textAlign: "center"
              }}>
                {t("recuperarSenha")}
              </div>
            )}

            <button
              type="submit"
              className="btn btn-primary"
              disabled={loading}
              style={{ marginTop: "0.25rem" }}
            >
              {loading ? t("processando") : actionLabel}
            </button>
          </form>

          <div className="mt-6 flex items-center justify-center gap-2 text-sm" style={{ marginTop: "1rem" }}>
            <span style={{ color: "var(--text-secondary)" }}>
              {mode === "login" ? t("switchRegister") : t("switchLogin")}
            </span>
            <button
              type="button"
              style={{
                background: "none",
                border: "none",
                fontWeight: "bold",
                color: "var(--heal-light)",
                cursor: "pointer"
              }}
              onClick={() => setMode((current) => (current === "login" ? "register" : "login"))}
            >
              {mode === "login" ? t("switchRegisterLink") : t("switchLoginLink")}
            </button>
          </div>

          <p className="terms">
            {t("termsText")}<a href="#">{t("termsLink")}</a>{t("termsText2")}<a href="#">{t("privacyLink")}</a>{t("termsText3")}<a href="#">{t("cookiesLink")}</a>{t("termsText4")}
          </p>
        </div>

        {/* ====== RIGHT: LOGO SHOWCASE ====== */}
        <div className="logo-side">
          <div className="grid-bg"></div>

          {/* ECG background line */}
          <div className="ecg-bg">
            <svg className="ecg-svg" viewBox="0 0 800 800" preserveAspectRatio="xMidYMid slice">
              <path className="ecg-path" d="M0,400 L120,400 L140,400 L150,380 L160,420 L170,360 L180,440 L195,400 L320,400 L340,400 L350,380 L360,420 L370,360 L380,440 L395,400 L520,400 L540,400 L550,380 L560,420 L570,360 L580,440 L595,400 L800,400" />
            </svg>
          </div>

          {/* Particles */}
          <div className="particles">
            {particleParams.map((p, i) => (
              <div
                key={i}
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

          {/* Stats */}
          <div className="stats-overlay">
            <div className="stat">
              <div className="stat-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M22 12h-4l-3 9L9 3l-3 9H2"/>
                </svg>
              </div>
              <div className="stat-content">
                <span className="stat-value">{stat1.toLocaleString("pt-BR")}</span>
                <span className="stat-label">{t("woundsLabel")}</span>
              </div>
            </div>
            <div className="stat">
              <div className="stat-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M9 12l2 2 4-4m6 2a9 9 0 1 1-18 0 9 9 0 0 1 18 0z"/>
                </svg>
              </div>
              <div className="stat-content">
                <span className="stat-value">{stat2.toFixed(1).replace(".", ",")}%</span>
                <span className="stat-label">{t("healingLabel")}</span>
              </div>
            </div>
          </div>

          {/* Big logo with pulse rings */}
          <div className="big-logo-wrap">
            <div className="pulse-rings">
              <div className="pulse-ring"></div>
              <div className="pulse-ring"></div>
              <div className="pulse-ring"></div>
            </div>

            <svg className="big-logo" viewBox="0 0 400 400" style={{ filter: "drop-shadow(0 20px 40px rgba(65,182,230,0.25))" }}>
              <defs>
                <linearGradient id="blueFlapGrad" x1="0%" y1="0%" x2="0%" y2="100%">
                  <stop offset="0%" stopColor="#6cd6ff" />
                  <stop offset="35%" stopColor="#41B6E6" />
                  <stop offset="100%" stopColor="#0077a3" />
                </linearGradient>

                <linearGradient id="whiteLoopGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#ffffff" />
                  <stop offset="40%" stopColor="#fafbfe" />
                  <stop offset="100%" stopColor="#e1eaf5" />
                </linearGradient>

                <radialGradient id="shinyDotGrad" cx="35%" cy="35%" r="65%">
                  <stop offset="0%" stopColor="#ffffff" />
                  <stop offset="25%" stopColor="#6cd6ff" />
                  <stop offset="65%" stopColor="#41B6E6" />
                  <stop offset="100%" stopColor="#0077a3" />
                </radialGradient>

                <linearGradient id="glossGrad" x1="0%" y1="0%" x2="0%" y2="100%">
                  <stop offset="0%" stopColor="#ffffff" stopOpacity="0.8" />
                  <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
                </linearGradient>

                <filter id="dotShadow" x="-30%" y="-30%" width="160%" height="160%">
                  <feDropShadow dx="0" dy="1.5" stdDeviation="1.5" floodColor="#003366" floodOpacity="0.3" />
                </filter>
              </defs>

              {/* 1. FILLS (BACKGROUND LAYER) */}
              <rect x="20" y="140" width="360" height="120" rx="60" fill="url(#blueFlapGrad)" />
              <path d="M 140,260 L 140,80 A 60,60 0 0,1 260,80 L 260,260 Z" fill="url(#whiteLoopGrad)" />

              {/* Glossy Highlights on Left/Right Flaps */}
              <path d="M 32,175 A 55,55 0 0,1 80,145 L 132,145 L 132,157 L 80,157 A 43,43 0 0,0 45,182 Z" fill="url(#glossGrad)" />
              <path d="M 368,175 A 55,55 0 0,0 320,145 L 268,145 L 268,157 L 320,157 A 43,43 0 0,1 355,182 Z" fill="url(#glossGrad)" />

              {/* Creases on Flaps */}
              <line x1="95" y1="165" x2="95" y2="235" stroke="#005a7d" strokeWidth="5.5" strokeLinecap="round" />
              <line x1="96.5" y1="166" x2="96.5" y2="236" stroke="#6cd6ff" strokeWidth="2" strokeLinecap="round" />

              <line x1="305" y1="165" x2="305" y2="235" stroke="#005a7d" strokeWidth="5.5" strokeLinecap="round" />
              <line x1="306.5" y1="166" x2="306.5" y2="236" stroke="#6cd6ff" strokeWidth="2" strokeLinecap="round" />

              {/* Outline Borders */}
              <g className="cross-outline">
                <path
                  d="M 80,140 L 140,140 L 140,80 A 60,60 0 0,1 260,80 L 260,140 L 320,140 A 60,60 0 0,1 380,200 A 60,60 0 0,1 320,260 L 260,260 L 260,320 A 60,60 0 0,1 140,320 L 140,260 L 80,260 A 60,60 0 0,1 20,200 A 60,60 0 0,1 80,140 Z"
                  fill="none"
                  stroke="#005a7d"
                  strokeWidth="10"
                  strokeLinejoin="round"
                />
                <path
                  d="M 80,140 L 140,140 L 140,80 A 60,60 0 0,1 260,80 L 260,140 L 320,140 A 60,60 0 0,1 380,200 A 60,60 0 0,1 320,260 L 260,260 L 260,320 A 60,60 0 0,1 140,320 L 140,260 L 80,260 A 60,60 0 0,1 20,200 A 60,60 0 0,1 80,140 Z"
                  fill="none"
                  stroke="#41B6E6"
                  strokeWidth="6"
                  strokeLinejoin="round"
                />
                <path
                  d="M 80,140 L 140,140 L 140,80 A 60,60 0 0,1 260,80 L 260,140 L 320,140 A 60,60 0 0,1 380,200 A 60,60 0 0,1 320,260 L 260,260 L 260,320 A 60,60 0 0,1 140,320 L 140,260 L 80,260 A 60,60 0 0,1 20,200 A 60,60 0 0,1 80,140 Z"
                  fill="none"
                  stroke="#e1f5fe"
                  strokeWidth="2.5"
                  strokeLinejoin="round"
                />
              </g>

              {/* Dividers */}
              <g className="dividers">
                <line x1="140" y1="140" x2="260" y2="140" stroke="#005a7d" strokeWidth="10" />
                <line x1="140" y1="140" x2="260" y2="140" stroke="#41B6E6" strokeWidth="6" />
                <line x1="140" y1="140" x2="260" y2="140" stroke="#e1f5fe" strokeWidth="2.5" />

                <line x1="140" y1="260" x2="260" y2="260" stroke="#005a7d" strokeWidth="10" />
                <line x1="140" y1="260" x2="260" y2="260" stroke="#41B6E6" strokeWidth="6" />
                <line x1="140" y1="260" x2="260" y2="260" stroke="#e1f5fe" strokeWidth="2.5" />
              </g>

              {/* Wound-care dots */}
              <g className="dots-matrix">
                <circle cx="165" cy="175" r="9.5" fill="url(#shinyDotGrad)" filter="url(#dotShadow)" className="bandage-dot" />
                <circle cx="165" cy="225" r="9.5" fill="url(#shinyDotGrad)" filter="url(#dotShadow)" className="bandage-dot" />
                <circle cx="200" cy="175" r="9.5" fill="url(#shinyDotGrad)" filter="url(#dotShadow)" className="bandage-dot" />
                <circle cx="200" cy="225" r="9.5" fill="url(#shinyDotGrad)" filter="url(#dotShadow)" className="bandage-dot" />
                <circle cx="235" cy="175" r="9.5" fill="url(#shinyDotGrad)" filter="url(#dotShadow)" className="bandage-dot" />
                <circle cx="235" cy="225" r="9.5" fill="url(#shinyDotGrad)" filter="url(#dotShadow)" className="bandage-dot" />
              </g>
            </svg>
          </div>

          {/* QR section */}
          <div className="qr-section">
            <div className="qr-text">
              <strong>{t("qrTitle")}</strong>
              <span>{t("qrSub")}</span>
            </div>
            <svg className="qr-code" viewBox="0 0 100 100">
              <rect width="100" height="100" fill="white"/>
              <g fill="black">
                <rect x="5" y="5" width="20" height="20"/>
                <rect x="75" y="5" width="20" height="20"/>
                <rect x="5" y="75" width="20" height="20"/>
                <rect x="10" y="10" width="10" height="10" fill="white"/>
                <rect x="80" y="10" width="10" height="10" fill="white"/>
                <rect x="10" y="80" width="10" height="10" fill="white"/>
                <rect x="13" y="13" width="4" height="4" fill="black"/>
                <rect x="83" y="13" width="4" height="4" fill="black"/>
                <rect x="13" y="83" width="4" height="4" fill="black"/>

                <rect x="30" y="5" width="4" height="4"/>
                <rect x="40" y="5" width="4" height="4"/>
                <rect x="50" y="5" width="4" height="4"/>
                <rect x="60" y="5" width="4" height="4"/>
                <rect x="65" y="10" width="4" height="4"/>
                <rect x="35" y="10" width="4" height="4"/>
                <rect x="55" y="10" width="4" height="4"/>
                <rect x="5" y="30" width="4" height="4"/>
                <rect x="15" y="30" width="4" height="4"/>
                <rect x="25" y="35" width="4" height="4"/>
                <rect x="35" y="30" width="4" height="4"/>
                <rect x="45" y="35" width="4" height="4"/>
                <rect x="55" y="30" width="4" height="4"/>
                <rect x="65" y="35" width="4" height="4"/>
                <rect x="75" y="30" width="4" height="4"/>
                <rect x="85" y="35" width="4" height="4"/>
                <rect x="30" y="45" width="4" height="4"/>
                <rect x="40" y="50" width="4" height="4"/>
                <rect x="50" y="45" width="4" height="4"/>
                <rect x="60" y="50" width="4" height="4"/>
                <rect x="70" y="45" width="4" height="4"/>
                <rect x="80" y="50" width="4" height="4"/>
                <rect x="90" y="45" width="4" height="4"/>
                <rect x="30" y="65" width="4" height="4"/>
                <rect x="40" y="60" width="4" height="4"/>
                <rect x="50" y="70" width="4" height="4"/>
                <rect x="60" y="65" width="4" height="4"/>
                <rect x="70" y="60" width="4" height="4"/>
                <rect x="80" y="70" width="4" height="4"/>
                <rect x="90" y="65" width="4" height="4"/>
                <rect x="30" y="85" width="4" height="4"/>
                <rect x="40" y="90" width="4" height="4"/>
                <rect x="55" y="85" width="4" height="4"/>
                <rect x="65" y="90" width="4" height="4"/>
                <rect x="80" y="85" width="4" height="4"/>
                <rect x="90" y="90" width="4" height="4"/>
              </g>
              {/* Heal+ logo in center */}
              <rect x="42" y="42" width="16" height="16" fill="white"/>
              <rect x="44" y="44" width="12" height="12" fill="#41B6E6" rx="2"/>
              <circle cx="48" cy="48" r="1.2" fill="white"/>
              <circle cx="52" cy="48" r="1.2" fill="white"/>
              <circle cx="48" cy="52" r="1.2" fill="white"/>
              <circle cx="52" cy="52" r="1.2" fill="white"/>
            </svg>
          </div>

          {/* Bottom ECG strip */}
          <div className="ecg-strip">
            <svg viewBox="0 0 1600 60" preserveAspectRatio="none">
              <path d="M0,30 L100,30 L120,30 L130,15 L140,45 L150,5 L160,55 L175,30 L300,30 L320,30 L330,15 L340,45 L350,5 L360,55 L375,30 L500,30 L520,30 L530,15 L540,45 L550,5 L560,55 L575,30 L700,30 L720,30 L730,15 L740,45 L750,5 L760,55 L775,30 L900,30 L920,30 L930,15 L940,45 L950,5 L960,55 L975,30 L1100,30 L1120,30 L1130,15 L1140,45 L1150,5 L1160,55 L1175,30 L1300,30 L1320,30 L1330,15 L1340,45 L1350,5 L1360,55 L1375,30 L1500,30 L1520,30 L1530,15 L1540,45 L1550,5 L1560,55 L1575,30 L1600,30" 
                    fill="none" stroke="#41B6E6" strokeWidth="1.5"/>
            </svg>
          </div>
        </div>
      </div>

      {/* Toast Notification */}
      <div className={`toast ${showToast ? "show" : ""}`}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10"/>
          <path d="M12 6v6l4 2"/>
        </svg>
        <span>{toastMsg}</span>
      </div>
    </div>
  );
}
