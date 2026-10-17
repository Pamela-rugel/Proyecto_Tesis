import { NavLink, Route, Routes } from "react-router-dom";
import PerfilesPage from "./pages/PerfilesPage";
import BusquedaPage from "./pages/BusquedaPage";
import CompararPage from "./pages/CompararPage";
import ValidacionPage from "./pages/ValidacionPage";

const pestana = ({ isActive }: { isActive: boolean }) =>
  `px-3 py-1.5 rounded-md text-sm ${isActive ? "bg-white/15 text-white" : "text-slate-300 hover:text-white"}`;

// Perfiles del personal por dimensión de evidencia (DEC-053/055): intensidad, patrones y temas descubiertos.
// Búsqueda (04_busqueda_semantica): personas a partir de una consulta en lenguaje natural.
// Comparar: 2–4 personas lado a lado en una dimensión, su patrón global o su microarquetipo.
// Validación: revisar los grupos (qué dicen, quién los representa, cuánto se le parecen); solo consulta.
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
              <NavLink to="/comparar" className={pestana}>Comparar</NavLink>
              <NavLink to="/validacion" className={pestana}>Validación</NavLink>
            </nav>
          </div>
        </div>
      </header>

      <main className="flex-1 max-w-[1600px] w-full mx-auto px-6 py-4">
        <Routes>
          <Route path="/busqueda" element={<BusquedaPage />} />
          <Route path="/comparar" element={<CompararPage />} />
          <Route path="/validacion" element={<ValidacionPage />} />
          <Route path="*" element={<PerfilesPage />} />
        </Routes>
      </main>

    </div>
  );
}
