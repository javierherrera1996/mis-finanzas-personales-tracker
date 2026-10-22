#!/bin/zsh
# Deja corriendo el bot de WhatsApp y el túnel ngrok (se reinician solos al prender el Mac).
set -e
cd "$(dirname "$0")"; P="$PWD"; ENVF="data/whatsapp.env"
v() { grep "^$1=" "$ENVF" | cut -d= -f2-; }
for k in WA_TOKEN WA_PHONE_NUMBER_ID WA_APP_SECRET WA_MI_NUMERO NGROK_DOMINIO NGROK_AUTHTOKEN; do
  val=$(v $k); if [[ -z "$val" || "$val" == pega* || "$val" == *XXXX* ]]; then echo "Falta llenar $k en $ENVF"; exit 1; fi
done
ngrok config add-authtoken "$(v NGROK_AUTHTOKEN)" >/dev/null
LA=~/Library/LaunchAgents
cat > $LA/com.cuentasclaras.whatsapp.plist <<PL
<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
 <key>Label</key><string>com.cuentasclaras.whatsapp</string>
 <key>ProgramArguments</key><array><string>$P/.venv/bin/python</string><string>$P/whatsapp_bot.py</string></array>
 <key>WorkingDirectory</key><string>$P</string><key>RunAtLoad</key><true/><key>KeepAlive</key><true/>
 <key>StandardOutPath</key><string>$P/data/whatsapp.out.log</string><key>StandardErrorPath</key><string>$P/data/whatsapp.err.log</string>
</dict></plist>
PL
cat > $LA/com.cuentasclaras.ngrok.plist <<PL
<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
 <key>Label</key><string>com.cuentasclaras.ngrok</string>
 <key>ProgramArguments</key><array><string>/opt/homebrew/bin/ngrok</string><string>http</string><string>--url=$(v NGROK_DOMINIO)</string><string>$(v WA_PORT)</string><string>--log=stdout</string></array>
 <key>RunAtLoad</key><true/><key>KeepAlive</key><true/>
 <key>StandardOutPath</key><string>$P/data/ngrok.log</string><key>StandardErrorPath</key><string>$P/data/ngrok.log</string>
</dict></plist>
PL
for s in whatsapp ngrok; do launchctl unload $LA/com.cuentasclaras.$s.plist 2>/dev/null || true; launchctl load $LA/com.cuentasclaras.$s.plist; done
sleep 6
curl -s "https://$(v NGROK_DOMINIO)/salud" && echo "  ← el túnel y el bot responden"
echo "Callback URL para Meta:  https://$(v NGROK_DOMINIO)/webhook"
echo "Verify token para Meta:  $(v WA_VERIFY_TOKEN)"
