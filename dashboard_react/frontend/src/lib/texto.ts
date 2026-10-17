// Contracciones del español al anteponer "de" / "a" a un grupo dicho en palabras
// ("de el personal docente" -> "del personal docente").
export const de = (s: string) => (s.startsWith("el ") ? `del ${s.slice(3)}` : `de ${s}`);
export const a = (s: string) => (s.startsWith("el ") ? `al ${s.slice(3)}` : `a ${s}`);

/** "Se parece un 64 % a la persona más representativa" o "Es la persona más representativa". */
export function textoSimilitud(sim: number | null, esRep: boolean) {
  if (esRep) return "Es la persona más representativa";
  if (sim === null) return "Sin persona representativa vigente";
  return `${Math.round(sim * 100)} % parecida a la persona más representativa`;
}

const numero = (v: number, dec = 1) => v.toLocaleString("es", { maximumFractionDigits: dec });

/** Nivel de formación (1 bachiller … 4 doctorado) en palabras, para promedios de grupo. */
export const nivelFormacion = (v: number) =>
  v >= 3.5 ? "doctorado" : v >= 2.75 ? "maestría" : v >= 2.25 ? "posgrado" : v >= 1.75 ? "tercer nivel" : v >= 1.25 ? "técnico" : "bachiller";

/** Valor de un componente en sus unidades: "35 %", "2,7 (≈ maestría)", "1,2". */
export function formatoValor(v: number, formato: "porcentaje" | "nivel" | "numero", descripcion = "") {
  if (formato === "porcentaje") return `${Math.round(v * 100)} %`;
  if (formato === "nivel" && descripcion.includes("bachiller")) return `${numero(v)} (≈ ${nivelFormacion(v)})`;
  return numero(v);
}

export const TEXTO_COMPARACION = {
  mucho_mas: "mucho más que el promedio",
  mas: "más que el promedio",
  similar: "cerca del promedio",
  menos: "menos que el promedio",
  mucho_menos: "mucho menos que el promedio",
} as const;
