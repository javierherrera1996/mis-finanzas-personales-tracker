# Bancos y billeteras: dónde buscar sus alertas

**Lector "motor"**: el motor entiende sus alertas solo. **Lector "tú"**: abres la alerta y la pasas en `movimientos_extra`.
**Remitente "confirmado"**: lo vimos en alertas reales. **"Por confirmar"**: busca por la palabra y quédate con el remitente cuyos correos traen un valor y una terminación (no publicidad); anótalo en Cuentas → "Correo de las alertas".

| Institución | Buscar en Gmail | Remitente | Lector | Nota |
|---|---|---|---|---|
| Bancolombia | `from:notificacionesbancolombia.com` | confirmado: `alertasynotificaciones@` (varios subdominios: an., ayn.) | motor | El mismo remitente manda códigos de verificación: el motor los ignora |
| Davivienda | `from:BANCO_DAVIVIENDA@davivienda.com` | confirmado | motor | Otros remitentes de Davivienda son publicidad o extractos |
| Nu | `from:nu.com.co` | confirmado: `nu@nu.com.co` | tú | La tarjeta Nu manda extracto mensual en PDF, no una alerta por compra: sus compras no se ven |
| RappiPay / RappiCard | `from:rappipay` | confirmado: `rappipay@hello.rappi.com.co` | tú | Los recibos de Rappi (pedidos) no son movimientos del banco |
| Nequi | `from:nequi` | por confirmar | tú | Muchas personas no reciben alertas de Nequi al correo: pide el saldo a mano |
| Daviplata | `from:daviplata` | por confirmar | tú | Igual que Nequi |
| BBVA | `from:bbva` | por confirmar | tú | |
| Banco de Bogotá | `from:bancodebogota` | por confirmar | tú | |
| Scotiabank Colpatria | `from:colpatria OR from:scotiabank` | por confirmar | tú | |
| Banco de Occidente | `from:bancodeoccidente` | por confirmar | tú | |
| Banco Popular | `from:bancopopular` | por confirmar | tú | |
| AV Villas | `from:avvillas` | por confirmar | tú | |
| Banco Caja Social | `from:bancocajasocial` | por confirmar | tú | |
| Itaú | `from:itau` | por confirmar | tú | |
| Banco Falabella | `from:bancofalabella` | por confirmar | tú | |
| Lulo Bank | `from:lulobank` | por confirmar | tú | |
| Global66 | `from:global66` | por confirmar | tú | |
| Movii / dale! | `from:movii OR from:dale` | por confirmar | tú | |
| Addi | `from:addi.com` | por confirmar | tú | Compras a cuotas |
| Trii, Tyba, Littio, Hapi, CDTs | — | — | — | Casi nunca mandan una alerta por movimiento: van en Cuentas con su saldo a mano. La plata que les manda desde el banco queda como Interno gracias al mapa |

**No son movimientos** (no los pases como correos ni como extra): comprobantes de PSE (`serviciopse@achcolombia.com.co`), recibos de comercios (Uber, Rappi, Amazon, aerolíneas), publicidad, extractos. Sirven para saber qué fue un cobro, no para sumarlo otra vez.

**Si eligió un banco y no aparece ninguna alerta**, dile que active en la app de ese banco las notificaciones de movimientos por correo, a este mismo Gmail. Mientras tanto, esa cuenta queda con el saldo que te dé.
