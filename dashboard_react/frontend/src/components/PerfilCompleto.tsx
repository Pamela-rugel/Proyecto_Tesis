import { de, NOMBRE_AMBITO } from "../lib/texto";
import { colorPatron } from "../lib/colores";
import type { Ambito, NavegacionFicha, Persona, TemaDistintivo } from "../api/client";
import Enlace from "./Enlace";
import { Bloque, Chip } from "./Bloques";

interface Props {
  ambito: Ambito;
  persona: Persona;
  nav: NavegacionFicha;
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

function Temas({ temas, nav }: { temas: TemaDistintivo[]; nav: NavegacionFicha }) {
  if (!temas.length) return null;
  return (
    <div className="flex flex-wrap gap-1 mt-1.5">
      {temas.map((t) => (
        <Chip key={`${t.dimension}-${t.tema}`} fuerte
          titulo={`${t.nombre_dimension ?? t.dimension}: ${Math.round(t.proporcion * 100)} % del grupo tiene evidencias en este tema (${t.lift}× más que en el total)`}>
          <span className="text-slate-500">{t.nombre_dimension ?? t.dimension}:</span>
          <Enlace onClick={nav.dimension ? () => nav.dimension!(t.dimension, { tipo: "tema", id: t.tema }) : undefined}>
            {t.etiqueta.split(",").slice(0, 3).join(",")}
          </Enlace>
        </Chip>
      ))}
    </div>
  );
}

// Pestaña "Perfil completo" (DEC-062): la persona en la red multivista que une cómo participa y de
// qué trata su evidencia (NEMO). Lo principal son las personas parecidas y en qué se parecen; el
// perfil amplio y su microarquetipo orientan (los datos son casi continuos, no grupos cerrados).
export default function PerfilCompleto({ ambito, persona, nav }: Props) {
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
          <div className="flex flex-wrap gap-1">
            {rasgos(g.etiqueta).map((r) => (
              <Chip key={r}>{r}</Chip>
            ))}
          </div>
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
          <div className="flex flex-wrap gap-1">
            {rasgos(g.micro.etiqueta).map((r) => (
              <Chip key={r}>{r}</Chip>
            ))}
          </div>
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
                  <Enlace className="font-medium" onClick={irPersona ? () => irPersona(x.persona_id) : undefined}>{x.nombre}</Enlace>
                </span>
                <span className="block ml-5 text-[11px] text-slate-500 leading-snug">{x.cargo_actual ?? "Sin cargo actual"}</span>
                {(x.vistas?.length ?? 0) > 0 && (
                  <span className="flex flex-wrap items-center gap-1 ml-5 mt-0.5">
                    <span className="text-[10px] text-slate-500">Se parecen en:</span>
                    {x.vistas!.map((v) => (
                      <Chip key={v.vista} titulo={DESCRIPCION_VISTA[v.vista]}>{v.nombre}</Chip>
                    ))}
                  </span>
                )}
              </li>
            ))}
          </ol>
        )}
        <p className="text-[10px] text-slate-400 mt-1.5">En orden de cercanía. Pasa el cursor por cada pastilla para ver qué significa. No mide competencia ni idoneidad.</p>
      </Bloque>
    </div>
  );
}
