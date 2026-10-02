# Evidencias de Reconocimientos (menciones de honor)

Fuente: `data/processed/mencion_honor.csv`. El nombre del país sale de
`data/raw/experenciaexterna.csv` (la fuente solo trae `IDPAIS`). Mismo esquema que las demás
secciones: `evidencia_id | persona_id | tipo_id | texto | atributos`. El formato de los
atributos está en [../ATRIBUTOS.md](../ATRIBUTOS.md).

- **Ejecución:** `evidencias_reconocimientos.ipynb`, o `python -m evidencias.reconocimientos.construir`.
- **Salidas:** en `data/evidencias/menciones_honor/`:
  - `evidencias_menciones_honor.csv`
  - `reporte_evidencias_menciones_honor.json`
  - `registros_no_considerados.csv`

## Reglas (decisiones del usuario, 2026-09-29, DEC-039)

| Regla | Detalle |
|---|---|
| Población | Solo personas con al menos una evidencia de trayectoria |
| Un solo tipo | `MENCION_HONOR` para todo: mérito docente, becas, años de servicio, cum laude, best paper, revisor, membresías… El nombre ya dice qué es; no se clasifica por reglas |
| Agrupación | Una evidencia por persona + nombre casi idéntico (similitud ≥ 0.95, sin tildes ni mayúsculas; misma regla que capacitación). `n_veces` cuenta cuántas veces la recibió y `fechas` lista cada fecha en que la recibió. No hay `fecha_inicio`/`fecha_fin`: una mención es un hecho puntual, no un periodo |
| Números en el nombre | Un número sustantivo impide agrupar: "25 AÑOS" y "30 AÑOS", "NIVEL I" y "NIVEL II" son evidencias distintas. Un número de edición u ocurrencia no: un año ("2006", "2005-2006", "2009-2") o un número junto a "EDICIÓN" o al nombre de un evento ("XV EDICIÓN", "IV CONCURSO", "CONGRESO IV"). Esas ediciones se conservan en `ediciones`. Ante la duda, un número es sustantivo ("IEEEXTREME 10.0" y "11.0" quedan separados) |
| Tipo | `TIPO` de la fuente: M = mención, P = premio (confirmado por el usuario). Vacío en el 74 % de los registros, casi todos anteriores a 2020 |
| Texto | `NOMBRE, Tipo: …, Otorgado por: …, País: …`, solo con lo que existe. La institución sin "ESPOL" (se omite si solo era ESPOL) y omitida si ya está en el nombre; el país solo si es del exterior |
| Nombres genéricos | "DIPLOMA DE HONOR", "RECONOCIMIENTO", "MENCIÓN DE HONOR"… sí son evidencia: la institución les da contexto |
| Nombre de persona | 21 registros de 2 personas tienen un nombre de persona como nombre de la mención. No son evidencia; se identifican por `IDMENCIONHONOR` (lista cerrada) y el nombre no se copia a ninguna salida |
| Sin tema | "N.A." no es evidencia |
| Fechas imposibles | 4 registros traen años como 0024 o 0199: se conservan, sin esa fecha en `fechas` |

## Pendiente
- `es.quitar_espol` no quita "ESPOL" cuando va pegado con guion bajo ("ESPOL_FIEC").
- La misma regla de números no se aplica todavía a capacitación, ponencias ni publicaciones.
