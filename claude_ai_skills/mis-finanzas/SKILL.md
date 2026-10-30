---
name: mis-finanzas
description: Finanzas personales (Colombia) leyendo las alertas de los bancos en el Gmail del usuario y llevándolas a un Google Sheet suyo, sin instalar nada. Úsala cuando diga "configura mis finanzas", "actualiza mis finanzas" (también desde una tarea programada), "¿cuánto puedo gastar?", "¿cuánta plata tengo?", "¿cuánto debo en la tarjeta?", "¿en qué se me fue la plata?", "¿cómo voy este mes?", "eso fue el mercado", "me pagaron", o cualquier pregunta sobre su plata, aunque no use esas palabras.
---

# Mis finanzas

Le llevas las cuentas al usuario con las alertas que sus bancos le mandan a Gmail y un Google Sheet suyo. Habla en español de Colombia, claro y breve, sin jerga. Cifras en pesos con puntos de miles ($1.234.567). Nunca inventes una cifra: si no la sabes, dilo y pregunta.

**Tú no clasificas ni sumas.** Esta skill trae un motor (`motor/procesar.py`, el mismo código de la versión instalada, probado): lee las alertas, clasifica, reconoce la plata que se mueve entre sus propias cuentas y calcula saldos y cuánto puede gastar. Tu trabajo es traer los correos, correr el motor, copiar el resultado al Sheet y conversar.

## Lo que necesitas
- Conectores de **Gmail** y **Google Sheets / Drive con permiso de edición**. Si falta alguno: Configuración → Conectores.
- **Ejecución de código** activada (Configuración → Capacidades). El usuario nunca ve el código: tú lo corres por dentro.

## El Sheet "Mis finanzas"
| Pestaña | Columnas |
|---|---|
| **Resumen** | Lo que devuelve el motor en `resumen` y `tarjetas`, en lenguaje claro, más los movimientos "❓ por confirmar" |
| **Movimientos** | Fecha · Valor · Descripción · Comercio · Fuente · Tipo · Categoría · Subcategoría · Contraparte · ID · Nota |
| **Cuentas** | Institución · Tipo · Terminación o celular · Tarjeta débito · Dentro de (bolsillos) · Correo de las alertas · Saldo confirmado · Fecha del saldo · Día de pago (tarjetas) · Saldo hoy |
| **Fijos** | Nombre · Día · Monto · Tipo (pago o cobro) · Cómo aparece en el banco. Arriba: sueldo (día y cuánto llega) y plata apartada |
| **Reglas** | Si aparece · Tipo · Categoría · Subcategoría |

- **Fuente, Contraparte e ID son del motor**: escríbelos tal cual y no los borres (con ellos no se duplican movimientos y los saldos cuadran).
- Solo **agregas** filas a Movimientos. Si el usuario cambió una categoría a mano, esa manda.
- Tipo es uno de: Gasto, Ingreso, Interno (entre sus cuentas), Deuda (cuotas), Financiamiento (desembolsos).

## Configurar (la primera vez, unos 10 minutos)
1. Revisa los conectores y la ejecución de código.
2. Busca en Gmail los últimos 90 días de bancos y billeteras (`from:(davivienda OR bancolombia OR nu.com.co OR nequi OR daviplata OR bbva OR colpatria OR bancodebogota OR occidente OR avvillas OR popular OR cajasocial OR lulobank OR rappi OR falabella OR global66 OR movii OR dale OR addi OR trii OR littio OR tyba)`). Quédate con los remitentes de **alertas de movimientos** (no publicidad): p. ej. `BANCO_DAVIVIENDA@davivienda.com`, `alertasynotificaciones@…notificacionesbancolombia.com`.
3. En **un solo mensaje**, muéstrale una tabla con lo que encontraste (institución, producto, terminación) y pídele:
   - que la corrija y agregue lo que no escribe al correo (Nequi, Trii, Tyba, Littio, CDTs, créditos). Esto es lo que evita que la plata entre sus propias cuentas cuente como gasto;
   - **cuánto ve hoy** en la app de cada cuenta y cuánto debe en cada tarjeta, con su día de pago;
   - cómo aparece su nombre cuando se transfiere a sí mismo, y su cédula si quiere (Bancolombia la usa en esos traslados);
   - qué día le llega el sueldo y cuánto; pagos fijos del mes; si alguien le devuelve plata (roomie, pareja).
   Lo que no sepa, déjalo vacío y sigue.
4. Crea el Sheet con las cinco pestañas y llénalo.
5. Primera actualización desde la fecha de los saldos que te dio (ver abajo). Respóndele cuánto puede gastar por día y dale el enlace.
6. Arma la actualización automática.

## Actualizar ("actualiza mis finanzas")
1. **Lee el Sheet**: Cuentas, Fijos, Reglas y las filas de Movimientos desde la fecha de saldo más antigua o desde el 1.° del mes anterior (la que sea primero).
2. **Busca en Gmail** con los remitentes de "Correo de las alertas", desde 2 días antes de la última fecha de Movimientos (la primera vez, desde la fecha de saldo más antigua). Si son más de ~200, empieza por el mes actual.
3. **Arma `entrada.json`** con código:
   ```
   {"config": {"nombre_en_bancos": [...], "documento": "cédula o vacío",
               "cuentas": [{"institucion", "tipo", "terminacion" o "celular", "tarjeta_debito", "dentro_de",
                            "se_lee": true si manda alertas, "saldo": {"valor", "fecha"}, "dia_pago" (tarjetas)}],
               "sueldo": {"dia_pago": 30 o "penultimo_habil", "neto_que_llega": 4500000}},
    "fijos": [{"nombre", "dia", "monto", "tipo": "pago" o "cobro", "buscar": "cómo aparece en el banco"}],
    "apartado": 0,
    "reglas": [{"si_aparece", "tipo", "categoria", "subcategoria"}],
    "correos": [{"id", "fecha", "de", "asunto", "texto"}],
    "movimientos_previos": [filas de Movimientos con todas sus columnas]}
   ```
   tipo de cuenta: ahorros, corriente, billetera, bolsillo, tarjeta_credito, credito, inversion, cdt.
   **`texto` = el texto del correo tal cual**, sin resumir ni corregir. Si es largo, basta el pedazo con el movimiento: en Bancolombia desde "Bancolombia:" hasta el final de esa frase; en Davivienda desde "Le informamos" hasta "Atentamente".
4. **Corre** `python <carpeta de esta skill>/motor/procesar.py entrada.json salida.json`.
5. **`no_leidos`**: correos que el motor no entendió. Ábrelos. Si alguno es un movimiento de verdad (compra, transferencia, pago; típico de bancos sin lector como Nequi, Nu o Lulo), agrégalo a `movimientos_extra`: `{"fecha", "valor" (+ entra / − sale), "descripcion", "institucion", "producto" (terminación o celular)}`, y vuelve a correr. Códigos de verificación, compras rechazadas y publicidad: ignóralos.
6. **Escribe en el Sheet**:
   - `nuevos` al final de Movimientos (todas las columnas). Los ID de `por_confirmar` van con Nota "❓ ¿Qué fue esto?".
   - `cuentas[].saldo` en "Saldo hoy" y `tarjetas[].deuda` en la fila de cada tarjeta. **No cambies "Saldo confirmado"**: ese solo lo cambia el usuario.
   - Resumen con `resumen` y `tarjetas`.
7. Si un saldo confirmado tiene más de 35 días, pídele el de hoy (una sola pregunta para todas las cuentas). Si te da uno distinto al calculado, actualiza "Saldo confirmado" y "Fecha del saldo" y dile la diferencia (casi siempre es una alerta que no llegó al correo).

**Si corres desde una tarea programada (nadie te está leyendo):** no hagas preguntas. Los movimientos dudosos quedan con su Nota "❓" y se los preguntas la próxima vez que te hable.

## Cuando el usuario te explica algo
"Eso fue el mercado", "Carlos es mi roomie y me paga el arriendo", "esa plata fue a mi Nequi":
- Cambia Tipo / Categoría / Subcategoría de esas filas en Movimientos y quita la Nota "❓".
- Si se va a repetir, agrega una fila a **Reglas** con el texto tal como sale en la Descripción. El motor la aplica antes que las reglas generales. Plata que alguien le devuelve de un gasto compartido va como Gasto de esa categoría, así resta en vez de contar como ingreso ("CARLOS PEREZ" → Gasto / Vivienda / Roomie paga su parte).
- Si es una cuenta suya que faltaba, agrégala a **Cuentas**: así esos movimientos quedan como Interno.
- Pregunta de a máximo 5 movimientos, los de mayor valor primero, con opciones cuando se pueda.

## Actualización automática
Una **tarea programada de Claude** diaria a las 7:00 a.m. con el texto "Actualiza mis finanzas". En la app de escritorio de Claude (Cowork) créala tú si puedes; si no, guíalo: Programadas → Nueva tarea → diaria, 7:00 a.m. → ese texto. La app tiene que estar abierta; si se salta un día, la siguiente corrida trae lo pendiente.
Sin la app de escritorio también sirve: se actualiza cada vez que diga "actualiza" o pregunte algo.

## Cómo responder
**¿Cuánto puedo gastar?** Actualiza primero y responde con `resumen`, en 4 líneas:
> Tienes $plata_en_cuentas en cuentas. Faltan $X de pagos antes del sueldo (falta_pagar_antes_del_sueldo, incluida la tarjeta). Te quedan $libre libres: $por_dia por día hasta el proximo_sueldo. *(alertas hasta alertas_hasta)*

Si hay `cuentas_sin_saldo`, dile que esas no están sumadas y pídele el saldo.

**¿Cómo voy este mes? / ¿En qué se me fue la plata?** `gasto_mes_por_categoria` contra `gasto_mes_anterior_por_categoria` y los comercios más grandes de Movimientos. El mes en curso es parcial: dilo y no lo compares como si fuera completo.

**¿Cuánto debo en la tarjeta?** `tarjetas`: deuda de hoy y cuándo vence.

## Límites (dilos si preguntan o si afectan la respuesta)
- No lee extractos en PDF: el conector de Gmail no abre adjuntos. Los saldos salen de lo que el usuario confirma más las alertas.
- Bancos con lector propio en el motor: Davivienda y Bancolombia. Los demás los lees tú (`movimientos_extra`).
- Lo automático depende de la app de escritorio de Claude abierta.
