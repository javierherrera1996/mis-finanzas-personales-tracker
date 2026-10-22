---
name: finanzas-actualizar
description: Actualiza las finanzas personales del usuario de punta a punta (correos nuevos de bancos, extractos, clasificación, Google Sheet, preguntas, calendario e informe semanal) y resume el resultado. Úsala siempre que el usuario diga cosas como "actualiza", "corre el proceso", "trae lo nuevo", "mándame el informe", "¿qué hay nuevo en mis cuentas?", "revisa mis movimientos de esta semana", o cuando cualquier otra tarea de finanzas necesite datos al día antes de responder.
---

# Actualizar finanzas

El proceso ya está automatizado en `actualizar.py`; tu trabajo es correrlo, detectar problemas y contarle al usuario lo que importa en pocas líneas.

## Pasos
1. Desde la carpeta del proyecto corre:
   - Solo actualizar: `.venv/bin/python actualizar.py`
   - Actualizar y enviar el informe por correo + sincronizar el calendario: `.venv/bin/python actualizar.py --informe` (úsalo si pide el informe o un "ejemplo").
   Tarda 1–5 minutos (cuota de Gmail). Usa un timeout de 10 min.
2. Si falla, mira `data/actualizaciones.log` y la salida:
   - `Quota exceeded` / `rateLimitExceeded`: espera 1 minuto y vuelve a correr (fetch.py reanuda donde quedó).
   - `invalid_grant: Token has been expired or revoked`: venció el permiso de Google. Si la app de Google Cloud está en modo "Testing", vence cada 7 días: pídele publicarla (Google Auth Platform → Público/Audience → Publicar app) y luego corre `reautorizar.py` en segundo plano y pásale el enlace que imprime en `data/reautorizar.log`.
   - Pide abrir el navegador / `WSGITimeoutError`: faltan permisos de Google. No lo reintentes en bucle: genera el enlace con `flow.run_local_server(port=8765, open_browser=False, timeout_seconds=1800)` en segundo plano, pásale el enlace y espera a que diga que aprobó.
   - `SERVICE_DISABLED`: la API no está habilitada en tu proyecto de Google Cloud; dale el enlace de la consola para habilitarla.
3. Resume con `.venv/bin/python agente.py` (caja, días al sueldo, pagos pendientes, cuánto puede gastar por día, suscripciones, preguntas).

## Qué contarle (corto, en español, cifras en pesos)
- Cuánto puede gastar por día hasta el sueldo y la fecha del sueldo.
- Pagos vencidos o que vencen antes del sueldo.
- Movimientos nuevos relevantes (ingresos, gastos grandes) y si el gasto de la semana pasó el techo.
- Cuántas preguntas nuevas hay en el Sheet (pestaña Preguntas) y el enlace.
- Si llegó un extracto nuevo de crédito, el saldo nuevo de la deuda.

No le pegues la salida completa del script: tradúcela a lo que le sirve para decidir.

## Cuidado
- Si los números se ven raros (caja negativa, saltos grandes), revisa antes de reportar; las reglas de caja y de no contar dos veces están en CLAUDE.md. Para un informe importante, pide al subagente `auditor-finanzas` que verifique las cifras.
