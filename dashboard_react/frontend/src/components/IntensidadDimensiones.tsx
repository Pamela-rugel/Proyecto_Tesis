import { useEffect, useRef, useState } from "react";
import { de, NOMBRE_AMBITO } from "../lib/texto";
import type { Ambito, DimensionPersona, EstadoRegistros, NavegacionFicha } from "../api/client";
import Enlace from "./Enlace";
import { Chip } from "./Bloques";
import { colorPatron } from "../lib/colores";

interface Props {
  ambito: Ambito;
  dimensiones: DimensionPersona[];
  /** dimensión desplegada al abrir (la de la vista desde la que se abrió la ficha) */
  dimensionInicial?: string;
  /** enlaces a la vista por dimensión, sus patrones y temas, y a otras personas */
  nav: NavegacionFicha;
  /** ir a la pestaña Evidencias con la dimensión abierta */
  onVerEvidencias: (dimension: string) => void;
}

// Texto de cada estado sin valor medible. "Sin registros" no es "actividad baja": las fuentes no
// traen evidencias de la persona en esa dimensión (puede faltar la información).
const TEXTO_ESTADO: Record<EstadoRegistros, string> = {
  con_registros: "",
  sin_registros: "Sin registros en las fuentes",
  solo_espanol: "Registró solo español",
  sin_validos: "Registró idiomas sin datos válidos",
  sin_informacion: "Sin información de idiomas",
};
const DETALLE_ESTADO: Record<EstadoRegistros, string> = {
  con_registros: "",
  sin_registros: "No hay evidencias en las fuentes; puede faltar información.",
  solo_espanol: "Solo declaró español; no tiene idiomas extranjeros registrados.",
  sin_validos: "Registró idiomas sin nivel válido; no cuentan como evidencia.",
  sin_informacion: "No aparece en el registro de idiomas: falta información.",
};

// Pestaña "Dimensiones" (DEC-060, opción C): estado de registros y NIVEL (percentil solo entre
// quienes tienen registros en la dimensión) en las 12 dimensiones; al desplegar una, la intensidad
// frente a todo el grupo (DEC-053), su patrón de actividad, sus temas (DEC-055) y de dónde sale el
// número.
export default function IntensidadDimensiones({ ambito, dimensiones, dimensionInicial, nav, onVerEvidencias }: Props) {
  // acordeón: el detalle (corto, en mini pestañas) se abre debajo de su fila, una dimensión a la vez.
  // Mientras está abierta, su fila pasa al primer lugar (con un resaltado breve) para que su detalle
  // quede a la vista; al cerrarla vuelve a su lugar.
  const [abierta, setAbierta] = useState<string | null>(dimensionInicial ?? null);
  const [destello, setDestello] = useState<string | null>(dimensionInicial ?? null);
  const lista = useRef<HTMLUListElement | null>(null);
  const elegir = (dim: string | null) => {
    setAbierta(dim);
    if (dim) {
      setDestello(dim);
      requestAnimationFrame(() => lista.current?.scrollIntoView({ block: "start", behavior: "smooth" }));
    }
  };
  useEffect(() => {
    if (dimensionInicial) lista.current?.scrollIntoView({ block: "start" });
  }, [dimensionInicial]);
  useEffect(() => {
    if (!destello) return;
    const t = setTimeout(() => setDestello(null), 1600);
    return () => clearTimeout(t);
  }, [destello]);
  if (!dimensiones.length) return <p className="text-xs text-slate-500">Esta versión de resultados no tiene dimensiones.</p>;
  const grupo = NOMBRE_AMBITO[ambito];
  const elegida = abierta ? dimensiones.find((d) => d.dimension === abierta) : undefined;
  const resto = elegida ? dimensiones.filter((d) => d !== elegida) : dimensiones;

  const fila = (d: DimensionPersona) => {
    const desplegada = abierta === d.dimension;
    const con = d.estado === "con_registros";
    return (
      <li
        key={d.dimension}
        className={`rounded-md transition-shadow duration-700 ${destello === d.dimension ? "ring-2 ring-espol-blue/50" : "ring-0"}`}
      >
        <button
          type="button"
          onClick={() => elegir(desplegada ? null : d.dimension)}
          aria-expanded={desplegada}
          title={
            con
              ? d.nivel != null
                ? `Nivel ${Math.round(d.nivel)} entre las ${d.n_con_registros} personas con registros.`
                : `Solo ${d.n_con_registros} personas tienen registros: muy pocas para comparar.`
              : DETALLE_ESTADO[d.estado]
          }
          className={`w-full grid grid-cols-[7.5rem_minmax(0,1fr)_2rem_3.25rem] items-center gap-2 py-1.5 px-1 rounded text-left ${
            desplegada ? "bg-slate-50" : "hover:bg-slate-50"
          }`}
        >
          <span className={`text-xs truncate ${desplegada ? "font-semibold text-espol-navy" : "text-slate-700"}`}>{d.nombre}</span>
          {con && d.nivel != null ? (
            <span className="relative h-2 rounded-sm bg-slate-100" aria-hidden>
              <span
                className="absolute top-1/2 w-2.5 h-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-espol-blue ring-2 ring-white"
                style={{ left: `${d.nivel}%` }}
              />
            </span>
          ) : (
            <span className="text-[11px] italic text-slate-400 truncate">
              {con ? "Muy pocas personas para comparar" : TEXTO_ESTADO[d.estado]}
            </span>
          )}
          <span className={`text-xs tabular-nums text-right ${con && d.nivel != null ? "text-slate-800 font-medium" : "text-slate-400"}`}>
            {con && d.nivel != null ? Math.round(d.nivel) : "—"}
          </span>
          <span className="text-[11px] tabular-nums text-right text-slate-500">
            {d.n_evidencias > 0 ? `${d.n_evidencias} ev.` : ""}
          </span>
        </button>
        {desplegada && <Detalle d={d} ambito={ambito} nav={nav} onVerEvidencias={onVerEvidencias} />}
      </li>
    );
  };

  return (
    <div>
      <p
        className="text-xs text-slate-600"
        title={`Percentil entre quienes tienen registros en cada dimensión (dentro de ${grupo}): ` +
          "50 = en la mitad; 90 = por encima del 90 % de ellas. Mide evidencia registrada, no capacidad."}
      >
        Nivel entre quienes tienen registros (percentil).
      </p>

      <ul ref={lista} className="mt-3 space-y-0.5 scroll-mt-12">
        {elegida && fila(elegida)}
        {elegida && (
          <li aria-hidden className="flex items-center gap-2 px-1 pt-2 pb-0.5 text-[10px] uppercase tracking-wide text-slate-400">
            <span>Demás dimensiones</span>
            <span className="flex-1 border-t border-slate-200" />
          </li>
        )}
        {resto.map(fila)}
      </ul>
      <div className="grid grid-cols-[7.5rem_minmax(0,1fr)_2rem_3.25rem] gap-2 px-1 mt-1 text-[10px] text-slate-400" aria-hidden>
        <span />
        <span className="flex justify-between"><span>0</span><span>50</span><span>100</span></span>
        <span className="col-span-2">percentil</span>
      </div>

    </div>
  );
}

// "Muy alto: a, b · Alto: c · Bajo: d" -> rasgos legibles por separado
const rasgos = (etiqueta: string) => etiqueta.split(" · ").map((r) => r.trim()).filter(Boolean);

const MAX_TEMAS = 4;

type SubPestana = "participa" | "temas" | "parecidos";

function Detalle({ d, ambito, nav, onVerEvidencias }: {
  d: DimensionPersona; ambito: Ambito; nav: NavegacionFicha; onVerEvidencias: (dimension: string) => void;
}) {
  const irDimension = nav.dimension;
  const con = d.estado === "con_registros";
  const grupo = NOMBRE_AMBITO[ambito];
  const [todos, setTodos] = useState(false);
  const [sub, setSub] = useState<SubPestana>("participa");
  const temas = todos ? d.temas : d.temas.slice(0, MAX_TEMAS);
  // "principal" solo si se nota: sin empate y al menos 20 puntos por encima del segundo tema
  const principalNotorio = d.temas.length > 0 && !d.dominante_empatado &&
    d.temas[0].proporcion - (d.temas[1]?.proporcion ?? 0) >= 0.2;
  const cercania = d.temas_dimension?.proporcion_por_cercania;

  if (!con) {
    return (
      <div className="mx-1 mt-1 mb-3 rounded-md bg-slate-50 px-3 py-2.5 text-xs text-slate-600">
        {DETALLE_ESTADO[d.estado]}
        {d.n_evidencias > 0 && (
          <>
            {" "}
            <Enlace onClick={() => onVerEvidencias(d.dimension)}>Ver el registro</Enlace>
          </>
        )}
        {d.idiomas && d.idiomas.length > 0 && <ListaIdiomas idiomas={d.idiomas} grupo={grupo} />}
      </div>
    );
  }

  const subpestanas: { id: SubPestana; texto: string }[] = [
    { id: "participa", texto: "Cómo participa" },
    { id: "temas", texto: d.idiomas ? "Idiomas" : "Temas" },
    { id: "parecidos", texto: "Parecidos" },
  ];
  return (
    <div className="mx-1 mt-1 mb-3 rounded-md bg-slate-50 p-2 text-xs text-slate-700">
      {/* resumen en una línea */}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 px-1">
        <span>
          <strong className="tabular-nums">{d.n_evidencias}</strong> evidencia{d.n_evidencias === 1 ? "" : "s"}
        </span>
        {d.nivel != null && (
          <span className="text-slate-500" title="Percentil entre quienes tienen registros en esta dimensión">
            nivel <strong className="text-slate-800 tabular-nums">{Math.round(d.nivel)}</strong> de 100 · entre {d.n_con_registros}
          </span>
        )}
        {d.ultima_evidencia && (
          <span className="text-slate-500" title={`Fecha de su evidencia más reciente en esta dimensión: ${d.ultima_evidencia}`}>
            · última en {d.ultima_evidencia.slice(0, 4)}
          </span>
        )}
      </div>

      {/* mini pestañas */}
      <div role="tablist" className="flex items-center gap-0.5 mt-1.5 border-b border-slate-200">
        {subpestanas.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={sub === t.id}
            onClick={() => setSub(t.id)}
            className={`px-2 py-1 text-[11px] border-b-2 -mb-px ${
              sub === t.id ? "border-espol-blue text-espol-navy font-semibold" : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            {t.texto}
          </button>
        ))}
        <span className="flex-1" />
        <button className="px-1.5 py-1 text-[11px] text-espol-blue hover:underline" onClick={() => onVerEvidencias(d.dimension)}>
          Evidencias →
        </button>
      </div>

      <div role="tabpanel" className="bg-white border border-t-0 border-slate-200 rounded-b-md px-3 py-2.5">
        {sub === "participa" && (
          <>
            {d.patron ? (
              <>
                <div className="flex items-center gap-2 mb-1">
                  <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: colorPatron(d.patron.patron) }} />
                  <Enlace
                    className="font-medium"
                    onClick={irDimension ? () => irDimension(d.dimension, { tipo: "patron", id: d.patron!.patron }) : undefined}
                  >
                    Patrón {d.patron.patron + 1}
                  </Enlace>
                  <span className="text-[11px] text-slate-400">· {d.patron.tamano} de {d.patron.n_personas} personas</span>
                </div>
                {d.patron.nombre ? (
                  <p className="text-slate-800" title={`Se cumple para todas las personas del patrón. En promedio: ${d.patron.etiqueta}`}>
                    {d.patron.nombre}
                  </p>
                ) : (
                  <div className="flex flex-wrap gap-1">
                    {rasgos(d.patron.etiqueta).map((r) => (
                      <Chip key={r}>{r}</Chip>
                    ))}
                  </div>
                )}
                {(d.patron.representante_nombre || d.patron.mixto) && (
                  <p className="text-[11px] text-slate-500 mt-1.5">
                    {d.patron.representante_nombre && d.patron.representante_id !== null && (
                      <>
                        Más representativa:{" "}
                        <Enlace onClick={nav.persona ? () => nav.persona!(d.patron!.representante_id!, "dimension", d.dimension) : undefined}>
                          {d.patron.representante_nombre}
                        </Enlace>
                      </>
                    )}
                    {d.patron.mixto && (
                      <span className="block text-amber-700" title={d.patron.segundo_nombre ?? d.patron.segundo}>
                        También cerca del{" "}
                        <Enlace onClick={irDimension ? () => irDimension(d.dimension, { tipo: "patron", id: d.patron!.segundo_id }) : undefined}>
                          Patrón {d.patron.segundo_id + 1}
                        </Enlace>
                      </span>
                    )}
                  </p>
                )}
              </>
            ) : (
              <p className="text-slate-500">Muy pocas personas con registros en esta dimensión para descubrir patrones.</p>
            )}
            <details className="mt-2 text-[11px] text-slate-400">
              <summary className="cursor-pointer hover:text-slate-600">¿Qué se tiene en cuenta?</summary>
              <ul className="list-disc ml-4 mt-1 space-y-0.5 text-slate-600">
                {d.componentes.map((c) => (
                  <li key={c.componente}>{c.descripcion.replace(/\s*\(.*\)\s*$/, "")}</li>
                ))}
              </ul>
              <p className="mt-1">El nivel compara esto con quienes tienen registros en la dimensión.</p>
            </details>
          </>
        )}

        {sub === "temas" && (
          d.idiomas ? (
            d.idiomas.length ? <ListaIdiomas idiomas={d.idiomas} grupo={grupo} /> : <p className="text-slate-500">Sin idiomas registrados.</p>
          ) : d.sin_temas ? (
            <p className="text-slate-500">{d.sin_temas}</p>
          ) : d.temas.length === 0 ? (
            <p className="text-slate-500">Sus evidencias no tienen un título que permita asignarles un tema.</p>
          ) : (
            <>
              <ul className="space-y-1.5">
                {temas.map((t, i) => (
                  <li key={t.tema} title={`${t.terminos.join(", ")} · ${t.n_personas_tema} personas tienen evidencias en este tema`}>
                    <div className="flex items-baseline gap-2">
                      <span className="flex-1 min-w-0 leading-snug">
                        <Enlace onClick={irDimension ? () => irDimension(d.dimension, { tipo: "tema", id: t.tema }) : undefined}>
                          {t.etiqueta}
                        </Enlace>
                      </span>
                      {t.parte_por_cercania !== null && t.parte_por_cercania >= 0.5 && (
                        <span className="text-[10px] text-amber-700" title="La mayoría de sus evidencias de este tema se asignaron por parecido: respaldo limitado">
                          aprox.
                        </span>
                      )}
                      {i === 0 && principalNotorio && <span className="text-[10px] font-semibold text-espol-navy">principal</span>}
                      <span className="text-[11px] tabular-nums text-slate-500 w-9 text-right">{Math.round(t.proporcion * 100)} %</span>
                    </div>
                    <span className="block h-1 mt-0.5 bg-slate-100 rounded-full">
                      <span className="block h-1 bg-espol-blue/70 rounded-full" style={{ width: `${t.proporcion * 100}%` }} />
                    </span>
                  </li>
                ))}
              </ul>
              <p className="text-[10px] text-slate-400 mt-1.5 flex flex-wrap gap-x-2">
                <span
                  title={"% = parte de sus evidencias de esta dimensión en cada tema. Agrupados automáticamente por el título de las evidencias." +
                    (cercania ? ` El ${Math.round(cercania * 100)} % de los textos de esta dimensión se asignó al tema más parecido.` : "")}
                >
                  Temas orientativos (agrupación automática)
                  {d.n_evidencias <= 2 ? " · pocas evidencias" : ""}
                </span>
                {d.temas.length > MAX_TEMAS && (
                  <button className="text-espol-blue hover:underline" onClick={() => setTodos(!todos)}>
                    {todos ? "ver menos" : `ver los ${d.temas.length}`}
                  </button>
                )}
              </p>
            </>
          )
        )}

        {sub === "parecidos" && <ParecidosDimension d={d} nav={nav} />}
      </div>
    </div>
  );
}

// Un idioma por línea: nombre y sus niveles tal como se registraron (sin combinarlos).
function ListaIdiomas({ idiomas, grupo }: { idiomas: NonNullable<DimensionPersona["idiomas"]>; grupo: string }) {
  return (
    <ul className="space-y-1.5">
      {idiomas.map((i, k) => (
        <li key={k} className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
          <span className="font-medium text-slate-800 w-20 shrink-0" title={`${i.n_personas} personas ${de(grupo)} lo registran`}>
            {i.idioma}
          </span>
          {i.mcer && <Chip fuerte titulo="Nivel MCER registrado">MCER {i.mcer}</Chip>}
          <span className="text-[11px] text-slate-500">
            {[["Conversación", i.conversacion], ["Lectura", i.lectura], ["Escritura", i.escritura]]
              .map(([h, v]) => `${h}: ${(v ?? "—").toLowerCase()}`)
              .join(" · ")}
          </span>
        </li>
      ))}
    </ul>
  );
}

// Dos listas separadas (DEC-061): cómo participa y de qué trata. Sin puntajes: orden y qué comparten.
function ParecidosDimension({ d, nav }: { d: DimensionPersona; nav: NavegacionFicha }) {
  const par = d.parecidos;
  if (!par || (!par.actividad && !par.tema)) {
    return <p className="text-slate-500">Muy pocas personas con registros en esta dimensión para comparar.</p>;
  }
  const abrir = nav.persona ? (id: number) => nav.persona!(id, "dimension", d.dimension) : undefined;
  const Lista = ({ titulo, filas, tipo }: { titulo: string; filas: NonNullable<typeof par.actividad>; tipo: "actividad" | "tema" }) => (
    <div>
      <p className="text-[11px] text-slate-500 mb-1">{titulo}</p>
      {filas.length === 0 ? (
        <p className="text-[11px] text-slate-400">Sin personas vigentes cercanas.</p>
      ) : (
        <ul className="space-y-1">
          {filas.map((x) => (
            <li key={x.persona_id} className="leading-tight">
              <span className="flex items-center gap-1.5">
                <Enlace onClick={abrir ? () => abrir(x.persona_id) : undefined}>{x.nombre}</Enlace>
                {x.en_ambos && <Chip fuerte titulo="También aparece en la otra lista">en ambos</Chip>}
              </span>
              <span className="block text-[11px] text-slate-500 truncate"
                title={x.texto_persona && x.texto_vecino && !x.misma_evidencia ? `«${x.texto_persona}» ~ «${x.texto_vecino}»` : undefined}>
                {tipo === "actividad"
                  ? x.identico ? "Mismo registro de actividad" : x.cargo_actual ?? "Sin cargo actual"
                  : x.misma_evidencia ? `Ambas registran «${x.texto_persona}»`
                  : x.comparte.length ? `Comparten: ${x.comparte.join(" · ")}`
                  : x.texto_vecino ? `Parecido a «${x.texto_vecino}»` : x.cargo_actual ?? ""}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
  return (
    <div className="space-y-2.5">
      {par.actividad && <Lista titulo="Participan de forma parecida" filas={par.actividad} tipo="actividad" />}
      {par.tema && <Lista titulo={d.idiomas ? "Registran los mismos idiomas" : "Trabajan temas parecidos"} filas={par.tema} tipo="tema" />}
      {par.n_identicos > 0 && (
        <p className="text-[10px] text-slate-400">
          {par.n_identicos} persona{par.n_identicos === 1 ? "" : "s"} del grupo tiene{par.n_identicos === 1 ? "" : "n"} exactamente el mismo registro de
          actividad en esta dimensión. No mide competencia ni idoneidad.
        </p>
      )}
    </div>
  );
}
