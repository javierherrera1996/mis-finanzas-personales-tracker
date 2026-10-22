---
name: finanzas-clasificar
description: Incorpora lo que el usuario explica sobre sus transacciones (qué fue un pago, a quién le transfirió, qué es un ingreso, qué suscripción cancelar) para reclasificar movimientos, crear reglas nuevas y dejar el Sheet al día. Úsala cuando responda preguntas pendientes ("eso fue el curso", "esa plata me la devolvió mi mamá", "eso es un préstamo a un amigo", "esa plata fueron mis cesantías"), cuando pida buscar un movimiento ("¿cuándo y cuánto le presté a X?"), o cuando algo esté mal categorizado.
---

# Clasificar y aprender de las respuestas

Cada respuesta del usuario debe dejar el sistema más inteligente, no solo corregir un número una vez.

## Primero: respuestas libres pendientes
Al empezar, revisa `data/respuestas_libres.json` (líneas de correos del usuario que el lector automático no pudo asignar, con `revisado: false`). Interprétalas con él, aplícalas (overrides con `tipo` si es traslado interno) y márcalas `revisado: true`.

## Decide el tipo de cambio
- **Regla general** (aplica a cobros que se repiten: un comercio, una cuenta destino, un NIT): agrega o ajusta una tupla en `REGLAS` de `build.py` (regex, Tipo, Categoría, Subcategoría). Las reglas más específicas van ANTES de las genéricas (el orden importa). Tipos válidos: Ingreso, Gasto, Deuda, Financiamiento, Interno, Inversión.
- **Caso puntual** (un solo movimiento): guárdalo en `data/overrides.json` → `movimientos[<ID>] = {"categoria": ..., "nota": ...}` (el ID está en la columna ID de la pestaña Movimientos o en `data/movimientos.json`). el usuario también puede hacerlo él mismo en la columna "Categoría manual" del Sheet.
- **Respuesta a una pregunta del Sheet**: si la escribió en la columna "Tu respuesta", `sheet_sync.py` la guarda y `build.py` la aplica (texto corto = categoría, largo = nota).
- **Hecho de contexto** (quién es alguien, qué es un producto): agrégalo a la sección "Hechos confirmados" de CLAUDE.md y quita la pregunta de `data/preguntas.json`.

## Montos que se devuelven
Si alguien le devuelve plata (roomie, mamá, reembolsos), clasifica la entrada en la MISMA categoría del gasto con valor positivo para que se neteen, no como ingreso. Las palabras de subcategoría que se netean están en config.json → `netear_con` (las lee `clasificar()` de build.py); amplíala si hace falta.

## Buscar un movimiento ("¿cuánto le presté a X?")
1. Busca el nombre en `data/movimientos.json` y en `data/*.jsonl` (Bancolombia trae nombres en transferencias por llave; Davivienda NO trae el nombre del destinatario).
2. Si no aparece, haz una búsqueda puntual en Gmail por el nombre (no búsquedas amplias: el usuario rechazó una antes).
3. Si sigue sin aparecer, muéstrale las transferencias a terceros sin destino más probables (fecha, monto, banco, cuenta) y pídele mes/monto/banco aproximados.

## Después de cambiar algo
Corre `.venv/bin/python build.py` y `.venv/bin/python make_sheet.py` (o `actualizar.py`), verifica que los totales de la categoría tengan sentido, y cuéntale en 2–3 líneas qué cambió y cómo mueve sus números (gasto, ingreso, déficit).
