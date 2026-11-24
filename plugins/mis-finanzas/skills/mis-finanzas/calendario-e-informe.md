# Recordatorios en Google Calendar e informe semanal

Lo usan "Empezar", paso 6, y "Actualización automática" de SKILL.md.

## Recordatorios en Google Calendar
El motor devuelve `calendario`: un evento mensual por pago fijo, cuota de crédito, tarjeta y sueldo, con `titulo`, `primera_fecha`, `recurrencia` (regla RRULE), `avisos_minutos_antes` y `descripcion` (el del sueldo trae la lista de lo que hay que pagar ese mes).
- Crea cada uno como evento **de todo el día** desde `primera_fecha`, que se repite con `recurrencia`, con avisos por notificación y por correo esos minutos antes (3 días y 1 día antes, a las 9:00 a. m.). Si el conector no deja poner avisos, créalo igual y dile que los active en el evento.
- **Sin duplicar**: cada descripción termina con su `id` ("mis-finanzas:pago-arriendo"). Antes de crear, busca eventos con ese id: si existe y es igual, no hagas nada; si cambió (monto, día), actualízalo; si un pago ya no está en el motor, borra su evento.
- Si la tarjeta tiene día de corte, también va un evento "✂️ Corte" sin aviso: desde el día siguiente, lo que compre se paga en el extracto siguiente.
- Sincroniza al configurar y cada vez que cambien Fijos, Créditos, tarjetas o el sueldo (no en cada actualización diaria).
- Si ya existe un evento de la versión instalada para ese pago ("Creado por tu agente de finanzas"), no crees otro.

## Informe semanal
Si lo quiere, una tarea programada **los lunes a las 7:30 a. m.** con el texto "Mándame el informe semanal de mis finanzas". Cuando corra:
1. Haz "Actualizar" completo (sin preguntas).
2. Manda por Gmail, al correo del propio usuario, `informe.asunto` y `informe.texto` **tal cual los arma el motor** (no recalcules ni cambies cifras), con el enlace del Sheet al final.
3. Si el conector no deja enviar sin que el usuario confirme, déjalo como borrador y anota en Resumen "📩 Informe del lunes listo en borradores".

El informe trae lo mismo que el de la versión instalada: cuánto puede gastar por día, qué tiene que pagar antes del sueldo, el gasto de la semana y desde el último sueldo, los próximos pagos, las deudas de mayor a menor tasa con dónde abonar y los movimientos "¿qué fue esto?". Además, lo que descubriste esa semana y lo que te falta saber. Si el usuario responde el correo, sus respuestas se aplican en la siguiente actualización (paso 2).
