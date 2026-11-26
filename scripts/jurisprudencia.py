"""
Jurisprudencia del Consejo de Estado, Sección Cuarta (sentencias), desde las dos relatorías oficiales.

* SAMAI · Mi Relatoría (providencias tituladas desde el 1 de diciembre de 2021):
  buscador de titulación https://samai.consejodeestado.gov.co/TitulacionRelatoria/...  Filtro: Sección Cuarta,
  tipo Sentencia, sin acciones de tutela. Por cada sentencia: proceso, interno, ponente, partes, fecha, y uno o
  varios bloques de titulación (descriptores, problema jurídico, respuesta, extracto de la tesis, fuente formal).
* Relatoría tradicional (hasta el 30 de noviembre de 2021): https://servicios.consejodeestado.gov.co/WebRelatoria
  Sección Cuarta, sentencias cuyo sustento normativo incluye el Estatuto Tributario. Por cada una: NR, radicado,
  interno, sustento normativo, fecha, ponente, partes, decisión, tema (descriptores) y extracto. El texto completo
  tiene dirección estable: FileReferenceServlet?corp=ce&ext=html&file=<NR>.

Las normas citadas salen de la "fuente formal" / "sustento normativo" (ESTATUTO TRIBUTARIO - ARTÍCULO 771-2,
DECRETO 624 DE 1989 - ARTÍCULO 670, DECRETO 1625 DE 2016 - ARTÍCULO 1.2.1.5.1.8 ...) y de las menciones del
extracto ("artículo 670 del Estatuto Tributario").

Resultado: data/jurisprudencia/<año>.json  {id: ficha}
  id SAMAI       s-<radicado 23 dígitos>-<aaaammdd>
  id relatoría   s-r<NR>-<aaaammdd>   (si la misma sentencia está en SAMAI, se conserva la de SAMAI con el NR)

Uso:
  python scripts/jurisprudencia.py --desde-lotes carpeta     carga inicial (cej_samai*.json.gz, cej_relatoria*.json.gz)
  python scripts/jurisprudencia.py                          incremental: sentencias nuevas en SAMAI
"""
import gzip
import html as H
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from doctrina import RE_MENC_DUR, RE_MENC_ET, RE_MENC_R227  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
CARPETA = RAIZ / "data" / "jurisprudencia"
SAMAI = "https://samai.consejodeestado.gov.co/TitulacionRelatoria/ResultadoBuscadorProvidenciasTituladas.aspx?BusquedaDictionary="
FILTRO_SAMAI = "(  TipoProvidencia  eq 'Sentencia') and (  NombreSalaDecision  eq 'Sección Cuarta') and (  ClaseProceso  ne 'ACCIONES DE TUTELA')"
RELATORIA_DOC = "https://servicios.consejodeestado.gov.co/WebRelatoria/FileReferenceServlet?corp=ce&ext=html&file="
MESES = {m: i + 1 for i, m in enumerate("enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split())}


def url_samai(busqueda: str, pagina: int = 0, filtro: str = "") -> str:
    from urllib.parse import quote
    d = {"corporacion": "1100103", "modo": "2", "filtro": filtro, "busqueda": busqueda, "searchMode": "all",
         "orderby": "FechaProvidencia desc", "PaginaActual": str(pagina)}
    return SAMAI + quote(json.dumps(d, ensure_ascii=False, separators=(",", ":")))


def url_sentencia(f: dict) -> str:
    """Enlace estable al texto: relatoría (NR) o búsqueda SAMAI por número de proceso."""
    if f.get("nr"):
        return RELATORIA_DOC + f["nr"]
    return url_samai(f["rad"])


# --------------------------------------------------------------------------- normas citadas
NORMA = (r"(ESTATUTO\s+TRIBUTARIO(?:\s+NACIONAL)?|DECRETO(?:\s+LEY)?\s+624\s+DE\s+1989|"
         r"DECRETO\s+(?:[ÚU]NICO\s+REGLAMENTARIO\s+)?(?:EN\s+MATERIA\s+TRIBUTARIA\s+)?1625\s+DE\s+2016|"
         r"RESOLUCI[ÓO]N\s+(?:DIAN\s+)?(?:N[O°º.]*\s*)?0*227\s+DE\s+2025)")
RE_FUENTE = re.compile(NORMA + r"[^/–\-]{0,60}?\s*[-–]\s*ART[ÍI]CULOS?\s+([0-9][^/]*?)(?=\s*(?:/|,\s*[A-ZÁÉÍÓÚÑ]{3,}|$))", re.I)
RE_LISTA = re.compile(r"[0-9][0-9.\-]*(?:\s*(?:,|\bY\b|\bE\b)\s*[0-9][0-9.\-]*)*", re.I)


def doc_norma(nombre: str) -> str:
    n = nombre.upper()
    if "1625" in n:
        return "dur"
    if "227" in n:
        return "r227"
    return "et"


def menciones_fuente(texto: str) -> set:
    out = set()
    for m in RE_FUENTE.finditer(texto or ""):
        d = doc_norma(m.group(1))
        lista = RE_LISTA.match(m.group(2).strip())
        if not lista:
            continue
        for num in re.findall(r"[0-9][0-9.\-]*", lista.group(0)):
            num = num.strip(".-")
            if d == "et" and not re.fullmatch(r"\d+(?:-\d+)*", num):
                continue
            if d == "dur" and not re.fullmatch(r"\d+(?:\.\d+){2,}", num):
                continue
            if d == "r227" and not re.fullmatch(r"\d+(?:\.\d+)+", num):
                continue
            out.add(f"{d}:{num}")
    return out


def menciones_texto(txt: str) -> set:
    txt = re.sub(r"\s+", " ", txt or "")
    men = set()
    for m in RE_MENC_ET.finditer(txt):
        for num in re.findall(r"\d+(?:-\d+)*", m.group(1)):
            men.add(f"et:{num}")
    for m in RE_MENC_DUR.finditer(txt):
        for num in re.findall(r"\d+(?:\.\d+){2,}", m.group(1)):
            men.add(f"dur:{num}")
    for m in RE_MENC_R227.finditer(txt):
        for num in re.findall(r"\d+(?:\.\d+){1,}", m.group(1)):
            men.add(f"r227:{num.rstrip('.')}")
    return men


# --------------------------------------------------------------------------- utilidades
def limpio(t: str) -> str:
    return re.sub(r"\s+", " ", H.unescape(t or "").replace("\xa0", " ")).strip()


def fecha_larga(t: str) -> str:
    """'jueves, 22 de octubre de 2026' -> '2026-10-22'"""
    m = re.search(r"(\d{1,2}) de ([a-záéíóú]+) de (\d{4})", (t or "").lower())
    if not m or m.group(2) not in MESES:
        return ""
    return f"{m.group(3)}-{MESES[m.group(2)]:02d}-{int(m.group(1)):02d}"


def fecha_corta(t: str) -> str:
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", t or "")
    return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}" if m else ""


def solo_digitos(t: str) -> str:
    return re.sub(r"\D", "", t or "")


def descriptores_unicos(lista) -> str:
    vistos, out = set(), []
    for d in lista:
        for p in re.split(r"\s+/\s+", d or ""):
            p = limpio(p)
            k = p.upper()
            if p and k not in vistos:
                vistos.add(k)
                out.append(p)
    return " / ".join(out)


# --------------------------------------------------------------------------- SAMAI
def de_samai(r: dict) -> dict:
    fecha = fecha_larga(r.get("fprov", ""))
    rad = solo_digitos(r.get("rad", ""))
    problemas, tesis, fuentes, notas, descs = [], [], [], [], []
    men = set()
    accesorio = lambda b: bool(re.search(r"costas|agencias en derecho", b.get("pj", ""), re.I))
    for b in sorted(r.get("bloques", []), key=accesorio):      # condena en costas al final
        pj = limpio(re.sub(r"^Problema jur[íi]dico:\s*", "", b.get("pj", ""), flags=re.I))
        resp = limpio(re.sub(r"^Respuesta al problema jur[íi]dico:\s*", "", b.get("resp", ""), flags=re.I))
        fu = limpio(re.sub(r"^FUENTE FORMAL:\s*", "", b.get("fuente", ""), flags=re.I))
        nota = limpio(re.sub(r"^NOTA DE RELATOR[ÍI]A:\s*", "", b.get("nota", ""), flags=re.I))
        desc = limpio(b.get("desc", ""))
        if fu:
            fuentes.append(fu)
        if nota:
            notas.append(nota)
        descs.append(desc)
        # extracto (tesis): lo que sigue a la respuesta del problema jurídico, sin fuente formal ni nota de relatoría
        texto = b.get("texto") or ""
        m = re.search(r"Respuesta al problema jur[íi]dico:[^\n]*\n", texto)
        if m:
            texto = texto[m.end():]
        elif re.search(r"Problema jur[íi]dico:", texto):
            texto = texto[re.search(r"Problema jur[íi]dico:", texto).end():].replace(b.get("pj", "").split(":", 1)[-1], "")
        texto = re.split(r"\n\s*(?:FUENTE FORMAL:|NOTA DE RELATOR[ÍI]A:)", texto)[0]
        t = limpio(texto)
        if t:
            tesis.append(t)
        if pj:      # [problema, respuesta corta, respuesta desarrollada (tesis de ese problema)]
            problemas.append([pj, resp, t[:3000]])
        men |= menciones_fuente(b.get("fuente", "")) | menciones_texto(t)
    return {
        "id": f"s-{rad}-{fecha.replace('-', '')}", "fuente": "samai", "rad": rad, "interno": limpio(r.get("interno")),
        "fecha": fecha, "ponente": limpio(r.get("ponente")), "actor": limpio(r.get("actor")), "demandado": limpio(r.get("demandado")),
        "clase": limpio(r.get("clase")), "tipo": limpio(r.get("tipo")) or "Sentencia", "decision": "", "cert": limpio(r.get("cert")),
        "fproc": fecha_larga(r.get("fproc", "")), "sala": limpio(r.get("sala")) or "Sección Cuarta",
        "descriptores": descriptores_unicos(descs), "problemas": problemas,
        "extracto": " (…) ".join(tesis)[:2500], "fuentes": " · ".join(fuentes)[:1500], "nota": " ".join(notas)[:600],
        "menciones": sorted(men),
    }


# --------------------------------------------------------------------------- relatoría tradicional
ETIQUETAS = ["SUSTENTO NORMATIVO", "NORMA DEMANDADA", "FECHA", "SECCION", "PONENTE", "ACTOR", "DEMANDADO", "DECISION", "TEMA"]


ACCESORIO = re.compile(r"COSTAS|AGENCIAS EN DERECHO|IMPEDIMENTO|QU[OÓ]RUM|RECUSACI|NOTA DE RELATOR", re.I)


def de_relatoria(r: dict) -> dict | None:
    t = r.get("t", "")
    if not t.startswith("<<HTML>>"):
        return None
    fr = t[len("<<HTML>>"):]
    fr = re.sub(r'<font style="BACKGROUND-COLOR: yellow">(.*?)</font>', r"\1", fr, flags=re.I | re.S)
    fr = re.sub(r"</?font[^>]*>", "", fr, flags=re.I)
    # TEMA: bloques separados por <br><br>; los que empiezan en <b> son descriptores, los demás extractos
    tema_html = ""
    m = re.search(r"<b>\s*TEMA\s*:\s*</b>(.*)$", fr, re.S | re.I)
    if m:
        tema_html = m.group(1)
        fr = fr[:m.start()]
    txt = re.sub(r"<br\s*/?>", "\n", fr, flags=re.I)
    txt = H.unescape(re.sub(r"<[^>]+>", "", txt)).replace("\xa0", " ")
    lineas = [l.strip() for l in txt.split("\n")]
    campos, actual, cab = {}, None, []
    for l in lineas:
        m = re.match(r"(" + "|".join(ETIQUETAS) + r")\s*:\s*(.*)$", l)
        if m:
            actual = m.group(1)
            campos[actual] = [m.group(2)]
        elif actual:
            campos[actual].append(l)
        elif l:
            cab.append(l)
    bloques, nota = [], []
    actual_b = None
    for seg in re.split(r"(?:<br\s*/?>\s*){2,}", tema_html, flags=re.I):
        plano_s = limpio(re.sub(r"<[^>]+>", " ", seg))
        if not plano_s:
            continue
        if plano_s.upper().startswith("NOTA DE RELATOR"):
            nota.append(plano_s)
        elif seg.lstrip().lower().startswith("<b>"):
            actual_b = {"d": plano_s, "x": []}
            bloques.append(actual_b)
        elif actual_b is not None:
            actual_b["x"].append(plano_s)
        else:
            bloques.append({"d": "", "x": [plano_s]})
    bloques.sort(key=lambda b: bool(ACCESORIO.search(b["d"][:120])))
    nr = solo_digitos(r.get("nr", ""))
    rad = solo_digitos(cab[2]) if len(cab) > 2 else ""
    interno_l = cab[3] if len(cab) > 3 else ""
    interno = (re.match(r"\d+", interno_l) or [""])[0]
    tipo_l = cab[4] if len(cab) > 4 else "SENTENCIA"
    tipo = "Sentencia de unificación" if ("UNIFICACI" in tipo_l.upper() or "SU" in interno_l) else "Sentencia"
    fecha = fecha_corta(" ".join(campos.get("FECHA", [])))
    descriptores = descriptores_unicos([b["d"] for b in bloques])
    extracto = " (…) ".join(" ".join(b["x"]) for b in bloques if b["x"])
    decision_l = [l for l in campos.get("DECISION", []) if l]
    sustento = limpio(" ".join(campos.get("SUSTENTO NORMATIVO", [])))
    men = menciones_fuente(sustento) | menciones_texto(extracto)
    return {
        "id": f"s-r{nr}-{fecha.replace('-', '')}", "fuente": "relatoria", "nr": nr, "rad": rad, "interno": interno,
        "fecha": fecha, "ponente": limpio(" ".join(campos.get("PONENTE", []))), "actor": limpio(" ".join(campos.get("ACTOR", []))),
        "demandado": limpio(" ".join(campos.get("DEMANDADO", []))), "clase": "", "tipo": tipo,
        "sala": "Sección " + (limpio(" ".join(campos.get("SECCION", []))).capitalize() or "Cuarta"),
        "decision": limpio(decision_l[0]) if decision_l else "", "salvamentos": limpio(" · ".join(decision_l[1:]))[:300],
        "descriptores": descriptores[:3000], "titulo": bloques[0]["d"].split(" / ")[0] if bloques and bloques[0]["d"] else "",
        "problemas": [], "extracto": extracto[:2500], "fuentes": sustento[:1500], "nota": " ".join(nota)[:600],
        "menciones": sorted(men),
    }


# --------------------------------------------------------------------------- almacenamiento
def cargar() -> dict:
    datos = {}
    if CARPETA.exists():
        for f in sorted(CARPETA.glob("*.json")):
            datos.update(json.loads(f.read_text(encoding="utf-8")))
    return datos


def guardar(datos: dict):
    CARPETA.mkdir(parents=True, exist_ok=True)
    por_anio = {}
    for k in sorted(datos, key=lambda k: (datos[k].get("fecha", ""), k), reverse=True):
        por_anio.setdefault(datos[k].get("fecha", "")[:4] or "0", {})[k] = datos[k]
    for f in CARPETA.glob("*.json"):
        if f.stem not in por_anio:
            f.unlink()
    for anio, d in por_anio.items():
        (CARPETA / f"{anio}.json").write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def combinar(datos: dict, nuevas) -> int:
    """Agrega fichas; si una sentencia de la relatoría está también en SAMAI (mismo radicado y fecha) conserva la de SAMAI con el NR."""
    por_clave = {(f["rad"], f["fecha"]): k for k, f in datos.items() if f.get("rad")}
    n = 0
    for f in nuevas:
        if not f or not f.get("fecha"):
            continue
        clave = (f.get("rad"), f["fecha"])
        previo = por_clave.get(clave) if f.get("rad") else None
        if previo and previo != f["id"]:
            p = datos[previo]
            if p["fuente"] == "samai" and f["fuente"] == "relatoria":
                p["nr"] = f["nr"]
                p["decision"] = p.get("decision") or f.get("decision", "")
                p["tipo"] = f["tipo"] if f["tipo"] != "Sentencia" else p["tipo"]
                p["menciones"] = sorted(set(p["menciones"]) | set(f["menciones"]))
                continue
            if p["fuente"] == "relatoria" and f["fuente"] == "samai":
                f["nr"] = p.get("nr", "")
                f["decision"] = p.get("decision", "")
                f["menciones"] = sorted(set(p["menciones"]) | set(f["menciones"]))
                del datos[previo]
        if f["id"] not in datos:
            n += 1
        datos[f["id"]] = f
        if f.get("rad"):
            por_clave[clave] = f["id"]
    return n


def leer_gz(ruta: Path):
    with gzip.open(ruta, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def desde_lotes(carpeta: Path):
    datos = cargar()
    samai, rel = [], []
    for f in sorted(carpeta.glob("cej_samai*.json.gz")):
        samai += leer_gz(f)
    for f in sorted(carpeta.glob("cej_relatoria*.json.gz")):
        rel += leer_gz(f)
    n1 = combinar(datos, [de_samai(r) for r in samai])
    n2 = combinar(datos, [de_relatoria(r) for r in rel])
    guardar(datos)
    print(f"Jurisprudencia CE: {len(datos)} sentencias ({n1} de SAMAI, {n2} de la relatoría tradicional)")
    return datos


# --------------------------------------------------------------------------- actualización incremental (SAMAI)
P = "ContentPlaceHolder1_ResultadoBusqueda1_TitulacionesRepeater_"


def parsear_pagina_samai(html_txt: str) -> list:
    from bs4 import BeautifulSoup
    s = BeautifulSoup(html_txt, "html.parser")
    g = lambda i: s.find(id=P + i)
    v = lambda i: limpio(g(i).get_text(" ")) if g(i) else ""
    out = []
    for i in range(10):
        h = g(f"HypRadicado_{i}")
        if not h:
            break
        bloques = []
        for k in range(40):
            pre = f"TitulacionProvidenciaTexto1_{i}_TitulacionRepeater_{i}_"
            pj = g(f"{pre}ProblemaJuridicoLabel_{k}")
            if not pj:
                break
            it = pj.find_parent(class_="samai-titulacion-item")
            desc = it.find(class_="bg-light") if it else None
            texto = ""
            if it:
                for br in it.find_all("br"):
                    br.replace_with("\n")
                texto = "\n".join(limpio(d.get_text(" ")) for d in it.find_all("div", recursive=False))
            bloques.append({"desc": limpio(desc.get_text(" ")) if desc else "", "pj": v(f"{pre}ProblemaJuridicoLabel_{k}"),
                            "resp": v(f"{pre}SeResuelveProblemaJuridicoLabel_{k}"), "nota": v(f"{pre}NotaRelatoriaLabel_{k}"),
                            "fuente": v(f"{pre}FuenteLabel_{k}"), "texto": texto[:8000]})
        out.append({"rad": v(f"HypRadicado_{i}"), "interno": v(f"LblInterno_{i}"), "fproc": v(f"LblFECHAPROC_{i}"), "sala": v(f"LblSala_{i}"),
                    "clase": v(f"LblClaseProceso_{i}"), "ponente": v(f"LblPonente_{i}"), "actor": v(f"LblActor_{i}"),
                    "demandado": v(f"LblDemandado_{i}"), "fprov": v(f"Label1_{i}"), "tipo": v(f"LblTIPOPROVIDENCIA_{i}"),
                    "cert": v(f"Lblhash_{i}").replace("Certificado:", "").strip(), "bloques": bloques})
    return out


def incremental(max_paginas: int = 30, pausa: float = 1.0) -> int:
    import requests
    datos = cargar()
    sesion = requests.Session()
    sesion.headers["User-Agent"] = "Mozilla/5.0 (compatible; Tribudata.co ET concordado)"
    nuevas_total = 0
    for p in range(max_paginas):
        r = sesion.get(url_samai("", p, FILTRO_SAMAI), timeout=90)
        r.raise_for_status()
        fichas = [de_samai(x) for x in parsear_pagina_samai(r.text)]
        if not fichas:
            break
        nuevas = [f for f in fichas if f["id"] not in datos]
        nuevas_total += combinar(datos, nuevas)
        if not nuevas:          # orden por fecha descendente: una página sin novedades = al día
            break
        time.sleep(pausa)
    if nuevas_total:
        guardar(datos)
    print(f"Jurisprudencia CE: {nuevas_total} sentencias nuevas (total {len(datos)})")
    return nuevas_total


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--desde-lotes":
        desde_lotes(Path(sys.argv[2]))
    else:
        mx = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 30
        incremental(mx)
