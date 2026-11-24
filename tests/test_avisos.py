"""Avisos generales (avisos.py): qué alertas salen, el ritmo (rojo cada 2 días, naranja cada 3, amarillo una vez), el
cupo de 2 correos al día, la plata que llega y que la primera vez no se manda nada. Sin Google ni archivos: la memoria
entra y sale como filas de la pestaña Avisos."""
import datetime, os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import avisos  # noqa: E402

HOY = datetime.date(2026, 11, 24)
D = lambda n: (HOY - datetime.timedelta(days=n)).isoformat()


def comp(nombre, estado, **k):
    base = {"id": f"2026-11|{nombre}", "nombre": nombre, "tipo": "pago", "periodo": "2026-11", "vence": D(5), "estado": estado,
            "monto_esperado": 150000, "pagado": 0}
    base.update(k)
    return base


def mov(valor, dias, cat="Otros ingresos", tipo="Ingreso", fuente="Bancolombia Ahorros *4455 (alerta)"):
    return {"Fecha": D(dias), "Valor": valor, "Descripción": "Transferencia recibida", "Fuente": fuente, "Tipo": tipo,
            "Categoría": cat, "Subcategoría": "", "ID": f"m{valor}{dias}"}


class Generar(unittest.TestCase):
    def test_severidades_de_compromisos_y_tarjetas(self):
        al = avisos.generar([comp("Gimnasio", "atrasado", dias_atraso=5),
                             comp("Seguro viejo", "atrasado", dias_atraso=40, periodo="2026-10"),
                             comp("Arriendo", "vence_pronto", vence=D(-2)),
                             comp("Marcado", "atrasado", dias_atraso=5, marcado_a_mano=True),
                             {"id": "2026-11|Tarjeta X", "nombre": "Tarjeta X", "tipo": "tarjeta", "estado": "vence_pronto", "vence": D(-2),
                              "falta": 800000, "estimado": True}],
                            tarjetas=[{"nombre": "Tarjeta X", "dia_pago": 25}], proximo_sueldo="2026-11-27", hoy=HOY)
        sev = {a["titulo"]: a["severidad"] for a in al}
        self.assertEqual(sev["Gimnasio de noviembre sin pagar"], "rojo")
        self.assertEqual(sev["No veo el pago de Seguro viejo de octubre"], "amarillo")
        self.assertEqual(sev["Arriendo: vence el 26-nov"], "naranja")
        self.assertFalse(any("Marcado" in t for t in sev))   # lo que el usuario marcó no se recuerda
        tc = next(a for a in al if a["de"] == "tarjetas" and "debes" in a["titulo"])
        self.assertEqual(tc["severidad"], "naranja")
        self.assertIn("DESPUÉS", tc["detalle"])   # vence el 26 y el sueldo llega el 27
        self.assertIn("estimado", tc["titulo"])
        self.assertTrue(any(a["id"].startswith("tarjetas:antes_del_sueldo") for a in al))
        self.assertEqual(al[0]["severidad"], "rojo")


class Revisar(unittest.TestCase):
    def setUp(self):
        self.rojo = {"id": "r1", "severidad": "rojo", "de": "compromisos", "titulo": "Gimnasio sin pagar", "detalle": "", "accion": ""}
        self.amarillo = {"id": "a1", "severidad": "amarillo", "de": "suscripciones", "titulo": "Netflix subió", "detalle": "", "accion": ""}
        self.naranja = {"id": "n1", "severidad": "naranja", "de": "compromisos", "titulo": "Arriendo vence", "detalle": "", "accion": ""}

    def memoria(self, alertas=(), envios=(), ingresos=()):
        f = [{"tipo": "inicio", "fecha": D(30)}]
        f += [{"tipo": "alerta", "id": i, "primera": D(10), "ultima": u, "veces": 1, "titulo": ""} for i, u in alertas]
        f += [{"tipo": "correo", "fecha": e, "titulo": "x"} for e in envios]
        f += [{"tipo": "ingreso", **x} for x in ingresos]
        return f

    def test_primera_vez_no_manda_y_todo_queda_visto(self):
        r = avisos.revisar([self.rojo], [mov(500000, 1)], [], HOY)
        self.assertFalse(r["enviar"])
        filas = r["memoria_si_no_envias"]
        self.assertTrue(any(x["tipo"] == "inicio" for x in filas))
        self.assertTrue(any(x.get("id") == "r1" for x in filas))
        self.assertTrue(any(x["tipo"] == "ingreso" and x["valor"] == 500000 for x in filas))
        # y la siguiente revisión ya no es "primera vez" aunque no haya alertas
        r2 = avisos.revisar([], [], filas, HOY)
        self.assertEqual(r2["motivo"], "nada nuevo ni urgente")

    def test_rojo_cada_dos_dias_amarillo_una_vez(self):
        self.assertFalse(avisos.revisar([self.rojo], [], self.memoria([("r1", D(1))]), HOY)["enviar"])
        r = avisos.revisar([self.rojo], [], self.memoria([("r1", D(2))]), HOY)
        self.assertTrue(r["enviar"])
        self.assertIn("🔴 Gimnasio sin pagar", r["asunto"])
        self.assertTrue(r["asunto"].endswith("[Mis finanzas]"))
        self.assertFalse(avisos.revisar([self.amarillo], [], self.memoria([("a1", D(20))]), HOY)["enviar"])
        self.assertTrue(avisos.revisar([self.amarillo], [], self.memoria(), HOY)["enviar"])   # nuevo: sale una vez

    def test_cupo_y_segundo_correo_solo_con_algo_nuevo_urgente(self):
        self.assertFalse(avisos.revisar([self.naranja], [], self.memoria(envios=[HOY.isoformat()] * 2), HOY)["enviar"])
        r = avisos.revisar([self.amarillo], [], self.memoria(envios=[HOY.isoformat()]), HOY)
        self.assertFalse(r["enviar"])
        self.assertIn("va mañana", r["motivo"])
        self.assertTrue(avisos.revisar([self.naranja], [], self.memoria(envios=[HOY.isoformat()]), HOY)["enviar"])

    def test_plata_que_llega_una_sola_vez_y_sin_sueldo(self):
        r = avisos.revisar([], [mov(1500000, 1, cat="Vivienda", tipo="Gasto"), mov(9000000, 1, cat="Salario")], self.memoria(), HOY)
        self.assertTrue(r["enviar"])
        self.assertIn("💰 Te llegaron $1.500.000", r["asunto"])
        self.assertNotIn("9.000.000", r["html"])
        # ya avisado (misma cuenta y valor, fecha ±3 días): no se repite aunque el movimiento cambie de ID
        visto = {"cuenta": "Bancolombia Ahorros *4455", "valor": 1500000, "fecha": D(3)}
        self.assertFalse(avisos.revisar([], [mov(1500000, 1, cat="Vivienda", tipo="Gasto")], self.memoria(ingresos=[visto]), HOY)["enviar"])

    def test_memoria_al_enviar(self):
        r = avisos.revisar([self.rojo, self.amarillo], [], self.memoria(), HOY)
        filas = r["memoria_si_envias"]
        alertas = {x["id"]: x for x in filas if x["tipo"] == "alerta"}
        self.assertEqual(alertas["r1"]["ultima"], HOY.isoformat())
        self.assertEqual(sum(1 for x in filas if x["tipo"] == "correo" and x["fecha"] == HOY.isoformat()), 1)


if __name__ == "__main__":
    unittest.main()
