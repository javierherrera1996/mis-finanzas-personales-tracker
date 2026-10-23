---
name: instalar-finanzas
description: Instala y configura el sistema de finanzas para un usuario nuevo haciéndole una entrevista guiada (requisitos, datos personales, bancos, Google Cloud, primera corrida, clasificación, automatización). Úsala SIEMPRE que no exista config.json, o cuando el usuario diga "instálalo", "configúralo", "empecemos", "hola" en una carpeta sin configurar, o quiera rehacer la configuración.
---

# Instalación guiada

Eres quien instala el sistema con el usuario. Él NO es programador necesariamente: habla claro, en español de Colombia, sin jerga. Tú corres los comandos; él solo responde y hace lo que pasa en el navegador.

## Cómo preguntar
- **Una cosa a la vez.** Máximo 2–3 preguntas por mensaje, y solo si están relacionadas.
- Usa la herramienta de preguntas con opciones (AskUserQuestion) cuando haya opciones claras (sí/no, bancos, día de pago). Para datos libres (nombre, montos), pregunta en texto.
- Explica en una línea **para qué** sirve cada dato antes de pedirlo, y que **todo se queda en su Mac** (config.json está en .gitignore y nunca se sube).
- Lo que no sepa, déjalo vacío y sigue: lo completas después mirando sus correos.
- Al final de cada fase, resume en 2–3 líneas qué quedó listo y qué sigue. Lleva el progreso con una lista de tareas.

## Fase 0 — Requisitos (pregunta antes de instalar nada)
1. ¿Usa Mac? (si es Windows/Linux: el sistema corre, pero el servicio automático usa launchd de Mac; avísale que esa parte habrá que adaptarla).
2. ¿Las alertas y extractos de sus bancos le llegan a un **Gmail**? ¿A cuál correo? (si le llegan a otro correo, no funciona sin redirigirlos).
3. ¿Le llegan los **extractos en PDF** por correo o solo alertas? (con extractos el sistema sabe saldos; con solo alertas, no).
4. ¿Tiene **billeteras o cuentas digitales**: RappiCuenta, Nequi, Daviplata, Lulo, cuenta Nu, Global66, MOVii, dale!? ¿Le mandan extractos o comprobantes por correo? Muchas mandan extracto mensual en PDF (RappiCuenta, Nu, Lulo) y se pueden leer igual que los de un banco; si no le llegan, dile cómo activarlos en la app (normalmente en Perfil → Extractos / Notificaciones por correo).
Luego corre `./instalar.sh` y confirma que dice "Entorno listo". Si falta Python, guíalo para instalarlo.

## Fase 1 — Datos básicos → config.json
Copia `config.ejemplo.json` a `config.json` y ve llenando:
1. **Nombre** (para los títulos del Sheet) y **correo** de Gmail (a dónde le llega el informe).
2. **Clave de los PDF**: en Colombia los extractos casi siempre se abren con la **cédula**. Pídela explicando que solo se usa localmente para abrir sus extractos. Ponla también en `documento`.
3. **Desde cuándo** quiere analizar (por defecto 1-ene-2025; más atrás = primera corrida más lenta).
4. **¿Cómo le pagan?** Empleado / independiente / ambos.
   - Empleado: ¿qué día llega el sueldo? (opciones: penúltimo día hábil, último día hábil → usa "penultimo_habil" o el número, día 15 y 30 → el número del pago principal) y **cuánto le llega a la cuenta**. ¿Le descuentan de nómina créditos (libranzas) o aportes antes de que llegue? Si sí: número del crédito, cuota y desde qué mes → `libranzas_nomina`.
   - Independiente / otros ingresos: promedio mensual aproximado → `sueldo.otros_ingresos_mes`.
5. **Techo de gasto del día a día** al mes (sin arriendo ni deudas). Si no sabe, pon un valor provisional y dile que lo ajustan cuando vean sus datos reales.
6. **¿Comparte gastos con alguien que le devuelve plata?** (roomie, pareja, familia) → nombre como aparece en las transferencias, para que esas entradas resten del gasto y no cuenten como ingreso (`reglas_personales` con la subcategoría + `netear_con`).
7. **¿Declara renta?** ¿Cuánto pagó la última vez y en qué mes? → `renta_anual` (para provisionarla).

## Fase 2 — Credenciales de Google (la parte más larga; guía paso a paso)
Sigue docs/google-cloud.md. Un paso por mensaje y espera su "listo":
proyecto nuevo → habilitar Gmail, Sheets, Drive y Calendar API → pantalla de consentimiento (Externo, sus datos) → agregar los 5 permisos → **PUBLICAR la app** (insiste: en modo prueba el permiso vence cada 7 días) → cliente "App de escritorio" → descargar JSON → renombrar a `credentials.json` en la carpeta (ofrece moverlo tú desde Descargas con `mv ~/Downloads/client_secret_*.json credentials.json`).
Luego corre `.venv/bin/python reautorizar.py` y explícale: aviso de "app no verificada" → Configuración avanzada → Ir a Finanzas Tracker → **marcar todas las casillas**. Si el navegador no abre, dale el enlace de `data/reautorizar.log`.

## Fase 3 — Detectar sus bancos (pregunta menos, confirma más)
Corre `.venv/bin/python detectar_bancos.py`. Muéstrale el resultado en una tabla corta y confirma:
1. "Estos son los bancos/billeteras que te escriben. ¿Falta alguno? ¿Alguno ya no lo usas?"
2. Con las terminaciones que aparecieron, pregunta cuáles son suyas y de qué tipo (cuenta de ahorros, tarjeta de crédito, tarjeta débito, bolsillo) → `davivienda` y `bancolombia` en config.json.
3. Sus **celulares** de Nequi/Daviplata → `celulares_propios`.
4. **Cómo aparece su nombre** en transferencias entre sus propias cuentas: búscalo tú en los correos (p. ej. "recibiste una transferencia de NOMBRE APELLIDO") y confírmalo con él → `nombre_en_bancos`.
5. Compara con lo que dijo en la Fase 0 (bancos y billeteras): si mencionó alguna que no aparece en el correo, es porque no le llegan notificaciones; ayúdale a activarlas o anótala como "sin datos".
Si usa bancos que el sistema no lee, anótalos para la Fase 5. Prioriza las que mandan **extractos en PDF** (traen todos los movimientos y el saldo).

## Fase 4 — Primera corrida
Avísale que tarda (baja correos desde la fecha elegida) y corre `.venv/bin/python actualizar.py` con timeout largo. Al terminar: enlace del Sheet, movimientos por mes (entradas, salidas), % sin clasificar, y los 3 hallazgos más llamativos. Si algo falla, arréglalo tú antes de seguir.

## Fase 5 — Bancos que faltan
Por cada banco de la Fase 3 que no se lee: usa la skill `finanzas-nueva-fuente` (lector, reglas, conciliación). Empieza por el que más movimientos tenga. Pregúntale si quiere hacerlo ya o después.

## Fase 6 — Clasificar con él
Agrupa los movimientos grandes sin clasificar ("Otros", "Transferencias a terceros") y pregúntale de a 10 qué son, con opciones cuando se pueda. Lo personal (arrendador, empleador, familia) va a `config.json → reglas_personales`; lo general, a REGLAS en build.py. Usa la skill `finanzas-clasificar`. Anota en CLAUDE.md → "Hechos confirmados por el usuario" lo que confirme.

## Fase 7 — Lo fijo
Pregunta y llena:
- **Créditos** activos: nombre, saldo, tasa E.A., cuota, día de pago, ¿se descuenta de nómina? → `data/deudas_config.json`. Corre primero `.venv/bin/python deudas.py`: las tasas de Davivienda y Nu salen solas de los extractos; pregunta solo las que falten (si no la sabe, que la busque en la app o en el certificado del crédito).
- **Tarjetas de crédito**: ¿paga el total cada mes o difiere a cuotas? Agrégalas a `pagos_config.json` con su día límite (tipo `tarjeta`).
- **Pagos fijos** del mes: arriendo, servicios, celular, administración, cursos… (día, monto, cómo se paga) → `data/pagos_config.json`.
- **Suscripciones**: confirma las detectadas y agrega las que falten → `data/suscripciones.json`.
- **Plata apartada** que no se debe gastar (ahorro, inversión) → `data/reservas.json`.
Regenera el Sheet y muéstrale "cuánto puedes gastar por día hasta el sueldo" con el cálculo, y la tabla de `deudas.py` con dónde le conviene abonar.

## Fase 8 — Automático, calendario e informe
1. Pregunta si quiere sus pagos en **Google Calendar** (avisos 3 días y 1 día antes, por notificación y correo). Si sí, corre `.venv/bin/python calendario.py` y dile que revise su calendario.
2. Explícale el **aviso de día de pago** ("hoy te pagaron: paga esto y te queda tanto libre") y muéstrale una vista previa con `.venv/bin/python dia_de_pago.py --simular=<su próximo día de pago>`. Revisa con él que lo que sale para pagar y apartar esté completo.
3. Pregunta si quiere el **informe del lunes** por correo.
4. Corre `./instalar.sh automatico`, verifica con `launchctl list | grep misfinanzas` y manda un informe de ejemplo con `.venv/bin/python actualizar.py --informe`. Explícale que puede responder ese correo con las preguntas numeradas.

## Fase 9 (opcional) — Objetivos y celular
Pregunta si quiere un plan: objetivos del año (pagar deudas, ahorrar para algo, viaje) y hoja de ruta → `data/plan.json` → `plan_sheet.py`. Si quiere consultar desde el celular: crea skills para claude.ai que lean sus Sheets por el conector de Google Drive y comprímelas.

## Cierre
Resume en una tabla qué quedó listo, los enlaces de sus Sheets y 4 frases que puede decirte en el día a día ("actualiza", "¿cuánto puedo gastar?", "eso fue el mercado", "¿cómo voy este mes?"). Recuérdale: nunca compartir config.json, credentials.json ni token.json.
