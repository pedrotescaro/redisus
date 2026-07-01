interface MarkdownRendererProps {
  text: string;
}

export function MarkdownRenderer({ text }: MarkdownRendererProps) {
  if (!text) return null;

  // Split text by lines
  const lines = text.split('\n');

  return (
    <div className="space-y-2">
      {lines.map((line, lineIdx) => {
        const trimmed = line.trim();

        // 1. Check for list item starting with * or -
        const isBullet = trimmed.startsWith('* ') || trimmed.startsWith('- ');
        if (isBullet) {
          const content = trimmed.substring(2);
          return (
            <div key={lineIdx} className="flex gap-2 pl-4 py-0.5">
              <span className="text-heal-blue shrink-0 font-bold select-none">•</span>
              <span className="flex-1 text-sm leading-relaxed">{parseInlineStyles(content)}</span>
            </div>
          );
        }

        // 2. Check for numbered list item (e.g. 1. , 2. )
        const numMatch = trimmed.match(/^(\d+)\.\s+(.*)$/);
        if (numMatch) {
          const num = numMatch[1];
          const content = numMatch[2];
          return (
            <div key={lineIdx} className="flex gap-2 pl-2 py-0.5">
              <span className="font-bold text-heal-blue shrink-0 select-none">{num}.</span>
              <span className="flex-1 text-sm leading-relaxed">{parseInlineStyles(content)}</span>
            </div>
          );
        }

        // 3. Check for headers (e.g. ##, ###)
        const headerMatch = trimmed.match(/^(#{1,6})\s+(.*)$/);
        if (headerMatch) {
          const level = headerMatch[1].length;
          const content = headerMatch[2];
          const textClass = level === 1 
            ? 'text-lg font-black text-heal-ink dark:text-white mt-4' 
            : level === 2 
            ? 'text-base font-bold text-heal-ink dark:text-white mt-3' 
            : 'text-sm font-bold text-heal-ink dark:text-white mt-2';
          return (
            <div key={lineIdx} className={textClass}>
              {parseInlineStyles(content)}
            </div>
          );
        }

        // 4. Regular line
        if (line === '') {
          return <div key={lineIdx} className="h-1" />;
        }

        return (
          <p key={lineIdx} className="text-sm leading-relaxed">
            {parseInlineStyles(line)}
          </p>
        );
      })}
    </div>
  );
}

function parseInlineStyles(text: string) {
  const parts = text.split(/(\*\*.*?\*\*)/g);
  return parts.map((part, idx) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      const content = part.slice(2, -2);
      return <strong key={idx} className="font-bold text-heal-ink dark:text-white">{content}</strong>;
    }
    return parseItalic(part);
  });
}

function parseItalic(text: string) {
  const parts = text.split(/(\*.*?\*)/g);
  return parts.map((part, idx) => {
    if (part.startsWith('*') && part.endsWith('*')) {
      const content = part.slice(1, -1);
      return <em key={idx} className="italic">{content}</em>;
    }
    return part;
  });
}
