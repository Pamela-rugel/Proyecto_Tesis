import { de, NOMBRE_AMBITO } from "../lib/texto";
import { colorPatron } from "../lib/colores";
import type { Ambito, NavegacionFicha, Persona, RasgoGrupo, TemaDistintivo } from "../api/client";
import Enlace from "./Enlace";
import { Bloque, Chip } from "./Bloques";

interface Props {
  ambito: Ambito;
  persona: Persona;
  nav: NavegacionFicha;
  /** ver el detalle de una dimensión en la pestaña Dimensiones de esta misma ficha */
  onVerDimension?: (dimension: string) => void;
}

// qué significa parecerse en cada vista de la red (tooltip de las pastillas)
const DESCRIPCION_VISTA: Record<string, string> = {
  actividad: "Su actividad en las 12 dimensiones tiene una forma parecida (cuánto hacen y cómo)",
  academico: "Sus publicaciones, proyectos, ponencias y tesis tratan temas parecidos",
  docencia: "Dictan materias de contenido parecido",
  formacion: "Sus títulos, capacitaciones y certificaciones son de áreas parecidas",
  trayectoria: "Han ocupado cargos parecidos (en ESPOL o fuera)",
};

// "Alto: a, b · Bajo: c · En Docencia: x · y" -> rasgos por separado. Los nombres de patrón llevan
// " · " por dentro ("sin posgrados · sin posgrado en curso"): esos trozos se unen al rasgo anterior.
const INICIO_RASGO = /^(Alto:|Bajo:|En |Patrón |Cerca |Como su |Sin diferencias)/;
const rasgos = (etiqueta: string) =>
  etiqueta.split(" · ").map((r) => r.trim()).filter(Boolean).reduce<string[]>((acc, r) => {
    if (acc.length && !INICIO_RASGO.test(r)) acc[acc.length - 1] += ` y ${r}`;
    else acc.push(r);
    return acc;
  }, []);

// Temas (de qué tratan las evidencias) mucho más frecuentes en el grupo que en su referencia, con
// un título que dice qué son y la dimensión en cada pastilla.
function Temas({ temas, nav }: { temas: TemaDistintivo[]; nav: NavegacionFicha }) {
  if (!temas.length) return null;
  return (
    <div className="mt-1.5">
      <p className="text-[11px] text-slate-500 mb-1"
        title="Temas descubiertos en el texto de las evidencias (títulos, materias, proyectos…) que aparecen mucho más en este grupo que en el total">
        <span className="text-espol-blue">◆</span> Temas frecuentes en el grupo (de qué tratan sus evidencias):
      </p>
      <div className="flex flex-wrap gap-1">
        {temas.map((t) => (
          <Chip key={`${t.dimension}-${t.tema}`} fuerte
            titulo={`Tema de ${t.nombre_dimension ?? t.dimension}: ${Math.round(t.proporcion * 100)} % del grupo tiene evidencias en este tema (${t.lift}× más que en el total)`}>
            <span className="text-slate-500">{t.nombre_dimension ?? t.dimension}:</span>
            <Enlace onClick={nav.dimension ? () => nav.dimension!(t.dimension, { tipo: "tema", id: t.tema }) : undefined}>
              {t.etiqueta.split(",").slice(0, 3).join(",")}
            </Enlace>
          </Chip>
        ))}
      </div>
    </div>
  );
}

const GRUPOS_RASGO: { tipo: RasgoGrupo["tipo"]; titulo: string; icono: string }[] = [
  { tipo: "alto", titulo: "Más que el promedio en", icono: "▲" },
  { tipo: "bajo", titulo: "Menos que el promedio en", icono: "▼" },
  { tipo: "patron", titulo: "Patrón típico en", icono: "●" },
];

// La etiqueta del perfil por piezas: cada dimensión es un enlace a su detalle en la pestaña
// Dimensiones de esta ficha. El título dice qué tiene el grupo frente a su referencia y qué tiene
// la persona en esa dimensión.
function RasgosGrupo({ rasgos, referencia, persona, onVerDimension, sinDiferencias = "Cerca del promedio en todo" }: {
  rasgos: RasgoGrupo[]; referencia: string; persona: Persona; onVerDimension?: (dimension: string) => void; sinDiferencias?: string;
}) {
  if (!rasgos.length) return <p className="text-[11px] text-slate-500">{sinDiferencias}.</p>;
  const suya = (dim: string) => persona.dimensiones.find((x) => x.dimension === dim);
  const titulo = (r: RasgoGrupo) => {
    const d = suya(r.dimension);
    const grupoTxt = r.tipo === "patron"
      ? `En ${r.nombre}, el ${Math.round((r.proporcion ?? 0) * 100)} % de quienes tienen evidencias sigue «${r.patron_nombre ?? `Patrón ${(r.patron ?? 0) + 1}`}» (en ${referencia}: ${Math.round((r.proporcion_referencia ?? 0) * 100)} %).`
      : `${r.nombre}: intensidad media ${Math.round(r.media)} de 100 en el grupo, frente a ${Math.round(r.media_referencia)} en ${referencia}.`;
    const suyoTxt = !d
      ? ""
      : d.estado !== "con_registros"
        ? " Esta persona no tiene registros en la dimensión."
        : ` Esta persona: ${d.nivel != null ? `nivel ${Math.round(d.nivel)}` : "con registros"}${d.patron ? ` · ${d.patron.nombre ?? `Patrón ${d.patron.patron + 1}`}` : ""}.`;
    return `${grupoTxt}${suyoTxt}${onVerDimension ? " Clic para ver su detalle en Dimensiones." : ""}`;
  };
  return (
    <div className="space-y-1">
      {GRUPOS_RASGO.map(({ tipo, titulo: t, icono }) => {
        const lista = rasgos.filter((r) => r.tipo === tipo);
        if (!lista.length) return null;
        return (
          <div key={tipo} className="flex flex-wrap items-center gap-1">
            <span className="text-[11px] text-slate-500 mr-0.5">
              <span className={tipo === "bajo" ? "text-slate-500" : "text-espol-blue"}>{icono}</span> {t}:
            </span>
            {lista.map((r) => {
              const contenido = (
                <>
                  {r.nombre}
                  {tipo === "patron" && r.patron_nombre && <span className="text-slate-500">: {r.patron_nombre}</span>}
                  {onVerDimension && <span aria-hidden className="text-slate-400">›</span>}
                </>
              );
              return onVerDimension ? (
                <button
                  key={`${tipo}-${r.dimension}`}
                  type="button"
                  title={titulo(r)}
                  onClick={() => onVerDimension(r.dimension)}
                  className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] max-w-full bg-slate-100 text-slate-700 hover:bg-blue-50 hover:text-espol-navy hover:ring-1 hover:ring-blue-200 text-left"
                >
                  {contenido}
                </button>
              ) : (
                <Chip key={`${tipo}-${r.dimension}`} titulo={titulo(r)}>{contenido}</Chip>
              );
            })}
          </div>
        );
      })}
    </div>
  );
}

// Pestaña "Perfil completo" (DEC-062): la persona en la red multivista que une cómo participa y de
// qué trata su evidencia (NEMO). Lo principal son las personas parecidas y en qué se parecen; el
// perfil amplio y su microarquetipo orientan (los datos son casi continuos, no grupos cerrados).
export default function PerfilCompleto({ ambito, persona, nav, onVerDimension }: Props) {
  const g = persona.patron_global;
  const grupo = NOMBRE_AMBITO[ambito];
  const irPersona = nav.persona ? (id: number) => nav.persona!(id, "perfil") : undefined;

  return (
    <div className="space-y-2.5 text-xs text-slate-700">
      <p className="text-[11px] text-slate-500"
        title="Red multivista (NEMO): cada par de personas se compara solo en las vistas que ambas tienen, así que la falta de datos no penaliza.">
        Une cómo participa en las 12 dimensiones y de qué tratan sus evidencias.
      </p>

      {g ? (
        <Bloque
          titulo="Perfil amplio"
          extra={g.estabilidad != null && (
            <span className="text-[10px] text-slate-400" title="Estabilidad del agrupamiento (ARI por submuestreo; 1 = siempre igual)">
              estabilidad {g.estabilidad.toFixed(2)}
            </span>
          )}
        >
          <div className="flex items-center gap-2 mb-1.5">
            {(g.k ?? 99) <= 6 && <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: colorPatron(g.patron) }} />}
            <Enlace className="font-medium" onClick={nav.patronGlobal ? () => nav.patronGlobal!(g.patron, null) : undefined}>
              Perfil {g.patron + 1}
            </Enlace>
            <span className="text-[11px] text-slate-400">· {g.tamano} personas {de(grupo)}</span>
          </div>
          {g.rasgos ? (
            <RasgosGrupo rasgos={g.rasgos} referencia={grupo} persona={persona} onVerDimension={onVerDimension} />
          ) : (
            <div className="flex flex-wrap gap-1">
              {rasgos(g.etiqueta).map((r) => (
                <Chip key={r}>{r}</Chip>
              ))}
            </div>
          )}
          <Temas temas={g.temas ?? []} nav={nav} />
          <p className="text-[11px] text-slate-500 mt-1.5">
            {g.es_representante ? (
              "Es la persona más representativa del perfil."
            ) : g.representante_nombre && g.representante_id !== null ? (
              <>
                Más representativa:{" "}
                <Enlace onClick={irPersona ? () => irPersona(g.representante_id!) : undefined}>{g.representante_nombre}</Enlace>
              </>
            ) : (
              "El perfil no tiene personas vigentes que lo representen."
            )}
          </p>
        </Bloque>
      ) : (
        <p className="text-slate-500">Esta versión de resultados no tiene perfil completo para la persona.</p>
      )}

      {g?.micro && (
        <Bloque
          titulo="Microarquetipo"
          extra={g.micro.estabilidad != null && (
            <span className={`text-[10px] ${g.micro.estable === false ? "text-amber-700" : "text-slate-400"}`}
              title="Estabilidad de la subdivisión del perfil (ARI por submuestreo). Por debajo de 0,90 es orientativa.">
              {g.micro.estable === false ? "orientativo · " : ""}estabilidad {g.micro.estabilidad.toFixed(2)}
            </span>
          )}
        >
          <div className="flex items-center gap-2 mb-1.5">
            <Enlace className="font-medium" onClick={nav.patronGlobal ? () => nav.patronGlobal!(g.patron, g.micro!.micro) : undefined}>
              {g.micro.codigo}
            </Enlace>
            <span className="text-[11px] text-slate-400">· {g.micro.tamano} personas del Perfil {g.patron + 1}</span>
          </div>
          <p className="text-[11px] text-slate-500 mb-1">Subgrupo dentro de su perfil amplio; se describe frente a él.</p>
          {g.micro.rasgos ? (
            <RasgosGrupo rasgos={g.micro.rasgos} referencia={`el Perfil ${g.patron + 1}`} persona={persona} onVerDimension={onVerDimension}
              sinDiferencias="Como su perfil amplio, sin diferencias marcadas" />
          ) : (
            <div className="flex flex-wrap gap-1">
              {rasgos(g.micro.etiqueta).map((r) => (
                <Chip key={r}>{r}</Chip>
              ))}
            </div>
          )}
          <Temas temas={g.micro.temas ?? []} nav={nav} />
          {!g.micro.es_representante && g.micro.representante_nombre && g.micro.representante_id !== null && (
            <p className="text-[11px] text-slate-500 mt-1.5">
              Más representativa:{" "}
              <Enlace onClick={irPersona ? () => irPersona(g.micro!.representante_id!) : undefined}>{g.micro.representante_nombre}</Enlace>
            </p>
          )}
          {g.micro.es_representante && <p className="text-[11px] text-slate-500 mt-1.5">Es la persona más representativa del microarquetipo.</p>}
        </Bloque>
      )}

      <Bloque titulo="Personas con perfil completo parecido">
        {persona.parecidos.length === 0 ? (
          <p className="text-slate-500">No hay personas vigentes entre sus vecinas más cercanas.</p>
        ) : (
          <ol className="space-y-1.5">
            {persona.parecidos.map((x, i) => (
              <li key={x.persona_id} className="leading-tight">
                <span className="flex items-baseline gap-1.5">
                  <span className="text-[10px] text-slate-400 tabular-nums w-4 text-right" title="Orden de cercanía entre las personas vigentes">{i + 1}</span>
                  <Enlace className="font-medium flex-1" onClick={irPersona ? () => irPersona(x.persona_id) : undefined}>{x.nombre}</Enlace>
                  {nav.comparar && (
                    <button
                      type="button"
                      onClick={() => nav.comparar!({ id: persona.persona_id, nombre: persona.nombre }, { id: x.persona_id, nombre: x.nombre })}
                      title="Comparar las dos personas vista por vista, con las evidencias que forman cada una"
                      className="shrink-0 rounded border border-slate-200 px-1.5 py-px text-[10px] text-espol-blue hover:bg-blue-50 hover:border-blue-200"
                    >
                      Comparar
                    </button>
                  )}
                </span>
                <span className="block ml-5 text-[11px] text-slate-500 leading-snug">{x.cargo_actual ?? "Sin cargo actual"}</span>
                {(x.vistas?.length ?? 0) > 0 && (
                  <span className="flex flex-wrap items-center gap-1 ml-5 mt-0.5">
                    <span className="text-[10px] text-slate-500">Se parecen en:</span>
                    {x.vistas!.map((v) => (
                      <Chip
                        key={v.vista}
                        titulo={
                          v.rango != null
                            ? `${DESCRIPCION_VISTA[v.vista]}. En esta vista es la ${v.rango}.ª persona vigente más parecida.`
                            : DESCRIPCION_VISTA[v.vista]
                        }
                      >
                        {v.nombre}
                        {v.rango != null && <span className="tabular-nums text-slate-500">N°{v.rango}</span>}
                      </Chip>
                    ))}
                  </span>
                )}
              </li>
            ))}
          </ol>
        )}
        <p className="text-[10px] text-slate-400 mt-1.5">
          En orden de cercanía. Clic en el nombre para ver su ficha, o en «Comparar» para ver vista por vista las evidencias de
          ambas. Pasa el cursor por cada pastilla para ver qué significa. No mide competencia ni idoneidad.
        </p>
      </Bloque>
    </div>
  );
}
