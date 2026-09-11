import { NavLink, Route, Routes, Navigate } from "react-router-dom";
import ResumenPage from "./pages/ResumenPage";
import MapaPage from "./pages/MapaPage";
import BuscarPage from "./pages/BuscarPage";
import EquiposPage from "./pages/EquiposPage";
import SemanticaPage from "./pages/SemanticaPage";

const TABS = [
  { to: "/resumen", label: "Resumen general y perfiles" },
  { to: "/mapa", label: "Mapa de perfiles" },
  { to: "/buscar", label: "Buscar persona" },
  { to: "/equipos", label: "Formar equipos / comisiones" },
  { to: "/semantica", label: "Búsqueda semántica" },
];

export default function App() {
  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-espol-navy text-white border-b border-black/10">
        <div className="max-w-7xl mx-auto px-6 pt-7 pb-4">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-md bg-espol-accent/90 flex items-center justify-center font-bold text-sm tracking-tight">
              EP
            </div>
            <div>
              <h1 className="text-xl font-semibold tracking-tight">Perfiles de Personal ESPOL</h1>
              <p className="text-xs text-slate-300">Sistema de apoyo a la decisión — talento humano</p>
            </div>
          </div>
          <p className="text-sm text-slate-300 mt-3 max-w-3xl leading-relaxed">
            Asignación de tareas, conformación de comisiones y equipos, planificación académica y
            administrativa. El mapa de puntos permite explorar afinidad de trayectoria por cercanía,
            sin forzar categorías nuevas.
          </p>
        </div>
        <nav className="max-w-7xl mx-auto px-6 flex gap-1 overflow-x-auto">
          {TABS.map((tab) => (
            <NavLink
              key={tab.to}
              to={tab.to}
              className={({ isActive }) =>
                `whitespace-nowrap px-4 py-2.5 text-sm font-medium rounded-t-md border-b-2 transition-colors ${
                  isActive
                    ? "bg-slate-50 text-espol-navy border-espol-accent"
                    : "text-slate-300 border-transparent hover:text-white hover:bg-white/5"
                }`
              }
            >
              {tab.label}
            </NavLink>
          ))}
        </nav>
      </header>

      <main className="flex-1 max-w-7xl w-full mx-auto px-6 py-6">
        <Routes>
          <Route path="/" element={<Navigate to="/resumen" replace />} />
          <Route path="/resumen" element={<ResumenPage />} />
          <Route path="/mapa" element={<MapaPage />} />
          <Route path="/buscar" element={<BuscarPage />} />
          <Route path="/equipos" element={<EquiposPage />} />
          <Route path="/semantica" element={<SemanticaPage />} />
        </Routes>
      </main>

      <footer className="text-center text-xs text-slate-400 py-4 border-t border-slate-200">
        Herramienta de apoyo a la decisión — no reemplaza el criterio institucional. Los perfiles
        son una síntesis analítica, no una categoría oficial de ESPOL.
      </footer>
    </div>
  );
}
