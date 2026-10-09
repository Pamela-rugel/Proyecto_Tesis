import { useQuery } from "@tanstack/react-query";
import { de } from "../lib/texto";
import { getPersonasPatronGlobal, type Ambito, type DimensionPatronGlobal, type PatronGlobal } from "../api/client";
import { colorPatron } from "../lib/colores";

interface Props {
  ambito: Ambito;
  /** p. ej. "todo el personal docente": contra quién se compara un patrón global */
  nombreAmbito: string;
  patron: PatronGlobal;
  /** con más de 6 patrones no hay color por patrón (ver MapaPerfil) */
  conColor: boolean;
  soloVigentes: boolean;
  microSel: number | null;
  onMicro: (m: number | null) => void;
  onPersona: (id: number) => void;
  onCerrar: () => void;
}

// Detalle de un patrón global (DEC-057) y de sus microarquetipos (DEC-058): en qué se distingue,
// quién lo representa y quiénes lo forman, con su similitud con la persona representativa.
export default function PanelPatronGlobal({ ambito, nombreAmbito, patron, conColor, soloVigentes, microSel, onMicro, onPersona, onCerrar }: Props) {
  const micros = patron.microarquetipos?.lista ?? [];
  const micro = microSel !== null ? micros[microSel] ?? null : null;
  const personas = useQuery({
    queryKey: ["personas-global", ambito, patron.id, micro?.id ?? null, soloVigentes],
    queryFn: () => getPersonasPatronGlobal(ambito, patron.id, micro?.id ?? null, soloVigentes),
  });
  const grupo = micro ?? patron;
  const nombreGrupo = micro ? micro.codigo : `Patrón global ${patron.id + 1}`;
  const referencia = micro ? `el Patrón global ${patron.id + 1}` : nombreAmbito;

  return (
    <section>
      <button onClick={onCerrar} className="text-xs text-espol-blue hover:underline px-5 pt-4 block text-left">
        ← Cerrar
      </button>
      <header className="px-5 pt-2 pb-3 border-b">
        <h3 className="text-lg font-semibold text-espol-navy flex items-center gap-2">
          {conColor && <span className="w-3 h-3 rounded-full" style={{ background: colorPatron(patron.id) }} />}
          Patrón global {patron.id + 1}
        </h3>
        <p className="text-sm text-slate-700 mt-1">{patron.etiqueta}</p>
        <p className="text-xs text-slate-500 mt-1">
          {soloVigentes ? `${patron.tamano_vigentes} personas vigentes` : `${patron.tamano} personas`} ·{" "}
          {Math.round(patron.proporcion * 100)} % {de(nombreAmbito)}
        </p>
      </header>

      {micros.length > 0 && (
        <div className="px-5 py-3 border-b">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Microarquetipos ({micros.length})</h4>
          <p className="text-[11px] text-slate-500 mb-2">
            Subgrupos descubiertos dentro de este patrón. Se describen frente al propio patrón global. Elige uno para verlo.
          </p>
          <ul className="space-y-1">
            {micros.map((m) => (
              <li key={m.id}>
                <button
                  onClick={() => onMicro(microSel === m.id ? null : m.id)}
                  aria-pressed={microSel === m.id}
                  className={`w-full text-left rounded-md px-2 py-1.5 border ${microSel === m.id ? "border-espol-blue bg-slate-50" : "border-transparent hover:bg-slate-50"}`}
                >
                  <span className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: colorPatron(m.id) }} />
                    <span className="text-sm font-medium text-slate-800 flex-1">{m.codigo}</span>
                    <span className="text-[11px] text-slate-500 tabular-nums">
                      {soloVigentes ? m.tamano_vigentes : m.tamano} personas
                    </span>
                  </span>
                  <span className="block text-[11px] text-slate-600 ml-[1.1rem]">{m.etiqueta}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="px-5 py-4 border-b">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">En qué se distingue {micro ? micro.codigo : "este patrón"}</h4>
        <p className="text-[11px] text-slate-500 mt-1 mb-2">
          Para cada dimensión: la <strong>barra y el número</strong> son la intensidad promedio de {nombreGrupo} (0 = sin evidencias
          registradas, 100 = el máximo del personal). La <strong>raya negra</strong> es el promedio {de(referencia)}, para comparar.
        </p>
        <ListaDimensiones dims={grupo.dimensiones} referencia={referencia} />
      </div>

      <div className="px-5 pt-4 pb-2">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          Personas de {nombreGrupo} {personas.data ? `(${personas.data.total})` : ""}
        </h4>
        {grupo.representante_id !== null ? (
          <p className="text-[11px] text-slate-500 mt-0.5">
            Persona más representativa:{" "}
            <button className="text-espol-blue hover:underline" onClick={() => onPersona(grupo.representante_id!)}>
              {grupo.representante_nombre}
            </button>
            . Cada persona muestra cuánto se parece a ella: 100 % es ella misma y 0 % la persona más distinta del grupo.
          </p>
        ) : (
          <p className="text-[11px] text-slate-500 mt-0.5">Este grupo no tiene personas vigentes que lo representen.</p>
        )}
      </div>
      <ul className="divide-y">
        {personas.data?.personas.map((x) => (
          <li key={x.persona_id}>
            <button onClick={() => onPersona(x.persona_id)} className="w-full text-left px-5 py-2 hover:bg-slate-50">
              <span className="flex items-baseline gap-2">
                <span className="text-sm text-slate-800 flex-1">{x.nombre}</span>
                {x.similitud !== null && (
                  <span className="text-xs tabular-nums text-slate-700" title="Similitud con la persona más representativa">
                    {x.es_rep ? "representante" : `${Math.round(x.similitud * 100)} %`}
                  </span>
                )}
              </span>
              <p className="text-[11px] text-slate-500 truncate">
                {x.cargo_actual ?? "Sin cargo actual"}
                {!x.vigente && " · no vigente"}
                {!micro && x.micro >= 0 && ` · ${micros[x.micro]?.codigo ?? ""}`}
                {x.entre_dos && " · entre dos grupos"}
              </p>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

function ListaDimensiones({ dims, referencia }: { dims: DimensionPatronGlobal[]; referencia: string }) {
  const orden = [...dims].sort((a, b) => b.intensidad_media - a.intensidad_media);
  return (
    <ul className="space-y-2">
      {orden.map((d) => {
        const pf = d.patron_frecuente;
        const destaca = pf && (pf.lift ?? 0) >= 1.5 && pf.proporcion >= 0.5;
        const dif = d.intensidad_media - d.intensidad_media_referencia;
        return (
          <li key={d.dimension} title={`${d.nombre}: ${d.intensidad_media} (promedio ${de(referencia)}: ${d.intensidad_media_referencia})`}>
            <div className="grid grid-cols-[8rem_1fr_4.5rem] gap-2 items-center">
              <span className="text-xs text-slate-700 truncate">{d.nombre}</span>
              <span className="relative h-2.5 bg-slate-100 rounded-sm">
                <span className="absolute inset-y-0 left-0 bg-espol-blue rounded-r-[3px]" style={{ width: `${d.intensidad_media}%` }} />
                <span className="absolute -inset-y-0.5 w-0.5 bg-slate-800" style={{ left: `${d.intensidad_media_referencia}%` }} />
              </span>
              <span className="text-xs tabular-nums text-right text-slate-800">
                {Math.round(d.intensidad_media)}
                {Math.abs(dif) >= 1 && (
                  <span className="text-[10px] text-slate-500"> ({dif > 0 ? "+" : "−"}{Math.round(Math.abs(dif))})</span>
                )}
              </span>
            </div>
            {destaca && (
              <p className="text-[11px] text-slate-500 ml-[8.5rem]">
                El {Math.round(pf!.proporcion * 100)} % de quienes tienen evidencias aquí sigue el Patrón {pf!.patron + 1} de esta
                dimensión (en {referencia}: {Math.round(pf!.proporcion_referencia * 100)} %).
              </p>
            )}
          </li>
        );
      })}
    </ul>
  );
}
