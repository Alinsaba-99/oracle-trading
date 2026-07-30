#!/usr/bin/env bash
# Avvia IBKR TWS/Gateway in Docker per backfill dati 1m storici
# Porta 7497 = TWS paper, 4002 = Gateway paper
# 
# Uso:
#   bash scripts/start_ibkr_gateway.sh
#
# Dopo l'avvio, il backfill si lancia con:
#   uv run --frozen python market/ingestion/orchestrator.py run
#
# Per verificare che TWS sia attivo:
#   curl -s http://127.0.0.1:7497/ 2>/dev/null && echo "OK" || echo "non raggiungibile"

set -euo pipefail

echo "=== IBKR Gateway — Paper Account ==="
echo ""

# Verifica Docker
if ! docker ps >/dev/null 2>&1; then
    echo "❌ Docker non disponibile. Installa Docker prima."
    exit 1
fi

# Container name
CONTAINER="ib-gateway"

# Avvia se non già in esecuzione
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo "✅ IBKR Gateway già in esecuzione."
else
    echo "🔄 Avvio IBKR Gateway in Docker..."
    echo "   Prima esecuzione: la prima volta devi autenticarti manualmente."
    echo "   Port: 7497 (TWS paper mode)"
    echo ""

    docker run -d \
        --name "${CONTAINER}" \
        --restart unless-stopped \
        -p 7497:7497 \
        -p 4002:4002 \
        ghcr.io/unusualalpha/ib-gateway-docker:latest 2>/dev/null || {

        # Fallback: immagine alternativa
        docker run -d \
            --name "${CONTAINER}" \
            --restart unless-stopped \
            -p 7497:7497 \
            -p 4002:4002 \
            ib-gateway:latest 2>/dev/null || {
            
            echo "⚠️  Nessuna immagine Docker trovata."
            echo ""
            echo "Soluzione manuale:"
            echo "  1. Scarica IB Gateway da:"
            echo "     https://www.interactivebrokers.com/en/trading/ibkr-light.php"
            echo "  2. Avvia con: java -jar ibgateway.jar"
            echo "  3. Configura su carta (paper account), porta API 7497"
            echo ""
            echo "Oppure usa un'immagine Docker ufficiale:"
            echo "  https://github.com/UnusualAlpha/ib-gateway-docker"
            exit 1
        }
    }

    echo "✅ Container avviato. Attendi 30-60 secondi per l'autenticazione."
    echo "   (La prima volta: docker logs -f ${CONTAINER})"
fi

echo ""
echo "=== Pronto per backfill ==="
echo "Lancia il backfill 1m:"
echo "  uv run --frozen python market/ingestion/orchestrator.py run"
echo ""
echo "Oppure per un singolo asset:"
echo "  python3 -c \"from market.ingestion.pipeline import Pipeline; import asyncio; asyncio.run(Pipeline().fetch('ES', '1m', 'ibkr', start=date(2010,1,1)))\""
