import { useQuery } from "@tanstack/react-query";
import { Fragment, useState, type ReactNode } from "react";
import Plot from "react-plotly.js";
import { getPersonaFicha } from "../api/client";
import { LoadingBlock, ErrorBlock } from "./LoadingBlock";
import TimelineTrayectoria from "./TimelineTrayectoria";
import DataTable from "./DataTable";

interface Props {
  idPersona: number;
  coincidenciaSemantica?: { rango: number; consulta: string };
  mostrarClusterPerfil?: boolean;
  mostrarEvidenciaTexto?: boolean;
  // "trayectoria": la coincidencia vino de /api/buscar_avanzado_trayectoria - el bloque
  // "¿Por qué coincide?" debe mostrar el documento/variables de TRAYECTORIA (el mismo texto
  // que se comparo semanticamente), no el corpus generico de temas/conocimiento.
  origenBusqueda?: "trayectoria";
}

const SECCIONES_CONFIG: Record<string, { titulo: string; columns: { key: string; label: string }[] }> = {
  formacion: {
    titulo: "Formación",
    columns: [
      { key: "Titulo", label: "Título" },
      { key: "Nivel", label: "Nivel" },
      { key: "Institucion", label: "Institución" },
      { key: "Pais", label: "País" },
      { key: "FechaGraduacion", label: "Graduación" },
    ],
  },
  docencia: {
    titulo: "Docencia",
    columns: [
      { key: "NOMMATERIA", label: "Materia" },
      { key: "ANIO_MIN", label: "Desde" },
      { key: "ANIO_MAX", label: "Hasta" },
      { key: "N_PERIODOS", label: "N° periodos" },
      { key: "UNIDAD", label: "Unidad" },
    ],
  },
  vinculacion: {
    titulo: "Vinculación",
    columns: [
      { key: "NOMBREPROYECTO", label: "Proyecto" },
      { key: "NOMBREPROGRAMA", label: "Programa" },
      { key: "FECHAINICIO", label: "Desde" },
      { key: "FECHAFIN", label: "Hasta" },
    ],
  },
  idiomas: {
    titulo: "Idiomas",
    columns: [
      { key: "IDIOMA", label: "Idioma" },
      { key: "NIVELLECTURA", label: "Lectura" },
      { key: "NIVELESCRITURA", label: "Escritura" },
      { key: "NIVELCONVERSACION", label: "Conversación" },
      { key: "NIVELMCER", label: "Nivel MCER" },
    ],
  },
  reconocimientos: {
    titulo: "Reconocimientos",
    columns: [
      { key: "NOMBREMENCION", label: "Mención" },
      { key: "INSTITUCION", label: "Institución" },
      { key: "FECHA", label: "Fecha" },
    ],
  },
};

function InvestigacionSeccion({ datos }: { datos: Record<string, Record<string, unknown>[]> }) {
  return (
    <div className="space-y-4">
      {datos.proyectos?.length > 0 && (
        <div>
          <p className="font-semibold text-sm mb-1">Proyectos de investigación</p>
          <DataTable
            rows={datos.proyectos}
            columns={[
              { key: "NOMBRE", label: "Proyecto" },
              { key: "STRAREACAMPOAMPLIO", label: "Área" },
              { key: "FECHAINICIO", label: "Desde" },
              { key: "FECHAFIN", label: "Hasta" },
              { key: "ESTADO_PROYECTO", label: "Estado" },
            ]}
          />
        </div>
      )}
      {datos.publicaciones?.length > 0 && (
        <div>
          <p className="font-semibold text-sm mb-1">Publicaciones</p>
          <DataTable
            rows={datos.publicaciones}
            columns={[
              { key: "TITULO", label: "Título" },
              { key: "ANIO", label: "Año" },
              { key: "TIPOPUBLICACION", label: "Tipo" },
              { key: "CUARTIL", label: "Cuartil" },
            ]}
          />
        </div>
      )}
      {datos.tesis_dirigidas?.length > 0 && (
        <div>
          <p className="font-semibold text-sm mb-1">Trabajos de titulación dirigidos</p>
          <DataTable
            rows={datos.tesis_dirigidas}
            columns={[
              { key: "NOMBRETRABAJOTITULACION", label: "Trabajo de titulación" },
              { key: "FECHASUSTENTACION", label: "Sustentación" },
              { key: "NIVELFORMACION", label: "Nivel" },
            ]}
          />
        </div>
      )}
      {datos.ponencias?.length > 0 && (
        <div>
          <p className="font-semibold text-sm mb-1">Ponencias</p>
          <DataTable
            rows={datos.ponencias}
            columns={[
              { key: "NOMBRE", label: "Ponencia" },
              { key: "FECHAINICIO", label: "Fecha" },
              { key: "NOMBREPAIS", label: "País" },
            ]}
          />
        </div>
      )}
    </div>
  );
}

function CapacitacionSeccion({ datos }: { datos: Record<string, Record<string, unknown>[]> }) {
  return (
    <div className="space-y-4">
      {datos.capacitaciones?.length > 0 && (
        <div>
          <p className="font-semibold text-sm mb-1">Capacitación ({datos.capacitaciones.length} registros)</p>
          <DataTable
            rows={datos.capacitaciones}
            maxHeight={320}
            columns={[
              { key: "NOMBRE", label: "Nombre" },
              { key: "FECHAINICIO", label: "Fecha" },
              { key: "TIPOCAPACITACION", label: "Tipo" },
              { key: "NOMBREPAIS", label: "País" },
            ]}
          />
        </div>
      )}
      {datos.certificaciones?.length > 0 && (
        <div>
          <p className="font-semibold text-sm mb-1">Certificaciones</p>
          <DataTable
            rows={datos.certificaciones}
            columns={[
              { key: "NOMBRE", label: "Nombre" },
              { key: "FECHAINICIO", label: "Fecha" },
              { key: "CERTIFICADOPOR", label: "Certificado por" },
            ]}
          />
        </div>
      )}
    </div>
  );
}

const CAMPOS_CABECERA: { key: string; label: string }[] = [
  { key: "TIPOEMPLEADO_ACTUAL_DESC", label: "Tipo de empleado" },
  { key: "CARGO_ACTUAL", label: "Cargo actual" },
  { key: "UNIDAD_ACTUAL_NOMBRE", label: "Unidad actual" },
];

export default function PersonaFicha({
  idPersona,
  coincidenciaSemantica,
  mostrarClusterPerfil = true,
  mostrarEvidenciaTexto = true,
  origenBusqueda,
}: Props) {
  const [tabActiva, setTabActiva] = useState<string | null>(null);
  const { data, isLoading, error } = useQuery({
    queryKey: ["persona", idPersona, origenBusqueda ?? null],
    queryFn: () => getPersonaFicha(idPersona, origenBusqueda),
  });

  if (isLoading) return <LoadingBlock label="Cargando ficha de persona..." />;
  if (error || !data) return <ErrorBlock message="No se pudo cargar la ficha de esta persona." />;

  const { persona, tiene_perfil, motivo_sin_perfil, eventos_trayectoria, resumen_cargos_espol, secciones, radar,
    cluster_descripcion, corpus_muestra, n_textos, evidencia_trayectoria, etiqueta_tipo_evento } = data;

  const seccionesDisponibles = Object.keys(SECCIONES_CONFIG).filter((k) => secciones[k]);
  if (secciones.investigacion) seccionesDisponibles.push("investigacion");
  if (secciones.capacitacion) seccionesDisponibles.push("capacitacion");
  const orden = ["formacion", "docencia", "investigacion", "vinculacion", "capacitacion", "idiomas", "reconocimientos"];
  seccionesDisponibles.sort((a, b) => orden.indexOf(a) - orden.indexOf(b));

  const activa = tabActiva && seccionesDisponibles.includes(tabActiva) ? tabActiva : seccionesDisponibles[0];

  return (
    <div className="space-y-5">
      <div>
        <div className="flex items-center gap-2">
          <h3 className="text-lg font-semibold tracking-tight">{fmtVal(persona.NOMBRE_COMPLETO)}</h3>
          {persona.VIGENTE_MOSTRAR ? (
            <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
              Vigente
            </span>
          ) : (
            <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-500 border border-slate-200">
              No vigente
            </span>
          )}
        </div>
        {coincidenciaSemantica && (
          <div className="mt-2 rounded-md bg-espol-blue/5 border border-espol-blue/20 text-slate-700 text-sm px-3 py-2">
            Resultado #{coincidenciaSemantica.rango} para tu búsqueda "{coincidenciaSemantica.consulta}". Ver
            el detalle en "¿Por qué coincide?", más abajo.
          </div>
        )}
        {tiene_perfil ? (
          <p className="mt-2 text-sm">
            <span className="text-slate-500">Perfil: </span>
            <span className="font-medium text-slate-800">{String(persona.PERFIL_NOMBRE)}</span>{" "}
            <span className="text-slate-400">(cluster {String(persona.CLUSTER)})</span>
          </p>
        ) : (
          <p className="mt-2 text-xs text-slate-500">
            Sin perfil/cluster asignado — esta persona no tiene un cargo estructural en ESPOL.{" "}
            {motivo_sin_perfil ?? "No se encontró un motivo específico en los datos."}
          </p>
        )}
        {Boolean(persona.TUVO_FUNCION_ADICIONAL) && (
          <p className="mt-1 text-xs text-slate-500 border-l-2 border-slate-200 pl-2">
            Además de su cargo, ha ejercido una función adicional en paralelo en algún momento (ver
            Trayectoria abajo).
          </p>
        )}
        {Boolean(persona.CARGO_ES_CONTRATO_PUNTUAL_VIGENTE) && (
          <p className="mt-1 text-xs text-slate-500 border-l-2 border-slate-200 pl-2">
            Su cargo estructural más reciente ya finalizó; "Cargo actual"/"Unidad actual" abajo
            corresponden a un contrato vigente de tipo puntual/servicios profesionales, no a un cargo
            estructural continuo.
          </p>
        )}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 bg-slate-50 rounded-lg p-4 border border-slate-100">
        {CAMPOS_CABECERA.map((c) => (
          <div key={c.key}>
            <p className="text-xs font-medium text-slate-500">{c.label}</p>
            <p className="text-sm font-semibold text-slate-800 mt-0.5">{fmtVal(persona[c.key])}</p>
          </div>
        ))}
        <div>
          <p className="text-xs font-medium text-slate-500">Vigente actualmente</p>
          <p className="text-sm font-semibold text-slate-800 mt-0.5">{persona.VIGENTE_MOSTRAR ? "Sí" : "No"}</p>
        </div>
      </div>

      <div className="bg-slate-50 rounded-lg p-4 border border-slate-100">
        <p className="text-xs font-medium text-slate-500 mb-2">
          Cargos en ESPOL ({resumen_cargos_espol.total} en total — no incluye experiencia externa;
          renovaciones consecutivas del mismo cargo cuentan como uno solo)
        </p>
        <div className="flex flex-wrap gap-2">
          <span className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium bg-espol-navy/10 text-espol-navy">
            Administrativo: {resumen_cargos_espol.administrativo}
          </span>
          <span className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium bg-espol-blue/10 text-espol-blue">
            Docente: {resumen_cargos_espol.docente}
          </span>
          {resumen_cargos_espol.otras_categorias.map((o) => (
            <span
              key={o.etiqueta}
              className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium bg-slate-200 text-slate-600"
            >
              {o.etiqueta}: {o.cantidad}
            </span>
          ))}
        </div>
      </div>

      <div>
        <h4 className="font-semibold text-sm mb-2 text-slate-700">Trayectoria</h4>
        <TimelineTrayectoria
          eventos={eventos_trayectoria}
          etiquetaTipoEvento={etiqueta_tipo_evento}
        />
      </div>

      {seccionesDisponibles.length > 0 ? (
        <div>
          <h4 className="font-semibold text-sm mb-2 text-slate-700">Perfil profesional</h4>
          <div className="flex gap-1 border-b border-slate-200 mb-3 overflow-x-auto">
            {seccionesDisponibles.map((k) => (
              <button
                key={k}
                onClick={() => setTabActiva(k)}
                className={`whitespace-nowrap px-3 py-1.5 text-sm rounded-t-md border-b-2 transition-colors ${
                  activa === k
                    ? "border-espol-accent font-semibold text-espol-navy"
                    : "border-transparent text-slate-500 hover:text-slate-700"
                }`}
              >
                {SECCIONES_CONFIG[k]?.titulo ?? (k === "investigacion" ? "Investigación" : "Capacitación")}
              </button>
            ))}
          </div>
          <div>
            {activa === "investigacion" && <InvestigacionSeccion datos={secciones.investigacion as never} />}
            {activa === "capacitacion" && <CapacitacionSeccion datos={secciones.capacitacion as never} />}
            {activa && SECCIONES_CONFIG[activa] && (
              <DataTable columns={SECCIONES_CONFIG[activa].columns} rows={secciones[activa] as never} />
            )}
          </div>
        </div>
      ) : (
        <p className="text-sm text-slate-400">
          No hay información adicional de formación/docencia/investigación registrada.
        </p>
      )}

      {tiene_perfil && mostrarClusterPerfil && (
        <div>
          <h4 className="font-semibold text-sm mb-1 text-slate-700">Cluster / perfil de trayectoria</h4>
          {cluster_descripcion && <p className="text-sm text-slate-600 mb-2">{cluster_descripcion}</p>}
          {radar && radar.features.length > 0 && (
            <details className="rounded-lg border border-slate-200 p-3">
              <summary className="cursor-pointer text-sm font-medium text-slate-700">
                Comparación con la institución (percentil sobre variables clave)
              </summary>
              <Plot
                data={[
                  {
                    type: "scatterpolar",
                    r: [...radar.valores, radar.valores[0]],
                    theta: [...radar.features, radar.features[0]],
                    fill: "toself",
                    name: "Esta persona",
                  },
                ]}
                layout={{
                  polar: { radialaxis: { visible: true, range: [0, 1] } },
                  showlegend: false,
                  height: 380,
                  margin: { l: 40, r: 40, t: 20, b: 20 },
                }}
                config={{ displayModeBar: false, responsive: true }}
                style={{ width: "100%" }}
              />
              <p className="text-xs text-slate-500">
                Percentil respecto a la población total (0 = valor más bajo, 1 = valor más alto).
              </p>
            </details>
          )}
        </div>
      )}

      {origenBusqueda === "trayectoria" ? (
        <details open className="rounded-lg border border-amber-200 bg-amber-50/40 p-3">
          <summary className="cursor-pointer text-sm font-medium text-amber-900">
            ¿Por qué coincide? (patrón de trayectoria)
          </summary>
          <div className="mt-3">
            <EvidenciaTrayectoriaBloque evidencia={evidencia_trayectoria} />
          </div>
        </details>
      ) : (
        n_textos > 0 && (mostrarEvidenciaTexto || coincidenciaSemantica) && (
          <details open={Boolean(coincidenciaSemantica)} className="rounded-lg border border-slate-200 p-3">
            <summary className="cursor-pointer text-sm font-medium text-slate-700">
              {coincidenciaSemantica
                ? "¿Por qué coincide? (texto semántico + datos estructurales)"
                : `Evidencia de texto usada en búsqueda semántica (${n_textos} registros)`}
            </summary>
            <div className="mt-3 space-y-2">
              {corpus_muestra.length > 0 && (
                <DataTable
                  rows={corpus_muestra as never}
                  columns={[
                    { key: "FUENTE", label: "Fuente" },
                    { key: "TEXTO", label: "Texto" },
                  ]}
                />
              )}
            </div>
          </details>
        )
      )}
    </div>
  );
}

type MetricaId = "cargos_significativos" | "cambios_cargo" | "cambios_unidad" | "unidades";

function EvidenciaTrayectoriaBloque({ evidencia }: { evidencia: import("../api/types").EvidenciaTrayectoria | null }) {
  const [metricaActiva, setMetricaActiva] = useState<MetricaId | null>(null);
  const [periodoParaleloActivo, setPeriodoParaleloActivo] = useState<number | null>(null);

  if (!evidencia || !evidencia.disponible) {
    return (
      <p className="text-sm text-slate-500">
        {evidencia?.motivo ?? "Sin información de trayectoria disponible para esta persona."}
      </p>
    );
  }
  const v = evidencia.variables!;
  const periodos = evidencia.periodos ?? [];
  const cambiosCargo = evidencia.secuencia_cambios_cargo ?? [];
  const cambiosUnidad = evidencia.secuencia_cambios_unidad ?? [];
  const cargosSignificativos = periodos.filter((p) => p.es_significativo);

  function toggle(id: MetricaId) {
    setMetricaActiva((actual) => (actual === id ? null : id));
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Metrica
          label="Cargos significativos"
          valor={`${v.n_cargos_significativos} / ${v.n_cargos_total}`}
          activa={metricaActiva === "cargos_significativos"}
          onClick={() => toggle("cargos_significativos")}
        />
        <Metrica
          label="Cambios de cargo"
          valor={String(v.n_cambios_cargo)}
          activa={metricaActiva === "cambios_cargo"}
          onClick={() => toggle("cambios_cargo")}
        />
        <Metrica
          label="Cambios de unidad"
          valor={String(v.n_cambios_unidad)}
          activa={metricaActiva === "cambios_unidad"}
          onClick={() => toggle("cambios_unidad")}
        />
        <Metrica
          label="Unidades distintas"
          valor={`${v.n_unidades_significativas} / ${v.n_unidades_total}`}
          activa={metricaActiva === "unidades"}
          onClick={() => toggle("unidades")}
        />
        <Metrica label="Duración mediana" valor={v.duracion_mediana_cargo_anios != null ? `${v.duracion_mediana_cargo_anios.toFixed(1)} años` : "-"} />
        <Metrica label="Duración media" valor={v.duracion_media_cargo_anios != null ? `${v.duracion_media_cargo_anios.toFixed(1)} años` : "-"} />
        <Metrica label="Cargo más largo" valor={v.duracion_max_cargo_anios != null ? `${v.duracion_max_cargo_anios.toFixed(1)} años` : "-"} />
        <Metrica
          label="% cargos significativos"
          valor={v.proporcion_cargos_significativos != null ? `${Math.round(v.proporcion_cargos_significativos * 100)}%` : "-"}
        />
      </div>

      {metricaActiva === "cargos_significativos" && (
        <DetalleCaja titulo="Cargos significativos (≥ 3 meses de duración)">
          {cargosSignificativos.length === 0 ? (
            <p className="text-xs text-slate-400">Sin cargos significativos registrados.</p>
          ) : (
            <ul className="space-y-1.5">
              {cargosSignificativos.map((p, i) => (
                <li key={i} className="text-xs text-slate-600">
                  <span className="font-medium text-slate-800">{p.cargo ?? "Cargo sin especificar"}</span>
                  {p.unidad && <span className="text-slate-500"> — {p.unidad}</span>}
                  <span className="text-slate-400">
                    {" "}({p.inicio ?? "?"} — {p.vigente ? "actualidad" : p.fin ?? "?"}, {p.duracion_anios?.toFixed(1)} años)
                  </span>
                </li>
              ))}
            </ul>
          )}
        </DetalleCaja>
      )}

      {metricaActiva === "cambios_cargo" && (
        <DetalleCaja titulo="Secuencia de cambios de cargo">
          {cambiosCargo.length === 0 ? (
            <p className="text-xs text-slate-400">Sin cambios de cargo registrados.</p>
          ) : (
            <ol className="space-y-1.5">
              {cambiosCargo.map((c, i) => (
                <li key={i} className="text-xs text-slate-600">
                  <span className="text-slate-400">{c.fecha ?? "?"}:</span>{" "}
                  <span className="text-slate-700">{c.de ?? "Cargo sin especificar"}</span>
                  <span className="text-slate-400"> → </span>
                  <span className="font-medium text-slate-800">{c.a ?? "Cargo sin especificar"}</span>
                </li>
              ))}
            </ol>
          )}
        </DetalleCaja>
      )}

      {metricaActiva === "cambios_unidad" && (
        <DetalleCaja titulo="Secuencia de cambios de unidad">
          {cambiosUnidad.length === 0 ? (
            <p className="text-xs text-slate-400">Sin cambios de unidad registrados.</p>
          ) : (
            <ol className="space-y-1.5">
              {cambiosUnidad.map((c, i) => (
                <li key={i} className="text-xs text-slate-600">
                  <span className="text-slate-400">{c.fecha ?? "?"}:</span>{" "}
                  <span className="text-slate-700">{c.de ?? "Unidad sin especificar"}</span>
                  <span className="text-slate-400"> → </span>
                  <span className="font-medium text-slate-800">{c.a ?? "Unidad sin especificar"}</span>
                </li>
              ))}
            </ol>
          )}
        </DetalleCaja>
      )}

      {metricaActiva === "unidades" && (
        <DetalleCaja titulo="Unidades donde ha trabajado">
          <ul className="space-y-1">
            {[...new Set(periodos.map((p) => p.unidad).filter((u): u is string => Boolean(u)))].map((u) => (
              <li key={u} className="text-xs text-slate-600">{u}</li>
            ))}
          </ul>
        </DetalleCaja>
      )}

      {evidencia.tiene_cargos_paralelos && (
        <p className="text-xs bg-amber-100 text-amber-800 rounded-md px-2.5 py-1.5 inline-block">
          ⚠ Esta persona ejerció 2 o más cargos en unidades distintas al mismo tiempo — haz clic en
          "Paralelo" en la tabla para ver con qué cargo.
        </p>
      )}

      {periodos.length > 0 && (
        <div>
          <p className="text-xs font-medium text-slate-500 mb-1.5">Períodos, cargos y unidades</p>
          <div className="overflow-auto rounded-md border border-slate-200">
            <table className="min-w-full text-xs">
              <thead className="bg-slate-50">
                <tr>
                  <th className="text-left px-2.5 py-1.5 font-medium text-slate-500">Cargo</th>
                  <th className="text-left px-2.5 py-1.5 font-medium text-slate-500">Unidad</th>
                  <th className="text-left px-2.5 py-1.5 font-medium text-slate-500">Período</th>
                  <th className="text-left px-2.5 py-1.5 font-medium text-slate-500">Duración</th>
                  <th className="text-left px-2.5 py-1.5 font-medium text-slate-500"></th>
                </tr>
              </thead>
              <tbody>
                {periodos.map((p, i) => (
                  <Fragment key={i}>
                    <tr className={`border-t border-slate-100 ${p.es_paralelo ? "bg-amber-50/50" : ""}`}>
                      <td className="px-2.5 py-1.5">{p.cargo ?? "-"}</td>
                      <td className="px-2.5 py-1.5">{p.unidad ?? "-"}</td>
                      <td className="px-2.5 py-1.5 whitespace-nowrap">
                        {p.inicio ?? "?"} — {p.vigente ? "actualidad" : p.fin ?? "?"}
                      </td>
                      <td className="px-2.5 py-1.5 whitespace-nowrap">
                        {p.duracion_anios != null ? `${p.duracion_anios.toFixed(1)} años` : "-"}
                        {!p.es_significativo && <span className="text-slate-400"> (corto)</span>}
                      </td>
                      <td className="px-2.5 py-1.5">
                        {p.es_paralelo && (
                          <button
                            onClick={() => setPeriodoParaleloActivo((actual) => (actual === i ? null : i))}
                            className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-200 text-amber-900 hover:bg-amber-300 transition-colors"
                          >
                            Paralelo {periodoParaleloActivo === i ? "▲" : "▼"}
                          </button>
                        )}
                      </td>
                    </tr>
                    {periodoParaleloActivo === i && p.paralelo_con.length > 0 && (
                      <tr className="bg-amber-50/70">
                        <td colSpan={5} className="px-2.5 py-2">
                          <p className="text-[11px] text-amber-800 mb-1">
                            Simultáneo con {p.paralelo_con.length === 1 ? "el siguiente cargo" : "los siguientes cargos"}:
                          </p>
                          <ul className="space-y-1">
                            {p.paralelo_con.map((par, k) => (
                              <li key={k} className="text-[11px] text-amber-900">
                                <span className="font-medium">{par.cargo ?? "Cargo sin especificar"}</span>
                                {par.unidad && <span> — {par.unidad}</span>}
                                <span className="text-amber-600"> ({par.inicio ?? "?"} — {par.fin ?? "actualidad"})</span>
                              </li>
                            ))}
                          </ul>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {evidencia.documento_texto && (
        <details className="rounded-md border border-slate-200 p-2.5">
          <summary className="cursor-pointer text-xs font-medium text-slate-600">
            Ver texto completo embebido (documento de trayectoria)
          </summary>
          <pre className="mt-2 text-xs text-slate-600 whitespace-pre-wrap font-sans">{evidencia.documento_texto}</pre>
        </details>
      )}
    </div>
  );
}

function DetalleCaja({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <div className="rounded-md border border-espol-blue/20 bg-espol-blue/5 p-3">
      <p className="text-xs font-medium text-espol-navy mb-2">{titulo}</p>
      {children}
    </div>
  );
}

function Metrica({
  label,
  valor,
  activa,
  onClick,
}: {
  label: string;
  valor: string;
  activa?: boolean;
  onClick?: () => void;
}) {
  const Componente = onClick ? "button" : "div";
  return (
    <Componente
      onClick={onClick}
      className={`text-left bg-white rounded-md border px-2.5 py-2 transition-colors ${
        onClick ? "cursor-pointer hover:border-espol-blue" : ""
      } ${activa ? "border-espol-blue ring-1 ring-espol-blue/30" : "border-slate-200"}`}
    >
      <p className="text-[10px] uppercase tracking-wide text-slate-400">{label}{onClick ? " ↕" : ""}</p>
      <p className="text-sm font-semibold text-slate-800">{valor}</p>
    </Componente>
  );
}

function fmtVal(v: unknown): string {
  if (v === null || v === undefined || v === "") return "-";
  return String(v);
}
