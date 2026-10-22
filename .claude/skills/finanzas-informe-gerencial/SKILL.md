---
name: finanzas-informe-gerencial
description: Prepara el informe gerencial de las finanzas del usuario (resumen ejecutivo, ingresos, gastos, deudas, balance, simulación de pago, hallazgos y recomendaciones) con bases de cálculo consistentes y verificadas. Úsala cuando pida "informe gerencial", "informe del mes/trimestre", "resumen de mis finanzas para presentar", "actualiza el informe", "¿cómo voy?", o cuando quiera proyecciones de cuándo sale de deudas o cuánto puede ahorrar para un viaje.
---

# Informe gerencial

El primer informe tuvo errores de coherencia que una revisión externa encontró. Esta skill existe para que no se repitan. Antes de escribir, actualiza los datos (skill `finanzas-actualizar`).

## Reglas de coherencia (el porqué: el lector compara cifras entre secciones)
1. **Una base por tabla.** Separa siempre *flujo promedio* (por período: año anterior, año en curso, total) de *foto a una fecha* (saldo, deuda, sueldo de un mes). Nunca mezcles promedios de distintos períodos en la misma comparación; si citas el gasto del año en curso, la meta se compara contra ese mismo número.
2. **Meses parciales fuera de los promedios** (dilo en una nota).
3. **Pagos únicos aparte** (matrículas, compras grandes, pagos a familiares, renta anual): muéstralos como único, no como "$X/mes".
4. **Caja** según CLAUDE.md (el bolsillo ya está dentro del saldo de la cuenta principal). Muestra el cálculo saldo → salidas → caja.
5. **Presupuesto que cuadre peso a peso**: ingreso que llega + otros ingresos − cuotas que se pagan aparte − provisión de renta − abonos = techo de gasto. Si una recomendación usa plata (abonos, fondo de emergencia), verifica que esa plata exista hoy.
6. **Deudas**: saldo, tasa, cuota y cuántas cuotas faltan desde `data/deudas_config.json`; separa en cada cuota interés / seguros / capital (extractos de crédito); las refinanciaciones deben sumar el total de prepagos.
7. **Simulación**: usa la lógica de la pestaña "Proyección deudas" (orden por tasa, bola de nieve opcional); compara siempre contra "solo cuotas" y "a este ritmo" (si el hueco se sigue cubriendo con crédito, no hay fecha de salida).
8. **Sin destino**: di qué % del gasto no tiene destino identificado y cómo eso limita las metas por categoría.

## Estructura
Título · fecha · autor → Resumen ejecutivo (respuesta en 2–3 frases + tabla de flujo + tabla foto) → Ingresos → En qué se va el dinero (grupos esencial/discrecional/sin destino + tabla por categoría con año en curso, total y cambio) → Deudas (saldos, interés vs capital, refinanciaciones, simulación) → Balance (activos vs pasivos, lo que falta confirmar) → Evolución mensual (gráfico de ahorro/déficit) → Hallazgos y riesgos → Recomendaciones (presupuesto peso a peso + metas por rubro + decisiones de deuda) → Pendientes que cambian una conclusión.

Publícalo como documento de Claude Docs (actualiza el existente si ya hay uno) o lo que el usuario pida.

## Antes de entregar
Pídele al subagente `auditor-finanzas` que revise el borrador contra los datos (sumas, bases, caja, que las recomendaciones sean posibles). Corrige lo que encuentre y dile al usuario qué verificaste.
