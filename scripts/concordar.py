"""
Concordancia entre las normas del sitio: Estatuto Tributario, Decreto 1625 de 2016 y Resolución DIAN 227 de 2025
(y cualquier otra registrada en documentos.py).

Fuentes de la relación, por artículo:
  * enlaces del normograma de una norma a otra (en el texto y en los desplegables "Concordancias";
    en el ET, en todos sus desplegables, porque ahí el editor pone las concordancias hacia los decretos);
  * menciones en texto plano: "artículos 240 y 241 del Estatuto Tributario",
    "artículo 1.6.1.13.2.11 del Decreto 1625 de 2016".
La relación es simétrica.

Devuelve REL[id_articulo] = {doc: [ids ordenados del otro documento]}.
"""
import html as H
import re

RE_ENLACE = re.compile(r'href="et:x/([a-z0-9]+)/([^"]+)"')
RE_MENCION_ET = re.compile(
    r"art[íi]culos?\s+(\d+(?:-\d+)*(?:\s*(?:,|;|y|e|o|al|a)\s*\d+(?:-\d+)*)*)\s*(?:,\s*)?(?:y\s+siguientes\s+|parágrafo[^.]{0,40}?\s+)?"
    r"del\s+(?:presente\s+)?Estatuto\s+Tributario", re.I)
RE_MENCION_DUR = re.compile(
    r"art[íi]culos?\s+(\d+(?:\.\d+){2,}(?:\s*(?:,|;|y|e|o|al|a)\s*\d+(?:\.\d+){2,})*)\.?\s*(?:,\s*)?(?:y\s+siguientes\s+|parágrafo[^.]{0,40}?\s+)?"
    r"del\s+Decreto\s+(?:Único\s+Reglamentario\s+(?:en\s+Materia\s+Tributaria\s+)?)?(?:número\s+)?(?:1625\s+de\s+2016|Único\s+Reglamentario)", re.I)


def _plano(h: str) -> str:
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", h)))


def concordar(docs: dict) -> dict:
    """docs: {clave: json_parseado}. Devuelve REL[id] = {clave_doc: [ids]}."""
    ids = {d: {a["id"] for a in v["articulos"]} for d, v in docs.items()}
    orden = {a["id"]: i for v in docs.values() for i, a in enumerate(v["articulos"])}
    doc_de = {a["id"]: d for d, v in docs.items() for a in v["articulos"]}
    pref = {d: v["articulos"][0]["id"].split("-")[0] + "-" for d, v in docs.items() if v["articulos"]}
    rel = {}

    def unir(x, y):
        if x == y or doc_de.get(x) == doc_de.get(y):
            return
        rel.setdefault(x, {}).setdefault(doc_de[y], set()).add(y)
        rel.setdefault(y, {}).setdefault(doc_de[x], set()).add(x)

    for d, v in docs.items():
        for a in v["articulos"]:
            for b in a["bloques"]:
                if d == "et" or b["tipo"] == "texto" or b.get("etiqueta") == "Concordancias":
                    for destino, ancla in RE_ENLACE.findall(b["html"]):
                        if destino == d or destino not in docs:
                            continue
                        t = docs[destino]["anclas"].get(H.unescape(ancla))
                        if t and t.startswith("art/"):
                            unir(a["id"], t[4:])
                if b["tipo"] == "texto" and d != "et":
                    txt = re.sub(r"<[^<>]*>", " ", _plano(b["html"]))  # quita notas del editor <...>
                    if "et" in docs:
                        for m in RE_MENCION_ET.finditer(txt):
                            for num in re.findall(r"\d+(?:-\d+)*", m.group(1)):
                                if "art-" + num in ids["et"]:
                                    unir(a["id"], "art-" + num)
                    if "dur" in docs and d != "dur":
                        for m in RE_MENCION_DUR.finditer(txt):
                            for num in re.findall(r"\d+(?:\.\d+){2,}", m.group(1)):
                                if "dur-" + num in ids["dur"]:
                                    unir(a["id"], "dur-" + num)
    return {k: {d: sorted(s, key=lambda x: orden.get(x, 0)) for d, s in v.items()} for k, v in rel.items()}


JERARQUIA = ["et", "dur", "r227"]   # de mayor a menor rango
RE_MARCO = re.compile(r"(para\s+(?:los\s+)?efectos|para\s+(?:la\s+)?aplicaci[óo]n|en\s+desarrollo|reglament\w*|a\s+que\s+se\s+refiere|"
                      r"de\s+que\s+trata|en\s+los\s+t[ée]rminos|de\s+conformidad\s+con|conforme\s+(?:con|a)|previst\w+\s+en|establecid\w+\s+en|"
                      r"señalad\w+\s+en|dispuest\w+\s+en|consagrad\w+\s+en|contemplad\w+\s+en)[^.]{0,90}$", re.I)


def _referencias_con_posicion(a, destino, docs):
    """{id del artículo de `destino`: (posición en el texto plano, contexto previo)} según enlaces y menciones del texto."""
    pos = {}
    html_txt = "".join(b["html"] for b in a["bloques"] if b["tipo"] == "texto")
    plano = ""
    for p in re.split(r'(<a[^>]*href="et:x/[a-z0-9]+/[^"]+"[^>]*>)', html_txt):
        m = re.match(r'<a[^>]*href="et:x/([a-z0-9]+)/([^"]+)"', p)
        if m:
            if m.group(1) == destino:
                t = docs[destino]["anclas"].get(H.unescape(m.group(2)))
                if t and t.startswith("art/"):
                    pos.setdefault(t[4:], (len(plano), plano[-140:]))
        else:
            plano += re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", p)))
    rx, pref, pat = ((RE_MENCION_ET, "art-", r"\d+(?:-\d+)*") if destino == "et" else (RE_MENCION_DUR, "dur-", r"\d+(?:\.\d+){2,}"))
    for m in rx.finditer(plano):
        for num in re.findall(pat, m.group(1)):
            pos.setdefault(pref + num, (m.start(), plano[max(0, m.start() - 140):m.start()]))
    return pos


def tipos_relacion(docs: dict, rel: dict) -> dict:
    """Clasifica cada par (artículo de menor rango, artículo de mayor rango) relacionado:
      'reglamenta'   el de menor rango lo invoca en su epígrafe o al comienzo, enmarcándolo
                     ("Para efectos del artículo 20-1 del Estatuto…", "a que se refiere el artículo 562…");
      'cita'         lo menciona más adelante en su texto, de paso;
      'concordancia' la relación la puso el editor del normograma (no hay mención en el texto)."""
    doc_de = {a["id"]: d for d, v in docs.items() for a in v["articulos"]}
    tipos = {}
    for bajo in JERARQUIA[1:]:
        if bajo not in docs:
            continue
        for a in docs[bajo]["articulos"]:
            altos = [x for d2, lst in rel.get(a["id"], {}).items() if d2 in JERARQUIA[:JERARQUIA.index(bajo)] for x in lst]
            if not altos:
                continue
            refs = {}
            for destino in {doc_de[x] for x in altos}:
                refs.update(_referencias_con_posicion(a, destino, docs))
            epi = a.get("epigrafe", "")
            for x in altos:
                num = x.split("-", 1)[1]
                if x not in refs:
                    tipos[(a["id"], x)] = "concordancia"
                    continue
                posicion, previo = refs[x]
                en_epigrafe = re.search(r"\b" + re.escape(num) + r"\b", epi) is not None
                temprano = posicion < 350
                marco = RE_MARCO.search(previo) is not None
                tipos[(a["id"], x)] = "reglamenta" if en_epigrafe or (temprano and marco) or (posicion < 160) else "cita"
    return tipos


def referencias_internas(docs: dict) -> dict:
    """Remisiones dentro de una misma norma (enlaces del texto vigente): {id: [ids a los que remite]}."""
    out = {}
    orden = {a["id"]: i for v in docs.values() for i, a in enumerate(v["articulos"])}
    for d, v in docs.items():
        for a in v["articulos"]:
            vistos = []
            for b in a["bloques"]:
                if b["tipo"] != "texto":
                    continue
                for destino, ancla in RE_ENLACE.findall(b["html"]):
                    if destino != d:
                        continue
                    t = v["anclas"].get(H.unescape(ancla))
                    if t and t.startswith("art/") and t[4:] != a["id"] and t[4:] not in vistos:
                        vistos.append(t[4:])
            if vistos:
                out[a["id"]] = sorted(vistos, key=lambda x: orden.get(x, 0))
    return out


if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from documentos import DOCUMENTOS, RAIZ
    docs = {d: json.loads((RAIZ / "data" / c["json"]).read_text(encoding="utf-8")) for d, c in DOCUMENTOS.items()
            if (RAIZ / "data" / c["json"]).exists()}
    rel = concordar(docs)
    for d in docs:
        for o in docs:
            if d < o:
                n = sum(len(v.get(o, [])) for k, v in rel.items() if k.startswith(docs[d]["articulos"][0]["id"].split("-")[0] + "-"))
                print(f"{d} ⇄ {o}: {n} enlaces")
    for k in ("art-240", "art-631", "art-555-2", "art-868"):
        print(k, {d: len(v) for d, v in rel.get(k, {}).items()}, rel.get(k, {}).get("r227", [])[:6])
