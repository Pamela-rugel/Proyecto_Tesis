import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import type { Ambito } from "../api/client";
import BuscadorPersonas from "../components/BuscadorPersonas";
import CompararPerfiles from "../components/CompararPerfiles";

const AMBITOS: { id: Ambito; nombre: string }[] = [
  { id: "todos", nombre: "Todo el personal" },
  { id: "administrativos", nombre: "Administrativos" },
  { id: "docentes", nombre: "Docentes" },
];

interface Elegida {
  id: number;
  nombre: string;
}
/** lo que llega al abrir la pestaña desde una ficha («Comparar» en las personas parecidas) */
export interface EntradaComparar {
  ambito: Ambito;
  a: Elegida;
  b: Elegida;
  desdeFicha?: boolean;
}

// Pestaña Comparar: dos personas lado a lado en las vistas del perfil completo. Se eligen con el
// buscador o llegan desde una ficha. Los identificadores no van en la URL (como en Perfiles).
export default function CompararPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const entrada = (location.state ?? null) as EntradaComparar | null;
  const [ambito, setAmbito] = useState<Ambito>(entrada?.ambito ?? "todos");
  const [a, setA] = useState<Elegida | null>(entrada?.a ?? null);
  const [b, setB] = useState<Elegida | null>(entrada?.b ?? null);

  const cambiarAmbito = (x: Ambito) => {
    setAmbito(x);
    setA(null);
    setB(null);
  };
  const abrirFicha = (id: number) => navigate("/", { state: { abrirFicha: id } });

  const casilla = (letra: "A" | "B", p: Elegida | null, set: (x: Elegida | null) => void) => (
    <div className="flex-1 min-w-[16rem]">
      <p className="text-[11px] text-slate-500 mb-1">Persona {letra}</p>
      {p ? (
        <div className="flex items-center gap-2 border rounded-md bg-white px-3 py-2">
          <span className="text-[10px] font-semibold text-white bg-espol-navy rounded w-5 h-5 grid place-items-center shrink-0">{letra}</span>
          <span className="text-sm text-slate-800 flex-1 truncate">{p.nombre}</span>
          <button onClick={() => set(null)} className="text-[11px] text-espol-blue hover:underline">cambiar</button>
        </div>
      ) : (
        <BuscadorPersonas ambito={ambito} onElegir={(r) => set({ id: r.persona_id, nombre: r.nombre })} />
      )}
    </div>
  );

  return (
    <div className="space-y-3">
      {entrada?.desdeFicha && (
        <button onClick={() => navigate("/")} className="text-xs text-espol-blue hover:underline">
          ← Volver a la ficha
        </button>
      )}
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-lg font-semibold text-espol-navy mr-2">Comparar perfiles</h2>
        <div className="inline-flex bg-white border rounded-lg p-1">
          {AMBITOS.map((x) => (
            <button
              key={x.id}
              onClick={() => cambiarAmbito(x.id)}
              className={`px-3 py-1.5 text-sm rounded-md ${ambito === x.id ? "bg-espol-navy text-white" : "text-slate-600 hover:bg-slate-50"}`}
            >
              {x.nombre}
            </button>
          ))}
        </div>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        {casilla("A", a, setA)}
        <button
          onClick={() => {
            setA(b);
            setB(a);
          }}
          disabled={!a && !b}
          className="mb-1 px-2 py-1.5 text-sm rounded-md border bg-white text-slate-600 hover:bg-slate-50 disabled:opacity-40"
          title="Intercambiar A y B (los puestos «N.º» se miden desde A)"
          aria-label="Intercambiar A y B"
        >
          ⇄
        </button>
        {casilla("B", b, setB)}
      </div>

      {a && b ? (
        a.id === b.id ? (
          <p className="text-sm text-slate-500 bg-white border rounded-lg p-5">Elige dos personas distintas.</p>
        ) : (
          <CompararPerfiles ambito={ambito} a={a.id} b={b.id} onPersona={abrirFicha} />
        )
      ) : (
        <div className="bg-white border rounded-lg p-6 text-sm text-slate-600 max-w-3xl">
          <p className="font-medium text-slate-800 mb-1">Elige dos personas para comparar sus perfiles.</p>
          <p>
            Búscalas arriba por nombre, cargo o unidad, o usa «Comparar» en las personas parecidas de una ficha. Se comparan en las cinco
            vistas del perfil completo: cómo participan en las 12 dimensiones y de qué tratan sus evidencias académicas, de docencia, de
            formación y de trayectoria, con las evidencias que forman cada vista.
          </p>
        </div>
      )}
    </div>
  );
}
