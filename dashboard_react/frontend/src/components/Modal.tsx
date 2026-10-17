import { useEffect, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";

// Ventana sobre la página para un detalle que no hace falta tener siempre a la vista. Se cierra
// con Esc, con la ✕ o con un clic fuera. Esc no llega a la página (que con Esc cierra la ficha).
export default function Modal({ titulo, onCerrar, children, ancho = "normal" }: {
  titulo: string; onCerrar: () => void; children: ReactNode; ancho?: "normal" | "amplio";
}) {
  const panel = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const anterior = document.activeElement as HTMLElement | null;
    panel.current?.focus();
    const f = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      e.stopImmediatePropagation();
      onCerrar();
    };
    window.addEventListener("keydown", f, { capture: true });
    return () => {
      window.removeEventListener("keydown", f, { capture: true });
      anterior?.focus?.();
    };
  }, [onCerrar]);

  return createPortal(
    <div className="fixed inset-0 z-50 bg-slate-900/40 grid place-items-center p-4" onMouseDown={(e) => e.target === e.currentTarget && onCerrar()}>
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-label={titulo}
        tabIndex={-1}
        className={`bg-white rounded-lg shadow-xl w-full ${ancho === "amplio" ? "max-w-4xl" : "max-w-xl"} max-h-[85vh] overflow-y-auto outline-none`}
      >
        <header className="flex items-center gap-3 px-5 pt-4 pb-3 border-b sticky top-0 bg-white">
          <h2 className="text-base font-semibold text-espol-navy flex-1">{titulo}</h2>
          <button onClick={onCerrar} className="text-slate-400 hover:text-slate-700 text-xl leading-none" aria-label="Cerrar">
            ×
          </button>
        </header>
        <div className="px-5 py-4">{children}</div>
      </div>
    </div>,
    document.body,
  );
}
