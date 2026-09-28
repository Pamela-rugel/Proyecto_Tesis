# Evidencias de Formación académica

Fuente: `data/processed/reporte_titulaciones_educacion.csv` (notebook 18 de preprocesamiento).
Mismo esquema que Trayectoria: `evidencia_id | persona_id | tipo_id | texto | atributos`. El
formato de los atributos está en [../ATRIBUTOS.md](../ATRIBUTOS.md).

- **Ejecución:** `evidencias_formacion.ipynb`, o `python -m evidencias.formacion.construir`.
- **Salidas:** en `data/evidencias/formacion/`:
  - `evidencias_formacion.csv`
  - `reporte_evidencias_formacion.json`
  - `registros_no_considerados.csv`

## Reglas (decisiones del usuario, 2026-09-28)

| Regla | Detalle |
|---|---|
| Población | Solo personas con al menos una evidencia de trayectoria. Quien no tiene formación no recibe ninguna evidencia de esta sección |
| Subtipos | `FORMACION_TITULO`: título obtenido (`Graduado`, o `Estado` vacío, que se asume terminado). `FORMACION_EN_CURSO`: Cursando, Egresado, En proceso de Graduación, A Prueba |
| Nivel mostrado | Si la persona tiene tercer o cuarto nivel, solo esos. Si no, sus bachilleratos. Si tampoco, su primaria. Aplica a títulos obtenidos |
| Duplicados | Misma persona, título casi idéntico (similitud ≥ 0.95, sin tildes ni mayúsculas) y misma institución salvo errores de escritura (similitud ≥ 0.85) → una evidencia; gana el registro más completo. Instituciones distintas con siglas parecidas (ESPAE vs ESPOL, ESPOL vs ESPE) no se unen |
| En curso ya obtenido | Si el mismo título ya figura como obtenido, el registro en curso no se agrega |
| Sin nombre de título | No genera evidencia; queda en `registros_no_considerados.csv` (persona, motivo, estado, nivel, institución, id) para revisarlo después |
| Texto | `TÍTULO (estado), INSTITUCIÓN, País, CINE: …, Subárea CINE: …, Frascati: …, Subárea Frascati: …`. Se omite lo que no existe; el país solo va si es del exterior |
| Fechas | `fecha_inicio` siempre null (no existe en la fuente); `fecha_fin` es la fecha de graduación |
| Excluido | Datos personales (`NumeroIdentificacion`, `Nombres`, `Apellidos`, `CodEstudiante`) y columnas administrativas de archivo o validación |
