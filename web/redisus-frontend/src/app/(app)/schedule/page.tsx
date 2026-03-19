"use client";

import { useMemo, useState } from "react";

type ViewMode = "mensal" | "semanal";
type AppointmentStatus = "pendente" | "em_andamento" | "concluida";

type Appointment = {
  id: string;
  date: string;
  time: string;
  patient: string;
  etiology: string;
  region: string;
  complexity?: "Alta Complexidade" | "Moderada" | "Baixa";
  status: AppointmentStatus;
};

const WEEK_DAYS = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"];

const INITIAL_APPOINTMENTS: Appointment[] = [
  {
    id: "apt-1",
    date: "2026-03-19",
    time: "09:00",
    patient: "Maria Santos",
    etiology: "Ferida Cirúrgica",
    region: "Abdominal",
    status: "pendente",
  },
  {
    id: "apt-2",
    date: "2026-03-19",
    time: "11:30",
    patient: "João Pereira",
    etiology: "Úlcera Diabética",
    region: "Pé Esquerdo",
    complexity: "Alta Complexidade",
    status: "pendente",
  },
  {
    id: "apt-3",
    date: "2026-03-19",
    time: "14:00",
    patient: "Ana Lúcia",
    etiology: "Lesão por Pressão",
    region: "Sacral",
    status: "concluida",
  },
  {
    id: "apt-4",
    date: "2026-03-21",
    time: "10:00",
    patient: "Carlos Mendes",
    etiology: "Ferida Venosa",
    region: "Tornozelo",
    complexity: "Moderada",
    status: "pendente",
  },
  {
    id: "apt-5",
    date: "2026-03-25",
    time: "15:00",
    patient: "Fernanda Costa",
    etiology: "Ferida Traumática",
    region: "Perna",
    status: "pendente",
  },
];

const toIsoDate = (date: Date) => date.toISOString().slice(0, 10);

const formatMonthYear = (date: Date) =>
  date.toLocaleDateString("pt-BR", { month: "long", year: "numeric" });

const formatLongDate = (isoDate: string) =>
  new Date(`${isoDate}T12:00:00`).toLocaleDateString("pt-BR", {
    weekday: "long",
    day: "2-digit",
    month: "long",
  });

const getMonthGrid = (referenceDate: Date) => {
  const year = referenceDate.getFullYear();
  const month = referenceDate.getMonth();

  const startOfMonth = new Date(year, month, 1);
  const endOfMonth = new Date(year, month + 1, 0);

  const startOffset = startOfMonth.getDay();
  const daysInMonth = endOfMonth.getDate();

  const cells: Date[] = [];

  for (let i = 0; i < startOffset; i += 1) {
    cells.push(new Date(year, month, i - startOffset + 1));
  }

  for (let day = 1; day <= daysInMonth; day += 1) {
    cells.push(new Date(year, month, day));
  }

  while (cells.length < 42) {
    const last = cells[cells.length - 1];
    cells.push(new Date(last.getFullYear(), last.getMonth(), last.getDate() + 1));
  }

  return cells;
};

const getWeekDays = (selectedDateIso: string) => {
  const base = new Date(`${selectedDateIso}T12:00:00`);
  const sunday = new Date(base);
  sunday.setDate(base.getDate() - base.getDay());

  return Array.from({ length: 7 }, (_, index) => {
    const day = new Date(sunday);
    day.setDate(sunday.getDate() + index);
    return day;
  });
};

export default function SchedulePage() {
  const [mode, setMode] = useState<ViewMode>("mensal");
  const [appointments, setAppointments] =
    useState<Appointment[]>(INITIAL_APPOINTMENTS);
  const [currentMonth, setCurrentMonth] = useState<Date>(new Date(2026, 2, 1));
  const [selectedDate, setSelectedDate] = useState<string>("2026-03-19");

  const monthGrid = useMemo(() => getMonthGrid(currentMonth), [currentMonth]);
  const weekDays = useMemo(() => getWeekDays(selectedDate), [selectedDate]);

  const appointmentsByDay = useMemo(() => {
    const map = new Map<string, Appointment[]>();
    for (const appointment of appointments) {
      const list = map.get(appointment.date) ?? [];
      list.push(appointment);
      list.sort((a, b) => a.time.localeCompare(b.time));
      map.set(appointment.date, list);
    }
    return map;
  }, [appointments]);

  const selectedDayAppointments = appointmentsByDay.get(selectedDate) ?? [];

  const monthStats = useMemo(() => {
    const month = currentMonth.getMonth();
    const year = currentMonth.getFullYear();

    const currentMonthAppointments = appointments.filter((item) => {
      const date = new Date(`${item.date}T12:00:00`);
      return date.getMonth() === month && date.getFullYear() === year;
    });

    const chronicCases = currentMonthAppointments.filter((item) =>
      ["Úlcera", "Lesão", "Ferida Venosa"].some((token) =>
        item.etiology.includes(token)
      )
    ).length;

    return {
      totalVisits: currentMonthAppointments.length,
      chronicCases,
      averageMinutes: currentMonthAppointments.length > 0 ? 35 : 0,
    };
  }, [appointments, currentMonth]);

  const updateStatus = (id: string, status: AppointmentStatus) => {
    setAppointments((current) =>
      current.map((item) => (item.id === id ? { ...item, status } : item))
    );
  };

  const addQuickAppointment = () => {
    const nextHour = `${String(8 + selectedDayAppointments.length).padStart(
      2,
      "0"
    )}:30`;
    const newItem: Appointment = {
      id: `apt-${Date.now()}`,
      date: selectedDate,
      time: nextHour,
      patient: "Novo Paciente",
      etiology: "Avaliação Inicial",
      region: "A definir",
      status: "pendente",
    };
    setAppointments((current) => [...current, newItem]);
  };

  return (
    <div className="space-y-8">
      <div className="grid grid-cols-12 gap-6">
        <section className="col-span-12 xl:col-span-8 space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-4xl font-extrabold font-headline tracking-tight text-on-surface">
                Agenda Clínica
              </h1>
              <p className="text-on-surface-variant mt-1 capitalize">
                {formatMonthYear(currentMonth)}
              </p>
            </div>
            <div className="bg-surface-container-low rounded-2xl p-1.5 flex gap-2 ghost-border">
              <button
                type="button"
                onClick={() => setMode("mensal")}
                className={`px-4 py-2 rounded-xl text-sm font-semibold transition-all ${
                  mode === "mensal"
                    ? "bg-surface-container-high text-on-surface shadow-ambient"
                    : "text-on-surface-variant hover:text-primary"
                }`}
              >
                Mensal
              </button>
              <button
                type="button"
                onClick={() => setMode("semanal")}
                className={`px-4 py-2 rounded-xl text-sm font-semibold transition-all ${
                  mode === "semanal"
                    ? "bg-surface-container-high text-on-surface shadow-ambient"
                    : "text-on-surface-variant hover:text-primary"
                }`}
              >
                Semanal
              </button>
            </div>
          </div>

          <div className="glass-effect rounded-3xl p-6 ghost-border shadow-ambient bg-surface-container-low/70">
            <div className="flex items-center justify-between mb-5">
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() =>
                    setCurrentMonth(
                      (current) =>
                        new Date(
                          current.getFullYear(),
                          current.getMonth() - 1,
                          1
                        )
                    )
                  }
                  className="w-9 h-9 rounded-xl bg-surface-container hover:bg-surface-container-high text-on-surface-variant hover:text-primary"
                >
                  <span className="material-symbols-outlined">chevron_left</span>
                </button>
                <button
                  type="button"
                  onClick={() =>
                    setCurrentMonth(
                      (current) =>
                        new Date(
                          current.getFullYear(),
                          current.getMonth() + 1,
                          1
                        )
                    )
                  }
                  className="w-9 h-9 rounded-xl bg-surface-container hover:bg-surface-container-high text-on-surface-variant hover:text-primary"
                >
                  <span className="material-symbols-outlined">chevron_right</span>
                </button>
              </div>
              <button
                type="button"
                onClick={() => {
                  const now = new Date();
                  setCurrentMonth(new Date(now.getFullYear(), now.getMonth(), 1));
                  setSelectedDate(toIsoDate(now));
                }}
                className="px-4 py-2 rounded-xl text-xs font-bold uppercase tracking-wider bg-primary/10 text-primary hover:bg-primary/15"
              >
                Hoje
              </button>
            </div>

            <div className="grid grid-cols-7 gap-3 mb-4">
              {WEEK_DAYS.map((day) => (
                <div
                  key={day}
                  className="text-center text-xs uppercase tracking-widest text-on-surface-variant font-bold"
                >
                  {day}
                </div>
              ))}
            </div>

            {mode === "mensal" ? (
              <div className="grid grid-cols-7 gap-3">
                {monthGrid.map((date) => {
                  const iso = toIsoDate(date);
                  const isCurrentMonth =
                    date.getMonth() === currentMonth.getMonth();
                  const isSelected = iso === selectedDate;
                  const isToday = iso === toIsoDate(new Date());
                  const dayAppointments = appointmentsByDay.get(iso) ?? [];

                  return (
                    <button
                      key={iso}
                      type="button"
                      onClick={() => setSelectedDate(iso)}
                      className={`h-28 rounded-2xl p-2 text-left bg-surface-container-low/60 hover:bg-primary/10 transition-colors ${
                        isSelected ? "bg-primary/10" : ""
                      } ${!isCurrentMonth ? "opacity-40" : ""}`}
                    >
                      <div
                        className={`text-xs font-bold ${
                          isSelected || isToday
                            ? "text-primary"
                            : "text-on-surface-variant"
                        }`}
                      >
                        {date.getDate()}
                      </div>
                      <div className="mt-1 space-y-1">
                        {dayAppointments.slice(0, 2).map((item) => (
                          <div
                            key={item.id}
                            className={`rounded-md px-1.5 py-1 text-[10px] font-semibold truncate ${
                              item.status === "concluida"
                                ? "bg-secondary-container/40 text-on-secondary-container"
                                : item.status === "em_andamento"
                                ? "bg-primary-container text-on-primary-container"
                                : "bg-tertiary/20 text-tertiary"
                            }`}
                          >
                            {item.time} - {item.patient}
                          </div>
                        ))}
                      </div>
                    </button>
                  );
                })}
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-3 md:grid-cols-7">
                {weekDays.map((date) => {
                  const iso = toIsoDate(date);
                  const isSelected = iso === selectedDate;
                  const items = appointmentsByDay.get(iso) ?? [];

                  return (
                    <button
                      key={iso}
                      type="button"
                      onClick={() => setSelectedDate(iso)}
                      className={`rounded-2xl p-3 bg-surface-container-low/60 text-left hover:bg-primary/10 ${
                        isSelected ? "bg-primary/10" : ""
                      }`}
                    >
                      <p className="text-xs font-bold text-on-surface-variant">
                        {WEEK_DAYS[date.getDay()]}
                      </p>
                      <p className="text-xl font-extrabold text-on-surface mt-1">
                        {date.getDate()}
                      </p>
                      <p className="mt-2 text-xs text-primary font-semibold">
                        {items.length} agendamento(s)
                      </p>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <article className="bg-surface-container-low rounded-3xl p-5 shadow-ambient">
              <p className="text-xs uppercase tracking-widest text-on-surface-variant">
                Total de visitas
              </p>
              <p className="mt-3 text-4xl font-extrabold font-headline">
                {monthStats.totalVisits}
              </p>
            </article>
            <article className="bg-surface-container-low rounded-3xl p-5 shadow-ambient">
              <p className="text-xs uppercase tracking-widest text-on-surface-variant">
                Feridas crônicas
              </p>
              <p className="mt-3 text-4xl font-extrabold font-headline text-tertiary">
                {monthStats.chronicCases}
              </p>
            </article>
            <article className="bg-surface-container-low rounded-3xl p-5 shadow-ambient">
              <p className="text-xs uppercase tracking-widest text-on-surface-variant">
                Tempo médio
              </p>
              <p className="mt-3 text-4xl font-extrabold font-headline text-primary">
                {monthStats.averageMinutes}m
              </p>
            </article>
          </div>
        </section>

        <aside className="col-span-12 xl:col-span-4 space-y-5">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-bold font-headline">Agenda do Dia</h2>
            <span className="px-3 py-1 rounded-full bg-primary/15 text-primary text-xs font-bold">
              {selectedDayAppointments.filter((item) => item.status !== "concluida")
                .length}{" "}
              pendente(s)
            </span>
          </div>
          <p className="text-sm text-on-surface-variant capitalize">
            {formatLongDate(selectedDate)}
          </p>

          <div className="space-y-3">
            {selectedDayAppointments.length === 0 && (
              <div className="rounded-3xl bg-surface-container-low p-6 text-center">
                <span className="material-symbols-outlined text-3xl text-primary">
                  event_busy
                </span>
                <p className="mt-2 text-sm text-on-surface-variant">
                  Sem consultas para este dia.
                </p>
              </div>
            )}

            {selectedDayAppointments.map((item) => (
              <article
                key={item.id}
                className="rounded-3xl bg-surface-container-low p-5 shadow-ambient"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="font-bold text-on-surface">{item.patient}</h3>
                    <p className="text-xs text-primary mt-1">
                      {item.etiology} • {item.region}
                    </p>
                  </div>
                  <span className="text-sm font-bold">{item.time}</span>
                </div>
                <div className="mt-4 flex items-center justify-between gap-2">
                  {item.complexity ? (
                    <span className="text-[10px] px-2 py-1 rounded-full bg-tertiary/15 text-tertiary font-bold uppercase tracking-wider">
                      {item.complexity}
                    </span>
                  ) : (
                    <span className="text-[10px] px-2 py-1 rounded-full bg-surface-container text-on-surface-variant font-bold uppercase tracking-wider">
                      Rotina
                    </span>
                  )}
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => updateStatus(item.id, "em_andamento")}
                      className="px-3 py-1.5 rounded-xl text-xs font-bold bg-primary-container text-on-primary-container hover:brightness-110"
                    >
                      Iniciar
                    </button>
                    <button
                      type="button"
                      onClick={() => updateStatus(item.id, "concluida")}
                      className="px-3 py-1.5 rounded-xl text-xs font-bold bg-surface-container-high text-on-surface hover:text-primary"
                    >
                      Concluir
                    </button>
                  </div>
                </div>
              </article>
            ))}
          </div>

          <button
            type="button"
            onClick={addQuickAppointment}
            className="w-full rounded-2xl bg-primary-gradient text-on-primary-container py-3 font-bold shadow-ambient"
          >
            + Novo agendamento rápido
          </button>
        </aside>
      </div>
    </div>
  );
}
