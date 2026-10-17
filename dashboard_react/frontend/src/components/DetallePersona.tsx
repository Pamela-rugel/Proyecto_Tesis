import { useCallback, useState, type ReactNode } from "react";
import type { ComponentePatron, DatoPersona, DimensionPatronGlobal, Evidencias, PersonaComparada, PersonaEnDimension } from "../api/client";
import { NOMBRE_TIPO, colorPatron } from "../lib/colores";
import { formatoValor, nivelFormacion, textoSimilitud } from "../lib/texto";
import Modal from "./Modal";

// Piezas para ver a una persona desde un contexto (una dimensión, su patrón global o su
// microarquetipo). Las usan la ficha, Comparar y Validación.

export function ListaEvidencias({ evidencias, abiertas = false, vacio = "Sin evidencias registradas." }: {
  evidencias: Evidencias; abiertas?: boolean; vacio?: string;
}) {
  if (!evidencias.length) return <p className="text-xs text-slate-500">{vacio}</p>;
  return (
    <div className="space-y-1.5">
      {evidencias.map((g) => (
        <details key={g.tipo_id} className="text-xs" open={abiertas}>
          <summary className="cursor-pointer text-slate-700">
            {NOMBRE_TIPO[g.tipo_id] ?? g.tipo_id} <span className="text-slate-500">({g.n})</span>
          </summary>
          <ul className="mt-1 ml-3 list-disc space-y-0.5 text-slate-600">
            {g.textos.map((t, i) => (
              <li key={i}>{t}</li>
            ))}
            {g.n > g.textos.length && <li className="list-none text-slate-400">… y {g.n - g.textos.length} más</li>}
          </ul>
        </details>
      ))}
    </div>
  );
}

/** Barra 0–100 con marcas de referencia (rayas verticales). */
export function BarraConReferencias({ valor, marcas }: {
  valor: number; marcas: { valor: number | null; clase: string; titulo: string }[];
}) {
  return (
    <span className="relative block h-2.5 bg-slate-100 rounded-sm">
      <span className="absolute inset-y-0 left-0 bg-espol-blue rounded-r-[3px]" style={{ width: `${Math.min(100, Math.max(0, valor))}%` }} />
      {marcas.map(
        (m) =>
          m.valor !== null && (
            <span
              key={m.titulo}
              title={m.titulo}
              className={`absolute -inset-y-0.5 w-0.5 ${m.clase}`}
              style={{ left: `calc(${Math.min(100, Math.max(0, m.valor))}% - 1px)` }}
            />
          ),
      )}
    </span>
  );
}

export function LeyendaReferencias({ items }: { items: { clase: string; texto: string }[] }) {
  return (
    <p className="flex flex-wrap gap-x-3 gap-y-0.5 text-[11px] text-slate-500">
      <span className="flex items-center gap-1">
        <span className="w-3 h-2 bg-espol-blue rounded-sm" /> la persona
      </span>
      {items.map((i) => (
        <span key={i.texto} className="flex items-center gap-1">
          <span className={`w-0.5 h-3 ${i.clase}`} /> {i.texto}
        </span>
      ))}
    </p>
  );
}

/** Componentes de la dimensión: nota de la persona (0–100; 100 = quien más tiene en el ámbito)
 *  frente al promedio de su patrón y al de la dimensión. Con `conAporte`, además cuánto aporta
 *  cada uno al puntaje (nota × peso ÷ suma de pesos), con el total. */
export function ComponentesFrentePatron({ componentes, nombrePatron, leyenda = true, conAporte = false, puntaje, sumaPesos, ambito }: {
  componentes: PersonaEnDimension["componentes"]; nombrePatron: string | null; leyenda?: boolean;
  conAporte?: boolean; puntaje?: number; sumaPesos?: number; ambito?: string;
}) {
  const columnas = conAporte ? "grid-cols-[minmax(0,1fr)_4.5rem_1.75rem_2rem_2.5rem]" : "grid-cols-[minmax(0,1fr)_7rem_2.5rem]";
  const num = (v: number, dec = 1) => v.toLocaleString("es", { maximumFractionDigits: dec });
  return (
    <div className="space-y-1.5">
      {leyenda && (
        <LeyendaReferencias
          items={[
            ...(nombrePatron ? [{ clase: "bg-slate-900", texto: `promedio de ${nombrePatron}` }] : []),
            { clase: "bg-amber-500", texto: "promedio de la dimensión" },
          ]}
        />
      )}
      {conAporte && (
        <div className={`grid ${columnas} gap-2 text-[10px] text-slate-400 uppercase tracking-wide`}>
          <span>Componente</span>
          <span />
          <span className="text-right" title="De 0 a 100: 100 = quien más tiene en el ámbito">Nota</span>
          <span className="text-right" title="Cuánto cuenta este componente en el puntaje">Peso</span>
          <span className="text-right" title="Puntos que aporta al puntaje: nota × peso ÷ suma de pesos">Aporte</span>
        </div>
      )}
      <ul className="space-y-1">
        {componentes.map((c) => (
          <li
            key={c.componente}
            className={`grid ${columnas} gap-2 items-center`}
            title={`${c.descripcion}: nota ${Math.round(c.valor * 100)} de 100${c.media_patron !== null ? ` · promedio de su patrón: ${Math.round(c.media_patron * 100)}` : ""} · promedio de la dimensión: ${Math.round(c.media_dimension * 100)}`}
          >
            <span className="text-[11px] text-slate-600 truncate">{c.descripcion.replace(" (log)", "")}</span>
            <BarraConReferencias
              valor={c.valor * 100}
              marcas={[
                { valor: c.media_dimension * 100, clase: "bg-amber-500", titulo: "promedio de la dimensión" },
                { valor: c.media_patron !== null ? c.media_patron * 100 : null, clase: "bg-slate-900", titulo: "promedio del patrón" },
              ]}
            />
            <span className="text-[11px] tabular-nums text-right text-slate-700">{Math.round(c.valor * 100)}</span>
            {conAporte && (
              <>
                <span className="text-[11px] tabular-nums text-right text-slate-500">×{num(c.peso)}</span>
                <span className="text-[11px] tabular-nums text-right text-slate-800 font-medium">{num(c.aporte)}</span>
              </>
            )}
          </li>
        ))}
      </ul>
      {conAporte && puntaje !== undefined && (
        <div className={`grid ${columnas} gap-2 items-center border-t pt-1`}>
          <span className="text-[11px] text-slate-800 font-semibold col-span-4">Puntaje (suma de aportes)</span>
          <span className="text-[11px] tabular-nums text-right text-slate-900 font-semibold">{num(puntaje)}</span>
        </div>
      )}
      <p className="text-[10px] text-slate-400">
        Nota de 0 a 100: 100 = quien más tiene en {ambito ?? "el ámbito"}.
        {conAporte && sumaPesos !== undefined &&
          ` Aporte = nota × peso ÷ ${num(sumaPesos)} (la suma de los pesos). Los pesos son un criterio definido en el proyecto, no salen de los datos.`}
      </p>
    </div>
  );
}

/** Puntaje de la persona en la dimensión y su lugar frente al personal del ámbito (cuántas personas
 *  tienen un puntaje menor, igual o mayor: los empates son frecuentes). El detalle del cálculo se
 *  abre en una ventana aparte. */
export function PuntajeYPosicion({ datos }: { datos: PersonaEnDimension }) {
  const [abierto, setAbierto] = useState(false);
  const cerrar = useCallback(() => setAbierto(false), []);
  const p = datos.posicion;
  const pct = (v: number) => `${v.toLocaleString("es", { maximumFractionDigits: 1 })} %`;
  if (datos.n_evidencias === 0) {
    return <p className="text-xs text-slate-600">Sin evidencias en {datos.nombre}: puntaje 0.</p>;
  }
  return (
    <div className="space-y-1.5">
      <p className="text-sm text-slate-800">
        Puntaje en {datos.nombre}: <strong className="tabular-nums">{Math.round(datos.puntaje)}</strong>
        <span className="text-slate-500"> de 100</span>
        <span className="text-[11px] text-slate-500">
          {" "}
          · {datos.n_evidencias} evidencia{datos.n_evidencias === 1 ? "" : "s"}
        </span>
      </p>
      <BarraPosicion p={p} />
      <p className="text-xs text-slate-600">
        Más alto que el <strong className="tabular-nums">{pct(p.menor)}</strong> de {p.ambito}, igual al{" "}
        <strong className="tabular-nums">{pct(p.igual)}</strong> y más bajo que el <strong className="tabular-nums">{pct(p.mayor)}</strong>.
      </p>
      <button onClick={() => setAbierto(true)} className="text-[11px] text-espol-blue hover:underline">
        ¿Cómo se calcula este puntaje?
      </button>
      {abierto && (
        <Modal titulo={`Cómo se calcula el puntaje en ${datos.nombre}`} onCerrar={cerrar}>
          <div className="space-y-4 text-xs text-slate-700">
            <section>
              <h3 className="font-semibold text-slate-800 mb-1">1. Una nota por componente</h3>
              <p className="mb-2">
                Cada componente se convierte en una nota de 0 a 100, donde 100 es lo que tiene quien más tiene en {p.ambito}.
                Luego cada nota se multiplica por su peso y se divide por la suma de los pesos (
                {datos.suma_pesos.toLocaleString("es")}): eso es lo que aporta al puntaje.
              </p>
              <ComponentesFrentePatron
                componentes={datos.componentes}
                nombrePatron={datos.patron ? `su Patrón ${datos.patron.patron + 1}` : null}
                conAporte
                puntaje={datos.puntaje}
                sumaPesos={datos.suma_pesos}
                ambito={p.ambito}
              />
            </section>
            <section>
              <h3 className="font-semibold text-slate-800 mb-1">2. Su lugar frente a {p.ambito}</h3>
              <p className="mb-2">
                Se calcula el mismo puntaje para las {p.n.toLocaleString("es")} personas de {p.ambito} y se compara con el suyo.
                Quien no tiene evidencias en {datos.nombre} tiene 0.
              </p>
              <BarraPosicion p={p} />
              <ul className="mt-2 space-y-0.5">
                <li>
                  <span className="inline-block w-2.5 h-2.5 rounded-sm bg-espol-blue/40 mr-1.5 align-middle" />
                  {pct(p.menor)} tiene un puntaje <strong>más bajo</strong> que el suyo
                </li>
                <li>
                  <span className="inline-block w-2.5 h-2.5 rounded-sm bg-espol-blue mr-1.5 align-middle" />
                  {pct(p.igual)} tiene <strong>el mismo</strong> puntaje (incluida ella): suele pasar cuando tienen la misma
                  combinación, p. ej. el mismo título
                </li>
                <li>
                  <span className="inline-block w-2.5 h-2.5 rounded-sm bg-slate-200 mr-1.5 align-middle" />
                  {pct(p.mayor)} tiene un puntaje <strong>más alto</strong>
                </li>
              </ul>
            </section>
            <p className="text-[11px] text-slate-500 border-t pt-3">
              Los componentes y sus pesos son un criterio definido en el proyecto; no salen de los datos. El puntaje mide
              cuánta evidencia hay registrada en los sistemas de ESPOL, no la capacidad de la persona.
            </p>
          </div>
        </Modal>
      )}
    </div>
  );
}

function BarraPosicion({ p }: { p: PersonaEnDimension["posicion"] }) {
  const pct = (v: number) => `${v.toLocaleString("es", { maximumFractionDigits: 1 })} %`;
  return (
    <div
      className="flex h-2.5 rounded-sm overflow-hidden"
      role="img"
      aria-label={`Puntaje más bajo que el suyo: ${pct(p.menor)}; igual: ${pct(p.igual)}; más alto: ${pct(p.mayor)}`}
    >
      <span className="bg-espol-blue/40" style={{ width: `${p.menor}%` }} title={`${pct(p.menor)} tiene un puntaje más bajo`} />
      <span className="bg-espol-blue" style={{ width: `${p.igual}%` }} title={`${pct(p.igual)} tiene el mismo puntaje`} />
      <span className="bg-slate-200" style={{ width: `${p.mayor}%` }} title={`${pct(p.mayor)} tiene un puntaje más alto`} />
    </div>
  );
}

/** Patrón de la persona en la dimensión, con afinidad y similitud con la representante. */
export function PatronEnDimension({ patron, onPersona }: {
  patron: NonNullable<PersonaEnDimension["patron"]>; onPersona?: (id: number) => void;
}) {
  return (
    <div>
      <p className="text-sm text-slate-800 flex items-center gap-2">
        <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: colorPatron(patron.patron) }} />
        Patrón {patron.patron + 1}
        <span className="text-[11px] text-slate-500">· {patron.tamano} personas · afinidad {Math.round(patron.afinidad * 100)} %</span>
      </p>
      <p className="text-xs text-slate-600">{patron.etiqueta}</p>
      <p className="text-[11px] text-slate-500 mt-0.5">
        {textoSimilitud(patron.similitud_representante, patron.es_representante)}
        {!patron.es_representante && patron.representante_id !== null && (
          <>
            {" ("}
            <button
              className="text-espol-blue hover:underline disabled:no-underline disabled:text-slate-600"
              disabled={!onPersona}
              onClick={() => onPersona?.(patron.representante_id!)}
            >
              {patron.representante_nombre}
            </button>
            )
          </>
        )}
        .
      </p>
      {patron.mixto && (
        <p className="text-[11px] text-amber-700 mt-0.5">
          Está entre dos patrones: también se parece mucho al Patrón {patron.segundo + 1} ({patron.segundo_etiqueta}).
        </p>
      )}
    </div>
  );
}

export function TemasPersona({ temas }: { temas: PersonaEnDimension["temas"] }) {
  if (!temas.length) return null;
  return (
    <ul className="space-y-0.5">
      {temas.map((t) => (
        <li key={t.tema} className="grid grid-cols-[minmax(0,1fr)_5rem] gap-2 items-center text-[11px]">
          <span className="text-slate-700 truncate" title={t.etiqueta}>
            Tema {t.tema + 1} · {t.etiqueta}
          </span>
          <span className="flex items-center gap-1">
            <span className="flex-1 h-1.5 bg-slate-100 rounded-sm">
              <span className="block h-1.5 bg-espol-blue/70 rounded-sm" style={{ width: `${t.proporcion * 100}%` }} />
            </span>
            <span className="tabular-nums text-slate-500 w-7 text-right">{Math.round(t.proporcion * 100)}%</span>
          </span>
        </li>
      ))}
    </ul>
  );
}

const Sub = ({ titulo, children }: { titulo: string; children: ReactNode }) => (
  <div>
    <p className="text-[11px] uppercase tracking-wide text-slate-500 mb-1">{titulo}</p>
    {children}
  </div>
);

/** Todo lo de la persona en una dimensión: patrón, componentes frente al patrón, temas y evidencias. */
export function BloqueDimension({ datos, onPersona, evidenciasAbiertas = false }: {
  datos: PersonaEnDimension; onPersona?: (id: number) => void; evidenciasAbiertas?: boolean;
}) {
  return (
    <div className="space-y-3">
      <PuntajeYPosicion datos={datos} />
      {datos.patron ? (
        <PatronEnDimension patron={datos.patron} onPersona={onPersona} />
      ) : (
        <p className="text-xs text-slate-500">
          {datos.n_evidencias === 0 ? "Sin evidencias en esta dimensión." : "Esta dimensión no se divide en patrones."}
        </p>
      )}
      {datos.n_evidencias > 0 && datos.datos.length > 0 && (
        <Sub titulo={datos.patron ? `Sus datos frente a su Patrón ${datos.patron.patron + 1}` : "Sus datos"}>
          <DatosFrentePatron datos={datos.datos} patron={datos.patron?.patron ?? null} nombreDimension={datos.nombre} />
        </Sub>
      )}
      {datos.temas.length > 0 && (
        <Sub titulo="Temas de su evidencia">
          <TemasPersona temas={datos.temas} />
        </Sub>
      )}
      <Sub titulo={`Evidencias de ${datos.nombre}`}>
        <ListaEvidencias evidencias={datos.evidencias} abiertas={evidenciasAbiertas} vacio="Sin evidencias en esta dimensión." />
      </Sub>
    </div>
  );
}

/** Intensidad de la persona en cada dimensión frente al promedio de un grupo (su patrón global o
 *  su microarquetipo), con su patrón en cada dimensión. */
export function IntensidadesFrenteGrupo({ intensidades, referencia, nombreReferencia, leyenda = true }: {
  intensidades: PersonaComparada["intensidades"];
  referencia: DimensionPatronGlobal[] | null;
  nombreReferencia: string | null;
  leyenda?: boolean;
}) {
  const ref = new Map((referencia ?? []).map((d) => [d.dimension, d.intensidad_media]));
  const orden = [...intensidades].sort((a, b) => b.intensidad - a.intensidad);
  return (
    <div className="space-y-1.5">
      {leyenda && nombreReferencia && <LeyendaReferencias items={[{ clase: "bg-slate-900", texto: `promedio de ${nombreReferencia}` }]} />}
      <ul className="space-y-1">
        {orden.map((d) => (
          <li key={d.dimension} className="grid grid-cols-[7rem_minmax(0,1fr)_2rem_1.75rem] gap-2 items-center">
            <span className="text-[11px] text-slate-700 truncate">{d.nombre}</span>
            <BarraConReferencias
              valor={d.intensidad}
              marcas={[{ valor: ref.get(d.dimension) ?? null, clase: "bg-slate-900", titulo: `promedio de ${nombreReferencia ?? "su grupo"}` }]}
            />
            <span className={`text-[11px] tabular-nums text-right ${d.n_evidencias ? "text-slate-800" : "text-slate-400"}`}>
              {Math.floor(d.intensidad)}
            </span>
            <span className="text-[10px] text-slate-500" title={d.patron !== null ? `Patrón ${d.patron + 1} en ${d.nombre}` : ""}>
              {d.patron !== null ? `P${d.patron + 1}` : ""}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

const PALABRA: Record<ComponentePatron["comparacion"], { flecha: string; texto: string; clase: string }> = {
  mucho_mas: { flecha: "▲▲", texto: "Mucho más", clase: "text-espol-blue bg-blue-50 border-blue-200" },
  mas: { flecha: "▲", texto: "Más", clase: "text-espol-blue bg-blue-50 border-blue-200" },
  similar: { flecha: "≈", texto: "Parecido", clase: "text-slate-500 bg-slate-50 border-slate-200" },
  menos: { flecha: "▼", texto: "Menos", clase: "text-slate-700 bg-slate-100 border-slate-300" },
  mucho_menos: { flecha: "▼▼", texto: "Mucho menos", clase: "text-slate-700 bg-slate-100 border-slate-300" },
};

/** Cómo es un patrón frente al promedio de su dimensión: arriba, lo que lo distingue (más o menos
 *  que el promedio, con el valor del grupo y el de la dimensión); abajo, las barras de todos los
 *  componentes (hacia la derecha, más que el promedio; hacia la izquierda, menos). */
export function ComponentesPatron({ componentes, nombreDimension }: { componentes: ComponentePatron[]; nombreDimension: string }) {
  const extremo = Math.max(1.5, ...componentes.map((c) => Math.abs(c.z)));
  const distintivos = [...componentes].filter((c) => c.comparacion !== "similar").sort((a, b) => Math.abs(b.z) - Math.abs(a.z));
  const valores = (c: ComponentePatron) =>
    `${formatoValor(c.media_grupo, c.formato, c.descripcion)} en el patrón · ${formatoValor(c.media_dimension, c.formato, c.descripcion)} en ${nombreDimension}`;
  return (
    <div className="space-y-2.5">
      <div>
        <p className="text-[11px] text-slate-500 mb-1">Frente al promedio de {nombreDimension}:</p>
        {distintivos.length === 0 ? (
          <p className="text-xs text-slate-600">≈ Cerca del promedio en todo.</p>
        ) : (
          <ul className="space-y-1">
            {distintivos.map((c) => {
              const w = PALABRA[c.comparacion];
              return (
                <li key={c.componente} className="flex items-start gap-2" title={valores(c)}>
                  <span className={`shrink-0 text-[10px] font-medium border rounded px-1 py-px whitespace-nowrap ${w.clase}`}>
                    {w.flecha} {w.texto}
                  </span>
                  <span className="text-[11px] text-slate-700 leading-snug">
                    {c.descripcion.replace(" (log)", "").split(" (")[0]}
                    <span className="block text-[10px] text-slate-400 tabular-nums">{valores(c)}</span>
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </div>
      <ul className="space-y-1">
        {componentes.map((c) => {
          const ancho = (Math.min(Math.abs(c.z), extremo) / extremo) * 50;
          return (
            <li key={c.componente} className="grid grid-cols-[minmax(0,1fr)_7rem] gap-2 items-center" title={`${c.descripcion}: ${valores(c)}`}>
              <span className="text-[11px] text-slate-600 truncate">{c.descripcion.replace(" (log)", "")}</span>
              <span className="relative h-2 bg-slate-100 rounded-sm">
                <span className="absolute top-0 bottom-0 left-1/2 w-px bg-slate-400" />
                <span
                  className={`absolute top-0 bottom-0 ${c.z >= 0 ? "bg-espol-blue rounded-r-sm" : "bg-slate-400 rounded-l-sm"}`}
                  style={c.z >= 0 ? { left: "50%", width: `${ancho}%` } : { right: "50%", width: `${ancho}%` }}
                />
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

const esNivelFormacion = (d: DatoPersona) => d.formato === "nivel" && d.descripcion.includes("bachiller");
const numeroCorto = (v: number) => v.toLocaleString("es", { maximumFractionDigits: 1 });
/** Dato de la persona en sus unidades: "Sí"/"No", "12", "50 %", "3 (maestría)". */
const datoPersona = (d: DatoPersona) =>
  d.marca ? (d.valor >= 0.5 ? "Sí" : "No") : esNivelFormacion(d) ? `${numeroCorto(d.valor)} (${nivelFormacion(d.valor)})` : formatoValor(d.valor, d.formato, d.descripcion);
/** Valor típico, corto para la tabla (el nivel en palabras va en el título de la fila). */
const valorTipico = (v: number | null, d: DatoPersona) =>
  v === null ? "—" : esNivelFormacion(d) ? numeroCorto(v) : formatoValor(v, d.formato, d.descripcion);

/** Sus datos reales en las variables con que se forman los patrones, junto al valor típico de su
 *  patrón y de la dimensión. Primero lo que distingue a su patrón (▲ más / ▼ menos que el
 *  promedio), indicando si su dato va en esa dirección: así se ve qué la hizo terminar ahí. */
export function DatosFrentePatron({ datos, patron, nombreDimension }: {
  datos: DatoPersona[]; patron: number | null; nombreDimension: string;
}) {
  const orden = [...datos].sort((a, b) => {
    const da = a.comparacion && a.comparacion !== "similar" ? 1 : 0;
    const db = b.comparacion && b.comparacion !== "similar" ? 1 : 0;
    return db - da || Math.abs(b.z ?? 0) - Math.abs(a.z ?? 0);
  });
  const nombrePatron = patron !== null ? `Patrón ${patron + 1}` : null;
  return (
    <div className="space-y-1.5">
      <div className="grid grid-cols-[minmax(0,1fr)_4.75rem_4.25rem_4.25rem] gap-2 text-[10px] uppercase tracking-wide text-slate-400">
        <span />
        <span className="text-right text-slate-600">Su dato</span>
        <span className="text-right">{nombrePatron ?? ""}</span>
        <span className="text-right truncate" title={nombreDimension}>
          {nombreDimension}
        </span>
      </div>
      <ul className="space-y-1">
        {orden.map((d) => {
          const distingue = d.comparacion !== null && d.comparacion !== "similar";
          const w = d.comparacion ? PALABRA[d.comparacion] : null;
          // ¿su dato va hacia donde se distingue su patrón (por encima o por debajo del promedio)?
          const sentido = d.media_patron !== null && d.media_dimension !== null ? Math.sign(d.media_patron - d.media_dimension) : 0;
          const coincide = d.media_dimension !== null && Math.sign(d.valor - d.media_dimension) === sentido;
          return (
            <li
              key={d.componente}
              className="grid grid-cols-[minmax(0,1fr)_4.75rem_4.25rem_4.25rem] gap-2 items-baseline"
              title={`${d.descripcion}. Su dato: ${datoPersona(d)}.${nombrePatron ? ` Típico de su ${nombrePatron}: ${valorTipico(d.media_patron, d)}.` : ""} Típico de ${nombreDimension}: ${valorTipico(d.media_dimension, d)}.${d.descripcion.includes("(log") ? " Típico = media en escala logarítmica, para que pocos casos extremos no la inflen." : ""}`}
            >
              <span className="text-[11px] text-slate-700 leading-snug">
                {distingue && w && (
                  <span className={`inline-block text-[9px] font-medium border rounded px-0.5 mr-1 align-[1px] ${w.clase}`}>{w.flecha}</span>
                )}
                {d.descripcion.replace(" (log)", "")}
                {distingue && !coincide && <span className="block text-[10px] text-amber-700">su dato no sigue a su patrón aquí</span>}
              </span>
              <span className={`text-[11px] tabular-nums text-right ${distingue ? "font-semibold text-slate-900" : "text-slate-800"}`}>
                {datoPersona(d)}
              </span>
              <span className="text-[11px] tabular-nums text-right text-slate-500">{valorTipico(d.media_patron, d)}</span>
              <span className="text-[11px] tabular-nums text-right text-slate-400">{valorTipico(d.media_dimension, d)}</span>
            </li>
          );
        })}
      </ul>
      {nombrePatron && (
        <p className="text-[10px] text-slate-400">
          ▲ / ▼: en qué su {nombrePatron} tiene más o menos que el promedio de {nombreDimension}; es lo que lo distingue. Las
          columnas de la derecha son valores típicos del patrón y de la dimensión.
        </p>
      )}
    </div>
  );
}
