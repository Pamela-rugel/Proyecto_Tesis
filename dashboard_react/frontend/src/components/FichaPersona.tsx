import { useQuery } from "@tanstack/react-query";
import { de } from "../lib/texto";
import { getPersona, type Ambito } from "../api/client";
import { NOMBRE_TIPO } from "../lib/colores";
import IntensidadDimensiones from "./IntensidadDimensiones";
import TimelineTrayectoria from "./TimelineTrayectoria";

interface Props {
  ambito: Ambito;
  personaId: number;
  /** volver a la vista anterior del panel */
  onVolver: () => void;
  textoVolver: string;
  /** abrir la ficha de otra persona (personas parecidas) */
  onPersona?: (id: number) => void;
}

const NOMBRE_AMBITO: Record<Ambito, string> = {
  todos: "todo el personal",
  administrativos: "el personal administrativo",
  docentes: "el personal docente",
};

const Seccion = ({ titulo, children }: { titulo: string; children: React.ReactNode }) => (
  <div className="px-5 py-4 border-b">
    <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2">{titulo}</h4>
    {children}
  </div>
);

// Ficha de la persona: intensidad, patrón y temas en cada dimensión, trayectoria y evidencias.
export default function FichaPersona({ ambito, personaId, onVolver, textoVolver, onPersona }: Props) {
  const { data, isLoading, isError } = useQuery({ queryKey: ["persona", ambito, personaId], queryFn: () => getPersona(personaId, ambito) });

  const volver = (
    <button onClick={onVolver} className="text-xs text-espol-blue hover:underline px-5 pt-4 block text-left">
      ← {textoVolver}
    </button>
  );
  if (isLoading) return <div>{volver}<p className="p-5 text-sm text-slate-500">Cargando ficha…</p></div>;
  if (isError || !data)
    return <div>{volver}<p className="p-5 text-sm text-red-600">La persona seleccionada no está en {NOMBRE_AMBITO[ambito]}.</p></div>;

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

      {data.patron_global && (() => {
        const g = data.patron_global;
        const similitud = (sim: number | null, esRep: boolean, rep: string | null, repId: number | null) =>
          esRep ? (
            <strong>Es la persona más representativa.</strong>
          ) : sim !== null && rep ? (
            <>
              Se parece un {Math.round(sim * 100)} % a la persona más representativa (
              <button className="text-espol-blue hover:underline disabled:no-underline disabled:text-slate-600" disabled={!onPersona}
                onClick={() => repId !== null && onPersona?.(repId)}>
                {rep}
              </button>
              ). 100 % = ella misma; 0 % = la más distinta del grupo.
            </>
          ) : (
            "El grupo no tiene personas vigentes que lo representen."
          );
        return (
          <Seccion titulo="Patrón global (todas las dimensiones)">
            <p className="text-sm text-slate-800">Patrón global {g.patron + 1}</p>
            <p className="text-xs text-slate-600">{g.etiqueta}</p>
            <p className="text-[11px] text-slate-500 mt-1">
              {g.tamano} personas {de(NOMBRE_AMBITO[ambito])} · {similitud(g.similitud_representante, g.es_representante, g.representante_nombre, g.representante_id)}
            </p>
            {g.mixto && (
              <p className="text-[11px] text-amber-700 mt-1">
                Está entre dos patrones: también se parece mucho al Patrón global {g.segundo + 1}.
              </p>
            )}
            {g.micro && (
              <div className="mt-2 pl-3 border-l">
                <p className="text-xs text-slate-800">Microarquetipo {g.micro.codigo}</p>
                <p className="text-[11px] text-slate-600">{g.micro.etiqueta}</p>
                <p className="text-[11px] text-slate-500 mt-0.5">
                  {g.micro.tamano} personas ·{" "}
                  {similitud(g.micro.similitud_representante, g.micro.es_representante, g.micro.representante_nombre, g.micro.representante_id)}
                </p>
                {g.micro.mixto && <p className="text-[11px] text-amber-700">Está entre dos microarquetipos.</p>}
              </div>
            )}
          </Seccion>
        );
      })()}

      <Seccion titulo="Intensidad por dimensión">
        <IntensidadDimensiones ambito={ambito} dimensiones={data.dimensiones} />
      </Seccion>

      {data.parecidos.length > 0 && (
        <Seccion titulo="Personas con perfil parecido">
          <p className="text-[11px] text-slate-500 mb-2">
            Las más cercanas considerando todas las dimensiones a la vez (cuánto tiene en cada una y cómo participa). Se
            indica en qué coinciden: dimensiones donde ambas tienen intensidad de 50 o más, y si siguen el mismo patrón.
          </p>
          <ol className="space-y-2">
            {data.parecidos.map((x) => (
              <li key={x.persona_id} className="text-xs">
                <button
                  className="text-espol-blue hover:underline font-medium text-left disabled:no-underline disabled:text-slate-800"
                  disabled={!onPersona}
                  onClick={() => onPersona?.(x.persona_id)}
                >
                  {x.rango}. {x.nombre}
                </button>
                <span className="text-slate-500"> · {x.cargo_actual ?? "Sin cargo actual"}</span>
                {x.comparte.length > 0 && (
                  <p className="text-slate-600 mt-0.5">
                    Ambas:{" "}
                    {x.comparte.map((c, i) => (
                      <span key={c.dimension}>
                        {i > 0 && ", "}
                        {c.nombre}
                        {c.mismo_patron && c.patron !== null && <span className="text-slate-500"> (Patrón {c.patron + 1})</span>}
                      </span>
                    ))}
                  </p>
                )}
              </li>
            ))}
          </ol>
        </Seccion>
      )}

      <Seccion titulo="Trayectoria laboral">
        <TimelineTrayectoria personaId={data.persona_id} />
      </Seccion>

      <Seccion titulo="Evidencias">
        <div className="space-y-2">
          {data.evidencias.map((g) => (
            <details key={g.tipo_id} className="text-xs">
              <summary className="cursor-pointer">
                {NOMBRE_TIPO[g.tipo_id] ?? g.tipo_id} ({g.n})
              </summary>
              <ul className="mt-1 ml-3 list-disc space-y-0.5 text-slate-600">
                {g.textos.map((t, i) => (
                  <li key={i}>{t}</li>
                ))}
              </ul>
            </details>
          ))}
        </div>
      </Seccion>
    </section>
  );
}
