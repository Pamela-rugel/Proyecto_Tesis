// Texto enlazado dentro del dashboard: botón con aspecto de hipervínculo. Sin `onClick` se muestra
// como texto normal (p. ej., cuando la página no ofrece ese destino).
export default function Enlace({ onClick, children, className = "" }: { onClick?: () => void; children: React.ReactNode; className?: string }) {
  if (!onClick) return <span className={className}>{children}</span>;
  return (
    <button type="button" onClick={onClick} className={`text-espol-blue hover:underline text-left ${className}`}>
      {children}
    </button>
  );
}
