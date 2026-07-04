import { useState, useRef, useEffect } from 'react';
import { Sparkles, ChevronDown, ChevronUp, Info } from 'lucide-react';

export interface ModelOption {
  id: string;
  name: string;
  speed?: string;
  description?: string;
}

export const AVAILABLE_MODELS: ModelOption[] = [
  { id: 'adaptive', name: 'Adaptativo (Groq / Gemini)', speed: 'Fast', description: 'Combina as duas respostas escolhendo a melhor' },
  { id: 'gemini', name: 'Gemini 2.5 Flash', speed: 'Fast', description: 'Modelo rápido da Google com as novas chaves do projeto' },
  { id: 'groq', name: 'Llama 3.1 (Groq)', speed: 'Fast', description: 'Inferência ultra-rápida via Groq API' }
];

interface ModelSelectorProps {
  value: string;
  onChange: (value: string) => void;
  align?: 'left' | 'right' | 'up-left' | 'up-right';
  variant?: 'default' | 'minimal';
  className?: string;
}

export function ModelSelector({ value, onChange, align = 'right', variant = 'default', className = '' }: ModelSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const selectedModel = AVAILABLE_MODELS.find(m => m.id === value) || AVAILABLE_MODELS[0];

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const getAlignClass = () => {
    switch (align) {
      case 'left':
        return 'left-0 mt-1.5';
      case 'up-left':
        return 'left-0 bottom-full mb-1.5';
      case 'up-right':
        return 'right-0 bottom-full mb-1.5';
      case 'right':
      default:
        return 'right-0 mt-1.5';
    }
  };

  return (
    <div className={`relative inline-block text-left ${className}`} ref={dropdownRef}>
      {/* Button */}
      {variant === 'minimal' ? (
        <button
          type="button"
          onClick={() => setIsOpen(!isOpen)}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-heal-muted dark:text-zinc-400 hover:text-heal-ink dark:hover:text-white transition-all cursor-pointer focus:outline-none bg-transparent border-0 py-1 px-1.5 rounded-lg hover:bg-heal-surfaceHover dark:hover:bg-zinc-800/40"
        >
          <Sparkles className="h-3.5 w-3.5 text-heal-blue animate-pulse shrink-0" />
          <span>{selectedModel.name}</span>
          {isOpen ? (
            <ChevronUp className="h-3 w-3 text-heal-muted dark:text-zinc-500 shrink-0" />
          ) : (
            <ChevronDown className="h-3 w-3 text-heal-muted dark:text-zinc-500 shrink-0" />
          )}
        </button>
      ) : (
        <button
          type="button"
          onClick={() => setIsOpen(!isOpen)}
          className="inline-flex items-center gap-2 px-3 py-1.5 rounded-xl border border-heal-line dark:border-zinc-800 bg-white dark:bg-[#131316] text-xs font-bold text-heal-ink dark:text-white hover:bg-heal-surfaceHover dark:hover:bg-[#1c1c22] transition-all cursor-pointer shadow-sm focus:outline-none"
        >
          <Sparkles className="h-3.5 w-3.5 text-heal-blue animate-pulse" />
          <span>{selectedModel.name}</span>
          {isOpen ? (
            <ChevronUp className="h-3.5 w-3.5 text-heal-muted dark:text-zinc-500" />
          ) : (
            <ChevronDown className="h-3.5 w-3.5 text-heal-muted dark:text-zinc-500" />
          )}
        </button>
      )}

      {/* Dropdown Menu */}
      {isOpen && (
        <div
          className={`absolute z-50 w-72 rounded-2xl border border-heal-line dark:border-zinc-800 bg-white dark:bg-[#131316] p-2.5 shadow-xl dark:shadow-2xl transition-all animate-fade-in ${getAlignClass()}`}
        >
          {/* Header */}
          <div className="px-2 pb-2 border-b border-heal-line/40 dark:border-zinc-800/40 select-none">
            <span className="text-[10px] font-bold uppercase tracking-wider text-heal-muted dark:text-zinc-500">Model</span>
          </div>

          {/* Options */}
          <div className="mt-1.5 space-y-0.5">
            {AVAILABLE_MODELS.map(model => {
              const isSelected = model.id === value;
              return (
                <button
                  key={model.id}
                  type="button"
                  onClick={() => {
                    onChange(model.id);
                    setIsOpen(false);
                  }}
                  className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-left text-xs transition-all cursor-pointer ${
                    isSelected
                      ? 'bg-heal-softBlue/60 dark:bg-blue-950/40 text-heal-blue dark:text-blue-400 font-bold'
                      : 'text-heal-ink dark:text-[#b3b3b9] hover:bg-heal-surfaceHover dark:hover:bg-[#1c1c22] hover:text-heal-ink dark:hover:text-white'
                  }`}
                  title={model.description}
                >
                  <span className="truncate mr-2">{model.name}</span>
                  {model.speed && (
                    <div className="flex items-center gap-1 shrink-0 select-none">
                      <span className="px-1.5 py-0.5 rounded bg-heal-canvas dark:bg-zinc-800 text-[9px] font-bold text-heal-muted dark:text-zinc-400">
                        {model.speed}
                      </span>
                      <Info className="h-3.5 w-3.5 text-heal-muted dark:text-zinc-500" />
                    </div>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
