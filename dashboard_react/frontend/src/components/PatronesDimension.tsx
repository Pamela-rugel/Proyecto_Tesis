import { useCallback, useMemo, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { getDimension, getPersonaEnDimension, getRepartoEnDimension, type Ambito } from "../api/client";
import { colorPatron } from "../lib/colores";
import { ContextoPatrones, usePatronesDimension, type GrupoGlobal } from "../lib/navegacion";
import { BloqueDimension } from "./DetallePersona";
import Modal from "./Modal";
import TarjetaPatron from "./TarjetaPatron";

// Los patrones de una dimensión vistos desde cualquier parte (perfil completo, ficha, validación):
// un chip "P2 · Investigación" que explica el patrón y, al hacer clic, abre todos los patrones de
// esa dimensión, con la opción de ir a ella y volver.

interface Abierto {
  dimension: string;
  patron: number | null;
  grupo: GrupoGlobal | null;
}

/** Da a los chips de su interior la ventana de patrones. `onIr`: ir a la dimensión (y al patrón)
 *  en la vista "Por dimensión"; sin él, la ventana no ofrece ir. */
export function ProveedorPatronesDimension({ ambito, onIr, children }: {
  ambito: Ambito; onIr?: (dimension: string, patron: number | null, persona?: number | null) => void; children: ReactNode;
}) {
  const [abierto, setAbierto] = useState<Abierto | null>(null);
  const valor = useMemo(
    () => ({
      verPatrones: (dimension: string, o?: { patron?: number | null; grupo?: GrupoGlobal | null }) =>
        setAbierto({ dimension, patron: o?.patron ?? null, grupo: o?.grupo ?? null }),
      irADimension: onIr,
    }),
    [onIr],
  );
  const cerrar = useCallback(() => setAbierto(null), []);
  return (
    <ContextoPatrones.Provider value={valor}>
      {children}
      {abierto && (
        <ModalPatronesDimension
          ambito={ambito}
          {...abierto}
          onCerrar={cerrar}
          onIr={
            onIr
              ? (d, p) => {
                  cerrar();
                  onIr(d, p);
                }
              : undefined
          }
        />
      )}
    </ContextoPatrones.Provider>
  );
}

/** "● P2 · Investigación": al pasar el mouse dice qué significa; al hacer clic abre los patrones. */
export function ChipPatronDimension({ ambito, dimension, patron, grupo = null, sinDimension = false }: {
  ambito: Ambito; dimension: string; patron: number; grupo?: GrupoGlobal | null;
  /** solo "P2" (cuando la dimensión ya se nombra al lado) */
  sinDimension?: boolean;
}) {
  const nav = usePatronesDimension();
  const detalle = useQuery({ queryKey: ["dimension", ambito, dimension], queryFn: () => getDimension(ambito, dimension) });
  const ficha = detalle.data?.patrones?.patrones[patron];
  const nombre = detalle.data?.nombre ?? dimension;
  const texto = `Patrón ${patron + 1} de ${nombre}${ficha ? `: ${ficha.etiqueta}` : ""}.${nav ? " Clic para ver todos los patrones de " + nombre + "." : ""}`;
  const contenido = (
    <>
      <span className="w-2 h-2 rounded-full shrink-0" style={{ background: colorPatron(patron) }} />
      P{patron + 1}
      {!sinDimension && <span className="text-slate-500">· {nombre}</span>}
    </>
  );
  const clase = "inline-flex items-center gap-1 border rounded px-1.5 py-px text-[11px] text-slate-800 bg-white align-baseline";
  if (!nav) return <span className={clase} title={texto}>{contenido}</span>;
  return (
    <button
      type="button"
      title={texto}
      onClick={(e) => {
        e.stopPropagation();
        nav.verPatrones(dimension, { patron, grupo });
      }}
      className={`${clase} hover:border-espol-blue hover:text-espol-blue`}
    >
      {contenido}
    </button>
  );
}

/** Todos los patrones de una dimensión, con el elegido resaltado y, si se mira desde un patrón
 *  global o microarquetipo, cuántas de sus personas siguen cada uno frente a su referencia. */
function ModalPatronesDimension({ ambito, dimension, patron, grupo, onCerrar, onIr }: Abierto & {
  ambito: Ambito; onCerrar: () => void; onIr?: (dimension: string, patron: number | null) => void;
}) {
  const detalle = useQuery({ queryKey: ["dimension", ambito, dimension], queryFn: () => getDimension(ambito, dimension) });
  const reparto = useQuery({
    queryKey: ["reparto", ambito, grupo?.patron, grupo?.micro, dimension],
    queryFn: () => getRepartoEnDimension(ambito, grupo!.patron, grupo!.micro, dimension),
    enabled: !!grupo,
  });
  const d = detalle.data;
  const nombre = d?.nombre ?? dimension;
  const referencia = grupo ? (grupo.micro !== null ? `su Patrón global ${grupo.patron + 1}` : "todo el ámbito") : "";
  const pct = (v: number) => `${Math.round(v * 100)} %`;

  return (
    <Modal titulo={`Patrones de ${nombre}`} onCerrar={onCerrar} ancho="amplio">
      {!d ? (
        <p className="text-sm text-slate-500">Cargando…</p>
      ) : !d.patrones ? (
        <p className="text-sm text-slate-600">{nombre} no se divide en patrones de actividad.</p>
      ) : (
        <div className="space-y-3">
          <p className="text-xs text-slate-600">
            Las {d.n_personas.toLocaleString("es")} personas con evidencias en {nombre} se agruparon en {d.patrones.k} patrones según
            cómo participan (los datos de la dimensión, sin el texto de las evidencias).
            {grupo && reparto.data && (
              <>
                {" "}
                Debajo de cada patrón: cuántas de las {reparto.data.con_evidencia} personas de <strong>{grupo.nombre}</strong> con
                evidencias en {nombre} lo siguen, frente a {referencia}.
              </>
            )}
          </p>
          <div className="grid md:grid-cols-2 gap-3">
            {d.patrones.patrones.map((p) => {
              const r = reparto.data?.patrones.find((x) => x.patron === p.id);
              return (
                <TarjetaPatron
                  key={p.id}
                  patron={p}
                  seleccionado={patron === p.id}
                  onClick={() => onIr?.(dimension, p.id)}
                  nombreDimension={nombre}
                  pie={
                    <div className="mt-2 pt-2 border-t space-y-1.5">
                      {grupo && r && (
                        <div title={`${r.n} personas de ${grupo.nombre}`}>
                          <p className="text-[11px] text-slate-700">
                            <strong className="tabular-nums">{pct(r.proporcion)}</strong> de {grupo.nombre}{" "}
                            <span className="text-slate-500">
                              ({r.n}) · en {referencia}: {pct(r.proporcion_referencia)}
                            </span>
                          </p>
                          <span className="relative block h-1.5 bg-slate-100 rounded-sm mt-0.5">
                            <span className="absolute inset-y-0 left-0 bg-espol-blue rounded-sm" style={{ width: `${r.proporcion * 100}%` }} />
                            <span
                              className="absolute -inset-y-0.5 w-0.5 bg-slate-800"
                              style={{ left: `${r.proporcion_referencia * 100}%` }}
                              title={`en ${referencia}`}
                            />
                          </span>
                        </div>
                      )}
                      {onIr && (
                        <button onClick={() => onIr(dimension, p.id)} className="text-[11px] text-espol-blue hover:underline">
                          Ver sus personas en {nombre} →
                        </button>
                      )}
                    </div>
                  }
                />
              );
            })}
          </div>
          {onIr && (
            <div className="flex justify-end">
              <button
                onClick={() => onIr(dimension, null)}
                className="text-xs px-3 py-1.5 rounded-md bg-espol-navy text-white hover:bg-espol-blue"
              >
                Ir a {nombre} →
              </button>
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}

/** La persona en una dimensión, en una ventana: su puntaje, su patrón, sus datos frente a su
 *  patrón, temas y evidencias. Desde aquí: ver todos los patrones de la dimensión, o ir a ella con
 *  su patrón elegido y la ficha de la persona abierta (con regreso). */
export function ModalDimensionPersona({ ambito, personaId, nombrePersona, dimension, onCerrar, onPersona }: {
  ambito: Ambito; personaId: number; nombrePersona: string; dimension: string; onCerrar: () => void; onPersona?: (id: number) => void;
}) {
  const nav = usePatronesDimension();
  const { data } = useQuery({
    queryKey: ["persona-dimension", ambito, personaId, dimension],
    queryFn: () => getPersonaEnDimension(personaId, dimension, ambito),
  });
  const patron = data?.patron?.patron ?? null;
  return (
    <Modal titulo={`${nombrePersona} en ${data?.nombre ?? dimension}`} onCerrar={onCerrar}>
      {!data ? (
        <p className="text-sm text-slate-500">Cargando…</p>
      ) : (
        <div className="space-y-4">
          {nav && (
            <div className="flex flex-wrap gap-2">
              {nav.irADimension && (
                <button
                  onClick={() => {
                    onCerrar();
                    nav.irADimension!(dimension, patron, personaId);
                  }}
                  className="text-xs px-3 py-1.5 rounded-md bg-espol-navy text-white hover:bg-espol-blue"
                >
                  Ir a {data.nombre}
                  {patron !== null ? ` · Patrón ${patron + 1}` : ""} →
                </button>
              )}
              {data.patron && (
                <button
                  onClick={() => {
                    onCerrar();
                    nav.verPatrones(dimension, { patron });
                  }}
                  className="text-xs px-3 py-1.5 rounded-md border text-espol-blue hover:border-espol-blue"
                >
                  Ver todos los patrones de {data.nombre}
                </button>
              )}
            </div>
          )}
          <BloqueDimension
            datos={data}
            onPersona={
              onPersona
                ? (id) => {
                    onCerrar();
                    onPersona(id);
                  }
                : undefined
            }
          />
        </div>
      )}
    </Modal>
  );
}
