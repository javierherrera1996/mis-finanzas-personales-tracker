---
name: finanzas-cuanto-puedo-gastar
description: Responde cuánta plata tiene el usuario hoy y cuánto puede gastar hasta su próximo sueldo (por día y por semana), descontando lo que falta pagar. Úsala cuando pregunte "¿cuánto tengo en caja?", "¿cuánto puedo gastar?", "¿me alcanza para X?", "¿cuánto me queda hasta el sueldo?", "falta pagar el inglés y el teatro", "tengo un viaje / voy a gastar X", o cualquier duda sobre su liquidez actual, aunque no use esas palabras exactas.
---

# ¿Cuánto tengo y cuánto puedo gastar?

Esta pregunta ya salió mal una vez (se sumó el bolsillo dos veces), así que sigue el método al pie de la letra y muestra el cálculo.

## Método
1. Si los datos tienen más de 2 días, corre primero la skill `finanzas-actualizar` (o `actualizar.py`).
2. Corre `.venv/bin/python agente.py`. Te da:
   - `caja.total` = saldo del último extracto (cuenta principal de config.json, que YA incluye el bolsillo, + cuenta AFC si existe) + movimientos posteriores a ese extracto.
   - `caja.bolsillo` = bolsillo: `reservado_inversion` (lo apartado en data/reservas.json) + `emergencia` (el resto). Nada de eso se cuenta como gastable.
   - `caja.disponible` = total − bolsillo.
   - `proximo_pago` = día del sueldo según config.json (por defecto penúltimo día hábil, con festivos de Colombia).
   - `por_pagar_antes_del_sueldo` = pagos no automáticos, no hechos, que vencen antes del sueldo (incluye vencidos).
   - `libre` y `por_dia`.
3. Agrega lo que el usuario mencione que falta pagar o gastar (p. ej. "el teatro", "el viaje"): réstalo de `libre`. Si no sabes el monto, pregúntalo o búscalo en sus movimientos/correos y dilo.
4. Suma ingresos que él diga que van a entrar antes del sueldo (p. ej. "$4 M de este mes") solo si lo confirma, y dilo explícitamente.

## Cómo responder
Una tabla corta con el cálculo (saldo → menos salidas → menos pendientes → libre), luego **por día** y **por semana** hasta la fecha del sueldo. Aclara qué NO está incluido: Bancolombia, Nu y Daviplata (las alertas no traen saldo), y que lo reservado en data/reservas.json no es gastable.

Si pregunta por el siguiente ciclo (después del sueldo): sueldo que llega (config.json) − cuotas que paga aparte − provisión de renta − pagos fijos de data/pagos_config.json = gasto del día a día del mes; divídelo por los días hasta el siguiente sueldo.
