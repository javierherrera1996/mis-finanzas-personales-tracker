<div align="center">

# 🧾 Mis Finanzas Personales Tracker+

**Tu agente de finanzas personales para Colombia.**
Lee los correos de tus bancos, organiza cada peso en un Google Sheet y cada lunes te dice cuánto puedes gastar por día.

*Cada peso en su lugar, sin hojas de cálculo a mano.*

![Hecho para Colombia](https://img.shields.io/badge/hecho%20para-Colombia%20🇨🇴-FCD116)
![Claude Code](https://img.shields.io/badge/funciona%20con-Claude%20Code-D97757)
![macOS](https://img.shields.io/badge/macOS-listo-111111)
![Privado](https://img.shields.io/badge/tus%20datos-se%20quedan%20en%20tu%20Mac-2E7D32)

</div>

---

## ¿Qué hace?

- 📬 **Lee tu Gmail**: alertas y extractos de Davivienda, Nu, Bancolombia, Addi… (las claves de los PDF las abre solo).
- 🗂️ **Clasifica todo**: comida, transporte, arriendo, viajes, deudas… y no cuenta dos veces los pagos de tarjeta ni los traslados entre tus cuentas.
- 📊 **Arma tu Google Sheet**: resumen mensual, gastos por categoría, calendario de pagos, suscripciones, proyección de deudas y de caja.
- 💌 **Te escribe cada lunes**: cuánto puedes gastar por día hasta el sueldo, qué tienes que pagar y en qué se te fue la plata esa semana.
- 🙋 **Te pregunta lo que no entiende**: le respondes el correo (`3: mercado`) y aprende para la próxima.
- 🔁 **Se actualiza solo** cada vez que prendes tu Mac.

## Así se ve el informe del lunes

> **Tu semana financiera — 26 oct**
>
> ### 💸 Puedes gastar **$209.000 por día** hasta el sueldo (29 oct)
> $1.673.000 libres = disponible en tu cuenta − $835.000 de pagos pendientes antes del sueldo.
>
> **Antes del sueldo tienes que pagar:** tarjeta $615.298 (25 oct) · Addi $119.900 (24 oct)
>
> **Esta semana gastaste $2.577.000** — techo semanal $2.055.000 ❌ te pasaste por $522.000
>
> **✍️ Responde este correo:** `1: mercado` · `2: préstamo a un amigo` · `Nequi: 120 mil`

*(cifras de ejemplo)*

## ¿Cómo funciona?

```mermaid
flowchart LR
    A[📬 Gmail<br/>alertas y extractos] --> B[🐍 Tu Mac<br/>lee, abre PDFs<br/>y clasifica]
    B --> C[📊 Google Sheet]
    B --> D[💌 Informe del lunes]
    B --> E[📅 Google Calendar]
    D -- "respondes el correo" --> B
    F[🤖 Claude Code] -. "te instala, te pregunta<br/>y mejora las reglas" .-> B
```

Todo corre **en tu computador** con **tu cuenta de Google**. No hay servidores de terceros ni nadie más ve tus datos.

---

## 🚀 Empieza en 3 pasos (≈ 1 hora la primera vez)

**Necesitas:** un Mac · un Gmail donde te lleguen los correos de tus bancos · [Claude Code](https://claude.com/claude-code) (plan Pro o Max).

**1. Instala Claude Code** (si no lo tienes)
```bash
curl -fsSL https://claude.ai/install.sh | bash
```

**2. Descarga Mis Finanzas Tracker+ y ábrelo con Claude**
```bash
cd ~/Documents
git clone https://github.com/javierherrera1996/mis-finanzas-personales-tracker.git
cd mis-finanzas-personales-tracker
claude
```

**3. Escríbele: `hola, instálalo`**

Eso es todo. Claude te entrevista, corre los comandos y te guía en lo que haya que hacer en el navegador.

### Lo que Claude te va a preguntar

| | Fase | Qué pasa |
|---|---|---|
| 1 | **Requisitos** | ¿Mac? ¿A qué Gmail te llegan los bancos? ¿Recibes extractos en PDF? ¿Usas billeteras como RappiCuenta, Nequi o Lulo? |
| 2 | **Tus datos** | Nombre, correo, clave de los PDF (casi siempre tu cédula), cómo te pagan y cuánto te llega, techo de gasto, si compartes gastos con alguien |
| 3 | **Google** | Te guía clic a clic para crear tu acceso a Gmail y Sheets ([detalle](docs/google-cloud.md)) |
| 4 | **Tus bancos** | Revisa tu Gmail, te muestra qué bancos te escriben y confirma cuáles cuentas son tuyas |
| 5 | **Primera corrida** | Baja tus correos, crea tu Sheet y te cuenta lo primero que encontró |
| 6 | **Clasificar** | Te pregunta qué son los movimientos que no entendió, de a 10 |
| 7 | **Lo fijo** | Créditos, arriendo, servicios, suscripciones y plata apartada |
| 8 | **Automático** | Deja todo corriendo solo y te manda un informe de prueba |
| 9 | **Plan** *(opcional)* | Tus metas del año y acceso desde Claude en el celular |

---

## 🏦 Bancos que ya lee

| Banco / billetera | Qué lee | Estado |
|---|---|---|
| **Davivienda** | Extractos de ahorros, tarjeta y créditos (PDF) + alertas | ✅ |
| **Nu** | Extractos de tarjeta (PDF) | ✅ |
| **Bancolombia** | Alertas por correo (compras, transferencias, QR) | ✅ |
| **Addi** | Extractos | ✅ |
| RappiCuenta, Nequi, Lulo, BBVA, otros | — | 🛠️ Claude lo agrega durante la instalación |

¿Tu banco no está? En la fase 4 Claude lo detecta y le escribe el lector.

## 🔒 Privacidad

- Tus datos **nunca salen de tu Mac y tu Google**.
- Estos archivos son solo tuyos y **git los ignora**: `config.json` (tus datos), `credentials.json` y `token.json` (tu acceso a Google), `data/` (tus movimientos) y `pdfs/` (tus extractos).
- **No los compartas con nadie**, ni por chat ni subiéndolos a internet.
- El acceso a Gmail es de **solo lectura**. El único correo que el sistema envía es tu informe, a ti mismo.

## 🗣️ El día a día

Abre Claude en la carpeta y háblale normal:

| Le dices | Te responde |
|---|---|
| `actualiza` | Trae lo nuevo de tus bancos y te dice qué cambió |
| `¿cuánto puedo gastar?` | Lo que tienes libre por día hasta el sueldo, con el cálculo |
| `¿cómo voy este mes?` | Gasto contra tu techo, por categoría |
| `eso de $300 mil fue el mercado` | Lo reclasifica y crea una regla |
| `mándame el informe` | El informe del lunes, ya |

O simplemente **responde el correo del lunes**.

---

<details>
<summary><b>📋 Prompts por fase</b> (si prefieres ir paso a paso en vez de "instálalo")</summary>

**1 — Instalar y configurar**
```
Lee CLAUDE.md y README.md. Corre ./instalar.sh y después crea mi config.json a partir de config.ejemplo.json preguntándome los datos uno por uno. Explícame para qué sirve cada dato.
```
**2 — Credenciales de Google**
```
Guíame paso a paso con docs/google-cloud.md para crear credentials.json con MI cuenta. Un paso a la vez, espera mi confirmación. Cuando tenga el archivo, corre reautorizar.py y dime qué hacer en el navegador.
```
**3 — Primera actualización**
```
Corre detectar_bancos.py y luego actualizar.py. Dame el enlace del Sheet, dime qué bancos me escriben que el sistema NO lee, y resúmeme cuánto me entró y cuánto gasté por mes.
```
**4 — Mis bancos**
```
Agrega los bancos o billeteras que no está leyendo (skill finanzas-nueva-fuente), empezando por los que mandan extractos en PDF.
```
**5 — Clasificar**
```
Muéstrame los movimientos más grandes sin clasificar, agrupados, y pregúntame qué son de a 10. Crea reglas con mis respuestas y regenera el Sheet.
```
**6 — Lo fijo**
```
Configura conmigo mis créditos, pagos fijos, suscripciones y plata apartada para que el Sheet tenga calendario de pagos y cuánto puedo gastar por día.
```
**7 — Automático**
```
Corre ./instalar.sh automatico, verifica el servicio y mándame un informe de ejemplo hoy.
```
**8 — Celular y plan** *(opcional)*
```
Llena data/plan.json conmigo (objetivos y hoja de ruta), corre plan_sheet.py y crea skills para claude.ai que lean mis Sheets por Google Drive.
```
</details>

<details>
<summary><b>🧯 Si algo falla</b></summary>

| Mensaje | Qué hacer |
|---|---|
| `invalid_grant` | Tu app de Google quedó en modo "Prueba" (vence cada 7 días). Publícala y corre `.venv/bin/python reautorizar.py` |
| `has not been used in project` / `SERVICE_DISABLED` | Falta habilitar esa API en Google Cloud |
| `NO ABRE` un PDF | La `clave_pdf` de config.json no es la correcta |
| No llega el informe del lunes | `tail data/revisiones.log` y `launchctl list \| grep misfinanzas` |
| Cualquier otro | Pégale el error a Claude tal cual |

Desactivar el servicio automático: `launchctl unload ~/Library/LaunchAgents/com.misfinanzas.actualizar.plist`
</details>

<details>
<summary><b>🧩 Qué hay en este repo</b></summary>

| Archivo | Para qué |
|---|---|
| `actualizar.py` | El proceso completo: correos → PDFs → clasificación → Sheet → informe |
| `build.py` | Reglas de clasificación (las tuyas van en `config.json → reglas_personales`) |
| `agente.py` | Los cálculos: caja, días al sueldo, pagos pendientes, cuánto gastar por día |
| `make_sheet.py` / `plan_sheet.py` | Los Google Sheets |
| `informe_semanal.py` / `respuestas.py` | El correo del lunes y la lectura de tus respuestas |
| `detectar_bancos.py` | Qué bancos te escriben y cuáles faltan |
| `parse_*.py` | Lectores de cada banco |
| `.claude/` | Skills y reglas para que Claude te instale y te ayude |
| `config.ejemplo.json` / `data_inicial/` | Plantillas que se llenan con tus datos |

Más detalle técnico en [docs/como-funciona.md](docs/como-funciona.md).
</details>

---

<div align="center">
<sub>Hecho con 🤖 Claude Code · Mejoras: <code>git pull</code> (tus datos no se tocan)</sub>
</div>
