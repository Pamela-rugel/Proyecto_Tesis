// Contracciones del español al anteponer "de" / "a" a un grupo dicho en palabras
// ("de el personal docente" -> "del personal docente").
export const de = (s: string) => (s.startsWith("el ") ? `del ${s.slice(3)}` : `de ${s}`);
export const a = (s: string) => (s.startsWith("el ") ? `al ${s.slice(3)}` : `a ${s}`);
