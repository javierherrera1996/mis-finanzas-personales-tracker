# 🔑 Crear tu acceso a Google (credentials.json)

Cuentas Claras necesita permiso para **leer** tu Gmail, crear tus **Sheets** y poner recordatorios en tu **Calendar**. Ese permiso lo creas tú, con tu cuenta, en Google Cloud. Es gratis y toma ≈ 15 minutos.

> Usa la **misma cuenta de Gmail** donde te llegan los correos de tus bancos.

## 1. Crea el proyecto
1. Entra a **https://console.cloud.google.com**.
2. Arriba, en el selector de proyectos → **Nuevo proyecto** → nombre `Cuentas Claras` → **Crear**.
3. Verifica que quedó seleccionado (su nombre aparece arriba).

## 2. Habilita las 4 APIs
**APIs y servicios → Biblioteca**, busca cada una y dale **Habilitar**:

- [ ] Gmail API
- [ ] Google Sheets API
- [ ] Google Drive API
- [ ] Google Calendar API

## 3. Configura la pantalla de permisos
Menú → **Google Auth Platform** (puede llamarse "Pantalla de consentimiento de OAuth") → **Comenzar**:

| Campo | Qué poner |
|---|---|
| Nombre de la app | `Cuentas Claras` |
| Correo de asistencia | tu correo |
| Público | **Externo** |
| Información de contacto | tu correo |

Luego **Acceso a los datos → Agregar o quitar permisos** y pega estos 5:
```
https://www.googleapis.com/auth/gmail.readonly
https://www.googleapis.com/auth/gmail.send
https://www.googleapis.com/auth/spreadsheets
https://www.googleapis.com/auth/drive.file
https://www.googleapis.com/auth/calendar.events
```

## 4. ⚠️ Publica la app
**Público → Publicar app** → confirma que diga **En producción**.

Si la dejas en "Prueba", **el permiso vence cada 7 días** y el informe deja de llegar sin avisar.

## 5. Crea el cliente y descarga el archivo
1. **Clientes → Crear cliente** → tipo **App de escritorio** → nombre `Cuentas Claras Mac` → **Crear**.
2. **Descargar JSON**.
3. Ponlo en la carpeta `cuentas-claras` con el nombre **`credentials.json`** (Claude lo puede mover por ti desde Descargas).

## 6. Autoriza
Claude corre `reautorizar.py` y se abre el navegador:
1. Elige tu cuenta.
2. Sale **"Google no verificó esta app"**: es normal, es *tu* app. **Configuración avanzada → Ir a Cuentas Claras**.
3. **Marca todas las casillas** (si dejas una sin marcar, alguna parte no funciona).

Listo: se crea `token.json`. Igual que `credentials.json`, **no se comparte nunca**.

---

### ¿Por qué cada permiso?
| Permiso | Para qué |
|---|---|
| `gmail.readonly` | Leer alertas y extractos de tus bancos (solo lectura) |
| `gmail.send` | Enviarte el informe del lunes **a ti mismo** |
| `spreadsheets` + `drive.file` | Crear y actualizar **solo los Sheets que crea Cuentas Claras** |
| `calendar.events` | Recordatorios de tus pagos |
