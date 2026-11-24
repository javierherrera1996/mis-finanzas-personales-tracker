# Modo prueba y versión instalada

Lo usa "Empezar", paso 0, de SKILL.md.

## Probar desde cero
Para probar la skill como un usuario nuevo, aunque tenga la versión instalada o ya te haya contado cosas:
- **No leas** el Doc "Mi economía — contexto para Claude", ni el Sheet "Finanzas Personales…", ni las Notas de otro Sheet, ni uses lo que recuerdes de él (memoria, otras conversaciones, otras skills). Solo Gmail y lo que te conteste en esta configuración.
- Si ya existe un "Mis finanzas", pregúntale si lo renombras a "Mis finanzas (anterior AAAA-MM-DD)" y crea uno nuevo.
- Haz la configuración completa ("Empezar", pasos 1 a 8) sin saltarte preguntas.
- No crees eventos de Calendar, ni el informe semanal, ni mandes correos de avisos si tiene la versión instalada (ya los recibe); en el paso 7 ofrece solo actualizar cada mañana, y en el paso 9b de Actualizar escribe la memoria de Avisos pero no mandes el correo.
- Anota en Notas "Modo prueba: configurado desde cero el AAAA-MM-DD".

## Si ya tiene la versión instalada
Hay una versión de este sistema que corre en el computador del usuario (con Claude Code). Si la tiene, ya hay un registro completo, con extractos en PDF y años de historia; no lo dupliques. Señales (búscalas en Drive y Gmail):
- un Google Doc "Mi economía — contexto para Claude" (se actualiza solo cada día: mira la fecha de "Actualizado" al inicio);
- un Google Sheet que empieza por "Finanzas Personales";
- correos del propio usuario en las últimas dos semanas con "[Fin-" en el asunto (su informe de los lunes) o que empiezan por "💰 Te pagaron:" (su aviso del día de pago, que trae sueldo, pagos fijos y deudas);
- eventos de Calendar cuya descripción dice "Creado por tu agente de finanzas".

Si encuentras alguna, dile qué viste (con la fecha de la última actualización) y pregúntale en una encuesta (cuatro opciones):
- **Usar la que ya tengo** (recomendado si está al día): no crees nada. Para responder, lee el Doc completo (ahí está todo: caja, pagos, deudas, gastos, hechos confirmados) y, si hace falta detalle, el Sheet. Las actualizaciones, el calendario y el informe ya los hace su computador. Si el Doc tiene más de 3 días, avísale que prenda el computador.
- **Pasarme a la versión sin instalar**: crea "Mis finanzas", pero llénalo con lo que ya dice el Doc (sueldo y lo apartado → Perfil; cuentas y saldos, incluido el del bolsillo → Cuentas; tarjetas, créditos con tasas, pagos fijos, reglas y hechos confirmados → Cuentas, Créditos, Fijos, Reglas y Notas), así no tiene que contestar todo otra vez; pregunta solo lo que falte. **No copies movimientos del Doc a Movimientos**: los movimientos salen solo de Correos con el motor; si los copias, en la primera actualización entran otra vez y quedan duplicados. Si ya hay filas con ID "doc-…" en Movimientos, bórralas antes de actualizar. Recuérdale apagar en su computador el servicio automático, para no recibir dos informes ni tener dos recordatorios por pago.
- **Probar las dos**: crea "Mis finanzas" igual que arriba, pero no crees eventos de Calendar, ni el informe semanal, ni mandes correos de avisos (ya los tiene): en el paso 9b escribe la memoria de Avisos sin mandar el correo.
- **Probar desde cero (como usuario nuevo)**: sigue "Probar desde cero"; no uses nada de lo que dice el Doc.

Aunque elija pasarse, en Calendar no crees un evento si ya hay uno de la versión instalada para el mismo pago.
