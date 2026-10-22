"""Guarda en data/overrides.json lo que el usuario editó en el Sheet (categoría manual, notas, respuestas)
para que no se pierda cuando el Sheet se regenera."""
import json, os
from googleapiclient.discovery import build
from auth import get_creds
from fetch_util import call

OV = "data/overrides.json"


def harvest():
    if not os.path.exists("data/sheet_id.txt"): return {}
    sid = open("data/sheet_id.txt").read().strip()
    svc = build("sheets", "v4", credentials=get_creds())
    ov = json.load(open(OV)) if os.path.exists(OV) else {"movimientos": {}, "respuestas": {}}
    titles = [s["properties"]["title"] for s in call(svc.spreadsheets().get(spreadsheetId=sid))["sheets"]]
    n_mov = n_resp = 0
    if "Movimientos" in titles:
        v = call(svc.spreadsheets().values().get(spreadsheetId=sid, range="'Movimientos'!A1:Z")).get("values", [])
        if v and "ID" in v[0]:
            h = v[0]; iid, icat, inota = h.index("ID"), h.index("Categoría manual"), h.index("Tu nota")
            for row in v[1:]:
                row = row + [""] * (len(h) - len(row))
                if not row[iid]: continue
                cat, nota = row[icat].strip(), row[inota].strip()
                if cat or nota:
                    # completar (no reemplazar): conserva subcategoría/tipo que se hayan guardado antes
                    ov["movimientos"].setdefault(row[iid], {}).update({"categoria": cat, "nota": nota}); n_mov += 1
                elif row[iid] in ov["movimientos"]:
                    del ov["movimientos"][row[iid]]  # el usuario borró su edición
    if "Preguntas" in titles:
        v = call(svc.spreadsheets().values().get(spreadsheetId=sid, range="'Preguntas'!A1:E")).get("values", [])
        for row in v[1:]:
            row = row + [""] * (5 - len(row))
            if row[4].strip():
                ov["respuestas"][row[1]] = row[4].strip(); n_resp += 1
    if "Suscripciones" in titles:
        v = call(svc.spreadsheets().values().get(spreadsheetId=sid, range="'Suscripciones'!A1:F")).get("values", [])
        for row in v[1:]:
            row = row + [""] * (6 - len(row))
            if row[0] and row[5].strip(): ov.setdefault("suscripciones", {})[row[0]] = row[5].strip()
    json.dump(ov, open(OV, "w"), ensure_ascii=False, indent=1)
    print(f"Ediciones guardadas: {n_mov} movimientos, {n_resp} respuestas")
    return ov


if __name__ == "__main__":
    harvest()
