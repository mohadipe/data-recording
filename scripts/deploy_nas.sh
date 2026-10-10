#!/usr/bin/env bash
# ==============================================================================
# deploy_nas.sh - Automatisches Rollout von data-recording auf das Synology NAS
# ==============================================================================
# Führt ein 1-Befehl-Deployment via SSH auf der Synology DiskStation aus:
# 1. Image pullen (docker compose pull data-recording)
# 2. Container aktualisieren (docker compose up -d --no-deps data-recording)
# 3. Healthcheck auf Port 9015 validieren
# 4. Status und Versionsnummer ausgeben
# ==============================================================================

set -euo pipefail

# Konfigurierbare Parameter mit Standardwerten
NAS_HOST="${NAS_HOST:-nas}"
NAS_APP_DIR="${NAS_APP_DIR:-/volume1/docker/nas-infra/03_apps}"
SERVICE_NAME="${SERVICE_NAME:-data-recording}"
HEALTH_PORT="${HEALTH_PORT:-9015}"
MAX_RETRIES="${MAX_RETRIES:-15}"
RETRY_INTERVAL="${RETRY_INTERVAL:-2}"
DRY_RUN=false

# ANSI Farbcodes für lesbare Ausgabe
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*" >&2
}

print_usage() {
    cat <<EOF
Verwendung: $(basename "$0") [OPTIONEN]

Automatisches Rollout von data-recording auf die Synology DiskStation (nas-infra).

Optionen:
  -h, --help        Zeigt diese Hilfe an und beendet das Skript.
  --dry-run         Simuliert die Schritte, ohne Änderungen auf dem NAS durchzuführen.

Umgebungsvariablen:
  NAS_HOST          SSH-Host oder IP des NAS (Standard: nas)
  NAS_APP_DIR       Zielverzeichnis auf dem NAS (Standard: /volume1/docker/nas-infra/03_apps)
  SERVICE_NAME      Compose-Servicename (Standard: data-recording)
  HEALTH_PORT       Port für Healthcheck (Standard: 9015)
  MAX_RETRIES       Maximale Versuche für Healthcheck (Standard: 15)
  RETRY_INTERVAL    Wartezeit zwischen Versuchen in Sekunden (Standard: 2)

Beispiele:
  ./scripts/deploy_nas.sh
  ./scripts/deploy_nas.sh --dry-run
  NAS_HOST=192.168.2.125 ./scripts/deploy_nas.sh
EOF
}

# Argumente parsen
while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)
            print_usage
            exit 0
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            log_error "Unbekanntes Argument: $1"
            print_usage
            exit 1
            ;;
    esac
done

log_info "Starte Deployment von '${SERVICE_NAME}' auf '${NAS_HOST}'..."
log_info "App-Verzeichnis: ${NAS_APP_DIR}"

if [ "$DRY_RUN" = true ]; then
    log_info "[DRY-RUN] Es werden keine Befehle auf dem NAS ausgeführt."
    echo "[DRY-RUN] cd ${NAS_APP_DIR}"
    echo "[DRY-RUN] docker compose pull ${SERVICE_NAME}"
    echo "[DRY-RUN] docker compose up -d --no-deps ${SERVICE_NAME}"
    echo "[DRY-RUN] Healthcheck: curl -fs http://localhost:${HEALTH_PORT}/health"
    log_success "[DRY-RUN] Simulation erfolgreich beendet."
    exit 0
fi

# 1. SSH-Verbindung und Remote-Rollout ausführen
log_info "Aktualisiere Container via Docker Compose auf dem NAS..."

REMOTE_COMMANDS=$(cat <<EOF
set -euo pipefail
cd "${NAS_APP_DIR}"

echo "Pulling neuestes Image für ${SERVICE_NAME}..."
if docker compose version >/dev/null 2>&1; then
    docker compose pull ${SERVICE_NAME}
    docker compose up -d --no-deps ${SERVICE_NAME}
else
    docker-compose pull ${SERVICE_NAME}
    docker-compose up -d --no-deps ${SERVICE_NAME}
fi
EOF
)

if ! ssh "${NAS_HOST}" "${REMOTE_COMMANDS}"; then
    log_error "Fehler beim Ausführen von docker compose auf dem NAS!"
    exit 1
fi

log_success "Container wurde erfolgreich auf dem NAS aktualisiert."

# 2. Healthcheck & Status-Validierung
log_info "Warte auf Container-Initialisierung und prüfe Healthcheck auf Port ${HEALTH_PORT}..."

HEALTH_CHECK_SCRIPT=$(cat <<EOF
set -euo pipefail
cd "${NAS_APP_DIR}"

attempt=1
max_retries=${MAX_RETRIES}
delay=${RETRY_INTERVAL}
healthy=false

while [ \$attempt -le \$max_retries ]; do
    if curl -fs "http://localhost:${HEALTH_PORT}/health" >/tmp/data_recording_health.json 2>/dev/null; then
        healthy=true
        break
    fi
    echo "Warte auf Healthcheck (Versuch \$attempt/\$max_retries)..." >&2
    sleep \$delay
    attempt=\$((attempt + 1))
done

if [ "\$healthy" != "true" ]; then
    echo "FEHLER: Healthcheck nach \$max_retries Versuchen fehlgeschlagen!" >&2
    exit 2
fi

# Gebe Health-JSON aus
cat /tmp/data_recording_health.json
rm -f /tmp/data_recording_health.json
EOF
)

HEALTH_OUTPUT=""
if ! HEALTH_OUTPUT=$(ssh "${NAS_HOST}" "${HEALTH_CHECK_SCRIPT}"); then
    log_error "Healthcheck auf Port ${HEALTH_PORT} ist fehlgeschlagen!"
    exit 2
fi

log_success "Healthcheck erfolgreich: ${HEALTH_OUTPUT}"

# 3. Container-Status abfragen
log_info "Ermittle Container-Status..."
CONTAINER_STATUS=$(ssh "${NAS_HOST}" "cd '${NAS_APP_DIR}' && docker compose ps '${SERVICE_NAME}'" 2>/dev/null || echo "Aktiv")

# Version aus Health-JSON extrahieren (falls grep/sed/jq verfügbar)
DEPLOYED_VERSION=$(echo "${HEALTH_OUTPUT}" | grep -o '"version":"[^"]*"' | cut -d':' -f2 | tr -d '"' || echo "unbekannt")

echo ""
echo "=============================================================================="
log_success "Deployment erfolgreich abgeschlossen! 🚀"
echo "  • Service:      ${SERVICE_NAME}"
echo "  • Version:      ${DEPLOYED_VERSION}"
echo "  • Host:         ${NAS_HOST}"
echo "  • Healthcheck:  http://localhost:${HEALTH_PORT}/health (HTTP 200 OK)"
echo "  • Status:"
echo "${CONTAINER_STATUS}"
echo "=============================================================================="
