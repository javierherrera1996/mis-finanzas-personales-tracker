"""Actualización completa en un paso:
  1) guarda tus ediciones del Sheet (categoría manual, notas, respuestas)
  2) baja solo los correos nuevos (Davivienda, Nu, Bancolombia, PSE, servicios)
  3) baja y abre los PDF nuevos (extractos) con tu cédula
  4) actualiza los saldos de los créditos con el extracto más reciente
  5) recalcula todos los movimientos y regenera el Google Sheet
Uso:  .venv/bin/python actualizar.py
"""
import datetime, glob, json, os, socket, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
PY = os.path.join(HERE, ".venv", "bin", "python")
LOG = "data/actualizaciones.log"


def run(*args):
    r = subprocess.run([PY, *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"Falló {' '.join(args)}:\n{r.stderr[-2000:]}")
    return r.stdout.strip()


def desde(path, dias=3):
    """Fecha (YYYY/MM/DD) desde la que hay que buscar correos nuevos."""
    if not os.path.exists(path): return "2025/01/01"
    ult = max(json.loads(l)["date"] for l in open(path))
    return (datetime.date.fromtimestamp(ult) - datetime.timedelta(days=dias)).strftime("%Y/%m/%d")


MARCA = "data/ultimo_informe.txt"   # semana ISO del último informe enviado con éxito
MARCA_DIA = "data/ultima_actualizacion.txt"   # fecha de la última actualización completa (Sheets al día para Claude del celular)


def toca_dia_pago():
    """Alrededor del día del sueldo (1 día antes a 2 después), si aún no se avisó, revisa cada hora si ya llegó."""
    import agente
    hoy = datetime.date.today()
    cerca = any(-1 <= (hoy - p).days <= 2 for p in (agente.ultimo_pago(hoy), agente.proximo_pago(hoy)))
    if not cerca: return False
    aviso = "data/ultimo_aviso_pago.txt"
    if os.path.exists(aviso) and (hoy - datetime.date.fromtimestamp(os.path.getmtime(aviso))).days <= 3: return False   # ya se avisó este sueldo
    marca = "data/ultima_revision_pago.txt"
    if os.path.exists(marca) and time.time() - os.path.getmtime(marca) < 3600: return False
    open(marca, "w").write(datetime.datetime.now().isoformat())
    return True


def toca_diaria():
    """True si hoy todavía no se actualizaron los Sheets (la primera vez que el Mac corre el servicio en el día)."""
    return not os.path.exists(MARCA_DIA) or open(MARCA_DIA).read().strip() != datetime.date.today().isoformat()


def hay_internet(espera_max=900):
    """Espera hasta 15 min a que el Mac tenga red (al despertar el wifi tarda en conectar)."""
    t = time.time()
    while time.time() - t < espera_max:
        try:
            socket.create_connection(("oauth2.googleapis.com", 443), timeout=5).close()
            return True
        except OSError:
            time.sleep(30)
    return False


def avisar(texto, limitar_horas=0):
    """Notificación del Mac. Con limitar_horas no repite el aviso más de una vez en ese lapso."""
    marca = "data/ultimo_aviso.txt"
    if limitar_horas and os.path.exists(marca) and time.time() - os.path.getmtime(marca) < limitar_horas * 3600:
        return
    open(marca, "w").write(texto)
    subprocess.run(["osascript", "-e", f'display notification "{texto}" with title "Finanzas"'], capture_output=True)


def semana_actual():
    y, w, _ = datetime.date.today().isocalendar()
    return f"{y}-W{w:02d}"


def toca_semanal():
    """True si ya pasó el lunes 7:00 de esta semana y aún no se envió el informe de esta semana."""
    ahora = datetime.datetime.now()
    lunes7 = datetime.datetime.combine(ahora.date() - datetime.timedelta(days=ahora.weekday()), datetime.time(7, 0))
    hecho = open(MARCA).read().strip() if os.path.exists(MARCA) else ""
    return ahora >= lunes7 and hecho != semana_actual()


def main():
    t0 = datetime.datetime.now()
    antes = len(json.load(open("data/movimientos.json"))) if os.path.exists("data/movimientos.json") else 0

    print("1/5 Guardando tus ediciones del Sheet…"); print(run("sheet_sync.py"))

    print("2/5 Bajando correos nuevos…")
    print(run("fetch.py", "davivienda", f"after:{desde('data/davivienda.jsonl')} from:davivienda.com"))
    print(run("fetch.py", "otros", f"after:{desde('data/otros.jsonl')} (from:nu.com.co OR from:addi.com OR from:achcolombia.com.co OR "
                                   "from:notificacionesbancolombia.com OR from:bancolombia.com.co OR from:nequi.com.co OR "
                                   "from:claro.com.co OR from:enel.com OR from:placetopay.com OR from:wompi.co OR from:bold.co)"))

    print("3/5 Bajando y abriendo extractos nuevos…")
    run("attachments.py", "data/davivienda.jsonl", "bancodavivienda@", "pdfs/davivienda")
    run("attachments.py", "data/otros.jsonl", r"nu@nu\.com\.co|soynu", "pdfs/nu")
    run("attachments.py", "data/otros.jsonl", r"addi\.com", "pdfs/addi")
    nuevos = [p for p in glob.glob("pdfs/*/*.pdf") if not os.path.exists(p[:-4] + ".txt")]
    if nuevos: run("pdftext.py", *nuevos)
    print(f"   {len(nuevos)} PDF nuevos")

    print("4/5 Actualizando saldos de créditos…")
    from parse_creditos import creditos
    cfg = json.load(open("data/deudas_config.json")); sal = creditos()
    for c in cfg["creditos"]:
        for num, d in sal.items():
            if num.endswith(c["sufijo"]) and d["fecha"] > c["fecha_saldo"]:
                print(f"   {c['nombre']}: {c['saldo']:,.0f} ({c['fecha_saldo']}) -> {d['saldo']:,.0f} ({d['fecha']})")
                c["saldo"], c["fecha_saldo"] = round(d["saldo"]), d["fecha"]
            if num.endswith(c["sufijo"]) and d.get("tasa_ea") and abs(d["tasa_ea"] - c.get("tasa_ea", 0)) > 0.0001:
                print(f"   {c['nombre']}: tasa {c.get('tasa_ea', 0):.2%} -> {d['tasa_ea']:.2%} (según el extracto)")
                c["tasa_ea"] = round(d["tasa_ea"], 4)
    json.dump(cfg, open("data/deudas_config.json", "w"), ensure_ascii=False, indent=1)

    print("5/5 Recalculando, buscando qué preguntarte y regenerando el Sheet…")
    run("build.py")
    from agente import nuevas_preguntas
    print(f"   {nuevas_preguntas(json.load(open('data/movimientos.json')))} preguntas nuevas")
    url = run("make_sheet.py").splitlines()[-1]
    print("   Plan y estrategia:", run("plan_sheet.py").splitlines()[-1])
    print("   Contexto para Claude web:", run("contexto_doc.py").splitlines()[-1].split("· ")[-1])
    try:   # ¿llegó el sueldo? -> correo "hoy te pagaron: paga esto y te queda tanto libre" (una vez por sueldo)
        import dia_de_pago
        if dia_de_pago.revisar(): print("   💰 Llegó el sueldo: te mandé el aviso de día de pago")
    except Exception as ex:
        print("   (no se pudo revisar el día de pago:", str(ex)[:150], ")")
    open(MARCA_DIA, "w").write(datetime.date.today().isoformat())
    despues = len(json.load(open("data/movimientos.json")))
    msg = f"{t0:%Y-%m-%d %H:%M} | movimientos {antes} -> {despues} (+{despues - antes}) | {url}"
    open(LOG, "a").write(msg + "\n")
    print("Listo:", msg)
    if "--informe" in sys.argv:
        from google.oauth2.credentials import Credentials
        granted = set(Credentials.from_authorized_user_file("token.json").scopes or [])
        if "https://www.googleapis.com/auth/calendar.events" in granted: print(run("calendario.py"))
        print(run("informe_semanal.py"))
        if os.path.exists("data/whatsapp.env") and "pega_aqui" not in open("data/whatsapp.env").read():
            run("whatsapp_bot.py", "--ping")   # (opcional) WhatsApp, solo si está configurado


if __name__ == "__main__":
    semanal = "--semanal" in sys.argv          # modo automático: launchd lo llama cada hora
    if semanal:
        try:  # cada 15 min: ¿respondiste el correo del informe? -> aplicar y confirmar
            if os.path.exists("data/listas_preguntas.json") and hay_internet(60):
                from googleapiclient.discovery import build
                from auth import get_creds, SCOPES
                import respuestas
                c = get_creds(SCOPES); g = build("gmail", "v1", credentials=c)
                n = respuestas.procesar(g, g)
                if n: avisar(f"Recibí tu respuesta del correo y actualicé tu Sheet ✅")
        except Exception as ex:
            open(LOG, "a").write(f"{datetime.datetime.now():%Y-%m-%d %H:%M} | respuestas: ERROR {str(ex)[:200]}\n")
            if "invalid_grant" in str(ex):   # sin esto, el permiso vencido no avisaba hasta el lunes
                avisar("Venció el permiso de Google: abre Claude y pide 'reautorizar finanzas' (y publica la app en Google Cloud)", limitar_horas=6)
        toca = toca_semanal()
        diaria = not toca and toca_diaria()
        pago = not toca and not diaria and toca_dia_pago()
        open("data/revisiones.log", "a").write(f"{datetime.datetime.now():%Y-%m-%d %H:%M} | {'toca: corriendo' if toca else 'diaria: actualizando Sheets' if diaria else 'día de pago: ¿llegó el sueldo?' if pago else 'no toca (ya enviado o antes del lunes 7:00)'}\n")
        if not toca and not diaria and not pago: sys.exit(0)
        if toca: sys.argv.append("--informe")
    try:
        if not hay_internet():
            raise RuntimeError("sin internet después de esperar 15 min; se reintenta en 1 hora")
        main()
        if semanal and "--informe" in sys.argv:
            open(MARCA, "w").write(semana_actual())
            avisar("Informe semanal enviado a tu correo ✅")
    except Exception as e:
        open(LOG, "a").write(f"{datetime.datetime.now():%Y-%m-%d %H:%M} | ERROR {str(e)[:300]}\n")
        print("ERROR:", e)
        if semanal:
            if "invalid_grant" in str(e):
                avisar("Venció el permiso de Google: abre Claude y pide 'reautorizar finanzas'", limitar_horas=6)
            else:
                avisar("No se pudo actualizar (se reintenta solo): " + str(e)[:80].replace('"', "'"), limitar_horas=6)
        sys.exit(1)
