# Mis Finanzas Tracker+ — reglas para Claude

Sistema que lee el Gmail del usuario (alertas y extractos de bancos colombianos), consolida sus movimientos y genera un Google Sheet, un informe semanal por correo (con preguntas que se responden por correo) y recordatorios en Google Calendar. Responde en español y con cifras en pesos ($1.234.567).

## Si el sistema todavía no está configurado (no existe config.json o token.json)
Toma la iniciativa: saluda, explica en 2 líneas qué hace el sistema y arranca la **instalación guiada con la skill `instalar-finanzas`**. Es una entrevista por fases (requisitos → datos básicos → Google Cloud → detectar bancos con `detectar_bancos.py` → primera corrida → bancos que faltan → clasificar → lo fijo → automático → plan opcional). Una pregunta a la vez; tú corres los comandos, el usuario solo responde. Un hook de inicio de sesión (.claude/settings.json) te avisa si falta config.json o token.json.

## Flujo
`actualizar.py [--informe]` = sheet_sync (guarda ediciones del Sheet) → fetch (correos nuevos) → attachments + pdftext (PDF con la clave de config.json) → saldos de créditos → build.py (clasifica con REGLAS y luego transferencias.py) → agente.nuevas_preguntas → make_sheet.py → plan_sheet.py → (calendario.py + informe_semanal.py). El servicio launchd `com.misfinanzas.actualizar` corre `actualizar.py --semanal`: la primera vez del día actualiza los Sheets; los lunes después de las 7:00 manda el informe; cada 15 min lee las respuestas al correo del informe.

## Mapa de cuentas (config.json → cuentas)
Cada producto del usuario (cuenta, billetera, bolsillo, tarjeta, crédito, inversión, CDT) con su institución, tipo y terminación, aunque el sistema no lo lea. `cuentas.py` lo normaliza (si no existe "cuentas", lo arma desde las llaves viejas "davivienda"/"bancolombia"/"celulares_propios") y `config.PRODUCTOS` lo expone.
- `transferencias.py` (corre en build.py después de las REGLAS): compra de cartera → Interno; si la descripción nombra un producto PROPIO (PSE a su Trii, retiro de Littio, pago de su tarjeta en otro banco, su cuenta por número, su celular) → Interno/hacia o desde mis inversiones/pago tarjeta; empareja salidas y entradas a su nombre entre sus productos. PSE es un medio de pago, no un comercio.
- Para reconocer un producto por el NOMBRE de su institución, el movimiento debe venir de otra institución (cada banco pone su nombre en sus propias descripciones) y, si es tarjeta, crédito o banco tradicional, decir PSE/tarjeta/"Pagaste $". "Pago" a secas no basta: las transferencias de terceros también lo dicen.
- Si el sistema no reconoce un producto propio, ponle `alias` en config.json; no crees una REGLA.
- Pruebas: `python -m unittest discover -s tests` (casos reales anonimizados). Córrelas al tocar cuentas.py, transferencias.py o la caja. `tests/test_usuario_nuevo.py` corre la primera actualización completa de una usuaria nueva (sin Davivienda, sin correos y con alertas) con un Google falso: si tocas make_sheet, contexto_doc, estado_general, dia_de_pago o la plantilla de data_inicial, córrela.
- Python: el código debe correr en 3.9 (el que trae el Mac). Nada de f-strings con `\` o comillas anidadas iguales, `match`, `X | None` en anotaciones.

## Versión sin instalar (skill de claude.ai)
`claude_ai_skills/mis-finanzas/`: SKILL.md + `motor/procesar.py`. Claude trae las alertas con el conector de Gmail, el motor (los mismos agente, build, cuentas, transferencias, deudas y lectores de este repo) clasifica y calcula, y Claude lo copia a un Google Sheet del usuario; `motor/reportes.py` arma deudas, eventos de Calendar, informe semanal, análisis del gasto, descubrimientos (pestaña Notas) y lo que falta preguntar (equivalentes a deudas.py, calendario.py e informe_semanal.py, sin Google) y Claude los crea/manda con sus conectores. Tareas programadas de Cowork: actualización diaria e informe de los lunes. Catálogo de bancos y remitentes de alertas: `claude_ai_skills/mis-finanzas/bancos.md`. `python claude_ai_skills/empaquetar.py` arma `mis-finanzas.zip` copiando los módulos de la raíz: **vuelve a empaquetar cada vez que cambies un módulo del motor**. El motor no puede importar nada fuera de la librería estándar (en claude.ai no se instalan paquetes; `motor/holidays.py` reemplaza a `holidays`). `build.py` lee `data/movimientos_extra.json` (movimientos que la skill lee de bancos sin lector) y pone en cada movimiento el ID de su correo (`Correo`). El Sheet de la skill guarda los correos crudos (pestaña Correos) y Movimientos se puede rehacer desde ahí conservando las columnas del usuario (Categoría manual, Tipo manual, Tu nota). Prueba: `tests/test_skill_motor.py`.

## Deudas, tasas y día de pago
`tarjetas.py` (deuda EN VIVO de cada tarjeta = extracto + compras de las alertas − pagos; vencido y próximo pago estimado; alimenta deudas.py, agente.proximos_pagos, el informe y el día de pago), `deudas.py` (deudas de mayor a menor tasa, intereses al mes, dónde abonar; tasas leídas de extractos Davivienda y Nu), `dia_de_pago.py` (al llegar el sueldo: correo + notificación con qué pagar, qué apartar y cuánto queda libre por día; `--simular=AAAA-MM-DD` para vista previa) y `calendario.py` (eventos "💳 Vence" con aviso 3 y 1 día antes). Skill `finanzas-deudas-y-pagos`. Lo extra siempre va a la deuda de MAYOR tasa.

## Procesos que se mantienen solos (no pedirle al usuario que repita cada mes)
- **Montos**: `agente.monto_real()` toma la mediana de los últimos pagos reales (el sueldo: el último) para cada pago/cobro de `pagos_config.json`. La configuración es solo el punto de partida.
- **Pagado**: un pago cuenta como hecho si aparece desde 20 días antes del vencimiento (también si lo pagó por adelantado).
- **Cobros** (`tipo: cobro`, ej. roomie): suman a lo libre mientras no lleguen.
- **Tarjetas** en vivo (`tarjetas.py`) y **cuentas que el sistema lee** en vivo (Bancolombia ahorros, Davivienda…): saldo confirmado una vez (o extracto) + alertas, sin vencer (`cuentas.saldos`).
- **Cobros recurrentes nuevos**: `agente.recurrentes_nuevos()` los detecta y salen en el Doc.
- **Permiso de Google vencido**: notificación del Mac en cualquier corrida.
- `estado_general.py`: cuentas (del mapa, vía `agente.caja`), tarjetas, créditos (intereses y seguros reales del extracto), cerrados y gasto día a día vs pagos grandes.

## Reglas que ya costaron errores (no repetirlas)
- **Caja** (`agente.caja`): suma las cuentas y billeteras del mapa, cada una desde su último saldo conocido (extracto, saldo confirmado por correo o `saldo` en config.json) + sus movimientos posteriores. El saldo de una cuenta YA INCLUYE su bolsillo (Davivienda): nunca sumes el bolsillo aparte; los traslados bolsillo↔cuenta son internos. Inversiones y CDTs no son caja (van en "inversiones"). Una billetera que no se lee (Nequi, Daviplata) solo cuenta con su saldo confirmado de los últimos 7 días: lo que se le manda se asume gastado. Las cuentas sin saldo salen en "sin_saldo" y se le preguntan al usuario en el correo del lunes.
- **No contar dos veces**: las compras con tarjeta cuentan el día de la compra; el pago de la tarjeta, los avances, los traslados entre cuentas propias, la plata hacia o desde sus inversiones, las compras de cartera y los rediferidos son "Interno".
- **Créditos**: los desembolsos son "Financiamiento" (no ingreso); los prepagos de créditos son "Deuda / Prepago" y van aparte de las cuotas.
- **Nómina**: si le descuentan libranzas o aportes antes de que llegue el sueldo, el salario real es mayor que lo que llega; configúralo en `libranzas_nomina`.
- **El documento del usuario** solo sirve para detectar traslados propios con el patrón "BANCOLOMBIA <doc>": Davivienda pone la cédula del que envía también en transferencias a terceros.
- **Comparar con la misma base**: no mezcles promedios largos con datos de un mes; el mes en curso es parcial.
- **Google Sheet**: configuración regional es_CO → las fórmulas usan ";" (make_sheet.loc lo hace).
- **Permisos de Google**: si sale `invalid_grant`, el permiso venció (app en modo prueba): publícala y corre `reautorizar.py`.
- **Privacidad**: config.json, credentials.json, token.json, data/ y pdfs/ son del usuario y nunca se comparten ni se suben a internet.

## Datos editables
`config.json` (datos personales, mapa de cuentas y reglas propias), `data/pagos_config.json` (calendario de pagos; léelo con `agente.pagos_config()`, que toma el día y el monto del sueldo de `config.json → sueldo`), `data/suscripciones.json`, `data/deudas_config.json` (créditos activos), `data/reservas.json` (plata apartada), `data/viajes.json` (línea de tiempo), `data/plan.json` (objetivos y hoja de ruta para el Sheet "Plan y estrategia"), `data/overrides.json` (ediciones del Sheet).

## Hechos confirmados por el usuario
(Ve anotando aquí lo que el usuario confirme sobre sus movimientos: quién es quién, qué es cada pago recurrente, metas.)
