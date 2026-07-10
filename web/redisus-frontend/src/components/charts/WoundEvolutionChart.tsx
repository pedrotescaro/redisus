import { useMemo, useState } from 'react';
import { formatDate } from '../../lib/date';
import type { Evaluation } from '../../lib/types';
import { 
  Activity, 
  ShieldAlert, 
  Droplet, 
  Layers, 
  Info,
  Maximize2,
  TrendingDown,
  TrendingUp,
  Minus,
  Calendar
} from 'lucide-react';
import { Badge } from '../ui/Badge';

interface WoundEvolutionChartProps {
  evaluations: Evaluation[];
}

const parseValue = (text: string, label: string): number | null => {
  const regex = new RegExp(`${label}:\\s*(\\d+(?:[.,]\\d+)?)\\s*(?:cm)?`, 'i');
  const match = text.match(regex);
  return match ? parseFloat(match[1].replace(',', '.')) : null;
};

const parsePercentage = (text: string, label: string): number => {
  const regex = new RegExp(`${label}\\s*(\\d+)\\s*%`, 'i');
  const match = text.match(regex);
  return match ? parseInt(match[1], 10) : 0;
};

export function WoundEvolutionChart({ evaluations }: WoundEvolutionChartProps) {
  const sortedPoints = useMemo(() => {
    return [...evaluations]
      .sort((a, b) => a.date.localeCompare(b.date))
      .map(ev => {
        const tissueText = ev.timers.tissue || '';
        const width = parseValue(tissueText, 'Largura');
        const length = parseValue(tissueText, 'Comprimento');
        const area = width !== null && length !== null ? width * length : null;
        
        const gran = parsePercentage(tissueText, 'Granulação');
        const epit = parsePercentage(tissueText, 'Epitelização');
        const esfa = parsePercentage(tissueText, 'Esfacelo');
        const necr = parsePercentage(tissueText, 'Necrose');
        
        let predTissue = 'N/D';
        let maxPct = 0;
        if (gran > maxPct) { predTissue = 'Granulação'; maxPct = gran; }
        if (epit > maxPct) { predTissue = 'Epitelização'; maxPct = epit; }
        if (esfa > maxPct) { predTissue = 'Esfacelo'; maxPct = esfa; }
        if (necr > maxPct) { predTissue = 'Necrose'; maxPct = necr; }
        if (maxPct > 0) {
          predTissue = `${predTissue} (${maxPct}%)`;
        }

        // Wound Score calculation (lower is better)
        let score = 0;
        const computedArea = area !== null ? area : 0;
        score += Math.min(computedArea, 50) * 0.5;
        score += ev.painLevel * 0.4;
        score += (ev.infectionSigns?.length || 0) * 2;
        const exudate = (ev.exudateAmount || '').toLowerCase();
        if (exudate.includes('abundante') || exudate.includes('grande')) {
          score += 3;
        } else if (exudate.includes('moderado')) {
          score += 2;
        } else if (exudate.includes('pequeno') || exudate.includes('leve')) {
          score += 1;
        }
        score += (necr * 0.08) + (esfa * 0.04) - (epit * 0.02);
        
        const woundScore = Math.max(1, parseFloat(score.toFixed(1)));

        return {
          date: ev.date,
          painLevel: ev.painLevel,
          infectionSigns: ev.infectionSigns || [],
          exudateAmount: ev.exudateAmount || 'Ausente',
          exudateType: ev.exudateType || '',
          area,
          predTissue,
          woundScore,
          width,
          length
        };
      });
  }, [evaluations]);

  // Track active index (defaults to the latest evaluation)
  const [activeIndex, setActiveIndex] = useState<number>(sortedPoints.length - 1);

  if (sortedPoints.length < 2) {
    return (
      <div className="rounded-2xl border border-zinc-100 dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-900/20 p-6 text-center">
        <p className="text-xs text-zinc-400 dark:text-zinc-500 font-semibold">
          Necessário ao menos 2 avaliações para exibir o painel de evolução clínica da ferida.
        </p>
      </div>
    );
  }

  const latest = sortedPoints[activeIndex] || sortedPoints[sortedPoints.length - 1];
  const first = sortedPoints[0];

  // Chart dimensions
  const W = 580;
  const H = 220;
  const PAD = { top: 28, right: 30, bottom: 40, left: 36 };
  const plotW = W - PAD.left - PAD.right;
  const plotH = H - PAD.top - PAD.bottom;

  // Y-axis scaling
  const maxScore = Math.max(...sortedPoints.map(p => p.woundScore), 10);
  const yMax = Math.ceil(maxScore / 5) * 5;
  const yMin = 0;
  const yTicks = Array.from({ length: 6 }).map((_, i) => Math.round((yMax / 5) * i));

  // X positions
  const xStep = plotW / (sortedPoints.length - 1);
  const points = sortedPoints.map((dp, i) => ({
    ...dp,
    x: PAD.left + i * xStep,
    y: PAD.top + plotH - ((dp.woundScore - yMin) / (yMax - yMin)) * plotH,
  }));

  // Generate cubic bezier path for smooth line
  const getBezierPath = (pts: { x: number; y: number }[]) => {
    if (pts.length === 0) return '';
    let path = `M ${pts[0].x} ${pts[0].y}`;
    for (let i = 0; i < pts.length - 1; i++) {
      const p0 = pts[i];
      const p1 = pts[i + 1];
      const cp1x = p0.x + (p1.x - p0.x) / 2;
      const cp1y = p0.y;
      const cp2x = p0.x + (p1.x - p0.x) / 2;
      const cp2y = p1.y;
      path += ` C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${p1.x} ${p1.y}`;
    }
    return path;
  };

  const linePath = getBezierPath(points);
  const areaPath = `${linePath} L ${points[points.length - 1].x} ${PAD.top + plotH} L ${points[0].x} ${PAD.top + plotH} Z`;

  // General wound evolution status (comparing last to first)
  const totalScoreDiff = sortedPoints[sortedPoints.length - 1].woundScore - first.woundScore;
  const totalImproving = totalScoreDiff < 0;
  const totalStable = totalScoreDiff === 0;

  const trendLabel = totalImproving ? 'Melhora Clínica' : totalStable ? 'Quadro Estável' : 'Necessita Atenção (Piora)';
  const trendColor = totalImproving ? 'text-emerald-600 dark:text-emerald-400' : totalStable ? 'text-zinc-550 dark:text-zinc-400' : 'text-rose-600 dark:text-rose-455';
  const trendBg = totalImproving ? 'bg-emerald-50/50 dark:bg-emerald-950/15 border-emerald-250 dark:border-emerald-900/30' : totalStable ? 'bg-zinc-50 dark:bg-zinc-900/20 border-zinc-200 dark:border-zinc-800' : 'bg-rose-50/50 dark:bg-rose-950/15 border-rose-250 dark:border-rose-900/30';
  const strokeColor = totalImproving ? '#10b981' : totalStable ? '#3b82f6' : '#f43f5e';

  return (
    <div className="space-y-4">
      {/* Main clinical dashboard layout */}
      <div className="rounded-2xl border border-zinc-200/80 dark:border-zinc-800/80 bg-white dark:bg-zinc-950/40 p-5 space-y-4 shadow-sm">
        
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-zinc-100 dark:border-zinc-900 pb-3.5">
          <div>
            <h3 className="text-sm font-black text-zinc-900 dark:text-white uppercase tracking-wider">Evolução clínica da ferida</h3>
            <p className="text-[10.5px] text-zinc-500 dark:text-zinc-400 font-semibold mt-0.5 leading-snug">
              Acompanhamento da evolução com base em escore clínico, dor, exsudato, tecido e sinais de infecção.
            </p>
          </div>
          <div className={`flex items-center gap-1.5 px-3 py-1 rounded-full border text-[10px] font-black shrink-0 select-none ${trendBg} ${trendColor}`}>
            {totalImproving ? (
              <TrendingDown className="h-3 w-3" />
            ) : totalStable ? (
              <Minus className="h-3 w-3" />
            ) : (
              <TrendingUp className="h-3 w-3" />
            )}
            <span>{trendLabel}</span>
          </div>
        </div>

        {/* Chart SVG */}
        <div className="relative">
          <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" preserveAspectRatio="xMidYMid meet">
            <defs>
              <linearGradient id="scoreGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={strokeColor} stopOpacity="0.16" />
                <stop offset="100%" stopColor={strokeColor} stopOpacity="0.00" />
              </linearGradient>
            </defs>

            {/* Y Gridlines */}
            {yTicks.map(tick => {
              const y = PAD.top + plotH - ((tick - yMin) / (yMax - yMin)) * plotH;
              return (
                <g key={tick}>
                  <line
                    x1={PAD.left}
                    y1={y}
                    x2={PAD.left + plotW}
                    y2={y}
                    stroke="currentColor"
                    className="text-zinc-100 dark:text-zinc-900/60"
                    strokeWidth="1"
                    strokeDasharray={tick === 0 ? undefined : '4 3'}
                  />
                  <text
                    x={PAD.left - 8}
                    y={y + 3}
                    textAnchor="end"
                    className="fill-zinc-400 dark:fill-zinc-500 font-bold"
                    fontSize="9"
                  >
                    {tick}
                  </text>
                </g>
              );
            })}

            {/* Area fill */}
            <path d={areaPath} fill="url(#scoreGrad)" />

            {/* Vertical connector line for active dot */}
            {points[activeIndex] && (
              <line
                x1={points[activeIndex].x}
                y1={PAD.top}
                x2={points[activeIndex].x}
                y2={PAD.top + plotH}
                stroke={strokeColor}
                strokeWidth="1.5"
                strokeDasharray="3 3"
                opacity="0.35"
              />
            )}

            {/* Neon Glow underlay line */}
            <path
              d={linePath}
              fill="none"
              stroke={strokeColor}
              strokeWidth="5"
              strokeLinecap="round"
              strokeLinejoin="round"
              opacity="0.15"
            />

            {/* Main score line */}
            <path
              d={linePath}
              fill="none"
              stroke={strokeColor}
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />

            {/* Points */}
            {points.map((p, i) => {
              const isActive = i === activeIndex;
              return (
                <g 
                  key={i} 
                  className="cursor-pointer group/point"
                  onClick={() => setActiveIndex(i)}
                >
                  {/* Invisible larger circle to make clicking easier */}
                  <circle cx={p.x} cy={p.y} r="14" fill="transparent" />

                  {/* Outer glow ring */}
                  <circle 
                    cx={p.x} 
                    cy={p.y} 
                    r={isActive ? "9" : "7"} 
                    fill={strokeColor} 
                    opacity={isActive ? "0.22" : "0.08"} 
                    className="transition-all duration-200 group-hover/point:opacity-20"
                  />
                  {/* White ring */}
                  <circle 
                    cx={p.x} 
                    cy={p.y} 
                    r={isActive ? "5.5" : "4.5"} 
                    fill="white" 
                    stroke={strokeColor} 
                    strokeWidth={isActive ? "2.5" : "2"} 
                    className="transition-all duration-200"
                  />
                  {/* Inner dot */}
                  <circle cx={p.x} cy={p.y} r="2" fill={strokeColor} />

                  {/* Score value above dot */}
                  <text
                    x={p.x}
                    y={p.y - 12}
                    textAnchor="middle"
                    fontSize={isActive ? "10.5" : "9.5"}
                    fontWeight="900"
                    className={`${isActive ? 'fill-zinc-900 dark:fill-white font-black' : 'fill-zinc-650 dark:fill-zinc-300'}`}
                  >
                    {p.woundScore}
                  </text>

                  {/* Date label */}
                  <text
                    x={p.x}
                    y={PAD.top + plotH + 16}
                    textAnchor="middle"
                    fontSize="8.5"
                    fontWeight={isActive ? "900" : "700"}
                    className={`${isActive ? 'fill-zinc-900 dark:fill-white' : 'fill-zinc-400 dark:fill-zinc-550'}`}
                  >
                    {formatDate(p.date).replace(/\/\d{4}$/, '')}
                  </text>

                  {/* Danger flag if there are infection signs */}
                  {p.infectionSigns.length > 0 && (
                    <g>
                      <circle cx={p.x + 8} cy={p.y - 8} r="5.5" fill="#fef2f2" stroke="#ef4444" strokeWidth="1" />
                      <text x={p.x + 8} y={p.y - 5} textAnchor="middle" fontSize="6.5" fontWeight="900" fill="#dc2626">
                        !
                      </text>
                    </g>
                  )}
                </g>
              );
            })}

            {/* Y axis label */}
            <text
              x={10}
              y={PAD.top + plotH / 2}
              textAnchor="middle"
              fontSize="8.5"
              fontWeight="900"
              className="fill-zinc-450 dark:fill-zinc-500 uppercase tracking-widest"
              transform={`rotate(-90, 10, ${PAD.top + plotH / 2})`}
            >
              Escore
            </text>
          </svg>
          
          <div className="absolute top-1 right-2 flex items-center gap-1.5 text-[8.5px] font-bold text-zinc-450 dark:text-zinc-500 select-none">
            <Info className="h-3.5 w-3.5 shrink-0 text-zinc-400" />
            <span>Clique nos pontos para visualizar os detalhes abaixo</span>
          </div>
        </div>
      </div>

      {/* Date banner for active card view */}
      <div className="flex items-center gap-2 px-1 text-xs text-zinc-555 dark:text-zinc-400 font-extrabold select-none">
        <Calendar className="h-4 w-4 opacity-75 text-heal-blue" />
        <span>Detalhamento da avaliação de: </span>
        <Badge tone="blue">{formatDate(latest.date)}</Badge>
        {activeIndex === sortedPoints.length - 1 && (
          <span className="text-[10px] font-medium text-zinc-405">(Última avaliação)</span>
        )}
      </div>

      {/* Supporting clinical cards for the active selected index */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5">
        {/* Card 1: Area */}
        <div className="rounded-xl border border-zinc-150 dark:border-zinc-800 bg-zinc-50/40 dark:bg-zinc-900/10 p-3.5">
          <div className="flex items-center gap-1.5 text-zinc-450 dark:text-zinc-500">
            <Maximize2 className="h-3.5 w-3.5" />
            <span className="text-[9px] font-black uppercase tracking-wider">Área</span>
          </div>
          <p className="text-sm font-extrabold text-zinc-900 dark:text-white mt-1.5 leading-none">
            {latest.area !== null ? `${latest.area.toFixed(1)} cm²` : 'N/D'}
          </p>
          <p className="text-[9px] text-zinc-405 dark:text-zinc-500 mt-1 font-semibold">
            {latest.area !== null && latest.length && latest.width ? `${latest.length} x ${latest.width} cm` : 'Medidas ausentes'}
          </p>
        </div>

        {/* Card 2: Dor */}
        <div className="rounded-xl border border-zinc-150 dark:border-zinc-800 bg-zinc-50/40 dark:bg-zinc-900/10 p-3.5">
          <div className="flex items-center gap-1.5 text-zinc-450 dark:text-zinc-500">
            <Activity className="h-3.5 w-3.5" />
            <span className="text-[9px] font-black uppercase tracking-wider">Dor</span>
          </div>
          <p className="text-sm font-extrabold text-zinc-900 dark:text-white mt-1.5 leading-none">
            {latest.painLevel}/10
          </p>
          <p className="text-[9px] text-zinc-405 dark:text-zinc-500 mt-1 font-semibold">
            Declaração de dor
          </p>
        </div>

        {/* Card 3: Exsudato */}
        <div className="rounded-xl border border-zinc-150 dark:border-zinc-800 bg-zinc-50/40 dark:bg-zinc-900/10 p-3.5">
          <div className="flex items-center gap-1.5 text-zinc-450 dark:text-zinc-500">
            <Droplet className="h-3.5 w-3.5" />
            <span className="text-[9px] font-black uppercase tracking-wider">Exsudato</span>
          </div>
          <p className="text-sm font-extrabold text-zinc-900 dark:text-white mt-1.5 leading-none truncate" title={latest.exudateAmount}>
            {latest.exudateAmount}
          </p>
          <p className="text-[9px] text-zinc-405 dark:text-zinc-500 mt-1 font-semibold truncate" title={latest.exudateType}>
            {latest.exudateType || 'Sem secreção'}
          </p>
        </div>

        {/* Card 4: Tecido Predominante */}
        <div className="rounded-xl border border-zinc-150 dark:border-zinc-800 bg-zinc-50/40 dark:bg-zinc-900/10 p-3.5">
          <div className="flex items-center gap-1.5 text-zinc-450 dark:text-zinc-500">
            <Layers className="h-3.5 w-3.5" />
            <span className="text-[9px] font-black uppercase tracking-wider">Tecido</span>
          </div>
          <p className="text-sm font-extrabold text-zinc-900 dark:text-white mt-1.5 leading-none truncate" title={latest.predTissue}>
            {latest.predTissue}
          </p>
          <p className="text-[9px] text-zinc-405 dark:text-zinc-500 mt-1 font-semibold">
            Predominância
          </p>
        </div>

        {/* Card 5: Infecção */}
        <div className="rounded-xl border border-zinc-150 dark:border-zinc-800 bg-zinc-50/40 dark:bg-zinc-900/10 p-3.5 col-span-2 sm:col-span-1">
          <div className="flex items-center gap-1.5 text-zinc-450 dark:text-zinc-500">
            <ShieldAlert className="h-3.5 w-3.5" />
            <span className="text-[9px] font-black uppercase tracking-wider">Infecção</span>
          </div>
          <p className={`text-sm font-extrabold mt-1.5 leading-none ${latest.infectionSigns.length > 0 ? 'text-rose-600 dark:text-rose-400' : 'text-emerald-600 dark:text-emerald-400'}`}>
            {latest.infectionSigns.length > 0 ? 'Presente' : 'Ausente'}
          </p>
          <p className="text-[9px] text-zinc-405 dark:text-zinc-500 mt-1 font-semibold truncate" title={latest.infectionSigns.join(', ')}>
            {latest.infectionSigns.length > 0 ? `${latest.infectionSigns.length} sinais clínicos` : 'Sem sinais ativos'}
          </p>
        </div>
      </div>
    </div>
  );
}
