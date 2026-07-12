export default function GaPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Genetic Algorithm</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Risultati delle run di evoluzione genetica
        </p>
      </div>
      <div className="rounded-lg border border-border bg-card p-8 flex items-center justify-center text-muted-foreground text-sm">
        Nessuna run GA trovata. Lancia una GA run da CLI.
      </div>
    </div>
  )
}
