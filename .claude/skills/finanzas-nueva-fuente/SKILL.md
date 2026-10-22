---
name: finanzas-nueva-fuente
description: Agrega una nueva fuente de datos al sistema de finanzas del usuario (un banco, billetera o tarjeta nueva como Bancolombia con extractos, Nequi, Daviplata, Lulo, RappiPay, un crédito nuevo, un comercio que manda facturas) con su lector, sus reglas y su conciliación. Úsala cuando diga "ya dejé los extractos de Bancolombia en la carpeta", "abrí una cuenta en X", "saqué un crédito nuevo", "pagué/cerré el crédito", o cuando aparezcan correos de un banco que el sistema no lee.
---

# Agregar una fuente nueva

Una fuente nueva solo vale si sus totales cuadran con los del banco; por eso la conciliación es parte del trabajo, no un extra.

## Pasos
1. **Mira ejemplos reales** antes de escribir código: 3–5 correos (en `data/*.jsonl` o con una búsqueda puntual en Gmail por remitente) o PDFs (`pdftext.py`, clave = `clave_pdf` de config.json). Anota formatos de fecha y de monto: hay bancos con "$1,234.56" y otros con "$1.234,56" o "COP1.234,56" (esto ya rompió un lector).
2. **Descarga**: agrega el remitente a la consulta de `actualizar.py` (fetch "otros") y, si trae PDF, una llamada a `attachments.py` con su carpeta en `pdfs/`.
3. **Lector**: escribe la función en `parse_otros.py` (o `parse_extractos.py` si es extracto) devolviendo dicts con `fuente, cuenta, fecha (YYYY-MM-DD), valor (negativo = sale), desc`. Ignora transacciones rechazadas.
4. **Integra** en `build.main()` y agrega reglas en `REGLAS` para que sus movimientos internos (pagos de tarjeta, traslados entre cuentas propias) queden como "Interno" y no se cuenten dos veces.
5. **Concilia**: compara lo leído con los totales del extracto (créditos, débitos, compras del mes, saldo final) por cada período. Diferencias >1% se investigan antes de seguir; muestra la tabla de conciliación al usuario.
6. **Si es un crédito**: agrégalo (o quítalo si se pagó) en `data/deudas_config.json` con sufijo del número, saldo, tasa E.A., cuota total y cuota capital+interés; si se descuenta por nómina, agrega sus filas en `LIBRANZAS_NOMINA` de build.py. El simulador de "Proyección deudas" asume 3 créditos: si cambian, ajusta make_sheet.py.
7. Corre `actualizar.py` y cuéntale qué cambió en caja, gasto e ingresos.
