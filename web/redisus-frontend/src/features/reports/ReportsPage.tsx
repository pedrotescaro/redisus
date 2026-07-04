import { Printer, FileText } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

import { useAuth } from '../../app/providers/AuthProvider';
import { auth } from '../../lib/firebase';
import { ReportPreview } from '../../components/reports/ReportPreview';
import { Button } from '../../components/ui/button';
import { Card } from '../../components/ui/Card';
import { EmptyState } from '../../components/ui/EmptyState';
import { LoadingState } from '../../components/ui/LoadingState';
import { PageHeader } from '../../components/ui/PageHeader';
import { Select } from '../../components/ui/Select';
import { ModelSelector } from '../../components/ui/ModelSelector';
import type { Evaluation, Patient } from '../../lib/types';
import { listEvaluations } from '../evaluations/evaluationService';
import { subscribePatients } from '../patients/patientService';

function scoreResponse(text: string): number {
  if (!text) return -1;
  const cleaned = text.trim();
  if (cleaned.length < 10) return 0;
  
  const isGenericRules = [
    "assistente de ia do heal+",
    "para analise de feridas, recomendo",
    "para gerar relatorios, use",
    "ola! sou o assistente de ia"
  ].some(term => cleaned.toLowerCase().includes(term));
  
  if (isGenericRules) {
    return 0.5;
  }

  let score = 1.0;
  if (cleaned.includes('\n-') || cleaned.includes('\n*')) score += 2.0;
  if (cleaned.includes('###') || cleaned.includes('##')) score += 1.5;
  if (cleaned.includes('**')) score += 1.0;
  
  const lengthBonus = Math.min(cleaned.length / 500.0, 1.5);
  score += lengthBonus;
  return score;
}

function generateLatex(patient: Patient, evaluation: Evaluation, profile: any, includeAi: boolean, aiText: string | null): string {
  const sanitize = (text: string) => {
    if (!text) return '';
    return text
      .replace(/\\/g, '\\textbackslash{}')
      .replace(/_/g, '\\_')
      .replace(/%/g, '\\%')
      .replace(/\$/g, '\\$')
      .replace(/#/g, '\\#')
      .replace(/&/g, '\\&')
      .replace(/{/g, '\\{')
      .replace(/}/g, '\\}')
      .replace(/~/g, '\\textasciitilde{}')
      .replace(/\^/g, '\\textasciicircum{}');
  };

  const sanitizeMarkdown = (text: string) => {
    if (!text) return '';
    let escaped = sanitize(text);
    escaped = escaped.replace(/\\#\\#\\#\s*(.*?)(?:\n|\r\n?)/g, '\\subsubsection*{$1}\n');
    escaped = escaped.replace(/\\#\\#\s*(.*?)(?:\n|\r\n?)/g, '\\subsection*{$1}\n');
    escaped = escaped.replace(/\\#\s*(.*?)(?:\n|\r\n?)/g, '\\section*{$1}\n');
    escaped = escaped.replace(/\\*\\*(.*?)\\*\\*/g, '\\textbf{$1}');
    escaped = escaped.replace(/\\*(.*?)\\*/g, '\\textit{$1}');
    escaped = escaped.replace(/(?:^|\n)\s*-\s+(.*?)(?=\n|$)/g, '\n\\item $1');
    return escaped;
  };

  let timersLatex = '';
  Object.entries(evaluation.timers).forEach(([key, value]) => {
    if (!value) {
      timersLatex += `\\textbf{${key}}: Não informado \\\\\n`;
      return;
    }
    const parts = value.split('|').map(p => p.trim()).filter(Boolean);
    timersLatex += `\\subsubsection*{${key}}\n`;
    if (parts.length > 0) {
      timersLatex += `\\begin{itemize}\n`;
      parts.forEach(part => {
        const colonIdx = part.indexOf(':');
        if (colonIdx > -1) {
          const l = part.substring(0, colonIdx).trim();
          const v = part.substring(colonIdx + 1).trim();
          timersLatex += `  \\item \\textbf{${sanitize(l)}}: ${sanitize(v)}\n`;
        } else {
          timersLatex += `  \\item ${sanitize(part)}\n`;
        }
      });
      timersLatex += `\\end{itemize}\n`;
    } else {
      timersLatex += `Não informado\\\\\n`;
    }
  });

  return `% Relatório Clínico - Heal+ (Minimalist LaTeX Template)
\\documentclass[11pt,a4paper]{article}
\\usepackage[utf8]{inputenc}
\\usepackage[T1]{fontenc}
\\usepackage[portuguese]{babel}
\\usepackage{graphicx}
% Margens manuais sem geometry
\\pdfpagewidth=\\paperwidth
\\pdfpageheight=\\paperheight
\\setlength{\\topmargin}{-1.5cm}
\\setlength{\\textheight}{24cm}
\\setlength{\\oddsidemargin}{-0.5cm}
\\setlength{\\evensidemargin}{-0.5cm}
\\setlength{\\textwidth}{18cm}
\\setlength{\\headheight}{0cm}
\\setlength{\\headsep}{0cm}
\\usepackage{xcolor}
\\usepackage{hyperref}

\\definecolor{healblue}{HTML}{1A56DB}
\\definecolor{healbg}{HTML}{F9FAFB}

\\begin{document}

\\begin{center}
  \\large\\textbf{\\textsc{Relatório Clínico de Evolução de Lesão}} \\\\
  \\vspace{0.2cm}
  \\textcolor{healblue}{\\rule{\\linewidth}{1.5pt}}
\\end{center}

\\vspace{0.2cm}

\\subsection*{Identificação do Paciente}
\\begin{minipage}[t]{0.5\\textwidth}
  \\textbf{Paciente:} ${sanitize(patient.name)} \\\\
  \\textbf{Nascimento:} ${sanitize(patient.birthDate)} \\\\
  \\textbf{Telefone:} ${sanitize(patient.phone || 'Não informado')}
\\end{minipage}
\\begin{minipage}[t]{0.5\\textwidth}
  \\textbf{E-mail:} ${sanitize(patient.email || 'Não informado')} \\\\
  \\textbf{Data da Avaliação:} ${sanitize(evaluation.date)} \\\\
  \\textbf{Registro Profissional:} ${sanitize(profile?.displayName || 'Não informado')}
\\end{minipage}

\\vspace{0.6cm}
\\textcolor{lightgray}{\\hrule}
\\vspace{0.4cm}

\\subsection*{Parâmetros Clínicos da Lesão}
\\begin{itemize}
  \\item \\textbf{Localização:} ${sanitize(evaluation.woundLocation)}
  \\item \\textbf{Etiologia:} ${sanitize(evaluation.woundEtiology)}
  \\item \\textbf{Nível de Dor:} ${sanitize(evaluation.painLevel.toString())}/10
  \\item \\textbf{Exsudato:} ${sanitize(evaluation.exudateAmount)} (${sanitize(evaluation.exudateType)})
  \\item \\textbf{Bordas:} ${sanitize(evaluation.borderCharacteristics)}
  \\item \\textbf{Pele Perilesional:} ${sanitize(evaluation.periwoundSkin)}
\\end{itemize}

${evaluation.images?.[0] ? `
\\begin{center}
  \\includegraphics[width=0.45\\textwidth]{${evaluation.images[0].downloadURL}}
  \\\\ \\small\\textit{Registro fotográfico clínico da lesão.}
\\end{center}
` : ''}

\\vspace{0.4cm}
\\textcolor{lightgray}{\\hrule}
\\vspace{0.4cm}

\\subsection*{Framework T.I.M.E.R.S.}
${timersLatex}

${evaluation.notes ? `
\\vspace{0.4cm}
\\textcolor{lightgray}{\\hrule}
\\vspace{0.4cm}
\\subsection*{Observações Adicionais}
${sanitize(evaluation.notes)}
` : ''}

${includeAi && aiText ? `
\\vspace{0.4cm}
\\textcolor{lightgray}{\\hrule}
\\vspace{0.4cm}
\\subsection*{Análise e Parecer de IA Generativa}
\\begin{center}
  \\colorbox{healbg}{
    \\begin{minipage}{0.95\\textwidth}
      \\vspace{0.2cm}
      ${sanitizeMarkdown(aiText)}
      \\vspace{0.2cm}
    \\end{minipage}
  }
\\end{center}
` : ''}

\\vspace{1.5cm}

\\begin{center}
  \\begin{minipage}{0.5\\textwidth}
    \\centering
    \\rule{6cm}{0.4pt} \\\\
    \\small ${sanitize(profile?.displayName || 'Profissional Responsável')} \\\\
    \\small Assinatura do Profissional
  \\end{minipage}
\\end{center}

\\end{document}`;
}

export function ReportsPage() {
  const { user, profile } = useAuth();
  const [patients, setPatients] = useState<Patient[]>([]);
  const [evaluationsByPatient, setEvaluationsByPatient] = useState<Record<string, Evaluation[]>>({});
  const [patientId, setPatientId] = useState('');
  const [evaluationId, setEvaluationId] = useState('');
  const [loading, setLoading] = useState(true);

  // Lifted AI analysis states
  const [analysis, setAnalysis] = useState<string | null>(null);
  const [loadingAnalysis, setLoadingAnalysis] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [includeAi, setIncludeAi] = useState(true);
  const [generatingPdf, setGeneratingPdf] = useState(false);
  const [selectedModel, setSelectedModel] = useState<string>('adaptive');

  useEffect(() => {
    if (!user) return undefined;
    return subscribePatients(user.uid, next => {
      setPatients(next);
      setLoading(false);
      void Promise.all(next.map(patient => listEvaluations(user.uid, patient.id))).then(groups => {
        setEvaluationsByPatient(Object.fromEntries(next.map((patient, index) => [patient.id, groups[index]])));
      });
    });
  }, [user]);

  const selectedPatient = patients.find(patient => patient.id === patientId) || null;
  const evaluations = patientId ? evaluationsByPatient[patientId] || [] : [];
  const selectedEvaluation = evaluations.find(evaluation => evaluation.id === evaluationId) || evaluations[0] || null;
  const patientOptions = useMemo(() => patients.filter(patient => (evaluationsByPatient[patient.id] || []).length > 0), [evaluationsByPatient, patients]);

  useEffect(() => {
    if (!patientOptions.length) {
      if (patientId) setPatientId('');
      if (evaluationId) setEvaluationId('');
      return;
    }

    if (!patientOptions.some(patient => patient.id === patientId)) {
      setPatientId(patientOptions[0].id);
      setEvaluationId('');
    }
  }, [evaluationId, patientId, patientOptions]);

  useEffect(() => {
    if (selectedEvaluation && selectedEvaluation.id !== evaluationId) setEvaluationId(selectedEvaluation.id);
  }, [evaluationId, selectedEvaluation]);

  // Reset analysis when evaluation changes
  useEffect(() => {
    setAnalysis(null);
    setAnalysisError(null);
  }, [evaluationId]);

  const handleGenerateAnalysis = () => {
    if (!selectedPatient || !selectedEvaluation) return;

    setLoadingAnalysis(true);
    setAnalysisError(null);

    const apiKey = import.meta.env.VITE_GROQ_API_KEY || '';
    const model = import.meta.env.VITE_AI_MODEL || 'llama-3.1-8b-instant';

    const userPrompt = `Analise a seguinte avaliação clínica de ferida do paciente ${selectedPatient.name} realizada em ${selectedEvaluation.date}.
Detalhes da ferida:
- Local: ${selectedEvaluation.woundLocation}
- Etiologia: ${selectedEvaluation.woundEtiology}
- Dor: ${selectedEvaluation.painLevel}/10
- Exsudato: ${selectedEvaluation.exudateAmount} (${selectedEvaluation.exudateType})
- Bordas: ${selectedEvaluation.borderCharacteristics}
- Pele perilesional: ${selectedEvaluation.periwoundSkin}
- Timers T.I.M.E.R.S.:
  * Tissue: ${selectedEvaluation.timers.tissue || 'Não informado'}
  * Infection: ${selectedEvaluation.timers.infection || 'Não informado'}
  * Moisture: ${selectedEvaluation.timers.moisture || 'Não informado'}
  * Edge: ${selectedEvaluation.timers.edge || 'Não informado'}
  * Repair: ${selectedEvaluation.timers.repair || 'Não informado'}
  * Social: ${selectedEvaluation.timers.social || 'Não informado'}
- Observações: ${selectedEvaluation.notes || 'Sem observações adicionais'}

Por favor, gere um parecer clínico estruturado contendo:
1. RESUMO CLÍNICO: Um resumo rápido da situação da lesão.
2. PONTOS DE ATENÇÃO: Alertas sobre possíveis riscos (como dor elevada ou infecção).
3. PROPOSTA DE CONDUTA (T.I.M.E.R.S.): Sugestões práticas de cuidados e curativos baseados na avaliação.`;

    const systemInstruction = 'Você é um clínico especialista em estomaterapia e cicatrização de feridas crônicas.';

    const runGroq = async () => {
      if (!apiKey) throw new Error("Groq API key not set");
      const res = await fetch('https://api.groq.com/openai/v1/chat/completions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${apiKey}`
        },
        body: JSON.stringify({
          model,
          messages: [
            { role: 'system', content: systemInstruction },
            { role: 'user', content: userPrompt }
          ]
        })
      });
      if (!res.ok) throw new Error(`Groq status ${res.status}`);
      const data = await res.json();
      return data.choices?.[0]?.message?.content || '';
    };

    const runGemini = async () => {
      const headers: HeadersInit = {
        'Content-Type': 'application/json'
      };
      const localMode = import.meta.env.VITE_HEAL_ANALYZER_LOCAL_MODE === 'true';
      if (!localMode) {
        const userCred = auth.currentUser;
        if (userCred) {
          const token = await userCred.getIdToken();
          headers['Authorization'] = `Bearer ${token}`;
        }
      }
      
      const res = await fetch('/api/clinical/ai-chat', {
        method: 'POST',
        headers,
        body: JSON.stringify({
          message: `System instruction: ${systemInstruction}\n\nUser request: ${userPrompt}`,
          conversation_id: 'report-analysis-' + selectedEvaluation.id,
          context: {}
        })
      });
      if (!res.ok) throw new Error(`Gemini status ${res.status}`);
      const data = await res.json();
      return data.response || '';
    };

    const generateCall = async () => {
      if (selectedModel === 'gemini') {
        return await runGemini();
      } else if (selectedModel === 'groq') {
        return await runGroq();
      } else {
        const results = await Promise.allSettled([runGroq(), runGemini()]);
        const successful: { text: string; score: number }[] = [];
        results.forEach(res => {
          if (res.status === 'fulfilled' && res.value) {
            const score = scoreResponse(res.value);
            successful.push({ text: res.value, score });
          }
        });

        if (successful.length === 0) {
          throw new Error("Nenhum serviço de IA respondeu com sucesso.");
        }

        successful.sort((a, b) => b.score - a.score);
        return successful[0].text;
      }
    };

    generateCall()
      .then(text => {
        setAnalysis(text);
      })
      .catch(err => {
        console.error(err);
        setAnalysisError('Falha ao gerar análise. Verifique sua chave de API ou conexão.');
      })
      .finally(() => {
        setLoadingAnalysis(false);
      });
  };

  const handleExportLatex = () => {
    if (!selectedPatient || !selectedEvaluation) return;
    const latexContent = generateLatex(
      selectedPatient,
      selectedEvaluation,
      profile,
      includeAi,
      analysis
    );
    const blob = new Blob([latexContent], { type: 'application/x-latex;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    const filename = `relatorio_${selectedPatient.name.toLowerCase().replace(/\s+/g, '_')}_${selectedEvaluation.date}.tex`;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  };

  const handlePrintPdf = async () => {
    if (!selectedPatient || !selectedEvaluation) return;
    setGeneratingPdf(true);
    try {
      const latexContent = generateLatex(
        selectedPatient,
        selectedEvaluation,
        profile,
        includeAi,
        analysis
      );
      
      const headers: HeadersInit = {
        'Content-Type': 'application/json'
      };
      const localMode = import.meta.env.VITE_HEAL_ANALYZER_LOCAL_MODE === 'true';
      if (!localMode) {
        const userCred = auth.currentUser;
        if (userCred) {
          const token = await userCred.getIdToken();
          headers['Authorization'] = `Bearer ${token}`;
        }
      }
      
      const response = await fetch('/api/clinical/generate-pdf', {
        method: 'POST',
        headers,
        body: JSON.stringify({ latex_code: latexContent })
      });
      
      if (!response.ok) {
        let errMessage = 'Erro ao compilar PDF';
        try {
          const errData = await response.json();
          console.error('LaTeX compile error details:', errData);
          if (errData.log) {
            // Take last 10 lines of LaTeX log for clarity
            const logLines = errData.log.split('\n');
            const lastLines = logLines.slice(-15).join('\n');
            errMessage = `Log do LaTeX:\n${lastLines}`;
          } else if (errData.detail) {
            errMessage = errData.detail;
          }
        } catch (parseErr) {
          console.error('Failed to parse error response:', parseErr);
        }
        throw new Error(errMessage);
      }
      
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      const filename = `relatorio_${selectedPatient.name.toLowerCase().replace(/\s+/g, '_')}_${selectedEvaluation.date}.pdf`;
      link.download = filename;
      link.click();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      console.error(err);
      alert(`Falha ao compilar o PDF via LaTeX:\n\n${err.message || err}`);
    } finally {
      setGeneratingPdf(false);
    }
  };

  if (loading) return <LoadingState label="Carregando relatórios..." />;

  return (
    <div className="flex flex-col xl:flex-row min-h-screen min-w-0 bg-white dark:bg-[#0c0c0e]">
      {/* Coluna Central */}
      <div className="flex-grow max-w-5xl w-full border-r border-heal-line dark:border-zinc-800/60 min-h-screen flex flex-col min-w-0">
        <PageHeader
          title="Relatórios"
          description="Documento clínico e prévia de avaliações"
          action={
            <div className="flex flex-wrap items-center gap-3 no-print">
              <label className="flex items-center gap-2 text-xs font-bold text-heal-muted dark:text-zinc-400 select-none cursor-pointer bg-heal-canvas dark:bg-zinc-900/60 px-3 py-2 rounded-xl border border-heal-line dark:border-zinc-800">
                <input
                  type="checkbox"
                  checked={includeAi}
                  onChange={e => setIncludeAi(e.target.checked)}
                  className="rounded border-heal-line text-heal-blue focus:ring-heal-blue/30 h-4 w-4 bg-transparent cursor-pointer"
                />
                <span>Incluir Parecer de IA</span>
              </label>

              <Button
                variant="outline"
                icon={<FileText className="h-4 w-4" />}
                onClick={handleExportLatex}
                disabled={!selectedEvaluation}
              >
                Exportar LaTeX (.tex)
              </Button>

              <Button
                variant="secondary"
                icon={<Printer className="h-4 w-4" />}
                onClick={handlePrintPdf}
                disabled={!selectedEvaluation || generatingPdf}
              >
                {generatingPdf ? 'Compilando PDF (LaTeX)...' : 'Imprimir / salvar PDF'}
              </Button>
            </div>
          }
        />

        {/* Flat selectors */}
        <div className="no-print grid gap-4 md:grid-cols-3 p-4 border-b border-heal-line/60 dark:border-zinc-800/60">
          <Select
            label="Paciente"
            options={
              patientOptions.length > 0
                ? patientOptions.map(patient => ({ value: patient.id, label: patient.name }))
                : [{ value: '', label: 'Nenhum paciente com avaliação' }]
            }
            value={patientId}
            disabled={patientOptions.length === 0}
            onChange={event => {
              setPatientId(event.target.value);
              setEvaluationId('');
            }}
          />
          <Select
            label="Avaliação"
            options={
              evaluations.length > 0
                ? evaluations.map(evaluation => ({ value: evaluation.id, label: `${evaluation.date} - ${evaluation.woundLocation}` }))
                : [{ value: '', label: 'Nenhuma avaliação disponível' }]
            }
            value={selectedEvaluation?.id || ''}
            disabled={evaluations.length === 0}
            onChange={event => setEvaluationId(event.target.value)}
          />
          <div className="flex flex-col gap-1 bg-transparent">
            <label className="text-[11px] font-bold text-heal-muted dark:text-zinc-500 uppercase tracking-wider mb-1">Modelo de IA</label>
            <ModelSelector
              value={selectedModel}
              onChange={setSelectedModel}
              align="left"
              className="w-full"
            />
          </div>
        </div>

        {/* Report Preview */}
        <div className="p-4 sm:p-6 flex-grow space-y-4">
          {selectedPatient && selectedEvaluation ? (
            <ReportPreview
              patient={selectedPatient}
              evaluation={selectedEvaluation}
              profile={profile}
              analysis={analysis}
              loadingAnalysis={loadingAnalysis}
              analysisError={analysisError}
              onGenerateAnalysis={handleGenerateAnalysis}
              includeAi={includeAi}
            />
          ) : (
            <EmptyState title="Selecione uma avaliação real" description="Pacientes sem avaliação não aparecem como fonte de relatório." />
          )}
        </div>
      </div>
    </div>
  );
}
