import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { NOMBRE_AMBITO } from "../lib/texto";
import { getPersona, type Ambito, type NavegacionFicha, type OrigenFicha } from "../api/client";
import IntensidadDimensiones from "./IntensidadDimensiones";
import TimelineTrayectoria from "./TimelineTrayectoria";
import PerfilCompleto from "./PerfilCompleto";
import DesgloseEvidencias from "./DesgloseEvidencias";

interface Props {
  ambito: Ambito;
  personaId: number;
  /** desde dónde se abrió: decide la pestaña inicial (dimensión → Dimensiones; perfil → Perfil completo; otra → Trayectoria) */
  origen: OrigenFicha;
  /** dimensión que se despliega al abrir la pestaña Dimensiones */
  dimensionInicial?: string;
  /** volver a la vista anterior del panel */
  onVolver: () => void;
  textoVolver: string;
  /** enlaces hacia otras personas, patrones globales y dimensiones (los que falten no se enlazan) */
  nav?: NavegacionFicha;
}

type Pestana = "trayectoria" | "dimensiones" | "perfil" | "evidencias";

const PESTANAS: { id: Pestana; texto: string }[] = [
  { id: "trayectoria", texto: "Trayectoria" },
  { id: "dimensiones", texto: "Dimensiones" },
  { id: "perfil", texto: "Perfil completo" },
  { id: "evidencias", texto: "Evidencias" },
];

const INICIAL: Record<OrigenFicha, Pestana> = { dimension: "dimensiones", perfil: "perfil", otra: "trayectoria" };

// Ficha de la persona en cuatro pestañas. La pestaña inicial sale del contexto de origen; quien
// la usa le da una `key` por persona y origen, así que abrir otra persona vuelve a calcularla y,
// mientras se navega dentro de la misma ficha, la pestaña elegida se conserva.
export default function FichaPersona({ ambito, personaId, origen, dimensionInicial, onVolver, textoVolver, nav = {} }: Props) {
  const { data, isLoading, isError } = useQuery({ queryKey: ["persona", ambito, personaId], queryFn: () => getPersona(personaId, ambito) });
  const [pestana, setPestana] = useState<Pestana>(INICIAL[origen]);
  const [dimensionEvidencias, setDimensionEvidencias] = useState<string | null>(null);

  const volver = (
    <button onClick={onVolver} className="text-[10px] text-espol-blue hover:underline px-5 pt-2 block text-left">
      ← {textoVolver}
    </button>
  );
  if (isLoading) return <div>{volver}<p className="p-5 text-sm text-slate-500">Cargando ficha…</p></div>;
  if (isError || !data)
    return <div>{volver}<p className="p-5 text-sm text-red-600">La persona seleccionada no está en {NOMBRE_AMBITO[ambito]}.</p></div>;

  // cabecera y pestañas fijas; solo el contenido de la pestaña hace scroll (el panel que la contiene
  // tiene alto fijo)
  return (
    <section className="h-full flex flex-col">
      <div className="shrink-0">{volver}</div>
      <header className="shrink-0 px-5 pt-0.5 pb-1.5">
        <h3 className="text-sm font-semibold leading-tight text-espol-navy">{data.nombre}</h3>
        {/* cargo_actual y unidad_actual son listas " / " alineadas, ya ordenadas por jerarquía de
            contrato (nombramiento, contrato, servicios); todas se muestran con el mismo peso */}
        {(() => {
          const cargos = (data.estado.cargo_actual ?? "").split(" / ").filter(Boolean);
          const unidades = (data.estado.unidad_actual ?? "").split(" / ");
          if (!cargos.length) return <p className="text-[11px] text-slate-700">Sin cargo actual</p>;
          return (
            <ul className="mt-0.5 space-y-0">
              {cargos.map((c, i) => (
                <li key={i} className="text-[11px] leading-tight text-slate-800 font-medium">
                  {c}
                  {unidades[i] && <span className="text-slate-500 font-normal"> · {unidades[i]}</span>}
                </li>
              ))}
            </ul>
          );
        })()}
        <p className="text-[10px] text-slate-500">
          {data.estado.tipo_empleado ?? "tipo desconocido"} · {data.estado.vigente ? "vigente" : "no vigente"}
        </p>
      </header>

      <div role="tablist" aria-label="Secciones de la ficha" className="shrink-0 bg-white border-y px-3 flex gap-1">
        {PESTANAS.map((p) => (
          <button
            key={p.id}
            role="tab"
            aria-selected={pestana === p.id}
            onClick={() => {
              setPestana(p.id);
              if (p.id === "evidencias") setDimensionEvidencias(null);
            }}
            className={`px-2.5 py-2 text-xs whitespace-nowrap border-b-2 -mb-px ${
              pestana === p.id ? "border-espol-blue text-espol-navy font-semibold" : "border-transparent text-slate-600 hover:text-slate-900"
            }`}
          >
            {p.texto}
          </button>
        ))}
      </div>

      <div role="tabpanel" className="flex-1 min-h-0 overflow-y-auto px-5 py-4">
        {pestana === "trayectoria" && <TimelineTrayectoria personaId={data.persona_id} />}
        {pestana === "dimensiones" && (
          <IntensidadDimensiones
            ambito={ambito}
            dimensiones={data.dimensiones}
            dimensionInicial={dimensionInicial}
            nav={nav}
            onVerEvidencias={(d) => {
              setDimensionEvidencias(d);
              setPestana("evidencias");
            }}
          />
        )}
        {pestana === "perfil" && (
          <PerfilCompleto ambito={ambito} persona={data} nav={nav} />
        )}
        {pestana === "evidencias" && <DesgloseEvidencias personaId={data.persona_id} dimensionInicial={dimensionEvidencias} />}
      </div>
    </section>
  );
}
