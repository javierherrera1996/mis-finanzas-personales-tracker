#!/bin/bash
# Instala el sistema de finanzas en este Mac.
#   ./instalar.sh             -> entorno de Python, carpetas y datos iniciales
#   ./instalar.sh automatico  -> además deja el servicio que actualiza solo al prender el Mac (launchd)
set -e
cd "$(dirname "$0")"
DIR="$PWD"

if ! command -v python3 >/dev/null; then
  echo "Falta Python 3. Instálalo desde https://www.python.org/downloads/ (o: brew install python) y vuelve a correr esto."; exit 1
fi
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' || { echo "Necesitas Python 3.10 o superior (tienes $(python3 --version))."; exit 1; }

[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt
mkdir -p data pdfs
for f in data_inicial/*.json; do [ -f "data/$(basename "$f")" ] || cp "$f" data/; done
echo "✅ Entorno listo."
[ -f config.json ] || echo "➡️  Falta config.json: pídele a Claude 'configúralo para mí' (o copia config.ejemplo.json y llénalo)."
[ -f credentials.json ] || echo "➡️  Falta credentials.json de Google Cloud: ver docs/google-cloud.md."

if [ "$1" = "automatico" ]; then
  PL=~/Library/LaunchAgents/com.misfinanzas.actualizar.plist
  cat > "$PL" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.misfinanzas.actualizar</string>
  <key>ProgramArguments</key><array>
    <string>$DIR/.venv/bin/python</string><string>$DIR/actualizar.py</string><string>--semanal</string>
  </array>
  <key>WorkingDirectory</key><string>$DIR</string>
  <key>RunAtLoad</key><true/>
  <key>StartInterval</key><integer>900</integer>
  <key>StartCalendarInterval</key><dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>7</integer><key>Minute</key><integer>5</integer></dict>
  <key>StandardOutPath</key><string>$DIR/data/launchd.out.log</string>
  <key>StandardErrorPath</key><string>$DIR/data/launchd.err.log</string>
</dict></plist>
EOF
  launchctl unload "$PL" 2>/dev/null || true
  launchctl load "$PL"
  echo "✅ Servicio automático cargado (com.misfinanzas.actualizar): actualiza al prender el Mac, informe los lunes 7:00."
fi
