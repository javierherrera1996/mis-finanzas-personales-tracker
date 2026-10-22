"""Vuelve a pedir los permisos de Google (leer correo, Sheets, enviar el informe, calendario).
Imprime un enlace: ábrelo en el navegador de este Mac y aprueba. Espera 30 minutos."""
import os
from google_auth_oauthlib.flow import InstalledAppFlow
from auth import SCOPES, CLIENT, TOKEN

flow = InstalledAppFlow.from_client_secrets_file(CLIENT, SCOPES)
creds = flow.run_local_server(port=8765, open_browser=True, timeout_seconds=1800,
                              authorization_prompt_message="Abre este enlace y aprueba:\n{url}\n", prompt="consent")
open(TOKEN, "w").write(creds.to_json()); os.chmod(TOKEN, 0o600)
print("PERMISOS OK:", creds.scopes)
