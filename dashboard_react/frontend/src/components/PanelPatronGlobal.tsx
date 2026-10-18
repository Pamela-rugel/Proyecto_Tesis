import { useCallback, useRef, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { de } from "../lib/texto";
import { getPersonasPatronGlobal, type Ambito, type DimensionPatronGlobal, type FiltroDimension, type PatronGlobal } from "../api/client";
import Enlace from "./Enlace";
import { Chip } from "./Bloques";
import Paginacion from "./Paginacion";
import BuscadorLista, { Resaltado } from "./BuscadorLista";
import { guardarPorPagina, porPaginaGuardado } from "../lib/paginacion";
import { colorPatron } from "../lib/colores";

export type PestanaPerfil = "micro" | "distingue" | "personas";

interface Props {
  ambito: Ambito;
  /** p. ej. "todo el personal docente": contra quién se compara un perfil amplio */
  nombreAmbito: string;
  patron: PatronGlobal;
  /** con más de 6 perfiles no hay color por perfil (ver MapaPerfil) */
  conColor: boolean;
  soloVigentes: boolean;
  microSel: number | null;
  onMicro: (m: number | null) => void;
  onPersona: (id: number) => void;
  onCerrar: () => void;
  /** pestaña activa (la guarda la página, para volver a ella al cerrar una ficha) */
  pestana: PestanaPerfil;
  onPestana: (p: PestanaPerfil) => void;
  /** ir a una dimensión (opcionalmente a uno de sus patrones) en la vista por dimensión */
  onDimension?: (dimension: string, filtro: FiltroDimension) => void;
}

// Detalle de un perfil amplio (DEC-062) en pestañas: sus microarquetipos, en qué se distingue
// (dimensiones y patrones) y las personas que lo forman. Elegir un microarquetipo lo aplica a las
// otras dos pestañas. Abrir una persona muestra su ficha en la pestaña Perfil completo.
export default function PanelPatronGlobal({
  ambito, nombreAmbito, patron, conColor, soloVigentes, microSel, onMicro, onPersona, onCerrar, pestana, onPestana, onDimension,
}: Props) {
  const micros = patron.microarquetipos?.lista ?? [];
  const micro = microSel !== null ? micros[microSel] ?? null : null;
  const activa: PestanaPerfil = pestana === "micro" && !micros.length ? "distingue" : pestana;
  // búsqueda por nombre en la lista: se vacía al cambiar de perfil, microarquetipo o vigencia
  const claveGrupo = JSON.stringify([ambito, patron.id, micro?.id ?? null, soloVigentes]);
  const [busqueda, setBusqueda] = useState({ clave: claveGrupo, q: "" });
  const q = busqueda.clave === claveGrupo ? busqueda.q : "";
  const buscar = useCallback((nuevo: string) => setBusqueda({ clave: claveGrupo, q: nuevo }), [claveGrupo]);
  // página de la lista: vuelve a la primera al cambiar de perfil, microarquetipo, vigencia o búsqueda
  const [porPagina, setPorPagina] = useState(porPaginaGuardado);
  const clave = JSON.stringify([ambito, patron.id, micro?.id ?? null, soloVigentes, porPagina, q]);
  const [paginaLista, setPaginaLista] = useState({ clave, n: 0 });
  const pagina = paginaLista.clave === clave ? paginaLista.n : 0;
  const tituloLista = useRef<HTMLDivElement | null>(null);
  const personas = useQuery({
    queryKey: ["personas-global", ambito, patron.id, micro?.id ?? null, soloVigentes, pagina, porPagina, q],
    queryFn: () => getPersonasPatronGlobal(ambito, patron.id, micro?.id ?? null, soloVigentes, pagina, porPagina, q),
    placeholderData: keepPreviousData,
  });
  const grupo = micro ?? patron;
  const nombreGrupo = micro ? micro.codigo : `Perfil ${patron.id + 1}`;
  const referencia = micro ? `el Perfil ${patron.id + 1}` : nombreAmbito;
  const pestanas: { id: PestanaPerfil; texto: string }[] = [
    ...(micros.length ? [{ id: "micro" as const, texto: `Microarquetipos (${micros.length})` }] : []),
    { id: "distingue", texto: "En qué se distingue" },
    { id: "personas", texto: `Personas${personas.data ? ` (${personas.data.total_grupo})` : ""}` },
  ];

  return (
    <section>
      <button onClick={onCerrar} className="text-xs text-espol-blue hover:underline px-5 pt-4 block text-left">
        ← Cerrar
      </button>
      <header className="px-5 pt-2 pb-3">
        <h3 className="text-lg font-semibold text-espol-navy flex items-center gap-2">
          {conColor && <span className="w-3 h-3 rounded-full" style={{ background: colorPatron(patron.id) }} />}
          Perfil {patron.id + 1}
        </h3>
        <p className="text-sm text-slate-700 mt-1">{patron.etiqueta}</p>
        {(patron.temas?.length ?? 0) > 0 && (
          <div className="flex flex-wrap gap-1 mt-1.5">
            {patron.temas!.map((t) => (
              <Chip key={`${t.dimension}-${t.tema}`} fuerte
                titulo={`${Math.round(t.proporcion * 100)} % del perfil tiene evidencias en este tema (${t.lift}× más que en el total)`}>
                <span className="text-slate-500">{t.nombre_dimension ?? t.dimension}:</span>
                <Enlace onClick={onDimension ? () => onDimension(t.dimension, { tipo: "tema", id: t.tema }) : undefined}>
                  {t.etiqueta.split(",").slice(0, 3).join(",")}
                </Enlace>
              </Chip>
            ))}
          </div>
        )}
        <p className="text-xs text-slate-500 mt-1">
          {soloVigentes ? `${patron.tamano_vigentes} personas vigentes` : `${patron.tamano} personas`} ·{" "}
          {Math.round(patron.proporcion * 100)} % {de(nombreAmbito)}
        </p>
        {micro && (
          <p className="mt-2 text-xs flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-espol-blue bg-blue-50 px-2 py-0.5 text-espol-navy">
              <span className="w-2 h-2 rounded-full" style={{ background: colorPatron(micro.id) }} />
              Viendo {micro.codigo}
            </span>
            <button className="text-[11px] text-espol-blue hover:underline" onClick={() => onMicro(null)}>ver todo el perfil</button>
          </p>
        )}
      </header>

      <div role="tablist" aria-label="Secciones del perfil" className="sticky top-0 z-20 bg-white border-y px-3 flex gap-1">
        {pestanas.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={activa === t.id}
            onClick={() => onPestana(t.id)}
            className={`px-2.5 py-2 text-xs whitespace-nowrap border-b-2 -mb-px ${
              activa === t.id ? "border-espol-blue text-espol-navy font-semibold" : "border-transparent text-slate-600 hover:text-slate-900"
            }`}
          >
            {t.texto}
          </button>
        ))}
      </div>

      {activa === "micro" && (
        <div role="tabpanel" className="px-5 py-3">
          <p className="text-[11px] text-slate-500 mb-2">
            Subgrupos dentro de este perfil, descritos frente a él. Elige uno para ver en qué se distingue y quiénes lo forman.
            {patron.microarquetipos?.estable === false && (
              <span className="text-amber-700"> Orientativos: estabilidad {patron.microarquetipos.estabilidad_ari.toFixed(2)}.</span>
            )}
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
                    <span className="text-[11px] text-slate-500 tabular-nums">{soloVigentes ? m.tamano_vigentes : m.tamano} personas</span>
                  </span>
                  <span className="block text-[11px] text-slate-600 ml-[1.1rem]">{m.etiqueta}</span>
                </button>
                {/* fuera del botón: un enlace no puede ir dentro de otro botón */}
                <p className="ml-[1.6rem] text-[11px] text-slate-500">
                  {m.representante_id !== null && m.representante_nombre ? (
                    <>
                      Más representativa: <Enlace onClick={() => onPersona(m.representante_id!)}>{m.representante_nombre}</Enlace>
                    </>
                  ) : (
                    "Sin personas vigentes que lo representen"
                  )}
                </p>
                {microSel === m.id && (
                  <p className="ml-[1.6rem] mt-0.5 mb-1 flex gap-3 text-[11px]">
                    <Enlace onClick={() => onPestana("distingue")}>En qué se distingue →</Enlace>
                    <Enlace onClick={() => onPestana("personas")}>Ver sus personas →</Enlace>
                  </p>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {activa === "distingue" && (
        <div role="tabpanel" className="px-5 py-4">
          <p className="text-[11px] text-slate-500 mb-2">
            Barra: % {de(nombreGrupo)} con registros (raya: {referencia}). Número: nivel típico de quienes tienen registros.
          </p>
          <ListaDimensiones dims={grupo.dimensiones} referencia={referencia} onDimension={onDimension} />
        </div>
      )}

      {activa === "personas" && (
        <div role="tabpanel">
          <div ref={tituloLista} className="px-5 pt-3 pb-2 scroll-mt-10">
            {grupo.representante_id !== null ? (
              <p className="text-[11px] text-slate-500">
                Más representativa de {nombreGrupo}:{" "}
                <Enlace onClick={() => onPersona(grupo.representante_id!)}>{grupo.representante_nombre}</Enlace>. El porcentaje es
                cuánto se parece cada persona a ella.
              </p>
            ) : (
              <p className="text-[11px] text-slate-500">Este grupo no tiene personas vigentes que lo representen.</p>
            )}
            <div className="mt-2">
              <BuscadorLista
                valor={q}
                onCambiar={buscar}
                contexto={nombreGrupo}
                coincidencias={personas.data?.q ? personas.data.total : undefined}
                totalGrupo={personas.data?.total_grupo}
              />
            </div>
          </div>
          <ul className="divide-y">
            {personas.data?.personas.map((x) => (
              <li key={x.persona_id}>
                <button onClick={() => onPersona(x.persona_id)} className="w-full text-left px-5 py-2 hover:bg-slate-50">
                  <span className="flex items-baseline gap-2">
                    <span className="text-sm text-slate-800 flex-1">
                      <Resaltado texto={x.nombre} q={q} />
                    </span>
                    {x.similitud !== null && (
                      <span className="text-xs tabular-nums text-slate-700"
                        title={x.similitud >= 0.9995 && !x.es_rep ? "Valores idénticos a la persona más representativa" : "Similitud con la persona más representativa"}>
                        {x.es_rep ? "representante" : x.similitud >= 0.9995 ? "idéntica" : `${Math.round(x.similitud * 100)} %`}
                      </span>
                    )}
                  </span>
                  <p className="text-[11px] text-slate-500 truncate">
                    {x.cargo_actual ?? "Sin cargo actual"}
                    {!x.vigente && " · no vigente"}
                    {!micro && x.micro >= 0 && ` · ${micros[x.micro]?.codigo ?? ""}`}
                    {q && ` · n.º ${x.posicion} de ${personas.data?.total_grupo ?? ""}`}
                  </p>
                </button>
              </li>
            ))}
          </ul>
          {personas.data && (
            <Paginacion
              pagina={pagina}
              total={personas.data.total}
              cargando={personas.isFetching}
              porPagina={porPagina}
              onPorPagina={(n) => {
                setPorPagina(n);
                guardarPorPagina(n);
                tituloLista.current?.scrollIntoView({ block: "start" });
              }}
              onCambiar={(n) => {
                setPaginaLista({ clave, n });
                tituloLista.current?.scrollIntoView({ block: "start" });
              }}
            />
          )}
        </div>
      )}
    </section>
  );
}

function ListaDimensiones({ dims, referencia, onDimension }: {
  dims: DimensionPatronGlobal[]; referencia: string; onDimension?: (dimension: string, filtro: FiltroDimension) => void;
}) {
  const orden = [...dims].sort((a, b) => b.pct_con_registros - a.pct_con_registros);
  return (
    <ul className="space-y-2">
      {orden.map((d) => {
        const pf = d.patron_frecuente;
        const destaca = pf && (pf.lift ?? 0) >= 1.5 && pf.proporcion >= 0.5;
        const nivel = (v: number | null) => (v === null ? "—" : String(Math.round(v)));
        return (
          <li key={d.dimension}
            title={`${d.nombre}: ${Math.round(d.pct_con_registros)} % con registros (${referencia}: ${Math.round(d.pct_con_registros_referencia)} %). ` +
              `Nivel típico: ${nivel(d.nivel_mediano)} (${referencia}: ${nivel(d.nivel_mediano_referencia)}).`}>
            <div className="grid grid-cols-[8rem_1fr_4.5rem] gap-2 items-center">
              <span className="text-xs text-slate-700 truncate">
                <Enlace onClick={onDimension ? () => onDimension(d.dimension, null) : undefined}>{d.nombre}</Enlace>
              </span>
              <span className="relative h-2.5 bg-slate-100 rounded-sm">
                <span className="absolute inset-y-0 left-0 bg-espol-blue rounded-r-[3px]" style={{ width: `${d.pct_con_registros}%` }} />
                <span className="absolute -inset-y-0.5 w-0.5 bg-slate-800" style={{ left: `${d.pct_con_registros_referencia}%` }} />
              </span>
              <span className="text-[11px] tabular-nums text-right text-slate-600">
                {d.nivel_mediano !== null ? <>nivel <strong className="text-xs text-slate-800">{Math.round(d.nivel_mediano)}</strong></> : "—"}
              </span>
            </div>
            {destaca && (
              <p className="text-[11px] text-slate-500 ml-[8.5rem]">
                El {Math.round(pf!.proporcion * 100)} % de quienes tienen evidencias aquí sigue el{" "}
                <Enlace onClick={onDimension ? () => onDimension(d.dimension, { tipo: "patron", id: pf!.patron }) : undefined}>
                  {pf!.nombre ? `«${pf!.nombre}»` : `Patrón ${pf!.patron + 1}`}
                </Enlace>{" "}de esta
                dimensión (en {referencia}: {Math.round(pf!.proporcion_referencia * 100)} %).
              </p>
            )}
          </li>
        );
      })}
    </ul>
  );
}
