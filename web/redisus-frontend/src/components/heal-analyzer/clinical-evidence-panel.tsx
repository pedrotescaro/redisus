import { useMemo, useState, type ReactNode } from 'react';
import {
  Activity,
  AlertTriangle,
  BookOpen,
  Camera,
  Droplets,
  ExternalLink,
  HeartPulse,
  Search,
  ShieldAlert,
  Sparkles,
  Target
} from 'lucide-react';

import { cn } from '../../lib/utils';

type EvidenceSection = {
  id: string;
  eyebrow: string;
  title: string;
  summary: string;
  items: string[];
  icon: ReactNode;
  tone: string;
};

const evidenceSections: EvidenceSection[] = [
  {
    id: 'time',
    eyebrow: 'Estrutura clínica',
    title: 'TIME — leitura sistemática do leito',
    summary: 'Organize a observação local em tecido, inflamação/infecção, umidade e bordas.',
    icon: <Target className="h-4 w-4" />,
    tone: 'bg-cyan-500/10 text-cyan-700 dark:text-cyan-300',
    items: [
      'T — tecido: registrar granulação, epitelização, esfacelo/fibrina e necrose; tecido não viável exige avaliação profissional.',
      'I — inflamação/infecção: observar dor nova ou crescente, calor, eritema, edema, secreção purulenta, odor e piora clínica.',
      'M — umidade: descrever quantidade e tipo de exsudato, ressecamento, maceração e impacto na pele ao redor.',
      'E — bordas: verificar avanço epitelial, descolamento, socavamento, hiperqueratose e condição perilesional.'
    ]
  },
  {
    id: 'dataset',
    eyebrow: 'Dados para consulta',
    title: 'Conjunto mínimo da avaliação',
    summary: 'Campos que tornam a análise reproduzível e comparável no acompanhamento.',
    icon: <Activity className="h-4 w-4" />,
    tone: 'bg-blue-500/10 text-blue-700 dark:text-blue-300',
    items: [
      'Etiologia provável, localização anatômica, duração, perfusão e fatores que interferem na cicatrização.',
      'Comprimento × largura em eixos perpendiculares, profundidade, túneis, descolamentos e método de medição.',
      'Leito, bordas, pele ao redor, exsudato, odor após limpeza, dor e sinais clínicos de infecção.',
      'Data, profissional responsável, fotografia padronizada e comparação com a avaliação anterior.'
    ]
  },
  {
    id: 'alerts',
    eyebrow: 'Triagem de segurança',
    title: 'Sinais que pedem avaliação presencial',
    summary: 'A imagem isolada não confirma nem exclui infecção, isquemia ou gravidade sistêmica.',
    icon: <ShieldAlert className="h-4 w-4" />,
    tone: 'bg-rose-500/10 text-rose-700 dark:text-rose-300',
    items: [
      'Febre, confusão, instabilidade clínica, eritema em progressão, crepitação ou piora rápida exigem escalonamento urgente.',
      'Dor desproporcional, necrose nova, extremidade fria/pálida, perfusão reduzida ou suspeita de isquemia não devem depender da análise visual.',
      'Em pé diabético, combinar sinais de infecção, profundidade, perfusão e achados sistêmicos; não usar cor do leito como único critério.',
      'Resultados do HEAL+ apoiam documentação e triagem, mas a decisão diagnóstica e terapêutica permanece profissional.'
    ]
  },
  {
    id: 'photo',
    eyebrow: 'Aquisição de imagem',
    title: 'Fotografia clínica comparável',
    summary: 'Uma foto consistente melhora o ROI e reduz variações que confundem a análise.',
    icon: <Camera className="h-4 w-4" />,
    tone: 'bg-violet-500/10 text-violet-700 dark:text-violet-300',
    items: [
      'Fotografar perpendicularmente, com luz homogênea, foco no leito e sem filtros de câmera.',
      'Manter distância e enquadramento consistentes; incluir escala métrica quando o protocolo institucional permitir.',
      'Evitar sombras, reflexos, sangue ou resíduos que ocultem o leito; realizar limpeza conforme protocolo antes do registro.',
      'Confirmar consentimento, remover identificadores visíveis e seguir as regras locais de privacidade e armazenamento.'
    ]
  },
  {
    id: 'exudate',
    eyebrow: 'Leitura estruturada',
    title: 'Exsudato e pele perilesional',
    summary: 'Registrar tendência é mais útil do que uma observação isolada.',
    icon: <Droplets className="h-4 w-4" />,
    tone: 'bg-teal-500/10 text-teal-700 dark:text-teal-300',
    items: [
      'Quantidade: ausente, baixa, moderada ou alta, de acordo com o instrumento adotado pela instituição.',
      'Aspecto: seroso, serossanguinolento, sanguinolento ou purulento; registrar mudança em relação ao último atendimento.',
      'Pele ao redor: íntegra, macerada, eritematosa, descamativa, edemaciada ou com dermatite associada à umidade.',
      'Odor deve ser reavaliado após limpeza e interpretado junto de outros sinais — nunca isoladamente.'
    ]
  }
];

const sources = [
  {
    label: 'Wound Bed Preparation 2021',
    detail: 'Paradigma com avaliação holística, causa, capacidade de cicatrização e documentação local.',
    href: 'https://pmc.ncbi.nlm.nih.gov/articles/PMC7982138/'
  },
  {
    label: 'TIME — wound bed preparation',
    detail: 'Revisão do framework Tissue, Infection/Inflammation, Moisture e Edge.',
    href: 'https://pmc.ncbi.nlm.nih.gov/articles/PMC7949772/'
  },
  {
    label: 'IWGDF Guidelines 2023',
    detail: 'Classificação e infecção em úlceras relacionadas ao diabetes.',
    href: 'https://iwgdfguidelines.org/guidelines-2023/'
  },
  {
    label: 'International Guideline — Assessment',
    detail: 'Avaliação de pele e tecidos em prevenção e manejo de lesão por pressão.',
    href: 'https://www.internationalguideline.com/assessment'
  }
];

function normalize(value: string) {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase();
}

export function ClinicalEvidencePanel() {
  const [query, setQuery] = useState('');
  const normalizedQuery = normalize(query.trim());
  const filteredSections = useMemo(() => {
    if (!normalizedQuery) return evidenceSections;
    return evidenceSections.filter(section =>
      normalize([section.eyebrow, section.title, section.summary, ...section.items].join(' ')).includes(normalizedQuery)
    );
  }, [normalizedQuery]);

  return (
    <div className="space-y-4">
      <section className="overflow-hidden rounded-[24px] border border-heal-line bg-white shadow-soft dark:border-zinc-800 dark:bg-[#0c0c0e]">
        <div className="border-b border-heal-line bg-gradient-to-br from-sky-50 via-white to-cyan-50 p-5 dark:border-zinc-800 dark:from-sky-950/30 dark:via-zinc-950 dark:to-cyan-950/20">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-heal-blue text-white shadow-sm">
              <BookOpen className="h-5 w-5" />
            </div>
            <div>
              <p className="text-[10px] font-black uppercase tracking-[0.18em] text-heal-blue">Base clínica consultável</p>
              <h2 className="mt-1 text-xl font-black tracking-tight text-heal-ink dark:text-white">Referência no ponto de cuidado</h2>
              <p className="mt-2 text-xs leading-relaxed text-heal-muted dark:text-zinc-400">
                Resumos operacionais para apoiar documentação e raciocínio. Use o protocolo da instituição e julgamento profissional.
              </p>
            </div>
          </div>

          <label className="mt-4 flex h-10 items-center gap-2 rounded-xl border border-heal-line bg-white px-3 shadow-sm focus-within:border-heal-blue focus-within:ring-2 focus-within:ring-heal-blue/10 dark:border-zinc-800 dark:bg-zinc-900">
            <Search className="h-4 w-4 text-heal-muted" />
            <input
              value={query}
              onChange={event => setQuery(event.target.value)}
              placeholder="Buscar: necrose, exsudato, foto..."
              className="min-w-0 flex-1 border-0 bg-transparent text-xs font-semibold text-heal-ink outline-none placeholder:text-heal-muted dark:text-white"
            />
          </label>
        </div>

        <div className="divide-y divide-heal-line/60 dark:divide-zinc-800/70">
          {filteredSections.map(section => (
            <details key={section.id} className="group p-4" open={section.id === 'time' && !normalizedQuery}>
              <summary className="flex cursor-pointer list-none items-start gap-3 [&::-webkit-details-marker]:hidden">
                <span className={cn('flex h-9 w-9 shrink-0 items-center justify-center rounded-xl', section.tone)}>{section.icon}</span>
                <span className="min-w-0 flex-1">
                  <span className="block text-[9px] font-black uppercase tracking-[0.16em] text-heal-muted">{section.eyebrow}</span>
                  <span className="mt-0.5 block text-sm font-black text-heal-ink dark:text-white">{section.title}</span>
                  <span className="mt-1 block text-[11px] leading-relaxed text-heal-muted dark:text-zinc-400">{section.summary}</span>
                </span>
                <PlusIndicator />
              </summary>
              <div className="ml-12 mt-3 space-y-2.5">
                {section.items.map(item => (
                  <div key={item} className="flex items-start gap-2 text-[11px] leading-relaxed text-slate-600 dark:text-zinc-400">
                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-heal-blue" />
                    <p>{item}</p>
                  </div>
                ))}
              </div>
            </details>
          ))}

          {!filteredSections.length ? (
            <div className="p-8 text-center">
              <Search className="mx-auto h-5 w-5 text-heal-muted" />
              <p className="mt-2 text-xs font-bold text-heal-ink dark:text-white">Nenhum tópico encontrado</p>
              <button type="button" onClick={() => setQuery('')} className="mt-2 text-xs font-black text-heal-blue">
                Limpar busca
              </button>
            </div>
          ) : null}
        </div>
      </section>

      <section className="rounded-[24px] border border-heal-line bg-white p-5 shadow-soft dark:border-zinc-800 dark:bg-[#0c0c0e]">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-heal-blue" />
          <h3 className="text-sm font-black text-heal-ink dark:text-white">Fontes e rastreabilidade</h3>
        </div>
        <div className="mt-4 space-y-2">
          {sources.map(source => (
            <a
              key={source.href}
              href={source.href}
              target="_blank"
              rel="noreferrer"
              className="group flex items-start gap-3 rounded-xl border border-heal-line/70 p-3 transition hover:border-heal-blue/30 hover:bg-heal-softBlue/20 dark:border-zinc-800 dark:hover:bg-blue-950/20"
            >
              <HeartPulse className="mt-0.5 h-4 w-4 shrink-0 text-heal-blue" />
              <span className="min-w-0 flex-1">
                <span className="block text-xs font-black text-heal-ink group-hover:text-heal-blue dark:text-white">{source.label}</span>
                <span className="mt-1 block text-[10px] leading-relaxed text-heal-muted dark:text-zinc-500">{source.detail}</span>
              </span>
              <ExternalLink className="h-3.5 w-3.5 shrink-0 text-heal-muted group-hover:text-heal-blue" />
            </a>
          ))}
        </div>
      </section>

      <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-[11px] leading-relaxed text-amber-900 dark:border-amber-900/50 dark:bg-amber-950/20 dark:text-amber-200">
        <div className="flex items-start gap-2.5">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <p>
            Esta base resume referências para consulta rápida. Ela não substitui a leitura integral das diretrizes, a avaliação presencial ou protocolos locais.
          </p>
        </div>
      </div>
    </div>
  );
}

function PlusIndicator() {
  return (
    <span className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-heal-canvas text-heal-muted transition group-open:rotate-45 dark:bg-zinc-900">
      <span className="text-lg font-medium leading-none">+</span>
    </span>
  );
}
