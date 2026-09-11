export function LoadingBlock({ label = "Cargando..." }: { label?: string }) {
  return (
    <div className="flex items-center justify-center py-16 text-slate-400 text-sm gap-2">
      <span className="inline-block w-4 h-4 border-2 border-slate-300 border-t-espol-blue rounded-full animate-spin" />
      {label}
    </div>
  );
}

export function ErrorBlock({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 text-red-700 text-sm px-4 py-3">
      {message}
    </div>
  );
}
