"""Reads the REAL schema of the SQLite database (tables, PK, FK, rows) in order to draw it.

Used by the app's /data screen and the Lucid skill script:
    python esquema.py            -> JSON ready for lucid_create_erd
"""
import json
import os
import sqlite3
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "restaurante.db"))
LUCID_JSON = os.path.join(BASE_DIR, "lucid_erd.json")
OCULTAS = {"password_hash"}  # never show hashes


def lucid_url():
    """URL of the diagram in Lucid (saved by the skill in lucid_erd.json)."""
    try:
        with open(LUCID_JSON, encoding="utf-8") as f:
            return json.load(f).get("url")
    except (OSError, ValueError):
        return None


def leer_esquema(db, con_filas=0):
    db.row_factory = sqlite3.Row
    tablas = [r["name"] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    entidades, relaciones = [], []
    for t in tablas:
        cols = db.execute('PRAGMA table_info("%s")' % t).fetchall()
        fks = db.execute('PRAGMA foreign_key_list("%s")' % t).fetchall()
        fk_cols = {f["from"]: (f["table"], f["to"]) for f in fks}
        attrs = []
        for c in cols:
            tipo = c["type"] or "TEXT"
            if c["notnull"] or c["pk"]:
                tipo += " NOT NULL"
            attrs.append({"name": c["name"], "type": tipo,
                          "key": "PK" if c["pk"] else None,
                          "fk": fk_cols.get(c["name"])})
        ent = {"id": t, "name": t, "attributes": attrs,
               "rows": db.execute('SELECT COUNT(*) FROM "%s"' % t).fetchone()[0]}
        if con_filas:
            visibles = [c["name"] for c in cols if c["name"] not in OCULTAS]
            ent["columns"] = visibles
            ent["sample"] = [[r[c] for c in visibles] for r in db.execute(
                'SELECT %s FROM "%s" ORDER BY rowid DESC LIMIT %d'
                % (",".join('"%s"' % c for c in visibles), t, con_filas))]
        entidades.append(ent)
        for f in fks:
            unico = any(
                i["unique"] and [x["name"] for x in db.execute('PRAGMA index_info("%s")' % i["name"])] == [f["from"]]
                for i in db.execute('PRAGMA index_list("%s")' % t))
            relaciones.append({
                "from": t, "fromAttribute": f["from"], "to": f["table"], "toAttribute": f["to"],
                "fromCardinality": "exactlyOne" if unico else "zeroOrMore",
                "toCardinality": "exactlyOne" if any(
                    a["name"] == f["from"] and "NOT NULL" in a["type"] for a in attrs) else "zeroOrOne",
            })
    return entidades, relaciones


if __name__ == "__main__":
    con = sqlite3.connect(DB_PATH)
    ents, rels = leer_esquema(con)
    for e in ents:  # lucid_create_erd format
        e["attributes"] = [{k: v for k, v in a.items() if k != "fk" and v is not None} for a in e["attributes"]]
        e.pop("rows")
    json.dump({"entities": ents, "relationships": rels}, sys.stdout, ensure_ascii=False, indent=1)
