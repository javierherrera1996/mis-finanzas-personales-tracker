"""Autoriza acceso de solo lectura a Gmail y creación de hojas en Sheets/Drive.

Uso: .venv/bin/python auth.py
Requiere credentials.json (cliente OAuth tipo "App de escritorio") en esta carpeta.
Guarda el permiso en token.json.
"""
import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar.events",
]
HERE = os.path.dirname(os.path.abspath(__file__))
TOKEN = os.path.join(HERE, "token.json")
CLIENT = os.path.join(HERE, "credentials.json")


BASE = SCOPES[:3]  # leer correo, Sheets y Drive: lo que necesita la actualización


def get_creds(need=BASE):
    """need = permisos requeridos por quien llama; si faltan, abre el navegador para pedirlos todos."""
    creds = None
    if os.path.exists(TOKEN):
        creds = Credentials.from_authorized_user_file(TOKEN)  # scopes realmente concedidos
    ok = creds and set(need) <= set(creds.scopes or [])
    if ok and creds.valid:
        return creds
    if ok and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file(CLIENT, SCOPES)
        creds = flow.run_local_server(port=0, timeout_seconds=600)
    with open(TOKEN, "w") as f:
        f.write(creds.to_json())
    os.chmod(TOKEN, 0o600)
    return creds


if __name__ == "__main__":
    from googleapiclient.discovery import build

    profile = build("gmail", "v1", credentials=get_creds(SCOPES)).users().getProfile(userId="me").execute()
    print("Conectado a:", profile["emailAddress"], "| mensajes:", profile["messagesTotal"])
