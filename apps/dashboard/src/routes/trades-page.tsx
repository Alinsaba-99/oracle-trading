export default function TradesPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Trade Log</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Cronologia completa degli ordini eseguiti
        </p>
      </div>
      <div className="rounded-lg border border-border bg-card p-8 flex items-center justify-center text-muted-foreground text-sm">
        Nessun trade trovato. Esegui un backtest o connetti un broker.
      </div>
    </div>
  )
}
