import { useParams, Link } from "react-router-dom";
import PersonaFicha from "../components/PersonaFicha";

export default function PersonaPage() {
  const { id } = useParams<{ id: string }>();
  const idPersona = Number(id);

  if (!id || Number.isNaN(idPersona)) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-5">
        <p className="text-sm text-red-600">Enlace inválido: falta el identificador de la persona.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <Link to="/resumen" className="text-sm text-espol-blue hover:text-espol-navy transition-colors">
        &larr; Ir al resumen general
      </Link>
      <div className="bg-white rounded-xl border border-slate-200 p-5">
        <PersonaFicha idPersona={idPersona} />
      </div>
    </div>
  );
}
