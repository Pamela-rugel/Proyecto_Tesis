/** Color determinístico (mismo texto -> siempre el mismo color) vía hash simple + HSL,
 * para paletas con demasiados valores distintos para una lista fija (ej. ~239 cargos
 * reales en el mapa de puntos, donde nunca se comparan dos colores "vecinos" de cerca).
 * Misma fórmula que `color_por_texto` en dashboard_react/backend/main.py - mantener ambas
 * en sync. */
export function colorPorTexto(texto: string): string {
  let hash = 0;
  for (let i = 0; i < texto.length; i++) {
    hash = (hash * 31 + texto.charCodeAt(i)) >>> 0;
  }
  const hue = hash % 360;
  return `hsl(${hue}, 45%, 55%)`;
}

/** Asigna un color a cada texto distinto de una lista, repartiendo los tonos (hue)
 * equiespaciados alrededor del círculo de color en vez de usar un hash independiente por
 * texto — garantiza una separación mínima entre colores que van a verse uno al lado del
 * otro (ej. los cargos de una misma persona en su línea de tiempo), donde un hash simple
 * podría asignar dos hues casi iguales a dos cargos distintos. Orden estable (orden de
 * primera aparición) para que el resultado no dependa de Set/Map iteration order. */
export function paletaPorTextos(textos: string[]): Map<string, string> {
  const distintos = Array.from(new Set(textos));
  const mapa = new Map<string, string>();
  distintos.forEach((texto, i) => {
    const hue = (i * (360 / distintos.length)) % 360;
    mapa.set(texto, `hsl(${hue}, 55%, 50%)`);
  });
  return mapa;
}
