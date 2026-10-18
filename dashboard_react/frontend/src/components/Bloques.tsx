// Piezas visuales compartidas de la ficha: bloque suave con título corto y "pastilla" (chip).

export function Bloque({ titulo, children, extra }: { titulo: string; children: React.ReactNode; extra?: React.ReactNode }) {
  return (
    <section className="rounded-md bg-white border border-slate-200 px-3 py-2.5">
      <div className="flex items-baseline gap-2 mb-1.5">
        <h5 className="text-[11px] font-medium text-slate-500 flex-1">{titulo}</h5>
        {extra}
      </div>
      {children}
    </section>
  );
}

export function Chip({ children, titulo, fuerte = false }: { children: React.ReactNode; titulo?: string; fuerte?: boolean }) {
  return (
    <span
      title={titulo}
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] max-w-full ${
        fuerte ? "bg-blue-50 text-espol-navy border border-blue-100" : "bg-slate-100 text-slate-700"
      }`}
    >
      {children}
    </span>
  );
}
