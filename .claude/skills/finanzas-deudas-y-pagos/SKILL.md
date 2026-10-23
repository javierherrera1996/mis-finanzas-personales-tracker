---
name: finanzas-deudas-y-pagos
description: Deudas, tasas y pagos del usuario. Úsala cuando pregunte por sus deudas o créditos ("¿cuánto debo?", "¿qué tasa tiene?", "¿cuánto pago de intereses?", "¿a cuál abono?", "¿cuándo termino de pagar?", "¿me conviene comprar cartera?"), por lo que tiene que pagar ("¿qué me toca pagar?", "¿qué vence esta semana?", "me pagaron, ¿qué pago?"), o quiera cambiar recordatorios del calendario o agregar un pago, factura o crédito.
---

# Deudas, tasas y pagos

## Las herramientas
| Comando | Qué da |
|---|---|
| `.venv/bin/python deudas.py` | Todas las deudas de mayor a menor tasa: saldo, tasa E.A., intereses al mes, cuota, meses que faltan y dónde abonar (👉) |
| `.venv/bin/python dia_de_pago.py --simular=AAAA-MM-DD` | Vista previa del correo del día de pago: qué pagar, qué apartar, qué sale solo y cuánto queda libre por día |
| `.venv/bin/python dia_de_pago.py --forzar` | Lo mismo con el último sueldo real |
| `.venv/bin/python calendario.py` | Sincroniza los recordatorios de Google Calendar con `data/pagos_config.json` |
| `.venv/bin/python agente.py` | Caja, pagos pendientes antes del sueldo, cuánto gastar por día |

## De dónde salen las tasas
- **Créditos Davivienda**: del extracto ("Tasa Interés Cte. Cobrada … E.A."); `actualizar.py` actualiza `tasa_ea` y saldo en `data/deudas_config.json` con cada extracto nuevo.
- **Tarjeta Davivienda**: tasa de la compra más reciente en el extracto (última columna del detalle).
- **Nu**: tasa M.V. del extracto, convertida a E.A. con (1 + M.V.)¹² − 1. También lee deuda total, pago total, mínimo, fecha límite e intereses de mora.
- **Otros créditos** (ICETEX, libranzas de otros bancos): a mano en `data/deudas_config.json`; si el usuario tiene el certificado o la tabla de amortización, calcula la tasa con ella.

## Cómo responder sobre deudas
1. Corre `deudas.py` y muestra la tabla corta (de mayor a menor tasa).
2. **Lo extra va a la deuda de MAYOR tasa** (método avalancha). Nunca recomiendes abonar a la más barata. Cada $1 M abonado ahorra ≈ $1 M × tasa E.A. de intereses al año.
3. **Tarjetas**: si paga el total cada mes, no paga intereses. Si difiere a cuotas, paga ≈ 28–30% E.A.: avísale qué compras están diferidas. Si hay **intereses de mora**, pagó tarde: díselo con la fecha límite.
4. **Compra de cartera / refinanciación**: compara la tasa nueva contra la actual y el costo total (seguros, comisiones). Solo conviene si baja la tasa de forma clara y no alarga mucho el plazo.
5. Para "¿cuándo salgo de deudas?" usa el simulador del Sheet (pestaña Proyección deudas) o simula con las cuotas y tasas de `deudas.py`.

## Pagos y recordatorios
- Todos los pagos recurrentes viven en `data/pagos_config.json` (`dia` = número o "penultimo_habil", `monto`, `como`, `automatico`, `tipo`: ingreso | ahorro | fijo | deuda | tarjeta, `buscar` = regex que lo marca como pagado, `solo_mes` para pagos de una vez).
- **Calendar**: cada pago no automático aparece como "💳 Vence: …" con aviso **3 días antes y 1 día antes** (notificación y correo), lo que se descuenta solo como "🔁 … (sale solo)", y el día del sueldo como "💰" con la lista de lo que hay que pagar en el mes. Después de cambiar `pagos_config.json`, corre `calendario.py`.
- **Día de pago**: cuando llega el sueldo, `actualizar.py` (cada hora alrededor de la fecha del sueldo) manda un correo y una notificación: "Hoy te pagaron $X · paga esto · aparta esto · te queda $Y libre ($Z por día)". Una sola vez por sueldo (`data/ultimo_aviso_pago.txt`).
- Si el usuario dice "agrega la factura de X" o "saqué un crédito": agrégalo a `pagos_config.json` (y a `deudas_config.json` si es crédito), corre `calendario.py` y confirma cómo quedó.
