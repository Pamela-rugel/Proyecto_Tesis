import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
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
}: Props) {
  const [tabActiva, setTabActiva] = useState<string | null>(null);
  const { data, isLoading, error } = useQuery({
    queryKey: ["persona", idPersona],
    queryFn: () => getPersonaFicha(idPersona),
  });

  if (isLoading) return <LoadingBlock label="Cargando ficha de persona..." />;
  if (error || !data) return <ErrorBlock message="No se pudo cargar la ficha de esta persona." />;

  const { persona, tiene_perfil, motivo_sin_perfil, eventos_trayectoria, resumen_cargos_espol, secciones, radar,
    cluster_descripcion, corpus_muestra, n_textos, etiqueta_tipo_evento } = data;

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

      {n_textos > 0 && (mostrarEvidenciaTexto || coincidenciaSemantica) && (
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
      )}
    </div>
  );
}

function fmtVal(v: unknown): string {
  if (v === null || v === undefined || v === "") return "-";
  return String(v);
}
