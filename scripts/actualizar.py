"""
Sincroniza con el normograma DIAN todas las normas registradas en scripts/documentos.py
(Estatuto Tributario, Decreto 1625 de 2016 y Resolución DIAN 227 de 2025).

Para cada documento:
1. Consulta las cabeceras (Last-Modified / ETag) en normograma.dian.gov.co.
2. Si hay una versión nueva (o se usa --forzar), descarga <doc>.htm (texto), js/<doc>.js
   (desplegables) y el índice; valida que la descarga esté completa.
3. Regenera el JSON de esa norma (data/estatuto.json, data/dur1625.json, data/res227.json) y registra en data/cambios.json qué
   artículos son nuevos, cuáles cambiaron (texto o desplegables) y cuáles salieron.
Al final descarga las gráficas (fórmulas/tablas en imagen) que falten.

Al final agrega a data/doctrina.json los conceptos y oficios DIAN nuevos (scripts/doctrina.py).

Uso:  python scripts/actualizar.py [--forzar] [--sin-doctrina] [--sin-jurisprudencia] [--sin-ctcp]
Salida para GitHub Actions: escribe cambios=true|false en $GITHUB_OUTPUT.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parent.parent
GRAFICAS = RAIZ / "data" / "graficas"
CAMBIOS = RAIZ / "data" / "cambios.json"
SITIO = os.environ.get("ET_NORMOGRAMA", "https://normograma.dian.gov.co/dian/compilacion/")
sys.path.insert(0, str(RAIZ / "scripts"))
from documentos import DOCUMENTOS  # noqa: E402

DOCS = {k: dict(v, fuente=RAIZ / "data" / v["fuente"], json=RAIZ / "data" / v["json"]) for k, v in DOCUMENTOS.items()}
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/130.0 Safari/537.36 TribudataETBot/1.0 (+https://tribudata.co)")
BOGOTA = timezone(timedelta(hours=-5))

S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept-Language": "es-CO,es;q=0.9"})


def get(url, intentos=4, **kw):
    for intento in range(intentos):
        try:
            r = S.get(url, timeout=180, **kw)
            if r.status_code == 200:
                return r
            print(f"  {url} -> HTTP {r.status_code}")
            if r.status_code in (403, 404, 410):
                break
        except requests.RequestException as e:
            print(f"  {url} -> {e}")
        if intento < intentos - 1:
            time.sleep(5 * (intento + 1))
    raise SystemExit(f"No se pudo descargar {url}")


def salida_gh(clave, valor):
    f = os.environ.get("GITHUB_OUTPUT")
    if f:
        with open(f, "a") as fh:
            fh.write(f"{clave}={valor}\n")


def sincronizar(doc: str, cfg: dict, corte: str, forzar: bool):
    """Devuelve (hubo_cambio, entrada_parcial_de_cambios, bytes_para_graficas)."""
    fuente, nombre = cfg["fuente"], cfg["archivo"]
    fuente.mkdir(parents=True, exist_ok=True)
    cab_prev = json.loads((fuente / "headers.json").read_text()) if (fuente / "headers.json").exists() else {}
    url_htm = f"{SITIO}docs/{nombre}.htm"
    h = S.head(url_htm, timeout=60)
    cab = {"last_modified": h.headers.get("Last-Modified", ""), "etag": h.headers.get("ETag", "")}
    print(f"[{doc}] Last-Modified: {cab['last_modified']!r} (antes {cab_prev.get('last_modified')!r})")
    if (not forzar and cab["last_modified"] and cab["last_modified"] == cab_prev.get("last_modified")
            and cab["etag"] == cab_prev.get("etag")):
        print(f"[{doc}] sin cambios.")
        return False, None, b""

    tmp = Path(tempfile.mkdtemp())
    urls = {f"{nombre}.htm": url_htm, f"{nombre}.js": f"{SITIO}docs/js/{nombre}.js",
            f"{nombre}_indice.html": f"{SITIO}docs/paneles/{nombre}_indice.html"}
    for archivo, url in urls.items():
        r = get(url, params={"v": "2.0", "t": int(time.time())} if archivo.endswith(".js") else None)
        (tmp / archivo).write_bytes(r.content)
        print(f"  [{doc}] descargado {archivo}: {len(r.content):,} bytes")
    (tmp / "corte.txt").write_text(corte + "\r\n", encoding="latin-1")
    htm, js = (tmp / f"{nombre}.htm").read_bytes(), (tmp / f"{nombre}.js").read_bytes()
    if (len(htm) < cfg["min_htm"] or b"bookmarkaj" not in htm or len(js) < cfg["min_js"]
            or js.count(b"function insRow") < cfg["min_funciones"]):
        raise SystemExit(f"[{doc}] La descarga parece incompleta o cambió el formato del normograma. No se actualiza.")
    cab["sha256"] = hashlib.sha256(htm + js).hexdigest()
    if not forzar and cab["sha256"] == cab_prev.get("sha256"):
        print(f"[{doc}] cabeceras distintas pero contenido idéntico.")
        (fuente / "headers.json").write_text(json.dumps(cab))
        return False, None, b""
    (tmp / "headers.json").write_text(json.dumps(cab))

    nuevo_json = tmp / "salida.json"
    subprocess.run([sys.executable, str(RAIZ / "scripts" / "parsear.py"), doc, str(tmp), str(nuevo_json)], check=True)
    nuevo = json.loads(nuevo_json.read_text(encoding="utf-8"))
    viejo = json.loads(cfg["json"].read_text(encoding="utf-8")) if cfg["json"].exists() else None
    if viejo and nuevo["meta"]["total_articulos"] < 0.95 * viejo["meta"]["total_articulos"]:
        raise SystemExit(f"[{doc}] El nuevo documento tiene muchos menos artículos que el anterior. Se detiene por seguridad.")
    entrada = None
    if viejo:
        hv = {a["id"]: a["hash"] for a in viejo["articulos"]}
        hn = {a["id"]: a["hash"] for a in nuevo["articulos"]}
        entrada = {"nuevos": [i for i in hn if i not in hv],
                   "modificados": [i for i in hn if i in hv and hn[i] != hv[i]],
                   "eliminados": [i for i in hv if i not in hn]}
    for f in list(urls) + ["corte.txt", "headers.json"]:
        shutil.copy(tmp / f, fuente / f)
    shutil.copy(nuevo_json, cfg["json"])
    shutil.rmtree(tmp, ignore_errors=True)
    return True, entrada, htm + js


def main():
    forzar = "--forzar" in sys.argv
    corte = get(SITIO + "data/corte.txt", params={"t": int(time.time())}).content.decode("latin-1").strip()
    print(f"Corte normograma: {corte!r}")
    hubo, para_graficas = False, b""
    resumen = {"nuevos": [], "modificados": [], "eliminados": []}
    for doc, cfg in DOCS.items():
        cambio, entrada, contenido = sincronizar(doc, cfg, corte, forzar)
        hubo = hubo or cambio
        para_graficas += contenido
        if entrada:
            for k in resumen:
                resumen[k] += entrada[k]

    # doctrina DIAN: conceptos y oficios nuevos (descarga incremental y pausada)
    nuevos_doc = 0
    if "--sin-doctrina" not in sys.argv:
        try:
            import doctrina
            nuevos_doc = doctrina.incremental(int(os.environ.get("ET_DOCTRINA_MAX", "1500")))
        except SystemExit as e:
            print(f"Doctrina: {e}")
        except Exception as e:  # noqa: BLE001 - la doctrina nunca debe tumbar la actualización de las normas
            print(f"Doctrina: error {e}")
    hubo = hubo or nuevos_doc > 0
    if nuevos_doc:
        resumen["doctrina_nuevos"] = nuevos_doc

    # jurisprudencia del Consejo de Estado (Sección Cuarta): sentencias nuevas tituladas en SAMAI
    nuevas_jur = 0
    if "--sin-jurisprudencia" not in sys.argv:
        try:
            import jurisprudencia
            nuevas_jur = jurisprudencia.incremental(int(os.environ.get("ET_JURIS_PAGINAS", "30")))
        except Exception as e:  # noqa: BLE001 - nunca debe tumbar la actualización de las normas
            print(f"Jurisprudencia: error {e}")
    hubo = hubo or nuevas_jur > 0
    if nuevas_jur:
        resumen["jurisprudencia_nuevas"] = nuevas_jur

    # conceptos del Consejo Técnico de la Contaduría Pública (CTCP)
    nuevos_ctcp = 0
    if "--sin-ctcp" not in sys.argv:
        try:
            import ctcp
            nuevos_ctcp = ctcp.incremental(int(os.environ.get("ET_CTCP_MAX", "300")))
        except Exception as e:  # noqa: BLE001 - nunca debe tumbar la actualización de las normas
            print(f"CTCP: error {e}")
    hubo = hubo or nuevos_ctcp > 0
    if nuevos_ctcp:
        resumen["ctcp_nuevos"] = nuevos_ctcp

    if any(resumen.values()):
        cambios = json.loads(CAMBIOS.read_text(encoding="utf-8")) if CAMBIOS.exists() else []
        resumen.setdefault("doctrina_nuevos", 0)
        cambios.insert(0, {"fecha": datetime.now(BOGOTA).strftime("%Y-%m-%d %H:%M"), "corte": corte, **resumen})
        CAMBIOS.write_text(json.dumps(cambios[:200], ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"Cambios: {len(resumen['nuevos'])} nuevos, {len(resumen['modificados'])} modificados, "
              f"{len(resumen['eliminados'])} eliminados, {resumen.get('doctrina_nuevos', 0)} documentos de doctrina")

    if hubo:
        GRAFICAS.mkdir(parents=True, exist_ok=True)
        texto = para_graficas.decode("cp1252", "replace")
        for nombre in sorted(set(re.findall(r"graficas/([\w\-.]+\.(?:gif|png|jpe?g))", texto, re.I))):
            destino = GRAFICAS / nombre
            if not destino.exists():
                try:
                    destino.write_bytes(get(SITIO + "graficas/" + nombre, intentos=2).content)
                except SystemExit as e:
                    print(f"  aviso: {e}")
    salida_gh("cambios", "true" if hubo else "false")
    print("Actualización completa." if hubo else "Nada que actualizar.")


if __name__ == "__main__":
    main()
