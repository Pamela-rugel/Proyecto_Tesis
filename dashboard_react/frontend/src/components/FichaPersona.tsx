import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { de } from "../lib/texto";
import { enlaceComparar } from "../lib/enlaces";
import { getPersona, getPersonaEnDimension, type Ambito, type Persona } from "../api/client";
import IntensidadDimensiones from "./IntensidadDimensiones";
import TimelineTrayectoria from "./TimelineTrayectoria";
import { BloqueDimension, ListaEvidencias } from "./DetallePersona";
import { ChipPatronDimension } from "./PatronesDimension";

interface Props {
  ambito: Ambito;
  personaId: number;
  /** volver a la vista anterior del panel */
  onVolver: () => void;
  textoVolver: string;
  /** abrir la ficha de otra persona (personas parecidas) */
  onPersona?: (id: number) => void;
  /** dimensión desde la que se abrió: lo de esa dimensión va primero y el resto, plegado */
  dimension?: string | null;
  /** ir a la vista "Perfil completo" con la persona en su patrón global (y microarquetipo) */
  onIrPerfil?: (personaId: number, patron: number, micro: number | null) => void;
}

const NOMBRE_AMBITO: Record<Ambito, string> = {
  todos: "todo el personal",
  administrativos: "el personal administrativo",
  docentes: "el personal docente",
};

const Seccion = ({ titulo, children }: { titulo: string; children: ReactNode }) => (
  <div className="px-5 py-4 border-b">
    <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2">{titulo}</h4>
    {children}
  </div>
);

/** Sección plegada (en la ficha abierta desde una dimensión, lo que no es de esa dimensión). */
const Plegable = ({ titulo, children }: { titulo: string; children: ReactNode }) => (
  <details className="border-b group">
    <summary className="px-5 py-3 cursor-pointer text-xs font-semibold uppercase tracking-wide text-slate-500 hover:bg-slate-50 list-none flex items-center gap-2">
      <span className="text-slate-400 transition-transform group-open:rotate-90">▸</span>
      {titulo}
    </summary>
    <div className="px-5 pb-4">{children}</div>
  </details>
);

// Ficha de la persona: intensidad, patrón y temas en cada dimensión, trayectoria y evidencias.
// Abierta desde una dimensión, empieza por lo de esa dimensión (patrón, componentes frente al
// patrón, temas, sus evidencias y las personas parecidas en ella).
export default function FichaPersona({ ambito, personaId, onVolver, textoVolver, onPersona, dimension = null, onIrPerfil }: Props) {
  const { data, isLoading, isError } = useQuery({ queryKey: ["persona", ambito, personaId], queryFn: () => getPersona(personaId, ambito) });

  const volver = (
    <button onClick={onVolver} className="text-xs text-espol-blue hover:underline px-5 pt-4 block text-left">
      ← {textoVolver}
    </button>
  );
  if (isLoading) return <div>{volver}<p className="p-5 text-sm text-slate-500">Cargando ficha…</p></div>;
  if (isError || !data)
    return <div>{volver}<p className="p-5 text-sm text-red-600">La persona seleccionada no está en {NOMBRE_AMBITO[ambito]}.</p></div>;

  const encabezado = (
    <header className="px-5 pt-2 pb-4 border-b">
      <h3 className="text-lg font-semibold leading-tight text-espol-navy">{data.nombre}</h3>
      {/* cargo_actual y unidad_actual son listas " / " alineadas, ya ordenadas por jerarquía de
          contrato (nombramiento, contrato, servicios); todas se muestran con el mismo peso */}
      {(() => {
        const cargos = (data.estado.cargo_actual ?? "").split(" / ").filter(Boolean);
        const unidades = (data.estado.unidad_actual ?? "").split(" / ");
        if (!cargos.length) return <p className="text-sm text-slate-700 mt-1">Sin cargo actual</p>;
        return (
          <ul className="mt-1 space-y-0.5">
            {cargos.map((c, i) => (
              <li key={i} className="text-sm text-slate-700">
                {c}
                {unidades[i] && <span className="text-slate-500"> · {unidades[i]}</span>}
              </li>
            ))}
          </ul>
        );
      })()}
      <p className="text-xs text-slate-500 mt-1">
        {data.estado.tipo_empleado ?? "tipo desconocido"} · {data.estado.vigente ? "vigente" : "no vigente"}
      </p>
    </header>
  );

  const patronGlobal = data.patron_global && (
    <PatronGlobalPersona g={data.patron_global} ambito={ambito} personaId={personaId} onPersona={onPersona} />
  );
  const parecidos = data.parecidos.length > 0 && <ParecidosGlobales ambito={ambito} parecidos={data.parecidos} onPersona={onPersona} />;
  const totalEvidencias = data.evidencias.reduce((s, g) => s + g.n, 0);

  if (dimension) {
    return (
      <section>
        {volver}
        {encabezado}
        <SeccionDimension ambito={ambito} personaId={personaId} dimension={dimension} onPersona={onPersona} />
        {parecidos && <Seccion titulo="Parecidas en todo el perfil">{parecidos}</Seccion>}
        {patronGlobal && (
          <Plegable titulo="Perfil completo · patrón global">
            {onIrPerfil && data.patron_global && (
              <button
                onClick={() => onIrPerfil(personaId, data.patron_global!.patron, data.patron_global!.micro?.micro ?? null)}
                className="mb-2 text-xs text-espol-blue hover:underline"
              >
                Ver a esta persona en el perfil completo →
              </button>
            )}
            {patronGlobal}
          </Plegable>
        )}
        <Plegable titulo="Todas las dimensiones: puntaje y patrón">
          <IntensidadDimensiones
            ambito={ambito}
            dimensiones={data.dimensiones}
            personaId={personaId}
            nombrePersona={data.nombre}
            onPersona={onPersona}
          />
        </Plegable>
        <Plegable titulo="Trayectoria laboral">
          <TimelineTrayectoria personaId={data.persona_id} />
        </Plegable>
        <Plegable titulo={`Todas las evidencias (${totalEvidencias})`}>
          <ListaEvidencias evidencias={data.evidencias} />
        </Plegable>
      </section>
    );
  }

  return (
    <section>
      {volver}
      {encabezado}
      {patronGlobal && <Seccion titulo="Patrón global (todas las dimensiones)">{patronGlobal}</Seccion>}

      <Seccion titulo="Por dimensión: puntaje y patrón">
        <IntensidadDimensiones
          ambito={ambito}
          dimensiones={data.dimensiones}
          personaId={personaId}
          nombrePersona={data.nombre}
          onPersona={onPersona}
        />
      </Seccion>

      {parecidos && <Seccion titulo="Personas con perfil parecido">{parecidos}</Seccion>}

      <Seccion titulo="Trayectoria laboral">
        <TimelineTrayectoria personaId={data.persona_id} />
      </Seccion>

      <Seccion titulo="Evidencias">
        <ListaEvidencias evidencias={data.evidencias} />
      </Seccion>
    </section>
  );
}

function SeccionDimension({ ambito, personaId, dimension, onPersona }: {
  ambito: Ambito; personaId: number; dimension: string; onPersona?: (id: number) => void;
}) {
  const { data, isLoading } = useQuery({
    queryKey: ["persona-dimension", ambito, personaId, dimension],
    queryFn: () => getPersonaEnDimension(personaId, dimension, ambito),
  });
  if (isLoading || !data) return <Seccion titulo="En esta dimensión"><p className="text-xs text-slate-500">Cargando…</p></Seccion>;
  const rep = data.patron && !data.patron.es_representante ? data.patron.representante_id : null;
  return (
    <>
      <Seccion titulo={`En ${data.nombre}`}>
        <BloqueDimension datos={data} onPersona={onPersona} />
        {rep !== null && (
          <Link to={enlaceComparar(ambito, dimension, [personaId, rep])} className="inline-block mt-3 text-xs text-espol-blue hover:underline">
            Comparar con la persona más representativa →
          </Link>
        )}
      </Seccion>
      {data.parecidos.length > 0 && (
        <Seccion titulo={`Parecidas en ${data.nombre}`}>
          <p className="text-[11px] text-slate-500 mb-2">
            Las más cercanas con las mismas variables con que se formaron los patrones de {data.nombre} (sin las proporciones). A
            igual valor, primero quien comparte más temas.
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
                <p className="text-slate-600 mt-0.5">
                  {x.patron !== null ? (x.mismo_patron ? `Mismo patrón (P${x.patron + 1})` : `Otro patrón (P${x.patron + 1})`) : "Sin patrón"}
                  {x.mismos_valores && " · mismos valores en todos los componentes"}
                  {x.temas_comunes.length > 0 && ` · temas en común: ${x.temas_comunes.join("; ")}`}
                </p>
              </li>
            ))}
          </ol>
          <Link
            to={enlaceComparar(ambito, dimension, [personaId, ...data.parecidos.slice(0, 3).map((x) => x.persona_id)])}
            className="inline-block mt-3 text-xs text-espol-blue hover:underline"
          >
            Comparar con las 3 más parecidas →
          </Link>
        </Seccion>
      )}
    </>
  );
}

function PatronGlobalPersona({ g, ambito, personaId, onPersona }: {
  g: NonNullable<Persona["patron_global"]>; ambito: Ambito; personaId: number; onPersona?: (id: number) => void;
}) {
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
    <div>
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
      {!g.es_representante && g.representante_id !== null && (
        <Link to={enlaceComparar(ambito, "global", [personaId, g.representante_id])} className="inline-block mt-2 text-xs text-espol-blue hover:underline">
          Comparar con la persona más representativa →
        </Link>
      )}
    </div>
  );
}

function ParecidosGlobales({ ambito, parecidos, onPersona }: {
  ambito: Ambito; parecidos: Persona["parecidos"]; onPersona?: (id: number) => void;
}) {
  return (
    <>
      <p className="text-[11px] text-slate-500 mb-2">
        Las más cercanas considerando todas las dimensiones a la vez (cuánto tiene en cada una y cómo participa). Se indica en qué
        coinciden: dimensiones donde ambas tienen intensidad de 50 o más, y si siguen el mismo patrón.
      </p>
      <ol className="space-y-2">
        {parecidos.map((x) => (
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
                    {c.mismo_patron && c.patron !== null && (
                      <>
                        {" "}
                        <ChipPatronDimension ambito={ambito} dimension={c.dimension} patron={c.patron} sinDimension />
                      </>
                    )}
                  </span>
                ))}
              </p>
            )}
          </li>
        ))}
      </ol>
    </>
  );
}
