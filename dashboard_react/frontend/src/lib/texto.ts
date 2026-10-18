import type { Ambito } from "../api/client";

// Contracciones del español al anteponer "de" / "a" a un grupo dicho en palabras
// ("de el personal docente" -> "del personal docente").
export const de = (s: string) => (s.startsWith("el ") ? `del ${s.slice(3)}` : `de ${s}`);
export const a = (s: string) => (s.startsWith("el ") ? `al ${s.slice(3)}` : `a ${s}`);

// con quién se compara cada número, dicho en palabras (en vez de "ámbito")
export const NOMBRE_AMBITO: Record<Ambito, string> = {
  todos: "todo el personal",
  administrativos: "el personal administrativo",
  docentes: "el personal docente",
};
