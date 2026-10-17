import { useRef } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { de } from "../lib/texto";
import { getPersonasPatronGlobal, type Ambito, type DimensionPatronGlobal, type PatronDistintivo, type PatronGlobal } from "../api/client";
import { colorPatron } from "../lib/colores";
import { usePatronesDimension, type GrupoGlobal } from "../lib/navegacion";
import { ChipPatronDimension } from "./PatronesDimension";
import { BuscadorEnGrupo, FiltroAplicado, Paginacion, Resaltado, ResumenPagina } from "./ListaPaginada";
import type { ListaPersonas } from "../lib/listaPersonas";

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
  /** página y búsqueda de la lista de personas (viven en la página para no perderse al abrir una ficha) */
  lista: ListaPersonas;
}

// Detalle de un patrón global (DEC-057) y de sus microarquetipos (DEC-058): en qué se distingue,
// quién lo representa y quiénes lo forman, con su similitud con la persona representativa.
export default function PanelPatronGlobal({
  ambito, nombreAmbito, patron, conColor, soloVigentes, microSel, onMicro, onPersona, onCerrar, lista,
}: Props) {
  const micros = patron.microarquetipos?.lista ?? [];
  const micro = microSel !== null ? micros[microSel] ?? null : null;
  const clave = ["personas-global", ambito, patron.id, micro?.id ?? null, soloVigentes];
  const personas = useQuery({
    queryKey: [...clave, lista.pagina, lista.porPagina, lista.q],
    queryFn: () =>
      getPersonasPatronGlobal(ambito, patron.id, micro?.id ?? null, soloVigentes, {
        pagina: lista.pagina, porPagina: lista.porPagina, q: lista.q,
      }),
    placeholderData: keepPreviousData,
  });
  const inicioLista = useRef<HTMLDivElement>(null);
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
        <Distintivos
          ambito={ambito}
          lista={patron.patrones_distintivos ?? []}
          grupo={{ patron: patron.id, micro: null, nombre: `Patrón global ${patron.id + 1}` }}
          referencia={nombreAmbito}
        />
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
        {micro && (
          <Distintivos
            ambito={ambito}
            lista={micro.patrones_distintivos ?? []}
            grupo={{ patron: patron.id, micro: micro.id, nombre: micro.codigo }}
            referencia={referencia}
          />
        )}
        <ListaDimensiones
          dims={grupo.dimensiones}
          referencia={referencia}
          ambito={ambito}
          grupo={{ patron: patron.id, micro: micro?.id ?? null, nombre: nombreGrupo }}
        />
      </div>

      <div ref={inicioLista} className="px-5 pt-4 pb-2 scroll-mt-2">
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
        <div className="mt-3 space-y-2">
          <BuscadorEnGrupo
            key={lista.contexto}
            claveGrupo={clave}
            nombreGrupo={nombreGrupo}
            totalGrupo={personas.data?.total ?? null}
            sugerir={(q) => getPersonasPatronGlobal(ambito, patron.id, micro?.id ?? null, soloVigentes, { q, pagina: 1, porPagina: 8 })}
            aplicado={lista.q}
            onAplicar={lista.setQ}
            onPersona={onPersona}
          />
          <FiltroAplicado lista={lista} />
          <ResumenPagina datos={personas.data} lista={lista} />
        </div>
      </div>
      <ul className={`divide-y border-t transition-opacity ${personas.isPlaceholderData ? "opacity-60" : ""}`}>
        {personas.data?.personas.map((x) => (
          <li key={x.persona_id}>
            <button onClick={() => onPersona(x.persona_id)} className="w-full text-left px-5 py-2 hover:bg-slate-50">
              <span className="flex items-baseline gap-2">
                <span className="text-sm text-slate-800 flex-1">
                  <Resaltado texto={x.nombre} q={lista.q} />
                </span>
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
                {lista.q && ` · n.º ${x.posicion} de ${personas.data?.total ?? ""}`}
              </p>
            </button>
          </li>
        ))}
      </ul>
      {personas.data?.total_filtrado === 0 && lista.q && (
        <p className="text-xs text-slate-500 px-5 py-4">Nadie en {nombreGrupo} coincide con «{lista.q}».</p>
      )}
      <Paginacion datos={personas.data} lista={lista} onCambio={() => inicioLista.current?.scrollIntoView({ block: "start", behavior: "smooth" })} />
    </section>
  );
}

/** Intensidad promedio del grupo en cada dimensión frente a su referencia (todo el ámbito o el patrón global). */
export function ListaDimensiones({ dims, referencia, ambito, grupo }: {
  dims: DimensionPatronGlobal[]; referencia: string; ambito: Ambito; grupo: GrupoGlobal;
}) {
  const nav = usePatronesDimension();
  const orden = [...dims].sort((a, b) => b.intensidad_media - a.intensidad_media);
  return (
    <ul className="space-y-2">
      {orden.map((d) => {
        const pf = d.patron_frecuente;
        const destaca = pf && (pf.lift ?? 0) >= 1.5 && pf.proporcion >= 0.5;
        const dif = d.intensidad_media - d.intensidad_media_referencia;
        return (
          <li key={d.dimension} title={`${d.nombre}: ${d.intensidad_media} (promedio ${de(referencia)}: ${d.intensidad_media_referencia})`}>
            <div className="grid grid-cols-[8rem_1fr_4.5rem_3.25rem] gap-2 items-center">
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
              {pf && nav ? (
                <button
                  onClick={() => nav.verPatrones(d.dimension, { patron: pf.patron, grupo })}
                  className="text-[10px] text-espol-blue hover:underline text-right whitespace-nowrap"
                  title={`Ver los patrones de ${d.nombre} y cómo se reparten las personas de ${grupo.nombre} entre ellos`}
                >
                  patrones ›
                </button>
              ) : (
                <span />
              )}
            </div>
            {destaca && (
              <p className="text-[11px] text-slate-500 ml-[8.5rem]">
                El {Math.round(pf!.proporcion * 100)} % de quienes tienen evidencias aquí sigue el{" "}
                <ChipPatronDimension ambito={ambito} dimension={d.dimension} patron={pf!.patron} grupo={grupo} /> (en {referencia}:{" "}
                {Math.round(pf!.proporcion_referencia * 100)} %).
              </p>
            )}
          </li>
        );
      })}
    </ul>
  );
}

/** Patrones de dimensión mucho más frecuentes en el grupo que en su referencia, como chips. */
function Distintivos({ ambito, lista, grupo, referencia }: {
  ambito: Ambito; lista: PatronDistintivo[]; grupo: GrupoGlobal; referencia: string;
}) {
  if (!lista.length) return null;
  return (
    <div className="mt-2">
      <p className="text-[11px] text-slate-500 mb-1">Patrones de dimensión típicos de {grupo.nombre}:</p>
      <ul className="flex flex-wrap gap-x-3 gap-y-1">
        {lista.map((x) => (
          <li key={x.dimension} className="text-[11px] text-slate-600 flex items-center gap-1">
            <ChipPatronDimension ambito={ambito} dimension={x.dimension} patron={x.patron} grupo={grupo} />
            <span title={`El ${Math.round(x.proporcion * 100)} % de quienes tienen evidencias en ${x.nombre} lo sigue; en ${referencia}, el ${Math.round(x.proporcion_referencia * 100)} %`}>
              {Math.round(x.proporcion * 100)} % <span className="text-slate-400">(vs {Math.round(x.proporcion_referencia * 100)} %)</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
