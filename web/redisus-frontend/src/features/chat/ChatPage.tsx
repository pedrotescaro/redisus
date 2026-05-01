import { Bot, CalendarCheck2, Database, HelpCircle, SendHorizontal, Sparkles } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

import { useAuth } from '../../app/providers/AuthProvider';
import { Button } from '../../components/ui/Button';
import { LoadingState } from '../../components/ui/LoadingState';
import type { Appointment, Evaluation, Patient } from '../../lib/types';
import { subscribeAppointments } from '../agenda/agendaService';
import { listEvaluations } from '../evaluations/evaluationService';
import { subscribePatients } from '../patients/patientService';
import { answerLocalQuestion } from './localAssistant';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

const suggestions = [
  {
    title: 'Como você pode me ajudar?',
    description: 'Entenda o que consigo consultar no banco local.',
    prompt: 'Como você pode me ajudar?',
    icon: HelpCircle
  },
  {
    title: 'Resumo do meu dia',
    description: 'Veja retornos e atendimentos já salvos no app.',
    prompt: 'Resumo do meu dia',
    icon: CalendarCheck2
  }
];

const quickTopics = ['pacientes ativos', 'agenda de hoje', 'avaliações salvas', 'pacientes arquivados'];

export function ChatPage() {
  const { user, profile } = useAuth();
  const [patients, setPatients] = useState<Patient[]>([]);
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [evaluationsByPatient, setEvaluationsByPatient] = useState<Record<string, Evaluation[]>>({});
  const [loading, setLoading] = useState(true);
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);

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

  const firstName = useMemo(() => (profile?.displayName || user?.displayName || 'Profissional').split(' ')[0], [profile?.displayName, user?.displayName]);

  const send = (override?: string) => {
    const question = (override || input).trim();
    if (!question) return;
    const answer = answerLocalQuestion(question, { patients, appointments, evaluationsByPatient });
    setMessages(current => [...current, { role: 'user', content: question }, { role: 'assistant', content: answer }]);
    setInput('');
  };

  if (loading) return <LoadingState label="Carregando dados para o assistente..." />;

  return (
    <div className="mx-auto flex min-h-[calc(100vh-9rem)] max-w-5xl flex-col overflow-hidden rounded-[1.75rem] border border-heal-line bg-white shadow-soft dark:border-zinc-800 dark:bg-zinc-900">
      <header className="flex items-center justify-between gap-4 border-b border-heal-line px-5 py-4 dark:border-zinc-800">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-heal-softBlue text-heal-blue dark:bg-blue-950/40">
            <Bot className="h-6 w-6" />
          </div>
          <div className="min-w-0">
            <h1 className="truncate text-xl font-black text-heal-ink dark:text-white">Assistente Heal+</h1>
            <p className="truncate text-sm font-semibold text-heal-muted dark:text-zinc-400">Consulta local aos seus dados do Firestore</p>
          </div>
        </div>
        <div className="hidden items-center gap-2 rounded-full bg-heal-canvas px-3 py-2 text-xs font-black text-heal-muted dark:bg-zinc-950 sm:inline-flex">
          <Database className="h-4 w-4 text-heal-teal" />
          Sem API externa
        </div>
      </header>

      <div className="flex-1 overflow-y-auto bg-heal-canvas/60 p-5 dark:bg-zinc-950/60">
        {messages.length === 0 ? (
          <div className="mx-auto flex max-w-2xl flex-col items-center justify-center py-12 text-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-heal-softBlue text-heal-blue dark:bg-blue-950/40">
              <Sparkles className="h-7 w-7" />
            </div>
            <h2 className="mt-5 text-3xl font-black tracking-tight text-heal-ink dark:text-white">Oi, {firstName}. O que você quer pesquisar?</h2>
            <p className="mt-3 max-w-lg text-sm leading-6 text-heal-muted dark:text-zinc-400">
              Posso responder sobre pacientes ativos, arquivados, avaliações e agenda que já estão salvos na sua conta.
            </p>
            <div className="mt-6 grid w-full gap-3 sm:grid-cols-2">
              {suggestions.map(item => (
                <button
                  key={item.title}
                  type="button"
                  onClick={() => send(item.prompt)}
                  className="rounded-2xl border border-heal-line bg-white p-4 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-heal-blue/50 dark:border-zinc-800 dark:bg-zinc-900"
                >
                  <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-heal-softBlue text-heal-blue dark:bg-blue-950/40">
                    <item.icon className="h-5 w-5" />
                  </div>
                  <p className="mt-4 text-sm font-black text-heal-ink dark:text-white">{item.title}</p>
                  <p className="mt-1 text-xs leading-5 text-heal-muted dark:text-zinc-400">{item.description}</p>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {messages.map((message, index) => (
              <div key={`${message.role}-${index}`} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div
                  className={`max-w-[82%] whitespace-pre-line rounded-2xl px-4 py-3 text-sm font-medium leading-6 shadow-sm ${
                    message.role === 'user'
                      ? 'rounded-br-md bg-heal-blue text-white'
                      : 'rounded-bl-md border border-heal-line bg-white text-slate-700 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-200'
                  }`}
                >
                  {message.content}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <footer className="border-t border-heal-line bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
        <div className="mb-3 flex gap-2 overflow-x-auto pb-1">
          {quickTopics.map(topic => (
            <button
              key={topic}
              type="button"
              className="shrink-0 rounded-full border border-heal-line bg-heal-canvas px-3 py-1.5 text-xs font-black text-heal-muted transition hover:border-heal-blue/50 hover:bg-heal-softBlue hover:text-heal-blue dark:border-zinc-800 dark:bg-zinc-950"
              onClick={() => send(topic)}
            >
              {topic}
            </button>
          ))}
        </div>

        <div className="flex gap-2">
          <input
            className="h-12 flex-1 rounded-2xl border border-heal-line bg-heal-canvas px-4 text-sm font-semibold text-heal-ink outline-none transition placeholder:text-heal-muted focus:border-heal-blue focus:bg-white focus:ring-2 focus:ring-heal-blue/15 dark:border-zinc-700 dark:bg-zinc-950 dark:text-white dark:focus:bg-zinc-900"
            value={input}
            onChange={event => setInput(event.target.value)}
            onKeyDown={event => {
              if (event.key === 'Enter') send();
            }}
            placeholder="Pergunte sobre pacientes, agenda ou avaliações"
          />
          <Button type="button" className="h-12 rounded-2xl px-4" icon={<SendHorizontal className="h-5 w-5" />} onClick={() => send()} aria-label="Enviar pergunta" />
        </div>
        <p className="mt-3 text-center text-xs font-semibold text-heal-muted dark:text-zinc-500">As respostas são um resumo operacional dos dados salvos, não uma decisão clínica automática.</p>
      </footer>
    </div>
  );
}
