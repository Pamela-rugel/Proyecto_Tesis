export const pct = (x: number | null | undefined, dec = 0) =>
  x === null || x === undefined ? "—" : `${(x * 100).toFixed(dec)} %`;

export const NOMBRE_TIPO: Record<string, string> = {
  TRAYECTORIA_CARGO_ESTRUCTURAL: "Cargos estructurales",
  TRAYECTORIA_CONTRATO_PUNTUAL: "Contratos puntuales",
  TRAYECTORIA_FUNCION_ADICIONAL: "Funciones adicionales",
  TRAYECTORIA_EXPERIENCIA_EXTERNA: "Experiencia externa",
  FORMACION_TITULO: "Títulos",
  FORMACION_EN_CURSO: "Formación en curso",
  PROYECTO_INVESTIGACION: "Proyectos de investigación",
  PROYECTO_VINCULACION: "Proyectos de vinculación",
  PUBLICACION: "Publicaciones",
  TESIS_DIRIGIDA: "Tesis dirigidas",
  PONENCIA: "Ponencias",
  CAPACITACION: "Capacitaciones",
  CERTIFICACION: "Certificaciones",
  IDIOMA: "Idiomas",
  MENCION_HONOR: "Menciones de honor",
  DOCENCIA_MATERIA: "Materias dictadas",
  ACTIVIDAD_CARGA: "Actividades de carga",
};

// Patrones de actividad (máx. 6 por dimensión): subconjunto de la paleta de referencia que pasa
// el validador en scatter (todos los pares: visión normal PASS, daltonismo en banda 6–8, legal con
// codificación secundaria: cada grupo lleva su rótulo P1…P6 en el mapa y en su tarjeta).
export const PALETA_PATRONES = ["#2a78d6", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7"];
export const colorPatron = (p: number) => PALETA_PATRONES[p % PALETA_PATRONES.length];
