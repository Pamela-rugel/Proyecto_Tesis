# Evidencias de Idiomas

Fuente: `data/processed/idiomas_personas.csv`, más columnas del raw `data/raw/idiomaspersonas.csv`
que la limpieza descartó (unidas por `IDIDIOMAPERSONA`). Mismo esquema que las demás secciones:
`evidencia_id | persona_id | tipo_id | texto | atributos`. El formato de los atributos está en
[../ATRIBUTOS.md](../ATRIBUTOS.md).

- **Ejecución:** `evidencias_idiomas.ipynb`, o `python -m evidencias.idiomas.construir`.
- **Salidas:** en `data/evidencias/idiomas/`:
  - `evidencias_idiomas.csv`
  - `reporte_evidencias_idiomas.json`
  - `registros_no_considerados.csv`

## Reglas (decisiones del usuario, 2026-09-29, DEC-038)

| Regla | Detalle |
|---|---|
| Población | Solo personas con al menos una evidencia de trayectoria |
| Agrupación | Una evidencia por persona + idioma. Si hay varios registros, cada tipo de nivel es una lista con todos los niveles declarados (de mayor a menor). No se guarda el detalle ni el conteo de registros |
| Lengua nativa | El español nativo no es evidencia. Otro idioma marcado como nativo sí, con `es_lengua_nativa = true`. Si algún registro de español de la persona dice nativo, ninguno es evidencia |
| Idioma "OTRO" | El nombre sale de `DESCRIPCION` (solo en el raw). Se unifican variantes de escritura (Catalán/CATALAN) y los sinónimos holandés/neerlandés/Nederland. Sin descripción no es evidencia |
| Texto | `IDIOMA, Conversación: …, Lectura: …, Escritura: …, MCER: …`, con el mayor nivel declarado de cada uno y solo con lo que existe |
| Nivel "Ninguna" | Nunca se escribe en el texto (queda en atributos). Si las tres habilidades son "Ninguna" y no hay MCER, no es evidencia |
| Comprensión | No va al texto: desde 2021 el sistema la llena siempre con "B" (básico), incluso con todo lo demás en avanzado. Se guarda en atributos tal cual |
| Fechas | Ninguna. La fuente no dice desde cuándo se sabe el idioma, y la fecha de modificación del registro no describe a la persona |

Niveles de la fuente (`catalogo_idiomas.csv`): A = avanzado, I = intermedio, B = básico,
N = ninguna. MCER (A1–C2) es el Marco Común Europeo de Referencia, presente solo en algunos
registros y no siempre coherente con el nivel autodeclarado.

## Pendiente
- 40 evidencias de español sin dato de lengua nativa y 35 marcadas como no nativas se conservan.
  No está confirmado si son hablantes nativos.
