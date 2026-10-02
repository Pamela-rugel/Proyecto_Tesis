import { NavLink, Route, Routes } from "react-router-dom";
import PerfilesPage from "./pages/PerfilesPage";
import BusquedaPage from "./pages/BusquedaPage";

const pestana = ({ isActive }: { isActive: boolean }) =>
  `px-3 py-1.5 rounded-md text-sm ${isActive ? "bg-white/15 text-white" : "text-slate-300 hover:text-white"}`;

// Perfiles del personal (DEC-045/046): grupos con clustering multivista (SNF).
// Búsqueda (04_busqueda_semantica): personas a partir de una consulta en lenguaje natural.
export default function App() {
  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-espol-navy text-white border-b border-black/10">
        <div className="max-w-[1600px] mx-auto px-6 py-3">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-md bg-espol-accent/90 flex items-center justify-center font-bold text-sm tracking-tight">
              EP
            </div>
            <div>
              <h1 className="text-xl font-semibold tracking-tight">Perfiles de Personal ESPOL</h1>
              <p className="text-xs text-slate-300">Sistema de apoyo a la decisión — talento humano</p>
            </div>
            <nav className="ml-8 flex gap-1">
              <NavLink to="/" end className={pestana}>Perfiles</NavLink>
              <NavLink to="/busqueda" className={pestana}>Búsqueda</NavLink>
            </nav>
          </div>
        </div>
      </header>

      <main className="flex-1 max-w-[1600px] w-full mx-auto px-6 py-4">
        <Routes>
          <Route path="/busqueda" element={<BusquedaPage />} />
          <Route path="*" element={<PerfilesPage />} />
        </Routes>
      </main>

      <footer className="text-center text-xs text-slate-400 py-4 border-t border-slate-200">
        Herramienta de apoyo a la decisión — no reemplaza el criterio institucional.
      </footer>
    </div>
  );
}
