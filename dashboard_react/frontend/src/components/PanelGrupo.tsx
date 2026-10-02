import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getDetalleCluster, type Ambito, type RasgoLegible } from "../api/client";
import { colorCluster, colorSub, pct } from "../lib/colores";

interface Props {
  ambito: Ambito;
  cluster: number;
  etiquetas: Record<string, string>;
  subpatron: number | null;
  onSubpatron: (s: number | null) => void;
  onPersona: (id: number) => void;
  onVolver: () => void;
}

type Pestana = "personas" | "caracteristicas" | "subgrupos";

// Rasgos en unidades reales: valor del grupo frente a la referencia, con ▲/▼.
export const TablaRasgos = ({ rasgos, grupo, referencia }: { rasgos: RasgoLegible[]; grupo: string; referencia: string }) => (
  <table className="w-full text-xs">
    <thead className="text-slate-400">
      <tr>
        <th className="text-left font-normal" />
        <th className="text-right font-normal">{grupo}</th>
        <th className="text-right font-normal">{referencia}</th>
      </tr>
    </thead>
    <tbody>
      {rasgos.map((r) => (
        <tr key={r.variable} className="border-t border-slate-100 align-top">
          <td className="py-1.5 pr-2">
            <span className={r.direccion === "más" ? "text-emerald-600" : "text-rose-600"}>{r.direccion === "más" ? "▲" : "▼"}</span>{" "}
            {r.texto}
          </td>
          <td className="text-right font-medium text-slate-800 pl-2">{r.valor_grupo}</td>
          <td className="text-right text-slate-500 pl-2">{r.valor_referencia}</td>
        </tr>
      ))}
    </tbody>
  </table>
);

const Titulo = ({ children }: { children: React.ReactNode }) => (
  <h4 className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 mb-2">{children}</h4>
);

// Vista "grupo" del panel derecho: resumen, personas, características y subgrupos.
export default function PanelGrupo({ ambito, cluster, etiquetas, subpatron, onSubpatron, onPersona, onVolver }: Props) {
  const { data, isLoading } = useQuery({ queryKey: ["cluster", ambito, cluster], queryFn: () => getDetalleCluster(ambito, cluster) });
  const [pestana, setPestana] = useState<Pestana>("personas");
  const [filtro, setFiltro] = useState("");
  const [verMas, setVerMas] = useState(false);

  const volver = (
    <button onClick={onVolver} className="text-xs text-espol-blue hover:underline">
      ← Todos los grupos
    </button>
  );
  if (isLoading || !data) return <div className="p-5">{volver}<p className="text-sm text-slate-500 mt-3">Cargando grupo…</p></div>;

  const f = data.ficha;
  const sub = f.subdivision;
  const subSel = sub?.subpatrones.find((s) => s.cluster === subpatron) ?? null;
  const etiquetaSub = (s: number) => sub?.subpatrones.find((x) => x.cluster === s)?.etiqueta ?? "";
  const q = filtro.trim().toLowerCase();
  const personas = (
    subSel
      ? data.integrantes
          .filter((p) => p.subpatron === subSel.cluster)
          .sort((a, b) => (b.similitud_subrepresentante ?? 0) - (a.similitud_subrepresentante ?? 0))
      : data.integrantes
  ).filter((p) => !q || `${p.nombre} ${p.cargo_actual ?? ""} ${p.unidad_actual ?? ""}`.toLowerCase().includes(q));

  const pestanas: { id: Pestana; texto: string }[] = [
    { id: "personas", texto: `Personas (${f.tamano_vigentes})` },
    { id: "caracteristicas", texto: "Características" },
    ...(sub ? [{ id: "subgrupos" as Pestana, texto: `Subgrupos (${sub.k})` }] : []),
  ];

  return (
    <section>
      <div className="px-5 pt-4">{volver}</div>
      <header className="px-5 pt-2 pb-3">
        <div className="flex items-start gap-2">
          <span className="mt-1.5 w-3 h-3 rounded-full shrink-0" style={{ background: colorCluster(f.cluster) }} />
          <h3 className="text-lg font-semibold leading-snug text-espol-navy">{f.etiqueta}</h3>
        </div>
        <p className={`text-xs text-slate-600 mt-2 leading-relaxed ${verMas ? "" : "line-clamp-2"}`}>{f.descripcion}</p>
        <button className="text-[11px] text-espol-blue hover:underline" onClick={() => setVerMas(!verMas)}>
          {verMas ? "ver menos" : "ver más"}
        </button>
        <p className="text-xs text-slate-500 mt-2">
          Representante:{" "}
          <button className="underline text-espol-blue" onClick={() => onPersona(f.representante.persona_id)}>
            {f.representante.nombre}
          </button>
          {!f.representante.vigente && " (ya no vigente)"}
        </p>
      </header>

      <nav className="px-5 border-b flex gap-4 text-sm sticky top-0 bg-white z-10">
        {pestanas.map((p) => (
          <button
            key={p.id}
            onClick={() => setPestana(p.id)}
            className={`py-2 -mb-px border-b-2 ${pestana === p.id ? "border-espol-accent text-espol-navy font-medium" : "border-transparent text-slate-500 hover:text-slate-700"}`}
          >
            {p.texto}
          </button>
        ))}
      </nav>

      {pestana === "personas" && (
        <div className="px-5 py-3 space-y-2">
          {sub && (
            <div className="flex flex-wrap gap-1">
              <button
                onClick={() => onSubpatron(null)}
                className={`text-[11px] px-2 py-0.5 rounded-full border ${subpatron === null ? "bg-espol-navy text-white border-espol-navy" : "bg-white text-slate-600"}`}
              >
                Todos
              </button>
              {sub.subpatrones.map((s) => (
                <button
                  key={s.subpatron_id}
                  onClick={() => onSubpatron(subpatron === s.cluster ? null : s.cluster)}
                  title={s.descripcion}
                  className={`text-[11px] px-2 py-0.5 rounded-full border flex items-center gap-1 ${subpatron === s.cluster ? "bg-slate-800 text-white border-slate-800" : "bg-white text-slate-600"}`}
                >
                  <span className="w-2 h-2 rounded-full" style={{ background: colorSub(s.cluster) }} />
                  {s.etiqueta.length > 34 ? `${s.etiqueta.slice(0, 33)}…` : s.etiqueta} ({s.tamano_vigentes})
                </button>
              ))}
            </div>
          )}
          <input
            value={filtro}
            onChange={(e) => setFiltro(e.target.value)}
            placeholder="Filtrar por nombre, cargo o unidad…"
            className="w-full border rounded-md px-2.5 py-1.5 text-xs"
          />
          <p className="text-[11px] text-slate-400">
            {personas.length} personas vigentes, de la más a la menos parecida a la representante{subSel ? " del subgrupo" : ""}.
          </p>
          <ul className="divide-y">
            {personas.map((p) => (
              <li key={p.persona_id}>
                <button onClick={() => onPersona(p.persona_id)} className="w-full text-left py-2 hover:bg-slate-50 flex items-start gap-2">
                  {sub && <span className="mt-1.5 w-2 h-2 rounded-full shrink-0" style={{ background: colorSub(p.subpatron) }} title={etiquetaSub(p.subpatron)} />}
                  <span className="flex-1 min-w-0">
                    <span className="block text-sm text-slate-800 truncate">
                      {p.nombre}
                      {(subSel ? p.es_subrepresentante : p.es_representante) && (
                        <span className="ml-1.5 text-[10px] font-medium text-slate-600 bg-slate-100 border border-slate-200 rounded px-1 align-middle">
                          Representante
                        </span>
                      )}
                    </span>
                    <span className="block text-[11px] text-slate-500 truncate">
                      {p.cargo_actual ?? "Sin cargo actual"}
                      {p.unidad_actual ? ` · ${p.unidad_actual}` : ""}
                    </span>
                    {p.perfil_mixto && (
                      <span className="inline-block mt-0.5 text-[10px] text-amber-800 bg-amber-50 border border-amber-200 rounded px-1">
                        también se parece a: {etiquetas[p.cluster_2]}
                      </span>
                    )}
                  </span>
                  <span className="text-[11px] text-slate-400 shrink-0" title="Parecido con la persona representante">
                    {pct(subSel ? p.similitud_subrepresentante : p.similitud_representante)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          {data.mixtos_desde_otros_clusters.length > 0 && !subSel && (
            <p className="text-[11px] text-slate-500 pt-2 border-t">
              Además, {data.mixtos_desde_otros_clusters.length} personas de otros grupos se parecen casi lo mismo a este.
            </p>
          )}
        </div>
      )}

      {pestana === "caracteristicas" && (
        <div className="px-5 py-4 space-y-5">
          <div>
            <Titulo>Qué lo distingue</Titulo>
            <TablaRasgos rasgos={f.rasgos_legibles.slice(0, 7)} grupo="Este grupo" referencia="En general" />
          </div>
          <div>
            <Titulo>Qué registros tienen más que el resto</Titulo>
            <table className="w-full text-xs">
              <thead className="text-slate-400">
                <tr>
                  <th className="text-left font-normal">Personas con…</th>
                  <th className="text-right font-normal">Este grupo</th>
                  <th className="text-right font-normal">En general</th>
                </tr>
              </thead>
              <tbody>
                {f.tipos_evidencia.slice(0, 6).map((t) => (
                  <tr key={t.tipo_id} className="border-t border-slate-100">
                    <td className="py-1.5 pr-2">{t.tipo}</td>
                    <td className="text-right font-medium">{pct(t.prop_integrantes)}</td>
                    <td className="text-right text-slate-500">{pct(t.prop_ambito)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div>
            <Titulo>Lo que más comparten</Titulo>
            <ul className="text-xs space-y-1.5">
              {f.evidencias_compartidas.slice(0, 6).map((e) => (
                <li key={e.texto}>
                  {e.texto} <span className="text-slate-400">({pct(e.prop)} del grupo)</span>
                </li>
              ))}
            </ul>
            {f.terminos_distintivos.length > 0 && (
              <p className="text-[11px] text-slate-500 mt-2">Palabras clave: {f.terminos_distintivos.slice(0, 8).join(", ")}</p>
            )}
          </div>
        </div>
      )}

      {pestana === "subgrupos" && sub && (
        <div className="px-5 py-4 space-y-2">
          <p className="text-[11px] text-slate-500">
            Grupos más pequeños dentro de este grupo, comparados con el grupo completo. Elige uno para verlo en el mapa.
          </p>
          {sub.subpatrones.map((s) => {
            const activo = subpatron === s.cluster;
            return (
              <div key={s.subpatron_id} className={`border rounded-md ${activo ? "ring-2 ring-espol-accent" : ""}`}>
                <button
                  onClick={() => onSubpatron(activo ? null : s.cluster)}
                  className="w-full text-left p-3 hover:bg-slate-50"
                  style={{ borderLeft: `4px solid ${colorSub(s.cluster)}` }}
                >
                  <p className="text-sm font-medium">{s.etiqueta}</p>
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    {s.tamano_vigentes} personas vigentes · representante: {s.representante.nombre}
                  </p>
                </button>
                {activo && (
                  <div className="px-3 pb-3">
                    <p className="text-xs text-slate-600 mb-2">{s.descripcion}</p>
                    <TablaRasgos rasgos={s.rasgos_legibles.slice(0, 5)} grupo="Subgrupo" referencia="Grupo completo" />
                    <button className="text-xs text-espol-blue hover:underline mt-2" onClick={() => setPestana("personas")}>
                      Ver sus personas →
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
