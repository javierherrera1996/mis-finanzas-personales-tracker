# Cuentas Claras — reglas para Claude

Sistema que lee el Gmail del usuario (alertas y extractos de bancos colombianos), consolida sus movimientos y genera un Google Sheet, un informe semanal por correo (con preguntas que se responden por correo) y recordatorios en Google Calendar. Responde en español y con cifras en pesos ($1.234.567).

## Si el sistema todavía no está configurado (no existe config.json o token.json)
Toma la iniciativa: saluda, explica en 2 líneas qué hace el sistema y arranca la **instalación guiada con la skill `instalar-finanzas`**. Es una entrevista por fases (requisitos → datos básicos → Google Cloud → detectar bancos con `detectar_bancos.py` → primera corrida → bancos que faltan → clasificar → lo fijo → automático → plan opcional). Una pregunta a la vez; tú corres los comandos, el usuario solo responde. Un hook de inicio de sesión (.claude/settings.json) te avisa si falta config.json o token.json.

## Flujo
`actualizar.py [--informe]` = sheet_sync (guarda ediciones del Sheet) → fetch (correos nuevos) → attachments + pdftext (PDF con la clave de config.json) → saldos de créditos → build.py (clasifica) → agente.nuevas_preguntas → make_sheet.py → plan_sheet.py → (calendario.py + informe_semanal.py). El servicio launchd `com.cuentasclaras.actualizar` corre `actualizar.py --semanal`: la primera vez del día actualiza los Sheets; los lunes después de las 7:00 manda el informe; cada 15 min lee las respuestas al correo del informe.

## Reglas que ya costaron errores (no repetirlas)
- **Caja**: el saldo de la cuenta principal de Davivienda en el extracto YA INCLUYE el bolsillo. Nunca sumes el bolsillo aparte. Caja hoy = saldo del último extracto + movimientos posteriores; los traslados bolsillo↔cuenta son internos.
- **No contar dos veces**: las compras con tarjeta cuentan el día de la compra; el pago de la tarjeta, los avances, los traslados entre cuentas propias y los rediferidos son "Interno".
- **Créditos**: los desembolsos son "Financiamiento" (no ingreso); los prepagos de créditos son "Deuda / Prepago" y van aparte de las cuotas.
- **Nómina**: si le descuentan libranzas o aportes antes de que llegue el sueldo, el salario real es mayor que lo que llega; configúralo en `libranzas_nomina`.
- **El documento del usuario** solo sirve para detectar traslados propios con el patrón "BANCOLOMBIA <doc>": Davivienda pone la cédula del que envía también en transferencias a terceros.
- **Comparar con la misma base**: no mezcles promedios largos con datos de un mes; el mes en curso es parcial.
- **Google Sheet**: configuración regional es_CO → las fórmulas usan ";" (make_sheet.loc lo hace).
- **Permisos de Google**: si sale `invalid_grant`, el permiso venció (app en modo prueba): publícala y corre `reautorizar.py`.
- **Privacidad**: config.json, credentials.json, token.json, data/ y pdfs/ son del usuario y nunca se comparten ni se suben a internet.

## Datos editables
`config.json` (datos personales y reglas propias), `data/pagos_config.json` (calendario de pagos), `data/suscripciones.json`, `data/deudas_config.json` (créditos activos), `data/reservas.json` (plata apartada), `data/viajes.json` (línea de tiempo), `data/plan.json` (objetivos y hoja de ruta para el Sheet "Plan y estrategia"), `data/overrides.json` (ediciones del Sheet).

## Hechos confirmados por el usuario
(Ve anotando aquí lo que el usuario confirme sobre sus movimientos: quién es quién, qué es cada pago recurrente, metas.)
