"""Conceptos del Consejo Técnico de la Contaduría Pública (CTCP).

Fuente: https://www.ctcp.gov.co/conceptos/<año> (tabla con número, fecha, tema, resumen y PDF).
El sitio del CTCP no admite descargas automáticas desde fuera de un navegador, así que los PDF se
bajan por lotes desde el navegador (lotes JSON con el PDF en base64) y aquí se convierten en texto
(pdftotext; los escaneados anteriores a 2019 pasan por OCR con tesseract) y luego en fichas.

Cada ficha guarda: número, fecha, tema, resumen oficial, consulta y extracto de la respuesta,
ponente, las normas tributarias que cita (ET, DUR 1625 y Res. DIAN 227, enlazables en el sitio)
y el resto de la normativa concordante que invoca (Ley 1314 de 2009, DUR 2420 de 2015, NIIF…).

Uso:
  python scripts/ctcp.py texto  LOTE.json [...]   # PDF -> texto (caché en data/ctcp_txt/)
  python scripts/ctcp.py fichas META.json [DOT.json]   # texto + metadatos -> data/ctcp/<año>.json
  python scripts/ctcp.py incremental              # conceptos nuevos (lo usa scripts/actualizar.py)
"""
from __future__ import annotations

import base64
import gzip
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
TXT = RAIZ / "data" / "ctcp_txt"
SALIDA = RAIZ / "data" / "ctcp"
BASE = "https://www.ctcp.gov.co"

MESES = "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split()


def id_de(anio, num) -> str:
    return f"t-{anio}-{re.sub(r'[^0-9a-z]', '', str(num).lower())}"


def guid(m) -> str:
    return m["g"].split("guid=")[-1].lower()


# ---------------------------------------------------------------- PDF -> texto
def a_texto(pdf: bytes) -> tuple[str, bool]:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "c.pdf"
        p.write_bytes(pdf)
        t = subprocess.run(["pdftotext", "-layout", str(p), "-"], capture_output=True, text=True).stdout
        if len(re.sub(r"\s", "", t)) >= 150:
            return t, False
        try:   # PDF escaneado: OCR (si tesseract no está instalado se conserva lo poco que haya)
            subprocess.run(["pdftoppm", "-r", "200", "-gray", "-png", "-l", "8", str(p), f"{d}/pg"], capture_output=True)
            partes = []
            for img in sorted(Path(d).glob("pg*.png")):
                partes.append(subprocess.run(["tesseract", str(img), "-", "-l", "spa"], capture_output=True, text=True).stdout)
            return "\n".join(partes), True
        except FileNotFoundError:
            return t, False


def _uno(args):
    cid, b64 = args   # cid: guid del PDF en el sitio del CTCP
    dest = TXT / f"{cid}.txt.gz"
    try:
        t, o = a_texto(base64.b64decode(b64))
    except Exception:
        return cid, None
    dest.write_bytes(gzip.compress(t.encode("utf-8")))
    return cid, o


def textos(lotes):
    from concurrent.futures import ProcessPoolExecutor
    TXT.mkdir(parents=True, exist_ok=True)
    for ruta in lotes:
        tareas, sin_pdf = [], []
        for x in json.load(open(ruta, encoding="utf-8")):
            cid = guid(x)
            if "b64" not in x:
                sin_pdf.append(cid)
            elif not (TXT / f"{cid}.txt.gz").exists():
                tareas.append((cid, x["b64"]))
        hechos = ocr = fallos = 0
        with ProcessPoolExecutor(max_workers=os.cpu_count() or 2) as ex:
            for cid, o in ex.map(_uno, tareas, chunksize=4):
                if o is None:
                    fallos += 1
                else:
                    hechos += 1
                    ocr += o
        (TXT / "_sin_pdf.txt").open("a").write("".join(c + "\n" for c in sin_pdf))
        print(f"{ruta}: {hechos} textos ({ocr} por OCR), {fallos} fallidos, {len(sin_pdf)} sin PDF", flush=True)


# ---------------------------------------------------------------- citas
SEP = r"\s*(?:,|;|y|e|o|al|a)\s*"
NUMS = r"(\d+(?:-\d+)*(?:" + SEP + r"\d+(?:-\d+)*)*)"
MODIF = r"(?:,\s*)?(?:(?:y\s+siguientes|inciso[^.;]{0,40}?|par[áa]grafo[^.;]{0,40}?|numeral[^.;]{0,40}?|literal[^.;]{0,40}?)\s+)?"
RE_ET = re.compile(r"\bart(?:[íi]culos?|s?\.)\s+" + NUMS + r"\s*[°º]?\s*" + MODIF + r"(?:del?\s+)?(?:presente\s+)?"
                   r"(?:Estatuto\s+Tributario|E\.\s?T\.?(?=\W)|ET\b)", re.I)
# DUR 1625: solo con el número del decreto (el «Decreto Único Reglamentario» a secas suele ser el 2420 de 2015)
RE_DUR = re.compile(r"\bart(?:[íi]culos?|s?\.)\s+(\d+(?:\.\d+){2,}(?:" + SEP + r"\d+(?:\.\d+){2,})*)\.?\s*" + MODIF +
                    r"(?:del?\s+)?(?:Decreto\s+(?:Único\s+Reglamentario\s+(?:en\s+Materia\s+Tributaria\s+)?)?(?:número\s+|No\.\s*)?1625\s+de\s+2016|DUR\s+1625)", re.I)
RE_R227 = re.compile(r"\bart(?:[íi]culos?|s?\.)\s+(\d+(?:\.\d+)+(?:" + SEP + r"\d+(?:\.\d+)+)*)\.?\s*" + MODIF +
                     r"de\s+la\s+Resoluci[óo]n\s+(?:DIAN\s+)?(?:número\s+|No\.\s*)?0*227\s+de\s+2025", re.I)

# resto de la normativa concordante: etiqueta -> patrón
OTRAS = [
    ("Ley 1314 de 2009", r"Ley\s+1314\s+de\s+2009|Ley\s+1314/09"),
    ("Decreto 2420 de 2015 (DUR normas contables)", r"Decreto\s+(?:Único\s+Reglamentario\s+)?(?:No\.\s*)?2420\s+de\s+2015|DUR\s+2420"),
    ("Decreto 2496 de 2015", r"Decreto\s+(?:No\.\s*)?2496\s+de\s+2015"),
    ("Decreto 2649 de 1993", r"Decreto\s+(?:No\.\s*)?2649\s+de\s+1993"),
    ("Decreto 2650 de 1993 (PUC)", r"Decreto\s+(?:No\.\s*)?2650\s+de\s+1993"),
    ("Ley 43 de 1990", r"Ley\s+43\s+de\s+1990"),
    ("Código de Comercio", r"C[óo]digo\s+de\s+Comercio"),
    ("Ley 222 de 1995", r"Ley\s+222\s+de\s+1995"),
    ("Ley 675 de 2001 (propiedad horizontal)", r"Ley\s+675\s+de\s+2001"),
    ("Ley 1116 de 2006", r"Ley\s+1116\s+de\s+2006"),
    ("Ley 2195 de 2022", r"Ley\s+2195\s+de\s+2022"),
    ("Ley 1819 de 2016", r"Ley\s+1819\s+de\s+2016"),
    ("Ley 1943 de 2018", r"Ley\s+1943\s+de\s+2018"),
    ("Ley 2010 de 2019", r"Ley\s+2010\s+de\s+2019"),
    ("Ley 2277 de 2022", r"Ley\s+2277\s+de\s+2022"),
    ("Ley 1607 de 2012", r"Ley\s+1607\s+de\s+2012"),
    ("Marco técnico NIIF plenas (Grupo 1)", r"Anexo\s+(?:técnico\s+)?(?:compilatorio\s+(?:y\s+actualizado\s+)?)?(?:No\.?\s*)?1\b(?![\d.])"),
    ("Marco técnico NIIF para las Pymes (Grupo 2)", r"Anexo\s+(?:técnico\s+)?(?:compilatorio\s+(?:y\s+actualizado\s+)?)?(?:No\.?\s*)?2\b(?![\d.])"),
    ("Marco técnico microempresas (Grupo 3)", r"Anexo\s+(?:técnico\s+)?(?:compilatorio\s+(?:y\s+actualizado\s+)?)?(?:No\.?\s*)?3\b(?![\d.])"),
    ("Normas de aseguramiento (NIA)", r"\bNIA\b|Normas\s+Internacionales\s+de\s+Auditor[íi]a"),
    ("Resolución 414 de 2014 (CGN)", r"Resoluci[óo]n\s+(?:No\.\s*)?414\s+de\s+2014"),
    ("Resolución 533 de 2015 (CGN)", r"Resoluci[óo]n\s+(?:No\.\s*)?533\s+de\s+2015"),
]
OTRAS = [(e, re.compile(p, re.I)) for e, p in OTRAS]
RE_NIIF = re.compile(r"\b(NIIF|NIC)\s+(\d{1,2})\b|\bSecci[óo]n\s+(\d{1,2})\b(?=[^.\n]{0,60}(?:Pymes|PYMES|NIIF))")
# fórmulas de cortesía y de competencia que no aportan al extracto
RE_FORMULA = re.compile(r"(Contadur[íi]a\s+P[úu]blica\s*(?:\(CTCP\))?,?\s+en\s+su\s+(?:car[áa]cter|calidad)|en\s+su\s+(?:car[áa]cter|calidad)\s+de\s+organismo|"
                        r"(?:respuestas|conceptos)\s+(?:del|de\s+este)\s+(?:CTCP|Consejo)[^.]{0,90}(?:general|abstract)|misi[óo]n\s+no\s+consiste\s+en\s+resolver|"
                        r"alcance\s+de\s+los\s+conceptos\s+emitidos|Dentro\s+del\s+(?:car[áa]cter|prop[óo]sito)\s+ya\s+indicado|"
                        r"Calle\s+28|Carrera\s+13\s+No|Conmutador|\bPBX\b|www\.mincit|830115297|C[óo]digo\s+Postal|"
                        r"procede\s+a\s+dar\s+respuesta|en\s+los\s+t[ée]rminos\s+anteriores\s+se\s+absuelve|"
                        r"art[íi]culo\s+28\s+de\s+la\s+Ley\s+1437|Proyect[óo]:|Revis[óo]\s+y\s+aprob[óo]|GD-FM-\d+|P[áa]gina\s+\d+\s+de\s+\d+)", re.I)


def menciones(t: str) -> list[str]:
    t = re.sub(r"\s+", " ", t)
    s = set()
    for m in RE_ET.finditer(t):
        for n in re.findall(r"\d+(?:-\d+)*", m.group(1)):
            s.add(f"et:{n}")
    for m in RE_DUR.finditer(t):
        for n in re.findall(r"\d+(?:\.\d+){2,}", m.group(1)):
            s.add(f"dur:{n}")
    for m in RE_R227.finditer(t):
        for n in re.findall(r"\d+(?:\.\d+)+", m.group(1)):
            s.add(f"r227:{n.rstrip('.')}")
    return sorted(s)


def otras_normas(t: str) -> list[str]:
    t1 = re.sub(r"\s+", " ", t)
    out = [e for e, rx in OTRAS if rx.search(t1)]
    niif = set()
    for m in RE_NIIF.finditer(t1):
        if m.group(1):
            niif.add(f"{m.group(1).upper()} {int(m.group(2))}")
        else:
            niif.add(f"Sección {int(m.group(3))} NIIF para las Pymes")
    orden = lambda x: (x.split()[0], int(re.search(r"\d+", x).group()))
    return out + sorted(niif, key=orden)


# ---------------------------------------------------------------- estructura del concepto
def _limpio(t: str) -> str:
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\S+@\S+\.\w+", "[correo]", t)          # sin datos de contacto del consultante
    lineas = [l.strip() for l in t.split("\n")]
    lineas = [l for l in lineas if l and not re.fullmatch(r"(GD-FM-\S+|P[áa]gina\s+\d+\s+de\s+\d+|\d+)", l)
              and not (len(l) < 120 and RE_MEMBRETE.search(l))]
    return re.sub(r"\s+", " ", " ".join(lineas)).strip()


RE_MEMBRETE = re.compile(r"Calle\s+28\s+N|Carrera\s+13\s+No|Conmutador|\bPBX\b|www\.mincit|www\.ctcp|830115297|C[óo]digo\s+Postal|L[íi]nea\s+Gratuita|Bogot[áa],?\s+(?:D\.\s?C\.\s+)?Colombia|Minist\w*\s+de\s+Comercio|Organismo\s+adscrito|Rep[úu]blica\s+de\s+Colombia", re.I)


TIT = r"(?:^|\n)\s*(RESUMEN|CONSULTA(?:\s*\(TEXTUAL\))?|CONSIDERACIONES\s+Y\s+(?:CONCEPTO|RESPUESTAS?)|CONCLUSI[ÓO]N(?:ES)?|RESPUESTA)\s*:?\s*\n"


def secciones(t: str) -> dict:
    partes = re.split(TIT, t)
    out = {}
    for i in range(1, len(partes) - 1, 2):
        k = partes[i].split()[0].upper()
        k = {"CONSIDERACIONES": "resp", "RESPUESTA": "resp", "CONCLUSIÓN": "concl", "CONCLUSION": "concl",
             "CONCLUSIONES": "concl", "RESUMEN": "res", "CONSULTA": "cons"}.get(k, k)
        out.setdefault(k, partes[i + 1])
    return out


def extracto(t: str, limite=1800) -> str:
    """Párrafos sustantivos de la respuesta, sin las fórmulas de competencia ni la despedida."""
    parr = [_limpio(p) for p in re.split(r"\n\s*\n", t)]
    parr = [p for p in parr if len(p) > 40 and not RE_FORMULA.search(p[:220])]
    x = " ".join(parr)
    return (x[:limite].rsplit(" ", 1)[0] + " …") if len(x) > limite else x


def ponente(t: str) -> str:
    m = re.search(r"Consejer[oa]\s+Ponente\s*:?\s*([^\n/]+)", t, re.I)
    return re.sub(r"\s+", " ", m.group(1)).strip(" .") if m else ""


def fecha_iso(f: str) -> str:
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", f or "")
    return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}" if m else ""


RE_TRIB = re.compile(r"tributari|impuest|\brenta\b|\bIVA\b|retenci[óo]n\s+en\s+la\s+fuente|\bDIAN\b|ex[óo]gena|"
                     r"conciliaci[óo]n\s+fiscal|base\s+gravable|declaraci[óo]n\s+de\s+renta|facturaci[óo]n\s+electr", re.I)


def ficha(m: dict, t: str) -> dict:
    s = secciones(t)
    tema = re.sub(r"\s+", " ", m.get("t", "")).strip()
    f = {
        "id": m.get("_id") or id_de(m["y"], m["n"]), "anio": int(m["y"]), "num": m.get("_num") or m["n"], "fecha": fecha_iso(m.get("f", "")),
        "tema": tema, "resumen": re.sub(r"\s+", " ", m.get("r", "")).strip() or _limpio(s.get("res", ""))[:1500],
        "consulta": extracto(s.get("cons", ""), 1200),
        "respuesta": extracto(s.get("concl") or s.get("resp", "") or t, 1800),
        "ponente": ponente(t), "url": BASE + m["g"] if m.get("g", "").startswith("/") else m.get("g", ""),
        "menciones": menciones(t + " " + m.get("r", "")), "otras": otras_normas(t),
        "traslado": bool(re.search(r"traslad\w*\s+(?:por\s+falta\s+de\s+competencia|a\s+la\s+DIAN)|falta\s+de\s+competencia", tema + " " + m.get("r", ""), re.I)),
        "trib": len(RE_TRIB.findall(t + " " + tema + " " + m.get("r", ""))),
        "con_texto": len(t.strip()) > 150,
    }
    return f


def relevante(f: dict) -> bool:
    """Se publica si cita normas tributarias o si el asunto es tributario."""
    if f["traslado"]:      # remitidos a la DIAN por falta de competencia: solo si dicen qué norma tributaria se consultó
        return bool(f["menciones"])
    return bool(f["menciones"]) or bool(RE_TRIB.search(f["tema"] + " " + f["resumen"])) or f["trib"] >= 6


def fichas(meta_path, conservar_dot=False):
    meta = json.load(open(meta_path, encoding="utf-8"))
    SALIDA.mkdir(parents=True, exist_ok=True)
    dots = {}
    for viejo in SALIDA.glob("*.json"):
        if conservar_dot:
            dots.update({k: v for k, v in json.loads(viejo.read_text(encoding="utf-8")).items() if "-dot" in k})
        viejo.unlink()
    por_anio, total, pub = {}, 0, 0
    # números repetidos en un mismo año (el CTCP a veces reutiliza el consecutivo): el más antiguo conserva
    # el id y los demás llevan sufijo -2, -3…
    vistos, grupos = set(), {}
    for m in meta:
        if re.search(r"CONSECUTIVO", m.get("t", ""), re.I) or guid(m) in vistos:
            continue
        vistos.add(guid(m))
        grupos.setdefault(id_de(m["y"], m["n"]), []).append(m)
    for base, ms in grupos.items():
        ms.sort(key=lambda m: (fecha_iso(m.get("f", "")), guid(m)))
        for k, m in enumerate(ms):
            m["_id"] = base if k == 0 else f"{base}-{k + 1}"
            m["_num"] = m["n"] if k == 0 else f"{m['n']}-{k + 1}"
    for ms in grupos.values():
      for m in ms:
        p = TXT / f"{guid(m)}.txt.gz"
        if not p.exists():
            continue
        total += 1
        f = ficha(m, gzip.decompress(p.read_bytes()).decode("utf-8"))
        if relevante(f):
            pub += 1
            por_anio.setdefault(f["anio"], {})[f["id"]] = f
    for k, v in dots.items():
        por_anio.setdefault(v["anio"], {})[k] = v
    for anio, d in por_anio.items():
        (SALIDA / f"{anio}.json").write_text(json.dumps(d, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"{total} conceptos con texto; {pub} publicados (citan normas tributarias o tratan un asunto tributario)")


# documentos de orientación técnica (DOT) que citan normas tributarias: número -> (fecha ISO, título)
DOTS = {
    "14": ("2015-10-01", "Entidades sin ánimo de lucro (ESAL)"),
    "15": ("2024-06-18", "Propiedades horizontales de uso residencial o mixto, grupos 2 y 3 (actualización 2024)"),
    "16": ("2015-12-01", "Elementos contables para la interacción entre la base contable y la fiscal durante los cuatro años de transición"),
    "18": ("2020-05-23", "Aplicación de las normas de información financiera y de aseguramiento por la pandemia del COVID-19"),
}


def orientaciones(ruta):
    """Fichas de los DOT del CTCP (lote JSON con el PDF de cada documento) que citan el ET, el DUR o la Res. 227."""
    SALIDA.mkdir(parents=True, exist_ok=True)
    n = 0
    for x in json.load(open(ruta, encoding="utf-8")):
        m = re.match(r"DOT\s+(\d+)", x.get("tit", ""))
        if not m or m.group(1) not in DOTS or "b64" not in x:
            continue
        num = m.group(1)
        fecha, titulo = DOTS[num]
        t, _ = a_texto(base64.b64decode(x["b64"]))
        intro = re.split(r"\n\s*(?:Introducci[óo]n|INTRODUCCI[ÓO]N|Justificaci[óo]n|JUSTIFICACI[ÓO]N|Contexto|CONTEXTO)\s*\n", t)
        cuerpo = intro[2] if len(intro) > 2 else intro[-1]
        anio = int(fecha[:4])
        f = {"id": f"t-{anio}-dot{num}", "anio": anio, "num": f"DOT {num}", "rotulo": f"Orientación técnica {num} de {anio}",
             "tipo": "Documento de Orientación Técnica", "fecha": fecha, "tema": titulo,
             "resumen": f"Documento de Orientación Técnica No. {num} del Consejo Técnico de la Contaduría Pública: {titulo}.",
             "consulta": "", "respuesta": extracto(cuerpo, 1800), "ponente": "",
             "url": x["u"], "menciones": menciones(t), "otras": otras_normas(t), "traslado": False,
             "trib": len(RE_TRIB.findall(t)), "con_texto": True}
        dest = SALIDA / f"{anio}.json"
        d = json.loads(dest.read_text(encoding="utf-8")) if dest.exists() else {}
        d[f["id"]] = f
        dest.write_text(json.dumps(d, ensure_ascii=False, indent=0), encoding="utf-8")
        n += 1
        print(f["id"], len(f["menciones"]), "citas")
    print(n, "orientaciones técnicas")


# ---------------------------------------------------------------- actualización automática
META = RAIZ / "data" / "ctcp_meta.json"


def catalogo_anio(sesion, anio: int) -> list[dict]:
    """Filas de https://www.ctcp.gov.co/conceptos/<año>: número, fecha, tema, resumen y enlace al PDF."""
    from bs4 import BeautifulSoup
    r = sesion.get(f"{BASE}/conceptos/{anio}", timeout=60)
    r.raise_for_status()
    out = []
    for tr in BeautifulSoup(r.text, "html.parser").select("tbody tr"):
        a = tr.select_one('a[href*="GetFile"]')
        if not a:
            continue
        tds = tr.find_all("td")
        th = tr.find("th")
        i = tr.select_one("i[title]")
        out.append({"y": anio, "n": th.get_text(strip=True) if th else "", "f": tds[0].get_text(strip=True) if tds else "",
                    "t": re.sub(r"\s+", " ", tds[1].get_text(" ", strip=True)) if len(tds) > 1 else "",
                    "g": a["href"], "r": re.sub(r"\s+", " ", i["title"]).strip() if i else ""})
    return out


def incremental(max_nuevos: int = 300) -> int:
    """Conceptos nuevos del año en curso y del anterior: descarga pausada del PDF, texto y fichas."""
    import time
    from datetime import date
    import requests
    if not META.exists():
        print("CTCP: falta data/ctcp_meta.json; se omite")
        return 0
    meta = json.loads(META.read_text(encoding="utf-8"))
    conocidos = {guid(m) for m in meta}
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0 (compatible; Tribudata.co ET concordado)"
    hoy = date.today().year
    nuevos = []
    for anio in (hoy, hoy - 1):
        try:
            filas = catalogo_anio(s, anio)
        except Exception as e:  # noqa: BLE001
            print(f"CTCP {anio}: {e}")
            continue
        vistos = {guid(m): m for m in meta if m["y"] == anio}
        for f in filas:
            if guid(f) in vistos:
                vistos[guid(f)].update(f)        # el CTCP completa resúmenes con el tiempo
            elif guid(f) not in conocidos:
                nuevos.append(f)
                conocidos.add(guid(f))
    TXT.mkdir(parents=True, exist_ok=True)
    hechos = 0
    for f in nuevos[:max_nuevos]:
        meta.append(f)
        if re.search(r"CONSECUTIVO", f["t"], re.I):
            continue
        try:
            r = s.get(BASE + f["g"], timeout=90)
            if r.ok and r.content[:4] == b"%PDF":
                t, _ = a_texto(r.content)
                (TXT / f"{guid(f)}.txt.gz").write_bytes(gzip.compress(t.encode("utf-8")))
                hechos += 1
        except Exception as e:  # noqa: BLE001
            print(f"CTCP {f['y']}-{f['n']}: {e}")
        time.sleep(1.5)
    if nuevos:
        META.write_text(json.dumps(meta, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        fichas(str(META), conservar_dot=True)
    print(f"CTCP: {len(nuevos)} conceptos nuevos en el catálogo, {hechos} con texto")
    return hechos


if __name__ == "__main__":
    if sys.argv[1] == "texto":
        textos(sys.argv[2:])
    elif sys.argv[1] == "incremental":
        incremental()
    elif sys.argv[1] == "fichas":
        fichas(sys.argv[2])
        if len(sys.argv) > 3:
            orientaciones(sys.argv[3])
