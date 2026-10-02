import { useQuery } from "@tanstack/react-query";
import { getPersona, type Ambito } from "../api/client";
import { colorCluster, colorSub, NOMBRE_TIPO, pct } from "../lib/colores";
import TimelineTrayectoria from "./TimelineTrayectoria";

interface Props {
  ambito: Ambito;
  personaId: number;
  onPersona: (id: number) => void;
  /** volver a la vista anterior del panel (el grupo o la lista de grupos) */
  onVolver: () => void;
  textoVolver: string;
  /** abrir el grupo de la persona en el panel */
  onVerGrupo: (cluster: number) => void;
}

const Seccion = ({ titulo, children }: { titulo: string; children: React.ReactNode }) => (
  <div className="px-5 py-4 border-b">
    <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2">{titulo}</h4>
    {children}
  </div>
);

// Ficha de la persona (vista del panel derecho) y por qué está en su grupo.
export default function FichaPersona({ ambito, personaId, onPersona, onVolver, textoVolver, onVerGrupo }: Props) {
  const { data, isLoading, isError } = useQuery({ queryKey: ["persona", ambito, personaId], queryFn: () => getPersona(personaId, ambito) });

  const volver = (
    <button onClick={onVolver} className="text-xs text-espol-blue hover:underline px-5 pt-4 block text-left">
      ← {textoVolver}
    </button>
  );
  if (isLoading) return <div>{volver}<p className="p-5 text-sm text-slate-500">Cargando ficha…</p></div>;
  if (isError || !data)
    return <div>{volver}<p className="p-5 text-sm text-red-600">La persona seleccionada no está en este ámbito.</p></div>;
  const c = data.cluster;
  const s = data.subpatron;

  return (
    <section>
      {volver}
      <header className="px-5 pt-2 pb-4 border-b">
        <h3 className="text-lg font-semibold leading-tight text-espol-navy">{data.nombre}</h3>
        <p className="text-sm text-slate-700 mt-1">{data.estado.cargo_actual ?? "Sin cargo actual"}</p>
        <p className="text-xs text-slate-500">
          {data.estado.unidad_actual ?? "Unidad no registrada"} · {data.estado.tipo_empleado ?? "tipo desconocido"} ·{" "}
          {data.estado.vigente ? "vigente" : "no vigente"}
        </p>
      </header>

      <Seccion titulo="Trayectoria laboral">
        <TimelineTrayectoria personaId={data.persona_id} />
      </Seccion>

      <Seccion titulo="Su grupo">
        <div className="rounded-md p-3" style={{ background: `${colorCluster(c.cluster)}14`, borderLeft: `4px solid ${colorCluster(c.cluster)}` }}>
          <button className="text-sm font-medium text-slate-800 hover:underline text-left" onClick={() => onVerGrupo(c.cluster)}>
            {c.etiqueta} →
          </button>
          <p className="text-xs text-slate-600 mt-1">
            {c.es_representante ? (
              <strong>Es la persona representante de este grupo.</strong>
            ) : (
              <>
                Parecido con el representante (
                <button className="underline text-espol-blue" onClick={() => onPersona(c.representante_id)}>
                  {c.representante_nombre}
                </button>
                ): {pct(c.similitud_representante)}
              </>
            )}
          </p>
          {c.perfil_mixto && data.pertenencias[1] && (
            <p className="text-xs text-amber-800 mt-2 bg-amber-50 rounded px-2 py-1">
              Está entre dos grupos: se parece casi lo mismo a «{data.pertenencias[1].etiqueta}». Su perfil combina rasgos de
              ambos.
            </p>
          )}
        </div>

        {s && (
          <div className="rounded-md p-3 mt-2" style={{ background: `${colorSub(s.subpatron)}14`, borderLeft: `4px solid ${colorSub(s.subpatron)}` }}>
            <p className="text-[11px] uppercase text-slate-500">Subgrupo</p>
            <p className="text-sm font-medium text-slate-800">{s.etiqueta}</p>
            <p className="text-xs text-slate-600 mt-1">{s.descripcion}</p>
            <p className="text-xs text-slate-600 mt-1">
              {s.es_representante ? (
                <strong>Es la persona representante de este subgrupo.</strong>
              ) : (
                <>
                  Parecido con su representante (
                  <button className="underline text-espol-blue" onClick={() => onPersona(s.representante_id)}>
                    {s.representante_nombre}
                  </button>
                  ): {pct(s.similitud_representante)}
                </>
              )}
            </p>
            {s.perfil_mixto && (
              <p className="text-xs text-amber-700 mt-1">
                Está entre dos subgrupos: también se parece mucho a «{s.segundo_subpatron}».
              </p>
            )}
          </div>
        )}
      </Seccion>

      <Seccion titulo="Cuánto se parece a cada grupo">
        {data.pertenencias.map((p) => (
          <div key={p.cluster} className="flex items-center gap-2 text-xs mb-1">
            <span className="w-48 truncate" title={p.etiqueta}>{p.etiqueta}</span>
            <div className="flex-1 bg-slate-100 h-2 rounded">
              <div className="h-2 rounded" style={{ width: `${p.pertenencia * 100}%`, background: colorCluster(p.cluster) }} />
            </div>
            <span className="w-10 text-right">{pct(p.pertenencia)}</span>
          </div>
        ))}
        <p className="text-[11px] text-slate-400 mt-1">
          Cada persona pertenece a un solo grupo; las barras muestran cuánto se parece también a los demás.
        </p>
      </Seccion>

      <Seccion titulo="Por qué está en este grupo">
        <ul className="text-xs space-y-1 mb-3">
          {data.cluster_por_vista.map((v) => (
            <li key={v.vista} className="flex gap-2">
              <span className={v.coincide ? "text-emerald-600" : "text-amber-600"}>{v.coincide ? "✓" : "↗"}</span>
              <span>
                Por su <strong>{v.nombre}</strong>{" "}
                {v.coincide ? "se parece a este mismo grupo" : <>se parece más a «{v.etiqueta}»</>}
              </span>
            </li>
          ))}
        </ul>
        {data.vistas_faltantes.length > 0 && (
          <p className="text-[11px] text-amber-700 mb-2">Sin evidencias para: {data.vistas_faltantes.join(", ")} (se usó un valor neutro).</p>
        )}
        <p className="text-xs text-slate-600 mb-1">Lo que caracteriza a su grupo, comparado con esta persona:</p>
        <table className="w-full text-xs">
          <thead className="text-slate-400">
            <tr>
              <th className="text-left font-normal" />
              <th className="text-right font-normal">Esta persona</th>
              <th className="text-right font-normal">Su grupo</th>
            </tr>
          </thead>
          <tbody>
            {data.rasgos_legibles.slice(0, 6).map((r) => (
              <tr key={r.variable} className="border-t border-slate-100 align-top">
                <td className="py-1 pr-2">
                  <span className={r.direccion === "más" ? "text-emerald-600" : "text-rose-600"}>{r.direccion === "más" ? "▲" : "▼"}</span>{" "}
                  {r.texto}
                </td>
                <td className={`text-right font-medium whitespace-nowrap pl-2 ${r.comparte ? "text-emerald-700" : "text-slate-800"}`}>
                  {r.valor_persona}
                  {r.comparte && " ✓"}
                </td>
                <td className="text-right text-slate-500 whitespace-nowrap pl-2">{r.valor_grupo}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="text-[11px] text-slate-400 mt-1">
          ▲ / ▼: el grupo tiene más / menos que el personal en general. ✓: la persona coincide con su grupo en ese rasgo.
        </p>
      </Seccion>

      <Seccion titulo="Evidencias">
        <div className="space-y-2">
          {data.evidencias.map((g) => (
            <details key={g.tipo_id} className="text-xs">
              <summary className="cursor-pointer">
                {NOMBRE_TIPO[g.tipo_id] ?? g.tipo_id} ({g.n})
                {g.compartidas_con_cluster.length > 0 && (
                  <span className="text-emerald-700"> · {g.compartidas_con_cluster.length} en común con su grupo</span>
                )}
              </summary>
              <ul className="mt-1 ml-3 list-disc space-y-0.5 text-slate-600">
                {g.textos.map((t, i) => (
                  <li key={i} className={g.compartidas_con_cluster.includes(t) ? "text-emerald-800" : ""}>{t}</li>
                ))}
              </ul>
            </details>
          ))}
        </div>
      </Seccion>
    </section>
  );
}
