# ⚙️ Cómo funciona Mis Finanzas Tracker+

## La actualización
```bash
.venv/bin/python actualizar.py            # todo, sin informe
.venv/bin/python actualizar.py --informe  # todo + calendario + correo del lunes
```

| Paso | Archivo | Qué hace |
|---|---|---|
| 1 | `sheet_sync.py` | Guarda lo que editaste en el Sheet (categoría manual, notas, respuestas) en `data/overrides.json` |
| 2 | `fetch.py` | Baja solo los correos nuevos de tus bancos a `data/*.jsonl` |
| 3 | `attachments.py` + `pdftext.py` | Descarga los extractos en PDF y los abre con tu `clave_pdf` |
| 4 | `parse_creditos.py` | Actualiza el saldo de tus créditos con el último extracto |
| 5 | `build.py` | Une todas las fuentes y clasifica cada movimiento → `data/movimientos.json` |
| 6 | `agente.py` | Detecta lo que no entiende y lo agrega a tus preguntas |
| 7 | `make_sheet.py` | Regenera tu Google Sheet |
| 8 | `plan_sheet.py` | Regenera el Sheet "Plan y estrategia" |
| 9 | `dia_de_pago.py` | Si llegó el sueldo, el correo "hoy te pagaron" |
| 10 | `calendario.py` + `informe_semanal.py` | Recordatorios en Calendar y el correo del lunes (solo con `--informe`) |

## Automático
`./instalar.sh automatico` crea el servicio `com.misfinanzas.actualizar` (launchd), que corre `actualizar.py --semanal`:
- **La primera vez del día** que el Mac está prendido → actualiza los Sheets.
- **Los lunes después de las 7:00** → además manda el informe (una vez por semana; si el Mac estaba apagado, lo manda cuando lo prendas).
- **Cada 15 minutos** → lee si respondiste el correo del informe y aplica tus respuestas.
- **Alrededor del día del sueldo** → revisa cada hora si ya llegó para mandarte el aviso de día de pago.
- Si no hay internet espera hasta 15 min; si algo falla te avisa con una notificación del Mac.

## Pagos, día de pago y deudas
- **Calendario** (`calendario.py`, desde `data/pagos_config.json`): cada pago no automático es un evento "💳 Vence: …" con aviso **3 días antes y 1 día antes a las 9:00 a. m.** (notificación + correo). Lo que se descuenta solo aparece como "🔁 … (sale solo)". El día del sueldo es "💰 Llega el sueldo" con la lista de pagos del mes. Se sincroniza con el informe semanal o con `.venv/bin/python calendario.py`.
- **Día de pago** (`dia_de_pago.py`): alrededor de la fecha del sueldo, el servicio revisa cada hora; cuando detecta el abono (categoría Salario) te manda un correo y una notificación con qué pagar antes del próximo sueldo, qué apartar, qué sale solo y cuánto te queda libre por día. Una vez por sueldo. Vista previa: `.venv/bin/python dia_de_pago.py --simular=2026-11-30`.
- **Deudas** (`deudas.py`): une `data/deudas_config.json` con lo que leen los extractos. De los créditos Davivienda toma saldo, cuota y **tasa cobrada**; de las tarjetas Davivienda y Nu, la tasa vigente, pago total, mínimo, fecha límite e intereses de mora. Ordena de mayor a menor tasa, calcula intereses al mes y meses que faltan, y marca con 👉 dónde abonar (método avalancha). Sale en el informe del lunes, en el correo del día de pago y en la pestaña "Hoy" del Sheet del plan.

## Tu Google Sheet
| Pestaña | Qué tiene |
|---|---|
| Tablero | Gasto de cada mes contra tu techo y tus metas por categoría |
| Calendario de pagos | Qué pagar y cuándo, con estado (pagado / pendiente / vencido) |
| Suscripciones | Cuánto te cuesta cada una; marca Mantener / Cancelar / Revisar |
| Proyección deudas | Simulador: cambia el abono extra y mira cuándo sales de deudas |
| Proyección caja | Hasta cuándo alcanza la plata a tu ritmo y con tu meta |
| Resumen mensual · Evolución ingresos · Gastos por categoría · Top comercios | El análisis |
| Movimientos | Todo, con columnas para corregir la categoría y poner notas |
| Preguntas | Lo que el sistema no entendió |

Lo que escribas en las columnas de **Categoría manual**, **Tu nota** y **Tu respuesta** se conserva en cada actualización.

## Responder por correo
El informe trae hasta 10 preguntas numeradas. Responde el correo, una por línea:
```
1: mercado
2: préstamo a un amigo
Bancolombia: 850 mil
Nequi: 120 mil
```
`respuestas.py` lo lee, actualiza el Sheet y te confirma en el mismo hilo lo que entendió.

## Tus datos y reglas
| Archivo | Qué guardas ahí |
|---|---|
| `config.json` | Tus datos: correo, clave de los PDF, cuentas propias, sueldo, techo de gasto, reglas personales |
| `data/pagos_config.json` | Pagos recurrentes (día, monto, cómo se paga, texto que lo identifica) |
| `data/deudas_config.json` | Créditos activos (saldo, tasa, cuota) |
| `data/suscripciones.json` | Suscripciones a vigilar |
| `data/reservas.json` | Plata apartada que no se cuenta como gastable |
| `data/viajes.json` | Viajes y proyectos para la línea de tiempo |
| `data/plan.json` | Objetivos y hoja de ruta (Sheet "Plan y estrategia") |

## Reglas de oro (ya costaron errores)
- El saldo de la cuenta principal **ya incluye el bolsillo**: nunca sumarlo aparte.
- Las compras con tarjeta cuentan el día de la compra; **el pago de la tarjeta no es gasto** (es interno), igual que los avances y traslados entre tus cuentas.
- Un desembolso de crédito **no es ingreso**: es financiamiento.
- Si te descuentan libranzas de nómina, tu salario real es mayor que lo que llega: configúralo en `libranzas_nomina`.

## Bot de WhatsApp (opcional)
`whatsapp_bot.py` + `./instalar_whatsapp.sh` (Meta Cloud API + ngrok). Te pregunta lo pendiente por WhatsApp. Las claves van en `data/whatsapp.env` (plantilla `whatsapp.env.ejemplo`). El correo es más simple y es el canal recomendado.
