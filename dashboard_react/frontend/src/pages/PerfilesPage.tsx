import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { NOMBRE_AMBITO } from "../lib/texto";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  getAmbitos, getDimension, getDimensiones, getMapaDimension, getMapaPerfil, getPatronesGlobales, getPersonasDimension,
  type Ambito, type FiltroDimension, type NavegacionFicha, type OrigenFicha, type Patron,
  type Tema, type TipoMapa,
} from "../api/client";
import MapaPerfil, { type ColorPerfil } from "../components/MapaPerfil";
import PanelPatronGlobal, { type PestanaPerfil } from "../components/PanelPatronGlobal";
import FichaPersona from "../components/FichaPersona";
import MapaDimension from "../components/MapaDimension";
import BuscadorPersonas from "../components/BuscadorPersonas";
import Paginacion from "../components/Paginacion";
import { guardarPorPagina, porPaginaGuardado } from "../lib/paginacion";
import { colorPatron } from "../lib/colores";

const AMBITOS: { id: Ambito; nombre: string }[] = [
  { id: "todos", nombre: "Todo el personal" },
  { id: "administrativos", nombre: "Administrativos" },
  { id: "docentes", nombre: "Docentes" },
];

type Filtro = FiltroDimension;

// Perfiles por dimensión de evidencia (DEC-053/055): dimensiones a la izquierda; al centro, los
// patrones de actividad y los temas descubiertos en la dimensión; a la derecha, las personas del
// patrón o tema elegido (o la ficha de una persona).
export default function PerfilesPage() {
  const [inicial] = useState(() => new URLSearchParams(window.location.search));
  const [ambito, setAmbito] = useState<Ambito>(
    AMBITOS.some((a) => a.id === inicial.get("ambito")) ? (inicial.get("ambito") as Ambito) : "todos",
  );
  const [dimension, setDimension] = useState<string>(inicial.get("dimension") ?? "investigacion");
  // ?patron=n / ?tema=n (enlaces desde la ficha en Búsqueda): filtro inicial de la dimensión
  const [filtro, setFiltro] = useState<Filtro>(() => {
    const patron = inicial.get("patron") !== null && !isNaN(Number(inicial.get("patron"))) ? Number(inicial.get("patron")) : null;
    const tema = inicial.get("tema") !== null && !isNaN(Number(inicial.get("tema"))) ? Number(inicial.get("tema")) : null;
    return patron !== null ? { tipo: "patron", id: patron } : tema !== null ? { tipo: "tema", id: tema } : null;
  });
  // ficha abierta y su contexto de origen (decide la pestaña inicial; ver FichaPersona)
  const [ficha, setFicha] = useState<{ id: number; origen: OrigenFicha; dimension?: string } | null>(null);
  const [soloVigentes, setSoloVigentes] = useState(true);
  const [tipoMapa, setTipoMapa] = useState<TipoMapa>(inicial.get("tema") !== null ? "temas" : "patrones");
  const [vista, setVistaEstado] = useState<"dimension" | "perfil">(inicial.get("vista") === "perfil" ? "perfil" : "dimension");
  const persona = ficha?.id ?? null;
  // abrir una ficha desde esta página: el contexto es la vista activa (en la vista por dimensión,
  // con la dimensión elegida desplegada)
  // la lista y la ficha comparten el panel derecho: al abrir una ficha desde la lista se guarda su
  // scroll y al volver ("← Volver" o Esc) se restaura, para seguir donde estaba esa persona
  const panelDerecho = useRef<HTMLElement | null>(null);
  const scrollLista = useRef(0);
  const restaurarScroll = useRef(false);
  const setPersona = (id: number | null) => {
    if (id !== null && ficha === null) scrollLista.current = panelDerecho.current?.scrollTop ?? 0;
    setFicha(id === null ? null : { id, origen: vista, dimension: vista === "dimension" ? dimension : undefined });
  };
  const volverDeFicha = () => {
    restaurarScroll.current = true;
    setFicha(null);
  };
  useLayoutEffect(() => {
    if (ficha === null && restaurarScroll.current && panelDerecho.current) {
      panelDerecho.current.scrollTop = scrollLista.current;
      restaurarScroll.current = false;
    }
  }, [ficha]);
  // cambiar de vista cierra la ficha: al volver a abrirla, el nuevo contexto decide la pestaña
  const setVista = (v: "dimension" | "perfil") => {
    if (v !== vista) setFicha(null);
    setVistaEstado(v);
  };
  const [colorPerfil, setColorPerfil] = useState<ColorPerfil>("global");
  const [globalSel, setGlobalSel] = useState<number | null>(
    inicial.get("global") !== null && !isNaN(Number(inicial.get("global"))) ? Number(inicial.get("global")) : null,
  );
  // pestaña del panel del perfil amplio: se conserva al abrir y cerrar fichas
  const [pestanaPerfil, setPestanaPerfil] = useState<PestanaPerfil>("micro");
  const [microSel, setMicroSel] = useState<number | null>(inicial.get("micro") !== null && !isNaN(Number(inicial.get("micro"))) ? Number(inicial.get("micro")) : null);
  const [dimColor, setDimColor] = useState<string | null>("investigacion");

  const calcularAlto = () => Math.max(560, window.innerHeight - 150);
  const [alto, setAlto] = useState(calcularAlto);
  useEffect(() => {
    const f = () => setAlto(calcularAlto());
    window.addEventListener("resize", f);
    return () => window.removeEventListener("resize", f);
  }, []);

  // enlace compartible sin identificadores de personas
  useEffect(() => {
    const url = new URL(window.location.href);
    url.searchParams.set("ambito", ambito);
    url.searchParams.set("dimension", dimension);
    url.searchParams.set("vista", vista);
    if (globalSel !== null) url.searchParams.set("global", String(globalSel));
    else url.searchParams.delete("global");
    if (globalSel !== null && microSel !== null) url.searchParams.set("micro", String(microSel));
    else url.searchParams.delete("micro");
    url.searchParams.delete("patron");
    url.searchParams.delete("tema");
    window.history.replaceState(null, "", url);
  }, [ambito, dimension, vista, globalSel, microSel]);

  // Esc vuelve un paso atrás
  useEffect(() => {
    const f = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      if (persona !== null) volverDeFicha();
      else setFiltro(null);
    };
    window.addEventListener("keydown", f);
    return () => window.removeEventListener("keydown", f);
  });

  const ambitos = useQuery({ queryKey: ["ambitos"], queryFn: getAmbitos });
  const dimensiones = useQuery({ queryKey: ["dimensiones", ambito], queryFn: () => getDimensiones(ambito) });
  const detalle = useQuery({ queryKey: ["dimension", ambito, dimension], queryFn: () => getDimension(ambito, dimension) });
  const mapa = useQuery({
    queryKey: ["mapa-dimension", ambito, dimension, tipoMapa, soloVigentes],
    queryFn: () => getMapaDimension(ambito, dimension, tipoMapa, soloVigentes),
  });
  const mapaPerfil = useQuery({
    queryKey: ["mapa-perfil", ambito, dimColor, soloVigentes],
    queryFn: () => getMapaPerfil(ambito, dimColor, soloVigentes),
    enabled: vista === "perfil",
  });
  const globales = useQuery({
    queryKey: ["patrones-globales", ambito],
    queryFn: () => getPatronesGlobales(ambito),
    enabled: vista === "perfil",
  });
  const globalesConColor = (globales.data?.patrones?.length ?? 0) <= 6;
  // página de la lista de personas: vuelve a la primera al cambiar ámbito, dimensión, filtro o vigencia
  const [porPagina, setPorPagina] = useState(porPaginaGuardado);
  const claveLista = JSON.stringify([ambito, dimension, filtro, soloVigentes, porPagina]);
  const [paginaLista, setPaginaLista] = useState({ clave: claveLista, n: 0 });
  const pagina = paginaLista.clave === claveLista ? paginaLista.n : 0;
  const cambiarPagina = (n: number) => {
    setPaginaLista({ clave: claveLista, n });
    if (panelDerecho.current) panelDerecho.current.scrollTop = 0;
  };
  const personas = useQuery({
    queryKey: ["personas-dimension", ambito, dimension, filtro, soloVigentes, pagina, porPagina],
    queryFn: () =>
      getPersonasDimension(ambito, dimension, filtro ? { [filtro.tipo]: filtro.id } : {}, soloVigentes, pagina, porPagina),
    placeholderData: keepPreviousData,
  });

  // el selector "Por patrones / Por temas" decide el mapa y la sección de abajo; si la dimensión
  // elegida no tiene lo seleccionado (p. ej. Idiomas no tiene temas), se cambia a lo que sí tiene
  useEffect(() => {
    const info = detalle.data;
    if (!info) return;
    if (tipoMapa === "temas" && !info.temas && info.patrones) setTipoMapa("patrones");
    if (tipoMapa === "patrones" && !info.patrones && info.temas) setTipoMapa("temas");
  }, [detalle.data, tipoMapa]);

  const elegirGlobal = (g: number) => {
    setGlobalSel(globalSel === g ? null : g);
    setMicroSel(null);
    setPestanaPerfil("micro");
    setColorPerfil("global");
    setPersona(null);
  };
  const cambiarAmbito = (a: Ambito) => {
    setAmbito(a);
    setGlobalSel(null);
    setMicroSel(null);
    setFiltro(null);
    setPersona(null);
  };
  const elegirDimension = (d: string) => {
    setDimension(d);
    setFiltro(null);
    setPersona(null);
  };
  const elegirFiltro = (f: Filtro) => {
    setFiltro(f && filtro && f.tipo === filtro.tipo && f.id === filtro.id ? null : f);
    if (f) setTipoMapa(f.tipo === "patron" ? "patrones" : "temas");
    setPersona(null);
  };
  // enlaces de la ficha: otra persona (con el contexto del clic), un patrón global o una dimensión
  const irPatronGlobal = (g: number, m: number | null) => {
    setVista("perfil");
    setFicha(null);
    setGlobalSel(g);
    setMicroSel(m);
    setColorPerfil("global");
    setPestanaPerfil(m !== null ? "distingue" : "micro");
  };
  const irDimension = (dim: string, f: Filtro) => {
    setVista("dimension");
    setFicha(null);
    setDimension(dim);
    setFiltro(f);
    if (f) setTipoMapa(f.tipo === "patron" ? "patrones" : "temas");
  };
  const nav: NavegacionFicha = {
    persona: (id, origen, dim) => setFicha({ id, origen, dimension: dim }),
    patronGlobal: irPatronGlobal,
    dimension: irDimension,
  };

  if (ambitos.isError) {
    return (
      <p className="text-sm text-red-600">
        No hay resultados o la API no responde. Correr <code>python -m perfiles.construir</code>.
      </p>
    );
  }
  const d = detalle.data;
  const resumenDim = dimensiones.data?.find((x) => x.dimension === dimension);
  const nombreDimColor = dimensiones.data?.find((x) => x.dimension === dimColor)?.nombre ?? "";
  const tituloFiltro =
    filtro?.tipo === "patron" ? `Patrón ${filtro.id + 1}` : filtro?.tipo === "tema" ? `Tema ${filtro.id + 1}` : null;

  return (
    <div className="space-y-3">
      {/* mismas columnas que los paneles de abajo: ámbito y vista sobre las dos primeras, buscador sobre la última */}
      <div className="grid lg:grid-cols-[17rem_minmax(0,1fr)_27rem] gap-4 items-center">
        <div className="lg:col-span-2 flex flex-wrap items-center justify-between gap-3">
          <div className="inline-flex bg-white border rounded-lg p-1">
            {AMBITOS.map((a) => {
              const info = ambitos.data?.ambitos.find((x) => x.ambito === a.id);
              return (
                <button
                  key={a.id}
                  onClick={() => cambiarAmbito(a.id)}
                  className={`px-3 py-1.5 text-sm rounded-md ${ambito === a.id ? "bg-espol-navy text-white" : "text-slate-600 hover:bg-slate-50"}`}
                >
                  {a.nombre}
                  {info && <span className="ml-1.5 text-xs opacity-70">{info.n_vigentes}</span>}
                </button>
              );
            })}
          </div>
          <div className="inline-flex bg-white border rounded-lg p-1" role="group" aria-label="Vista">
            {([["dimension", "Por dimensión"], ["perfil", "Perfil completo"]] as const).map(([v, t]) => (
              <button
                key={v}
                onClick={() => setVista(v)}
                aria-pressed={vista === v}
                className={`px-3 py-1.5 text-sm rounded-md ${vista === v ? "bg-espol-navy text-white" : "text-slate-600 hover:bg-slate-50"}`}
              >
                {t}
              </button>
            ))}
          </div>
        </div>
        <BuscadorPersonas ambito={ambito} onElegir={(r) => setPersona(r.persona_id)} />
      </div>

      {ambitos.data && !ambitos.data.estado.actualizado && (
        <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-2">
          Las evidencias cambiaron después de este cálculo (versión {ambitos.data.version}); conviene recalcularlo.
        </p>
      )}

      {vista === "perfil" && (
        <div className="grid lg:grid-cols-[17rem_minmax(0,1fr)_27rem] gap-4 items-start">
          <nav className="bg-white border rounded-lg overflow-y-auto p-2" style={{ height: alto }} aria-label="Perfiles amplios">
            <p className="text-[11px] uppercase tracking-wide text-slate-500 px-2 pt-1">Perfiles amplios</p>
            <p className="text-[11px] text-slate-500 px-2 pb-2"
              title="Agrupamiento de la red que une actividad y temas (NEMO). Debajo de cada perfil, sus microarquetipos (G1.1, G1.2…). Los datos son casi continuos: orientan, no son grupos cerrados.">
              Actividad y temas juntos{globales.data?.estabilidad_ari ? ` · estabilidad ${globales.data.estabilidad_ari.toFixed(2)}` : ""}. Número: personas{soloVigentes ? " vigentes" : ""}.
            </p>
            {globales.data?.patrones?.map((g) => (
            <div key={g.id}>
              <button
                onClick={() => elegirGlobal(g.id)}
                aria-pressed={globalSel === g.id}
                className={`w-full text-left rounded-md px-2 py-2 mb-0.5 ${globalSel === g.id ? "bg-slate-100" : "hover:bg-slate-50"}`}
              >
                <span className="flex items-center gap-2">
                  {globalesConColor && <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: colorPatron(g.id) }} />}
                  <span className={`text-sm flex-1 ${globalSel === g.id ? "font-semibold text-espol-navy" : "text-slate-800"}`}>
                    Perfil {g.id + 1}
                  </span>
                  <span className="text-[11px] text-slate-500 tabular-nums" title={soloVigentes ? "personas vigentes" : "personas"}>
                    {soloVigentes ? g.tamano_vigentes : g.tamano}
                  </span>
                </span>
                <span className="block text-[11px] text-slate-500 mt-0.5">{g.etiqueta}</span>
              </button>
              {(g.microarquetipos?.lista.length ?? 0) > 0 && (
                <ul className="ml-4 mb-2 border-l pl-2" aria-label={`Microarquetipos del Perfil ${g.id + 1}`}
                  title={g.microarquetipos!.estable === false ? `Subdivisión orientativa: estabilidad ${g.microarquetipos!.estabilidad_ari.toFixed(2)} (< 0,90)` : undefined}>
                  {g.microarquetipos!.lista.map((m) => {
                    const activo = globalSel === g.id && microSel === m.id;
                    return (
                      <li key={m.id}>
                        <button
                          onClick={() => {
                            if (globalSel !== g.id) setGlobalSel(g.id);
                            setMicroSel(activo ? null : m.id);
                            setColorPerfil("global");
                            setPersona(null);
                          }}
                          aria-pressed={activo}
                          title={m.etiqueta}
                          className={`w-full text-left rounded px-1.5 py-1 flex items-center gap-1.5 ${activo ? "bg-slate-100" : "hover:bg-slate-50"}`}
                        >
                          {globalSel === g.id && <span className="w-2 h-2 rounded-full shrink-0" style={{ background: colorPatron(m.id) }} />}
                          <span className={`text-xs ${activo ? "font-semibold text-espol-navy" : "text-slate-700"}`}>{m.codigo}</span>
                          <span className="text-[11px] text-slate-500 truncate flex-1">{m.etiqueta}</span>
                          <span className="text-[11px] text-slate-500 tabular-nums">{soloVigentes ? m.tamano_vigentes : m.tamano}</span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
            ))}

            <p className="text-[11px] uppercase tracking-wide text-slate-500 px-2 pt-4 pb-2 border-t mt-3">Colorear el mapa por</p>
            <button
              onClick={() => setColorPerfil("global")}
              className={`w-full text-left rounded-md px-2 py-1.5 mb-1 text-sm ${colorPerfil === "global" ? "bg-slate-100 font-semibold text-espol-navy" : "text-slate-700 hover:bg-slate-50"}`}
            >
              Perfil amplio
            </button>
            <div className="inline-flex bg-slate-100 rounded-md p-0.5 mx-2 mb-2" role="group" aria-label="Por dimensión">
              {([["intensidad", "Nivel"], ["patron", "Patrón"]] as const).map(([c, t]) => (
                <button
                  key={c}
                  onClick={() => {
                    setColorPerfil(c);
                    if (!dimColor) setDimColor("investigacion");
                  }}
                  aria-pressed={colorPerfil === c}
                  className={`px-2.5 py-1 text-xs rounded ${colorPerfil === c ? "bg-white shadow-sm text-espol-navy font-medium" : "text-slate-600"}`}
                >
                  {t} de una dimensión
                </button>
              ))}
            </div>
            {colorPerfil !== "global" &&
              dimensiones.data?.map((x) => (
                <button
                  key={x.dimension}
                  onClick={() => setDimColor(x.dimension)}
                  disabled={colorPerfil === "patron" && x.k_patrones === 0}
                  className={`w-full text-left rounded-md px-2 py-1 mb-0.5 text-sm disabled:opacity-40 ${dimColor === x.dimension ? "bg-slate-100 font-semibold text-espol-navy" : "text-slate-700 hover:bg-slate-50"}`}
                >
                  {x.nombre}
                </button>
              ))}
          </nav>

          <section className="bg-white border rounded-lg overflow-hidden flex flex-col" style={{ height: alto }}>
            <div className="px-5 pt-4 pb-2 border-b">
              <h2 className="text-lg font-semibold text-espol-navy">Perfil completo</h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Cada punto es una persona, ubicada según todas sus dimensiones a la vez: cuánto tiene en cada una y cómo
                participa. Las personas cercanas se parecen en el conjunto (p. ej. quienes lideran investigación y además tienen
                muchos reconocimientos).{" "}
                {colorPerfil === "global"
                  ? "Color y rótulos G1, G2…: el perfil amplio de cada persona (clic en un rótulo para resaltarlo)."
                  : `Color: ${nombreDimColor}, por ${colorPerfil === "patron" ? "patrón" : "nivel"}.`}
              </p>
              <label className="text-[11px] text-slate-500 flex items-center gap-1 mt-1">
                <input type="checkbox" checked={soloVigentes} onChange={(e) => setSoloVigentes(e.target.checked)} />
                solo vigentes
              </label>
            </div>
            <div className="flex-1 min-h-0">
              {mapaPerfil.data && mapaPerfil.data.length > 0 ? (
                <MapaPerfil
                  puntos={mapaPerfil.data}
                  color={colorPerfil === "global" ? "global" : dimColor === null ? "ninguno" : colorPerfil}
                  nombreDimension={colorPerfil !== "global" && dimColor ? nombreDimColor : null}
                  personaSeleccionada={persona}
                  alto={alto - 130}
                  onPersona={setPersona}
                  globalSeleccionado={globalSel}
                  onGlobal={elegirGlobal}
                  microSeleccionado={microSel}
                  onMicro={(m) => {
                    setMicroSel(microSel === m ? null : m);
                    setPersona(null);
                  }}
                />
              ) : (
                <p className="text-sm text-slate-500 p-5">
                  {mapaPerfil.isLoading ? "Cargando mapa…" : "Sin datos del perfil completo en esta versión."}
                </p>
              )}
            </div>
          </section>

          <aside ref={panelDerecho} className="bg-white border rounded-lg overflow-y-auto" style={{ height: alto }}>
            {ficha !== null ? (
              <FichaPersona
                key={`${ficha.id}-${ficha.origen}-${ficha.dimension ?? ""}`}
                ambito={ambito}
                personaId={ficha.id}
                origen={ficha.origen}
                dimensionInicial={ficha.dimension}
                onVolver={volverDeFicha}
                textoVolver={
                  globalSel !== null
                    ? `Volver a ${microSel !== null ? `G${globalSel + 1}.${microSel + 1}` : `Perfil ${globalSel + 1}`}`
                    : "Cerrar ficha"
                }
                nav={nav}
              />
            ) : globalSel !== null && globales.data?.patrones?.[globalSel] ? (
              <PanelPatronGlobal
                ambito={ambito}
                nombreAmbito={NOMBRE_AMBITO[ambito]}
                patron={globales.data.patrones[globalSel]}
                conColor={globalesConColor}
                soloVigentes={soloVigentes}
                microSel={microSel}
                onMicro={setMicroSel}
                onPersona={setPersona}
                onDimension={irDimension}
                pestana={pestanaPerfil}
                onPestana={setPestanaPerfil}
                onCerrar={() => {
                  setGlobalSel(null);
                  setMicroSel(null);
                }}
              />
            ) : (
              <p className="text-sm text-slate-500 p-5">
                Elige un perfil amplio para ver qué lo caracteriza y quiénes lo forman, o haz clic en un punto para ver la ficha
                de esa persona y las personas con el perfil más parecido.
              </p>
            )}
          </aside>
        </div>
      )}

      {vista === "dimension" && (
      <div className="grid lg:grid-cols-[17rem_minmax(0,1fr)_27rem] gap-4 items-start">
        {/* dimensiones */}
        <nav className="bg-white border rounded-lg overflow-y-auto p-2" style={{ height: alto }} aria-label="Dimensiones">
          <p className="text-[11px] uppercase tracking-wide text-slate-500 px-2 pt-1 pb-2">Dimensiones</p>
          {dimensiones.data?.map((x) => {
            const cobertura = x.n_vigentes / Math.max(1, x.n_vigentes_ambito);
            return (
              <button
                key={x.dimension}
                onClick={() => elegirDimension(x.dimension)}
                className={`w-full text-left rounded-md px-2 py-2 mb-0.5 ${x.dimension === dimension ? "bg-slate-100" : "hover:bg-slate-50"}`}
              >
                <span className={`block text-sm ${x.dimension === dimension ? "font-semibold text-espol-navy" : "text-slate-700"}`}>{x.nombre}</span>
                <span className="block text-[11px] text-slate-500">
                  {x.n_vigentes} vigentes con evidencias · {Math.round(cobertura * 100)} %
                </span>
                <span className="block mt-1 h-1 bg-slate-100 rounded-sm">
                  <span className="block h-1 bg-espol-blue rounded-sm" style={{ width: `${cobertura * 100}%` }} />
                </span>
              </button>
            );
          })}
        </nav>

        {/* detalle de la dimensión */}
        <section className="bg-white border rounded-lg overflow-y-auto" style={{ height: alto }}>
          {!d ? (
            <p className="text-sm text-slate-500 p-5">Cargando…</p>
          ) : (
            <div>
              <header className="px-5 pt-4 pb-3 border-b">
                <h2 className="text-lg font-semibold text-espol-navy">{d.nombre}</h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  {resumenDim ? `${resumenDim.n_vigentes} de ${resumenDim.n_vigentes_ambito} personas vigentes tienen evidencias. ` : ""}
                  Patrones y temas se descubrieron con los datos (no son categorías predefinidas); los números son solo
                  identificadores.
                </p>
              </header>

              {d.nota && !d.patrones && !d.temas && <p className="text-sm text-slate-600 px-5 py-4">{d.nota}.</p>}

              {(d.patrones || d.temas) && (
                <div className="border-b">
                  <div className="px-5 pt-3 flex flex-wrap items-center gap-x-3 gap-y-1">
                    <div className="inline-flex bg-slate-100 rounded-md p-0.5" role="group" aria-label="Mapa">
                      {(["patrones", "temas"] as TipoMapa[]).map((t) => (
                        <button
                          key={t}
                          disabled={t === "patrones" ? !d.patrones : !d.temas}
                          onClick={() => setTipoMapa(t)}
                          aria-pressed={tipoMapa === t}
                          className={`px-2.5 py-1 text-xs rounded disabled:opacity-40 ${tipoMapa === t ? "bg-white shadow-sm text-espol-navy font-medium" : "text-slate-600"}`}
                        >
                          {t === "patrones" ? "Por patrones" : "Por temas"}
                        </button>
                      ))}
                    </div>
                    <p className="text-[11px] text-slate-500 flex-1 min-w-[16rem]">
                      Cada punto es una persona; las cercanas se parecen en{" "}
                      {tipoMapa === "patrones" ? "cómo participan" : "el contenido de su evidencia"}. Los rótulos{" "}
                      {tipoMapa === "patrones" ? "P1, P2… (y el color)" : "T1, T2… (los 10 temas más grandes)"} marcan cada grupo;
                      haz clic en uno para resaltarlo, o en un punto para abrir la ficha.
                      {tipoMapa === "temas" && " Al elegir un tema se resaltan todas las personas con evidencias en él (más grande = más parte de sus evidencias)."}
                    </p>
                  </div>
                  {mapa.data && mapa.data.length > 0 ? (
                    <MapaDimension
                      puntos={mapa.data}
                      tipo={tipoMapa}
                      seleccion={filtro && (filtro.tipo === "patron") === (tipoMapa === "patrones") ? filtro.id : null}
                      personaSeleccionada={persona}
                      alto={Math.max(320, Math.round(alto * 0.5))}
                      onPersona={setPersona}
                      onGrupo={(g) => elegirFiltro({ tipo: tipoMapa === "patrones" ? "patron" : "tema", id: g })}
                      nombresPatrones={Object.fromEntries((d.patrones?.patrones ?? []).map((p) => [p.id, p.nombre ?? ""]))}
                    />
                  ) : (
                    <p className="text-sm text-slate-500 px-5 py-6">{mapa.isLoading ? "Cargando mapa…" : "Sin mapa para esta dimensión."}</p>
                  )}
                  <p className="text-[11px] text-slate-400 px-5 pb-2">
                    Dibujo aproximado (t-SNE) para orientarse; personas con valores idénticos se agrupan alrededor del mismo punto.
                  </p>
                </div>
              )}

              {d.patrones && tipoMapa === "patrones" && (
                <div className="px-5 py-4 border-b">
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Patrones de actividad · cómo participan ({d.patrones.k})
                  </h3>
                  <p className="text-[11px] text-slate-500 mt-0.5 mb-3">
                    Personas agrupadas por cuánto hacen y en qué proporciones. Barras: cuánto se aleja el grupo del promedio
                    de la dimensión (hacia la derecha, más; hacia la izquierda, menos).
                  </p>
                  <div className="grid xl:grid-cols-2 gap-3">
                    {d.patrones.patrones.map((p) => (
                      <TarjetaPatron
                        key={p.id}
                        patron={p}
                        seleccionado={filtro?.tipo === "patron" && filtro.id === p.id}
                        onClick={() => elegirFiltro({ tipo: "patron", id: p.id })}
                        onPersona={setPersona}
                      />
                    ))}
                  </div>
                </div>
              )}

              {d.temas && tipoMapa === "temas" && (
                <div className="px-5 py-4">
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Temas · de qué trata su evidencia ({d.temas.k})
                  </h3>
                  <p className="text-[11px] text-slate-500 mt-0.5 mb-3">
                    Evidencias agrupadas por el contenido de su título. Una persona puede tener varios temas. Se muestran las
                    palabras que más distinguen a cada tema.
                  </p>
                  <ul className="divide-y">
                    {d.temas.temas.map((t) => (
                      <FilaTema
                        key={t.id}
                        tema={t}
                        maximo={d.temas!.temas.reduce((m, x) => Math.max(m, x.n_personas), 1)}
                        seleccionado={filtro?.tipo === "tema" && filtro.id === t.id}
                        onClick={() => elegirFiltro({ tipo: "tema", id: t.id })}
                      />
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </section>

        {/* personas o ficha */}
        <aside ref={panelDerecho} className="bg-white border rounded-lg overflow-y-auto" style={{ height: alto }}>
          {ficha !== null ? (
            <FichaPersona
              key={`${ficha.id}-${ficha.origen}-${ficha.dimension ?? ""}`}
              ambito={ambito}
              personaId={ficha.id}
              origen={ficha.origen}
              dimensionInicial={ficha.dimension}
              onVolver={volverDeFicha}
              textoVolver={tituloFiltro ? `Volver a ${tituloFiltro}` : "Volver a la lista"}
              nav={nav}
            />
          ) : (
            <div>
              <div className="px-5 pt-4 pb-3 border-b">
                <h3 className="text-base font-semibold text-espol-navy">
                  {tituloFiltro ? `Personas · ${tituloFiltro}` : `Personas con evidencias de ${d?.nombre ?? ""}`}
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  {personas.data ? `${personas.data.total} personas. ` : ""}
                  {filtro?.tipo === "patron"
                    ? "Ordenadas por afinidad con el patrón."
                    : filtro?.tipo === "tema"
                      ? "Ordenadas por la parte de sus evidencias que trata este tema."
                      : "Ordenadas por nivel. Elige un patrón o un tema para filtrar."}
                </p>
                <div className="flex items-center gap-3 mt-2">
                  <label className="text-[11px] text-slate-500 flex items-center gap-1">
                    <input type="checkbox" checked={soloVigentes} onChange={(e) => setSoloVigentes(e.target.checked)} />
                    solo vigentes
                  </label>
                  {filtro && (
                    <button onClick={() => setFiltro(null)} className="text-[11px] text-espol-blue hover:underline">
                      Quitar filtro
                    </button>
                  )}
                </div>
              </div>
              <div>
              <ul className="divide-y">
                {personas.data?.personas.map((x) => (
                  <li key={x.persona_id}>
                    <button onClick={() => setPersona(x.persona_id)} className="w-full text-left px-5 py-2 hover:bg-slate-50">
                      <div className="flex items-baseline gap-2">
                        <span className="text-sm text-slate-800 flex-1">{x.nombre}</span>
                        <span className="text-[11px] tabular-nums text-slate-600" title="Nivel: percentil entre quienes tienen registros en esta dimensión">
                          {x.nivel != null ? <>nivel <strong className="text-slate-800 text-xs">{Math.round(x.nivel)}</strong></> : "—"}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-500 truncate">
                        {x.cargo_actual ?? "Sin cargo actual"}
                        {!x.vigente && " · no vigente"}
                      </p>
                      <p className="text-[11px] text-slate-500">
                        {filtro?.tipo === "tema" && x.proporcion !== undefined
                          ? `${Math.round(x.proporcion * 100)} % de sus evidencias en este tema`
                          : x.patron !== null && x.patron !== undefined
                            ? `Patrón ${x.patron + 1}${!filtro && d?.patrones?.patrones[x.patron]?.nombre ? `: ${d.patrones.patrones[x.patron].nombre}` : ""}${filtro?.tipo === "patron" ? textoSimilitud(x.similitud_representante, x.es_representante) : ""}${x.mixto ? " · entre dos patrones" : ""}`
                            : ""}
                      </p>
                    </button>
                  </li>
                ))}
              </ul>
              {personas.data && (
                <Paginacion
                  pagina={pagina}
                  total={personas.data.total}
                  porPagina={porPagina}
                  onCambiar={cambiarPagina}
                  onPorPagina={(n) => {
                    setPorPagina(n);
                    guardarPorPagina(n);
                    if (panelDerecho.current) panelDerecho.current.scrollTop = 0;
                  }}
                  cargando={personas.isFetching}
                  nota={<>Nivel: percentil entre quienes tienen registros en la dimensión.{filtro?.tipo === "patron" ? " Similitud: frente a la persona más representativa del patrón (0 % = la más distinta)." : ""}</>}
                />
              )}
              </div>
            </div>
          )}
        </aside>
      </div>
      )}
    </div>
  );
}

// Similitud con la persona representativa del patrón. Con valores idénticos (empate) la distancia es
// 0 y daría 100 % sin ser la representante: se dice en palabras.
function textoSimilitud(sim: number | null | undefined, esRep: boolean | null | undefined) {
  if (esRep) return " · persona más representativa";
  if (sim === null || sim === undefined) return "";
  if (sim >= 0.9995) return " · valores idénticos a la persona más representativa";
  return ` · similitud con la persona más representativa ${Math.round(sim * 100)} %`;
}

function TarjetaPatron({ patron, seleccionado, onClick, onPersona }: {
  patron: Patron; seleccionado: boolean; onClick: () => void; onPersona: (id: number) => void;
}) {
  const extremo = Math.max(1.5, ...patron.componentes.map((c) => Math.abs(c.z)));
  return (
    <div className={`border rounded-md p-3 ${seleccionado ? "border-espol-blue ring-1 ring-espol-blue" : "hover:border-slate-300"}`}>
      <button onClick={onClick} className="w-full text-left" aria-pressed={seleccionado}>
        <div className="flex items-baseline gap-2">
          <span className="w-2.5 h-2.5 rounded-full shrink-0 self-center" style={{ background: colorPatron(patron.id) }} />
          <span className="text-sm font-semibold text-slate-800 flex-1">Patrón {patron.id + 1}</span>
          <span className="text-xs text-slate-500 tabular-nums">
            {patron.tamano_vigentes} vigentes · {patron.tamano} en total
          </span>
        </div>
        {patron.nombre && (
          <p className="text-xs font-medium text-slate-800 mt-1"
            title={`Se cumple para todas sus personas · distingue del resto de la dimensión: ${Math.round((patron.nombre_distingue ?? 0) * 100)} %`}>
            {patron.nombre}
          </p>
        )}
        <p className={`text-xs mt-1 ${patron.nombre ? "text-slate-500" : "text-slate-600"}`}>
          {patron.nombre ? `En promedio: ${patron.etiqueta}` : patron.etiqueta}
        </p>
        <ul className="mt-2 space-y-1">
          {patron.componentes.map((c) => {
            const ancho = (Math.min(Math.abs(c.z), extremo) / extremo) * 50;
            return (
              <li key={c.componente} className="grid grid-cols-[minmax(0,1fr)_7rem] gap-2 items-center" title={`${c.descripcion}: z = ${c.z}`}>
                <span className="text-[11px] text-slate-600 truncate">{c.descripcion.replace(" (log)", "")}</span>
                <span className="relative h-2 bg-slate-100 rounded-sm">
                  <span className="absolute top-0 bottom-0 left-1/2 w-px bg-slate-400" />
                  <span
                    className={`absolute top-0 bottom-0 ${c.z >= 0 ? "bg-espol-blue rounded-r-sm" : "bg-slate-400 rounded-l-sm"}`}
                    style={c.z >= 0 ? { left: "50%", width: `${ancho}%` } : { right: "50%", width: `${ancho}%` }}
                  />
                </span>
              </li>
            );
          })}
        </ul>
      </button>
      {patron.representante_id !== null && (
        <p className="text-[11px] text-slate-500 mt-2">
          Persona más representativa:{" "}
          <button className="text-espol-blue hover:underline" onClick={() => onPersona(patron.representante_id!)}>
            {patron.representante_nombre}
          </button>
        </p>
      )}
    </div>
  );
}

function FilaTema({ tema, maximo, seleccionado, onClick }: { tema: Tema; maximo: number; seleccionado: boolean; onClick: () => void }) {
  return (
    <li>
      <button
        onClick={onClick}
        aria-pressed={seleccionado}
        className={`w-full text-left py-2 px-2 -mx-2 rounded ${seleccionado ? "bg-slate-100" : "hover:bg-slate-50"}`}
      >
        <div className="grid grid-cols-[4.5rem_minmax(0,1fr)_8rem] gap-2 items-center">
          <span className="text-xs font-semibold text-slate-700">Tema {tema.id + 1}</span>
          <span className="text-xs text-slate-700 truncate">{tema.terminos_distintivos.slice(0, 6).join(", ")}</span>
          <span className="flex items-center gap-2">
            <span className="flex-1 h-1.5 bg-slate-100 rounded-sm">
              <span className="block h-1.5 bg-espol-blue rounded-sm" style={{ width: `${(tema.n_personas / maximo) * 100}%` }} />
            </span>
            <span className="text-[11px] tabular-nums text-slate-600 w-10 text-right" title="personas con al menos una evidencia en el tema">
              {tema.n_personas}
            </span>
          </span>
        </div>
        {seleccionado && (
          <ul className="mt-2 ml-[4.5rem] space-y-0.5">
            {tema.ejemplos.map((e) => (
              <li key={e.texto} className="text-[11px] text-slate-500">
                · {e.texto} {e.personas > 1 && <span className="text-slate-400">({e.personas} personas)</span>}
              </li>
            ))}
          </ul>
        )}
      </button>
    </li>
  );
}
