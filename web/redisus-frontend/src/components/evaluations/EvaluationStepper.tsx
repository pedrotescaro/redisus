import { Check } from 'lucide-react';

interface EvaluationStepperProps {
  steps: string[];
  currentStep: number;
}

export function EvaluationStepper({ steps, currentStep }: EvaluationStepperProps) {
  return (
    <ol className="grid gap-2 rounded-card border border-heal-line bg-white p-3 shadow-sm dark:border-zinc-800 dark:bg-zinc-900 md:grid-cols-4">
      {steps.map((step, index) => {
        const active = index === currentStep;
        const done = index < currentStep;
        return (
          <li
            key={step}
            className={`flex items-center gap-3 rounded-2xl px-3 py-2 text-sm font-bold transition ${
              active
                ? 'bg-heal-softBlue text-heal-blue'
                : done
                  ? 'bg-heal-tealSoft text-heal-teal'
                  : 'text-heal-muted dark:text-zinc-400'
            }`}
          >
            <span
              className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs ${
                done ? 'bg-heal-teal text-white' : active ? 'bg-heal-blue text-white' : 'bg-slate-100 text-slate-500'
              }`}
            >
              {done ? <Check className="h-4 w-4" /> : index + 1}
            </span>
            <span className="truncate">{step}</span>
          </li>
        );
      })}
    </ol>
  );
}
