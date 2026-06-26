import {
  Bot,
  CalendarCheck2,
  ClipboardList,
  Copy,
  Database,
  HelpCircle,
  History,
  Loader2,
  Pencil,
  Plus,
  RotateCw,
  Search,
  SendHorizontal,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  Trash2,
  X
} from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';

import { useAuth } from '../../app/providers/AuthProvider';
import { Sidebar } from '../../components/layout/sidebar';
import { Topbar } from '../../components/layout/Topbar';
import { LoadingState } from '../../components/ui/LoadingState';
import type { Appointment, Evaluation, Patient } from '../../lib/types';
import { subscribeAppointments } from '../agenda/agendaService';
import { listEvaluations } from '../evaluations/evaluationService';
import { subscribePatients } from '../patients/patientService';
import { answerLocalQuestion } from './localAssistant';

/* ──────────────────────────────────────────────
   Types
   ────────────────────────────────────────────── */

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  isStreaming?: boolean;
}

interface ChatSession {
  id: string;
  title: string;
  messages: Message[];
  createdAt: number;
  isSaved?: boolean;
}

/* ──────────────────────────────────────────────
   Suggestion Cards (empty state)
   ────────────────────────────────────────────── */

const suggestions = [
  {
    title: 'Evolução de Enfermagem',
    description: 'Como registrar uma evolução clínica detalhada?',
    prompt: 'Como posso estruturar uma evolução de enfermagem completa e assertiva?',
    icon: ClipboardList,
    color: 'text-blue-400'
  },
  {
    title: 'Diagnósticos NANDA-I',
    description: 'Sugestões de diagnósticos para dor aguda.',
    prompt: 'Quais os principais diagnósticos de enfermagem NANDA para um paciente com dor aguda no pós-operatório?',
    icon: HelpCircle,
    color: 'text-teal-400'
  },
  {
    title: 'Sinais Vitais & Alertas',
    description: 'Parâmetros de monitoramento clínico.',
    prompt: 'Quais são os principais sinais de alerta no monitoramento de sinais vitais de um paciente crítico?',
    icon: CalendarCheck2,
    color: 'text-purple-400'
  }
];

const quickTopics = ['pacientes ativos', 'agenda de hoje', 'avaliações salvas', 'pacientes arquivados'];

/* ──────────────────────────────────────────────
   ChatPage Component
   ────────────────────────────────────────────── */

export function ChatPage() {
  const { user, profile } = useAuth();
  const [patients, setPatients] = useState<Patient[]>([]);
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [evaluationsByPatient, setEvaluationsByPatient] = useState<Record<string, Evaluation[]>>({});
  const [loading, setLoading] = useState(true);
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [thinking, setThinking] = useState(false);

  // Focus / fullscreen mode toggle matching DevDeck's Ducky IA (defaults to false)
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  // History
  const [history, setHistory] = useState<ChatSession[]>([]);
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [historySearch, setHistorySearch] = useState('');
  const [historyTab, setHistoryTab] = useState<'chats' | 'saved'>('chats');

  const chatEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Load data
  useEffect(() => {
    if (!user) return undefined;
    const unPatients = subscribePatients(user.uid, next => {
      setPatients(next);
      setLoading(false);
      void Promise.all(next.map(patient => listEvaluations(user.uid, patient.id))).then(groups => {
        setEvaluationsByPatient(Object.fromEntries(next.map((patient, index) => [patient.id, groups[index]])));
      });
    });
    const unAppointments = subscribeAppointments(user.uid, setAppointments);
    return () => {
      unPatients();
      unAppointments();
    };
  }, [user]);

  // Load history from localStorage
  useEffect(() => {
    try {
      const saved = localStorage.getItem('heal-chat-history');
      if (saved) setHistory(JSON.parse(saved));
    } catch {
      // ignore
    }
  }, []);

  // Auto-save chat to history
  useEffect(() => {
    if (messages.length === 0) return;
    const timeout = setTimeout(() => {
      const userMsgs = messages.filter(m => m.role === 'user');
      if (userMsgs.length === 0) return;
      const rawTitle = userMsgs[0].content;
      const derivedTitle = rawTitle.trim()
        ? rawTitle.length > 50 ? rawTitle.slice(0, 50) + '...' : rawTitle
        : 'Conversa';

      if (!activeChatId) {
        const newId = 'heal-chat-' + Date.now() + '-' + Math.random().toString(36).slice(2, 9);
        const newSession: ChatSession = { id: newId, title: derivedTitle, messages, createdAt: Date.now() };
        setActiveChatId(newId);
        setHistory(prev => {
          const next = [newSession, ...prev];
          localStorage.setItem('heal-chat-history', JSON.stringify(next));
          return next;
        });
      } else {
        setHistory(prev => {
          const updated = prev.map(s => s.id === activeChatId ? { ...s, title: s.title || derivedTitle, messages } : s);
          const exists = updated.some(s => s.id === activeChatId);
          const final = exists ? updated : [{ id: activeChatId, title: derivedTitle, messages, createdAt: Date.now() }, ...updated];
          localStorage.setItem('heal-chat-history', JSON.stringify(final));
          return final;
        });
      }
    }, 500);
    return () => clearTimeout(timeout);
  }, [messages, activeChatId]);

  // Scroll to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, thinking]);

  // Auto-resize textarea
  useEffect(() => {
    const textarea = inputRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = `${Math.min(textarea.scrollHeight, 160)}px`;
    }
  }, [input]);

  const firstName = useMemo(() => (profile?.displayName || user?.displayName || 'Profissional').split(' ')[0], [profile?.displayName, user?.displayName]);

  /* ── Send message ── */
  const send = (override?: string) => {
    const question = (override || input).trim();
    if (!question) return;

    const userMsg: Message = { id: Math.random().toString(), role: 'user', content: question };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setThinking(true);

    // Simulate a small delay for the "thinking" effect
    setTimeout(() => {
      const answer = answerLocalQuestion(question, { patients, appointments, evaluationsByPatient });
      const assistantMsgId = Math.random().toString();
      const assistantMsg: Message = { id: assistantMsgId, role: 'assistant', content: '', isStreaming: true };
      setMessages(prev => [...prev, assistantMsg]);
      setThinking(false);

      // Streaming text simulation
      let currentIdx = 0;
      const interval = setInterval(() => {
        setMessages(prev =>
          prev.map(msg => {
            if (msg.id === assistantMsgId) {
              const nextText = answer.slice(0, currentIdx + 12);
              const done = nextText.length === answer.length;
              if (done) clearInterval(interval);
              return { ...msg, content: nextText, isStreaming: !done };
            }
            return msg;
          })
        );
        currentIdx += 12;
      }, 15);
    }, 400 + Math.random() * 300);
  };

  /* ── History helpers ── */
  const handleNewChat = () => {
    setActiveChatId(null);
    setMessages([]);
    setInput('');
  };

  const handleSelectSession = (session: ChatSession) => {
    setActiveChatId(session.id);
    setMessages(session.messages);
    setIsHistoryOpen(false);
  };

  const toggleBookmark = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setHistory(prev => {
      const updated = prev.map(s => s.id === id ? { ...s, isSaved: !s.isSaved } : s);
      localStorage.setItem('heal-chat-history', JSON.stringify(updated));
      return updated;
    });
  };

  const deleteSession = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setHistory(prev => {
      const updated = prev.filter(s => s.id !== id);
      localStorage.setItem('heal-chat-history', JSON.stringify(updated));
      return updated;
    });
    if (activeChatId === id) handleNewChat();
  };

  if (loading) return <LoadingState label="Carregando dados para o assistente..." />;

  /* ──────────────────────────────────────────────
     Input Card (DevDeck / DeepSeek style)
     ────────────────────────────────────────────── */
  const renderInputCard = () => (
    <div className="w-full bg-white/90 dark:bg-[#131316]/90 border border-heal-line dark:border-[#232329] rounded-2xl p-4 flex flex-col justify-between min-h-[120px] shadow-lg dark:shadow-2xl focus-within:border-heal-blue/40 dark:focus-within:border-blue-500/40 focus-within:shadow-[0_0_25px_rgba(59,130,246,0.08)] dark:focus-within:shadow-[0_0_25px_rgba(59,130,246,0.12)] transition-all duration-300 max-w-2xl mx-auto backdrop-blur-md">
      <textarea
        ref={inputRef}
        value={input}
        onChange={e => setInput(e.target.value)}
        onKeyDown={e => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            send();
          }
        }}
        disabled={thinking}
        placeholder="Pergunte sobre pacientes, agenda ou avaliações..."
        rows={2}
        className="w-full bg-transparent border-0 outline-0 ring-0 text-sm text-heal-ink dark:text-white placeholder-heal-muted dark:placeholder-[#53535f] resize-none py-1.5 max-h-36 overflow-y-auto font-sans leading-relaxed focus:ring-0 focus:outline-none disabled:opacity-50"
      />

      {/* Bottom row */}
      <div className="flex items-center justify-between border-t border-heal-line/40 dark:border-[#1f1f23]/40 pt-3 mt-2 select-none">
        {/* Left: Badge */}
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[11px] font-semibold border bg-heal-softBlue/60 dark:bg-blue-950/30 border-heal-blue/20 dark:border-blue-500/20 text-heal-blue dark:text-blue-400">
            <Database className="w-3.5 h-3.5" />
            <span>Dados locais</span>
          </div>
        </div>

        {/* Right: Send button */}
        <button
          type="button"
          onClick={() => send()}
          disabled={!input.trim() || thinking}
          className="p-2 bg-heal-blue hover:bg-heal-blueDark disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-full transition-all cursor-pointer flex items-center justify-center shrink-0 w-9 h-9 shadow-md"
          title="Enviar"
        >
          <SendHorizontal className="w-4 h-4" />
        </button>
      </div>
    </div>
  );

  /* ──────────────────────────────────────────────
     History Drawer
     ────────────────────────────────────────────── */
  const renderHistoryDrawer = () => {
    const query = historySearch.trim().toLowerCase();
    const isSavedOnly = historyTab === 'saved';
    const filtered = history.filter(s => {
      if (isSavedOnly && !s.isSaved) return false;
      if (!query) return true;
      return s.title.toLowerCase().includes(query) || s.messages.some(m => m.content.toLowerCase().includes(query));
    });

    return (
      <>
        {/* Backdrop */}
        {isHistoryOpen && (
          <div
            className="fixed inset-0 bg-black/40 dark:bg-black/60 backdrop-blur-sm z-40 transition-opacity animate-fade-in"
            onClick={() => setIsHistoryOpen(false)}
          />
        )}

        {/* Drawer */}
        <div className={`fixed top-0 right-0 h-screen w-full max-w-[360px] md:max-w-[400px] bg-white/95 dark:bg-[#0c0c0e]/95 border-l border-heal-line dark:border-[#1f1f23]/60 shadow-lg dark:shadow-2xl z-50 flex flex-col transition-transform duration-300 ease-out backdrop-blur-md ${isHistoryOpen ? 'translate-x-0' : 'translate-x-full'}`}>
          {/* Header */}
          <div className="flex items-center gap-4 px-4 pt-5 pb-3 border-b border-heal-line dark:border-[#1c1c1f]/40 select-none shrink-0">
            <button
              onClick={() => setIsHistoryOpen(false)}
              className="p-1.5 hover:bg-heal-surfaceHover dark:hover:bg-[#1c1c1f] rounded-full text-heal-muted dark:text-[#8b8b93] hover:text-heal-ink dark:hover:text-white transition-colors cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>
            <h2 className="text-base font-bold text-heal-ink dark:text-white">Histórico</h2>
          </div>

          {/* Tabs */}
          <div className="flex px-2 border-b border-heal-line dark:border-[#1c1c1f] select-none shrink-0">
            {(['chats', 'saved'] as const).map(tab => {
              const isActive = historyTab === tab;
              const labels = { chats: 'Conversas', saved: 'Salvos' };
              return (
                <button
                  key={tab}
                  onClick={() => setHistoryTab(tab)}
                  className={`flex-1 py-3 text-center text-xs font-semibold relative transition-colors cursor-pointer ${isActive ? 'text-heal-ink dark:text-white font-bold' : 'text-heal-muted dark:text-[#8b8b93] hover:text-heal-ink dark:hover:text-white'}`}
                >
                  {labels[tab]}
                  {isActive && <span className="absolute bottom-0 left-1/2 -translate-x-1/2 w-1/2 h-[2.5px] bg-heal-blue rounded-full" />}
                </button>
              );
            })}
          </div>

          {/* Search */}
          <div className="p-4 border-b border-heal-line/40 dark:border-[#1c1c1f]/40 shrink-0">
            <div className="relative flex items-center bg-heal-canvas dark:bg-[#131316] border border-heal-line dark:border-[#1f1f23] rounded-full px-3.5 py-2 focus-within:border-heal-blue/40 transition-colors">
              <Search className="w-4 h-4 text-heal-muted dark:text-[#53535f] mr-2.5 shrink-0" />
              <input
                type="text"
                value={historySearch}
                onChange={e => setHistorySearch(e.target.value)}
                placeholder="Pesquisar conversas..."
                className="bg-transparent border-none outline-none text-xs text-heal-ink dark:text-white placeholder-heal-muted dark:placeholder-[#53535f] w-full"
              />
              {historySearch && (
                <button
                  onClick={() => setHistorySearch('')}
                  className="p-0.5 hover:bg-heal-surfaceHover dark:hover:bg-[#1c1c1f] rounded text-heal-muted hover:text-heal-ink dark:hover:text-white transition-colors cursor-pointer shrink-0"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          </div>

          {/* List */}
          <div className="flex-grow overflow-y-auto p-4">
            {filtered.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-center select-none">
                <History className="w-8 h-8 text-heal-muted dark:text-[#53535f] mb-2" />
                <p className="text-xs text-heal-muted dark:text-[#71767b]">
                  {isSavedOnly ? 'Nenhum item salvo.' : 'Nenhuma conversa encontrada.'}
                </p>
              </div>
            ) : (
              <div className="flex flex-col gap-0.5 select-none">
                {filtered.map(s => (
                  <div
                    key={s.id}
                    onClick={() => handleSelectSession(s)}
                    className={`group flex items-center justify-between px-3 py-2.5 rounded-xl cursor-pointer transition-all border ${
                      activeChatId === s.id
                        ? 'bg-heal-softBlue dark:bg-blue-500/10 border-heal-blue/20 dark:border-blue-500/20 text-heal-ink dark:text-white font-medium'
                        : 'bg-transparent border-transparent hover:bg-heal-surfaceHover dark:hover:bg-[#131316]/60 text-heal-muted dark:text-[#b3b3b9] hover:text-heal-ink dark:hover:text-white'
                    }`}
                  >
                    <span className="text-xs truncate flex-1 pr-2 leading-relaxed">{s.title}</span>
                    <div className="flex items-center gap-1.5 opacity-100 md:opacity-0 md:group-hover:opacity-100 transition-opacity shrink-0">
                      <button
                        onClick={e => toggleBookmark(s.id, e)}
                        className={`p-1 hover:bg-heal-surfaceHover dark:hover:bg-[#1c1c1f] rounded transition-colors cursor-pointer ${s.isSaved ? 'text-heal-blue' : 'text-heal-muted dark:text-[#8b8b93] hover:text-heal-blue'}`}
                        title={s.isSaved ? 'Remover dos salvos' : 'Salvar'}
                      >
                        <Sparkles className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={e => deleteSession(s.id, e)}
                        className="p-1 hover:bg-heal-surfaceHover dark:hover:bg-[#1c1c1f] rounded text-heal-muted dark:text-[#8b8b93] hover:text-red-500 transition-colors cursor-pointer"
                        title="Excluir"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </>
    );
  };

  /* ──────────────────────────────────────────────
     Main Render
     ────────────────────────────────────────────── */
  return (
    <div className="flex h-screen bg-heal-canvas text-heal-ink dark:bg-[#060606] text-heal-ink dark:text-white antialiased overflow-hidden w-full">
      {!isFullscreen && (
        <Sidebar isOpen={isSidebarOpen} setIsOpen={setIsSidebarOpen} />
      )}

      <div
        className={`flex-grow flex flex-col min-h-0 min-w-0 bg-heal-canvas dark:bg-[#060606] relative overflow-hidden transition-all duration-300 ${
          !isFullscreen ? 'lg:pl-[280px] border-l border-heal-line dark:border-[#1f1f23]/40' : ''
        }`}
      >
        {/* On mobile, if not fullscreen, show the mobile topbar */}
        {!isFullscreen && (
          <div className="lg:hidden shrink-0">
            <Topbar onMenuClick={() => setIsSidebarOpen(true)} />
          </div>
        )}

        <div className="flex flex-col flex-grow min-h-0 relative overflow-hidden bg-heal-canvas dark:bg-[#060606]">
          {/* Top Header */}
          <header className="flex items-center justify-between px-5 py-3.5 bg-white/80 dark:bg-[#060606]/40 backdrop-blur-md sticky top-0 z-20 border-b border-heal-line dark:border-[#1f1f23]/40 select-none shrink-0">
            <div className="flex items-center gap-3">
              {isFullscreen ? (
                <button
                  onClick={() => setIsFullscreen(false)}
                  className="p-2 hover:bg-heal-surfaceHover dark:hover:bg-[#16161a] text-heal-muted dark:text-[#8b8b93] hover:text-heal-ink dark:hover:text-white rounded-full transition-all cursor-pointer animate-in fade-in duration-300"
                  title="Mostrar barra lateral (Sair do modo expandido)"
                >
                  <svg
                    viewBox="0 0 24 24"
                    className="w-5 h-5 fill-none stroke-current"
                    strokeWidth="2.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <line x1="19" y1="12" x2="5" y2="12" />
                    <polyline points="12 19 5 12 12 5" />
                  </svg>
                </button>
              ) : (
                <button
                  onClick={() => setIsFullscreen(true)}
                  className="p-2 hover:bg-heal-surfaceHover dark:hover:bg-[#16161a] text-heal-muted dark:text-[#8b8b93] hover:text-heal-ink dark:hover:text-white rounded-full transition-all cursor-pointer animate-in fade-in duration-300"
                  title="Modo Foco (Ocultar barra lateral)"
                >
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    className="w-5 h-5"
                  >
                    <rect width="18" height="18" x="3" y="3" rx="4" />
                    <path d="M9 3v18" />
                  </svg>
                </button>
              )}

              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-heal-softBlue dark:bg-blue-950/40 text-heal-blue">
                <Bot className="h-5 w-5" />
              </div>
              <div className="min-w-0">
                <h1 className="text-lg font-black text-heal-ink dark:text-white truncate">Assistente Heal+</h1>
                <p className="text-[11px] font-semibold text-heal-muted dark:text-zinc-500 truncate">Consulta local aos seus dados</p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={handleNewChat}
                className="flex items-center gap-1 px-3 py-1.5 text-heal-blue font-bold text-xs hover:underline cursor-pointer bg-transparent border-0 transition-colors"
                title="Novo chat"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Novo Chat</span>
              </button>

              <button
                onClick={() => setIsHistoryOpen(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 text-heal-muted dark:text-[#8b8b93] hover:text-heal-ink dark:hover:text-white font-medium text-xs cursor-pointer bg-transparent border-0 transition-colors"
                title="Ver histórico"
              >
                <History className="w-3.5 h-3.5" />
                <span>Histórico</span>
              </button>

              <div className="hidden items-center gap-2 rounded-full bg-heal-canvas dark:bg-zinc-900 px-3 py-1.5 text-[11px] font-black text-heal-muted sm:inline-flex">
                <Database className="h-3.5 w-3.5 text-heal-teal" />
                Sem API externa
              </div>
            </div>
          </header>

          {/* Chat / Welcome Area */}
          {messages.length === 0 ? (
            /* ── Empty state (Centered Input Card & Suggestions) ── */
            <div className="flex-grow flex flex-col justify-center items-center overflow-y-auto px-4 py-8 max-w-3xl w-full mx-auto relative z-10">
              <div className="w-full max-w-2xl flex flex-col items-center gap-6 text-center -mt-16">
                {/* Branding */}
                <div className="flex items-center justify-center gap-3 select-none mb-1 animate-fade-in">
                  <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-heal-softBlue dark:bg-blue-950/40 text-heal-blue">
                    <Sparkles className="h-6 w-6" />
                  </div>
                  <span className="text-2xl font-bold tracking-tight text-heal-ink dark:text-white">
                    Conversar com o Assistente
                  </span>
                </div>

                {/* Input Card in the center */}
                <div className="w-full">{renderInputCard()}</div>

                {/* Suggestion pills */}
                <div className="flex flex-wrap items-center justify-center gap-2.5 w-full select-none animate-slide-up">
                  {suggestions.map(item => (
                    <button
                      key={item.title}
                      onClick={() => send(item.prompt)}
                      className="flex items-center gap-2 px-4 py-2.5 border border-heal-line dark:border-[#232329] bg-white/80 dark:bg-[#131316]/90 hover:bg-heal-surfaceHover dark:hover:bg-[#1c1c22] hover:border-heal-blue/30 dark:hover:border-[#383842] text-[11px] font-semibold text-heal-muted dark:text-[#8b8b93] hover:text-heal-ink dark:hover:text-white rounded-full transition-all duration-200 cursor-pointer shadow-sm hover:scale-[1.02] active:scale-[0.98]"
                    >
                      <item.icon className={`w-3.5 h-3.5 ${item.color}`} />
                      <span>{item.title}</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            /* ── Conversation flow ── */
            <>
              <div className="flex-grow overflow-y-auto relative z-10">
                <div className="px-5 py-5 max-w-3xl w-full mx-auto">
                  <div className="flex flex-col w-full pb-6">
                    {messages.map(msg => {
                      const isAssistant = msg.role === 'assistant';
                      return isAssistant ? (
                        /* ASSISTANT MESSAGE: Left-aligned clean text */
                        <div
                          key={msg.id}
                          className="flex flex-col items-start w-full py-4 border-b border-heal-line/20 dark:border-[#1f1f23]/10 animate-fade-in"
                        >
                          <div className="max-w-[85%] text-sm text-heal-ink dark:text-white leading-relaxed font-sans whitespace-pre-line">
                            {msg.content}
                            {msg.isStreaming && (
                              <span className="inline-block w-1.5 h-3.5 bg-heal-blue ml-1 animate-pulse rounded-sm" />
                            )}
                          </div>

                          {/* Action icons */}
                          {!msg.isStreaming && (
                            <div className="flex items-center gap-3.5 mt-2.5 text-heal-muted dark:text-[#53535f] select-none">
                              <button
                                onClick={() => navigator.clipboard.writeText(msg.content)}
                                className="hover:text-heal-ink dark:hover:text-white transition-colors cursor-pointer"
                                title="Copiar"
                              >
                                <Copy className="w-3.5 h-3.5" />
                              </button>
                              <button
                                onClick={() => {
                                  const userMsgs = messages.filter(m => m.role === 'user');
                                  const lastQ = userMsgs[userMsgs.length - 1]?.content;
                                  if (lastQ) send(lastQ);
                                }}
                                className="hover:text-heal-ink dark:hover:text-white transition-colors cursor-pointer"
                                title="Regenerar"
                              >
                                <RotateCw className="w-3.5 h-3.5" />
                              </button>
                              <button className="hover:text-heal-ink dark:hover:text-white transition-colors cursor-pointer" title="Útil">
                                <ThumbsUp className="w-3.5 h-3.5" />
                              </button>
                              <button className="hover:text-heal-ink dark:hover:text-white transition-colors cursor-pointer" title="Não útil">
                                <ThumbsDown className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          )}
                        </div>
                      ) : (
                        /* USER MESSAGE: Right-aligned bubble */
                        <div
                          key={msg.id}
                          className="flex flex-col items-end w-full py-3.5 animate-fade-in"
                        >
                          <div className="bg-heal-softBlue dark:bg-[#1c1c1f] hover:bg-blue-100 dark:hover:bg-[#232328] border border-heal-blue/10 dark:border-[#2c2c35]/40 text-heal-ink dark:text-white px-4 py-2.5 rounded-2xl max-w-[70%] text-sm break-words whitespace-pre-wrap font-sans transition-colors">
                            {msg.content}
                          </div>

                          {/* User action icons */}
                          <div className="flex items-center gap-3 mt-1.5 text-heal-muted dark:text-[#53535f] select-none mr-2">
                            <button
                              onClick={() => navigator.clipboard.writeText(msg.content)}
                              className="hover:text-heal-ink dark:hover:text-white transition-colors cursor-pointer"
                              title="Copiar"
                            >
                              <Copy className="w-3.5 h-3.5" />
                            </button>
                            <button
                              onClick={() => {
                                setInput(msg.content);
                                inputRef.current?.focus();
                              }}
                              className="hover:text-heal-ink dark:hover:text-white transition-colors cursor-pointer"
                              title="Editar"
                            >
                              <Pencil className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </div>
                      );
                    })}

                    {/* Thinking indicator */}
                    {thinking && (
                      <div className="flex flex-col items-start w-full py-4 border-b border-heal-line/20 dark:border-[#1f1f23]/10 animate-fade-in">
                        <div className="flex items-center gap-2.5 text-xs text-heal-muted dark:text-[#71767b] py-1 font-sans">
                          <div className="flex gap-1.5">
                            <span className="w-1.5 h-1.5 bg-heal-blue rounded-full animate-bounce [animation-delay:-0.3s]" />
                            <span className="w-1.5 h-1.5 bg-heal-blue rounded-full animate-bounce [animation-delay:-0.15s]" />
                            <span className="w-1.5 h-1.5 bg-heal-blue rounded-full animate-bounce" />
                          </div>
                          <span>Assistente está consultando seus dados...</span>
                        </div>
                      </div>
                    )}

                    <div ref={chatEndRef} />
                  </div>
                </div>
              </div>

              {/* Bottom fixed input */}
              <div className="shrink-0 bg-gradient-to-t from-white dark:from-[#060606] via-white dark:via-[#060606] to-white/80 dark:to-[#060606]/80 px-4 pt-2 pb-4 z-20 border-t border-heal-line/40 dark:border-[#1f1f23]/40">
                <div className="max-w-3xl w-full mx-auto flex flex-col items-center">
                  {/* Quick topics */}
                  <div className="mb-3 flex gap-2 overflow-x-auto pb-1 w-full">
                    {quickTopics.map(topic => (
                      <button
                        key={topic}
                        type="button"
                        className="shrink-0 rounded-full border border-heal-line dark:border-[#232329] bg-white dark:bg-[#131316]/90 px-3 py-1.5 text-[11px] font-bold text-heal-muted hover:border-heal-blue/40 hover:bg-heal-softBlue hover:text-heal-blue dark:hover:bg-[#1c1c22] dark:hover:text-blue-400 transition-all cursor-pointer"
                        onClick={() => send(topic)}
                      >
                        {topic}
                      </button>
                    ))}
                  </div>

                  {renderInputCard()}

                  <p className="mt-2.5 text-[10px] text-heal-muted dark:text-[#71767b] max-w-xl text-center flex items-center justify-center gap-1.5 select-none">
                    <Database className="w-3 h-3 text-heal-teal" />
                    <span>As respostas são um resumo dos dados salvos, não uma decisão clínica automática.</span>
                  </p>
                </div>
              </div>
            </>
          )}

          {/* History Drawer */}
          {renderHistoryDrawer()}
        </div>
      </div>
    </div>
  );
}
