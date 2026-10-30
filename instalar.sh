#!/bin/bash
# Instala el sistema de finanzas en este Mac.
#   ./instalar.sh             -> entorno de Python, carpetas y datos iniciales
#   ./instalar.sh automatico  -> además deja el servicio que actualiza solo al prender el Mac (launchd)
set -e
cd "$(dirname "$0")"
DIR="$PWD"

# el Python más nuevo que haya (sirve desde 3.9, el que trae el Mac con las herramientas de Apple)
PY=""
for v in python3.14 python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$v" >/dev/null && "$v" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then PY="$v"; break; fi
done
if [ -z "$PY" ]; then
  echo "Falta Python 3. En un Mac corre:  xcode-select --install  (instala las herramientas de Apple, que traen Python y git; ≈ 5 min) y vuelve a correr esto."
  exit 1
fi
echo "Python: $($PY --version)"

[ -d .venv ] || "$PY" -m venv .venv
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
