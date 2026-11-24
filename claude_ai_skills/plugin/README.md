# Mis finanzas

Tus finanzas personales en Colombia, sin instalar nada en tu computador. Claude lee las alertas de movimientos que tus
bancos te mandan a Gmail (Bancolombia, Davivienda y otros), las clasifica con un motor que viene dentro del plugin y lo
deja todo en un Google Sheet tuyo: cuánto puedes gastar por día hasta el sueldo, en qué se te va la plata, tus
suscripciones, tus deudas de mayor a menor tasa y si hay ofertas para pagar menos intereses.

## Instalar (unos 15 minutos)

Necesitas Claude Pro o Max y que tus bancos te manden las alertas de cada movimiento a Gmail.

1. **Conecta Gmail y Google Drive** (y Google Sheets si aparece aparte): Personalizar → Conectores
   (claude.ai/customize/connectors). Para los recordatorios de pagos, también Google Calendar.
2. **Activa la ejecución de código**: Configuración → Capacidades → "Ejecución de código y creación de archivos".
3. **Instala el plugin**: Personalizar → Plugins (claude.ai/customize/plugins) → Agregar → Agregar marketplace →
   `javierherrera1996/mis-finanzas-personales-tracker` → instala **Mis finanzas**.
   En Claude Code: `/plugin marketplace add javierherrera1996/mis-finanzas-personales-tracker` y luego
   `/plugin install mis-finanzas@mis-finanzas`.
4. **Empieza**: en un chat nuevo escribe `/mis-finanzas:empezar` (o "configura mis finanzas"). Son unos 10 minutos.
5. **Déjalo solo** (opcional): Programadas → Nueva tarea → todos los días a las 7:00 → "Actualiza mis finanzas".
   Los lunes a las 7:30 → "Mándame el informe semanal de mis finanzas".

Después pregunta lo que quieras: "¿cuánto puedo gastar?", "¿en qué se me fue la plata?", "¿qué suscripciones tengo?".

## Tus datos

Solo lee las alertas de tus bancos en tu Gmail. Todo lo que arma queda en tu Google Drive (un Sheet "Mis finanzas"); el
plugin no manda tus datos a ningún servidor propio. Las búsquedas de tasas en internet no llevan tus datos personales.

No es asesoría financiera ni de inversión: hace cuentas con tus datos y compara información pública.
