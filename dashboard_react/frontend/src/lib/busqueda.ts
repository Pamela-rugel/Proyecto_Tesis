// Sin acentos y en minúsculas, para que "tecnico"/"pamela" encuentren "TÉCNICO"/"Pamela" sin
// importar tildes ni mayúsculas.
export function normalizar(texto: string): string {
  return texto
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase();
}

// Coincidencia por PALABRAS, no por substring exacto del nombre completo: "pamela rugel" debe
// encontrar a "Pamela Nayeli Rugel Diaz" aunque "rugel" no sea contiguo a "pamela" en el
// nombre real (queda un segundo nombre en medio) — un simple `.includes(query)` de la cadena
// completa falla en ese caso real, obligando a escribir el nombre completo para encontrar a
// alguien. Cada palabra de la consulta debe aparecer como PREFIJO de alguna palabra del
// nombre (no necesariamente en el mismo orden), para que "rugel pamela" o "rugel diaz"
// también encuentren a la misma persona.
export function coincideNombre(nombreCompleto: string, consulta: string): boolean {
  const palabrasConsulta = normalizar(consulta).trim().split(/\s+/).filter(Boolean);
  if (palabrasConsulta.length === 0) return false;
  const palabrasNombre = normalizar(nombreCompleto).split(/\s+/).filter(Boolean);
  return palabrasConsulta.every((pq) => palabrasNombre.some((pn) => pn.startsWith(pq)));
}
