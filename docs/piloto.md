# Piloto de CHARLIE con personas reales

Las pruebas automáticas (`tests/test_usuarios_simulados.py`) pasan cinco personas inventadas por todo el recorrido:
estudiante sin sueldo, alguien con mucho movimiento, alguien sin alertas, alguien solo con Davivienda y alguien con
varias deudas. Eso prueba el motor. Lo que no prueban es cómo se comporta Claude con una persona de verdad en
claude.ai. Para eso, este piloto.

## A quién
5 personas, distintas entre sí: 2 "simples" (una o dos cuentas, sin deudas), 1 con tarjeta y crédito, 1 con mucho
movimiento y 1 cuyo banco no le manda alertas. Todas con Claude Pro o Max.

## Qué hace cada una (unos 30 minutos, con Javier mirando si se puede)
1. Instala CHARLIE con la guía, sin ayuda. **Se mide:** minutos hasta tener el plugin instalado y dónde se trabó.
2. Escribe `/charlie:empezar`. **Se mide:** minutos hasta ver "Lo que vi"; minutos hasta el resumen financiero;
   cuántas alertas leyó contra cuántas hay en su Gmail ese periodo; si pudo crear el Sheet.
3. Responde las preguntas numeradas. **Se mide:** cuántas entendió sin ayuda.
4. Hace tres preguntas suyas, al menos una de "¿y si…?". **Se mide:** si la respuesta usó una simulación del motor y si la
   persona la entendió y la encontró útil (1 a 5).
5. Pide su tablero (`/charlie:tablero`). **Se mide:** si se publicó y si lo abre en el celular.
6. Deja programada la actualización diaria. **Se mide:** si al día siguiente corrió (Avisos/Correos del Sheet).

## Al cabo de una semana
- ¿Corrieron las actualizaciones? ¿Completó la historia hacia atrás (Perfil → Historia desde)?
- ¿Llegaron avisos? ¿Alguno falso (algo que ya había pagado)?
- ¿Volvió a preguntarle algo a CHARLIE por su cuenta? (Lo más importante: la conversación es el producto.)
- Tres preguntas: ¿qué te sirvió?, ¿qué te sobró?, ¿pagarías por esto y cuánto?

## Cuándo se da por bueno
- 4 de 5 terminan la configuración solos, en menos de 20 minutos.
- Lee al menos el 95 % de las alertas del periodo y no inventa cifras.
- 4 de 5 hacen al menos una pregunta o simulación por su cuenta durante la semana.
- Ningún aviso falso de "atrasado".

## Cómo se registra
Al terminar la configuración, CHARLIE pregunta si la persona se quiere anotar en la lista de usuarios (con su
autorización; ver `privacidad.md`). Los que acepten aparecen en el Sheet "Usuarios CHARLIE" de Javier. Las mediciones de
arriba van en una pestaña "Piloto" de ese mismo Sheet, a mano.
