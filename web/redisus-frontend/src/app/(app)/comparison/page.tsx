export default function ComparisonPage() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-extrabold font-headline text-on-surface">
          Comparação
        </h1>
        <p className="text-on-surface-variant mt-1">
          Compare avaliações lado a lado para acompanhar a evolução
        </p>
      </div>

      {/* Coming Soon Card */}
      <section className="bg-surface-container-low rounded-xl p-12 text-center border border-dashed border-outline-variant/20">
        <div className="max-w-md mx-auto space-y-4">
          <div className="w-20 h-20 bg-primary/10 rounded-full flex items-center justify-center mx-auto mb-6">
            <span className="material-symbols-outlined text-4xl text-primary">
              compare
            </span>
          </div>
          <h3 className="text-2xl font-bold font-headline">
            Em desenvolvimento
          </h3>
          <p className="text-on-surface-variant font-body">
            O módulo de comparação side-by-side permitirá visualizar múltiplas
            avaliações do mesmo paciente simultaneamente, facilitando o
            acompanhamento da evolução clínica da ferida.
          </p>
          <div className="pt-4 flex flex-wrap gap-3 justify-center">
            <div className="flex items-center gap-2 text-sm text-primary bg-primary/10 px-4 py-2 rounded-full">
              <span className="material-symbols-outlined text-sm">
                compare_arrows
              </span>
              Visão lado a lado
            </div>
            <div className="flex items-center gap-2 text-sm text-tertiary bg-tertiary/10 px-4 py-2 rounded-full">
              <span className="material-symbols-outlined text-sm">
                timeline
              </span>
              Linha do tempo
            </div>
            <div className="flex items-center gap-2 text-sm text-secondary bg-secondary/10 px-4 py-2 rounded-full">
              <span className="material-symbols-outlined text-sm">
                difference
              </span>
              Análise de diferenças
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
