export default function SchedulePage() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-extrabold font-headline text-on-surface">
          Agenda
        </h1>
        <p className="text-on-surface-variant mt-1">
          Gerencie seus agendamentos e consultas
        </p>
      </div>

      {/* Coming Soon Card */}
      <section className="bg-surface-container-low rounded-xl p-12 text-center border border-dashed border-outline-variant/20">
        <div className="max-w-md mx-auto space-y-4">
          <div className="w-20 h-20 bg-primary/10 rounded-full flex items-center justify-center mx-auto mb-6">
            <span className="material-symbols-outlined text-4xl text-primary">
              calendar_month
            </span>
          </div>
          <h3 className="text-2xl font-bold font-headline">
            Em desenvolvimento
          </h3>
          <p className="text-on-surface-variant font-body">
            O módulo de agenda permitirá agendar consultas, acompanhamentos e
            definir lembretes para avaliações de feridas. Integração com
            calendários externos será suportada.
          </p>
          <div className="pt-4 flex flex-wrap gap-3 justify-center">
            <div className="flex items-center gap-2 text-sm text-primary bg-primary/10 px-4 py-2 rounded-full">
              <span className="material-symbols-outlined text-sm">
                event
              </span>
              Agendamentos
            </div>
            <div className="flex items-center gap-2 text-sm text-tertiary bg-tertiary/10 px-4 py-2 rounded-full">
              <span className="material-symbols-outlined text-sm">
                notifications_active
              </span>
              Lembretes
            </div>
            <div className="flex items-center gap-2 text-sm text-secondary bg-secondary/10 px-4 py-2 rounded-full">
              <span className="material-symbols-outlined text-sm">
                sync
              </span>
              Sincronização
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
