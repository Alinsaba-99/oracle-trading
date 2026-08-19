#!/usr/bin/env bash
# Avvia IBKR Gateway (paper) in Docker per backfill dati 1m storici (BL-097).
#
# Immagine: ghcr.io/unusualalpha/ib-gateway (UnusualAlpha/ib-gateway) —
#   auto-login via IBC; VNC opzionale per la prima 2FA.
# Porte: 4002 = API paper (socket), 5900 = VNC (se VNC_SERVER_PASSWORD set).
#   NOTA: 7497 era la porta TWS; il Gateway paper usa 4002.
#
# Credenziali da .env.ibkr (gitignored), template in .env.ibkr.example:
#   TWS_USERID=<username paper>  /  TWS_PASSWORD=<password paper>
#   VNC_SERVER_PASSWORD=<opzionale, prima login/2FA>
#
# Uso:
#   bash scripts/start_ibkr_gateway.sh            # avvia il container
#   bash scripts/start_ibkr_gateway.sh status     # stato del container
#   bash scripts/start_ibkr_gateway.sh logs       # log del gateway

set -euo pipefail

CONTAINER="ib-gateway"
IMAGE="ghcr.io/unusualalpha/ib-gateway:latest"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/../.env.ibkr"

if [ "${1:-}" = "status" ]; then
    docker ps -a --filter "name=^${CONTAINER}$" --format '{{.Names}} {{.Status}} {{.Ports}}'
    exit 0
fi
if [ "${1:-}" = "logs" ]; then
    docker logs -f "${CONTAINER}"
    exit 0
fi

echo "=== IBKR Gateway — Paper Account (BL-097) ==="

if ! docker ps >/dev/null 2>&1; then
    echo "❌ Docker non disponibile. Installa/avvia Docker prima."
    exit 1
fi

# Credenziali: .env.ibkr o ambiente
if [ -f "${ENV_FILE}" ]; then
    set -a
    # shellcheck disable=SC1090
    source "${ENV_FILE}"
    set +a
fi
if [ -z "${TWS_USERID:-}" ] || [ -z "${TWS_PASSWORD:-}" ]; then
    echo "❌ TWS_USERID/TWS_PASSWORD mancanti. Copia .env.ibkr.example in .env.ibkr"
    echo "   e inserisci le credenziali del PAPER account."
    exit 1
fi

# Avvia se non già in esecuzione
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo "✅ IBKR Gateway già in esecuzione."
    docker ps --filter "name=^${CONTAINER}$" --format '{{.Names}} {{.Status}} {{.Ports}}'
else
    echo "🔄 Avvio IBKR Gateway in Docker (auto-login paper)..."
    echo "   Ports: 4002 (API paper) + 5900 (VNC, se configurato)"
    echo ""

    docker run -d \
        --name "${CONTAINER}" \
        --restart unless-stopped \
        -p 127.0.0.1:4002:4002 \
        -p 127.0.0.1:5900:5900 \
        -e "TWS_USERID=${TWS_USERID}" \
        -e "TWS_PASSWORD=${TWS_PASSWORD}" \
        -e "TRADING_MODE=paper" \
        -e "READ_ONLY_API=yes" \
        -e "VNC_SERVER_PASSWORD=${VNC_SERVER_PASSWORD:-}" \
        "${IMAGE}"
fi

echo ""
echo "✅ Container avviato. Attendi 30-60s per l'auto-login IBC:"
echo "   bash scripts/start_ibkr_gateway.sh logs"
echo ""
echo "Se l'account richiede 2FA: apri il VNC (usa la variabile d'ambiente VNC_SERVER_PASSWORD)"
echo "   vncviewer 127.0.0.1:5900   # completa la verifica nel browser del gateway"
echo ""
echo "Verifica API dopo il login:"
echo "   curl -s http://127.0.0.1:4002/ && echo OK"
