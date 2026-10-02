// Paleta categórica para los clusters (legible sobre fondo claro).
export const PALETA = [
  "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b",
  "#e377c2", "#17becf", "#bcbd22", "#7f7f7f", "#393b79", "#ad494a",
];

export const colorCluster = (c: number) => PALETA[c % PALETA.length];

// Subpatrones: paleta propia (en el mapa los demás patrones se muestran en gris).
export const PALETA_SUB = ["#0b7285", "#e8590c", "#5c940d", "#c2255c", "#5f3dc4", "#a61e4d", "#1864ab", "#946c00"];
export const colorSub = (s: number) => PALETA_SUB[s % PALETA_SUB.length];

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
