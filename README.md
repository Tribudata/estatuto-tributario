# Estatuto Tributario concordado — Tribudata.co

Sitio estático de consulta del **Estatuto Tributario** (Decreto 624 de 1989), del **Decreto 1625 de 2016**
(Único Reglamentario en Materia Tributaria) y de la **Resolución DIAN 227 de 2025** (Resolución Única en Materia
Tributaria, Aduanera y Cambiaria), enlazados artículo por artículo, con sus desplegables
(Notas de Vigencia, Concordancias, Doctrina, Jurisprudencia, Legislación Anterior y Notas del Editor),
**sincronizado automáticamente** con el normograma DIAN:

* https://normograma.dian.gov.co/dian/compilacion/docs/estatuto_tributario.htm
* https://normograma.dian.gov.co/dian/compilacion/docs/decreto_1625_2016.htm
* https://normograma.dian.gov.co/dian/compilacion/docs/resolucion_dian_0227_2025.htm

Las normas se registran en `scripts/documentos.py`: para sumar otra (por ejemplo, una resolución nueva)
basta con agregar una entrada y ejecutar `python scripts/actualizar.py --forzar`.

## Funciones

* **Concordancia entre normas.** Cada artículo del ET muestra los artículos del DUR 1625 y de la Resolución
  227 que lo reglamentan; cada artículo del DUR o de la Resolución muestra los del ET (y entre ellas) con que
  concuerda. La relación se arma con los enlaces del texto y de los desplegables "Concordancias", con las
  menciones en texto ("artículos 240 y 241 del Estatuto Tributario", "artículo 1.6.1.13.2.11 del Decreto
  1625 de 2016") y con las concordancias que el editor del normograma puso en el ET.
* **Anexos de la Resolución 227** (especificaciones técnicas de exógena, factura electrónica, etc.) y del DUR
  como páginas propias, con enlace al PDF oficial; se encuentran buscando, por ejemplo, "formato 1001".
* **Doctrina DIAN (conceptos y oficios).** Los ~16.200 documentos de la doctrina tributaria del normograma
  (1987 a hoy) entran a la búsqueda en vivo con la etiqueta "Doctrina DIAN" (por tema, número —p. ej. `18702`—,
  descriptores y, con la casilla de notas activada, problema y tesis jurídica). Cada artículo del ET, del DUR y
  de la Resolución 227 muestra "Conceptos y oficios DIAN que lo citan", del más reciente al más antiguo: la relación
  sale de los artículos que cada concepto cita (enlaces del normograma y menciones en texto) y de la
  "Doctrina Concordante" del editor. Clic en un concepto: vista rápida con fecha, problema jurídico, tesis,
  descriptores, fuentes formales, extracto y normas citadas; el texto completo se abre en el normograma.
  `scripts/doctrina.py` mantiene `data/doctrina/<año>.json` y en cada actualización descarga solo los nuevos.
* **Jurisprudencia del Consejo de Estado (Sección Cuarta).** Las sentencias (sin tutelas) tituladas en
  SAMAI · Mi Relatoría desde el 1 de diciembre de 2021, y las de la relatoría tradicional hasta el 30 de noviembre de
  2021 cuyo sustento normativo incluye el Estatuto Tributario, entran a la búsqueda con la etiqueta "Consejo de Estado"
  (por tema, número interno —p. ej. `27998`—, radicado, ponente o partes). Cada artículo muestra "Sentencias del Consejo
  de Estado que lo aplican", de la más reciente a la más antigua: la relación sale de la fuente formal / sustento
  normativo de la relatoría ("ESTATUTO TRIBUTARIO - ARTÍCULO 771-2", "DECRETO 624 DE 1989 - ARTÍCULO 670") y de las
  menciones del extracto. Clic: ponente, partes, problemas jurídicos con su respuesta, tesis, descriptores, decisión y
  normas que aplica; el texto completo se abre en la relatoría (enlace estable por NR) o en SAMAI (búsqueda por número
  de proceso). `scripts/jurisprudencia.py` mantiene `data/jurisprudencia/<año>.json` y en cada actualización trae las
  sentencias nuevas de SAMAI.
* **Conceptos del Consejo Técnico de la Contaduría Pública (CTCP).** De los ~12.000 conceptos publicados en
  ctcp.gov.co/conceptos (2001 en adelante) se leen los de 2019 en adelante y, de los años anteriores (PDF escaneados,
  con OCR), los de temática tributaria. Se publican los que citan el ET, el DUR 1625 o la Res. 227, o tratan un asunto
  tributario, más los documentos de orientación técnica que citan el Estatuto (DOT 14, 15, 16 y 18; el 16 trata la
  interacción entre la base contable y la fiscal). Cada artículo muestra "Conceptos del CTCP que lo citan"; clic:
  número de radicación, fecha, ponente, resumen oficial, consulta, extracto de la respuesta, normas tributarias que cita
  (enlazadas) y el resto de la normativa concordante que invoca (Ley 1314 de 2009, DUR 2420 de 2015, Ley 43 de 1990,
  Código de Comercio, NIIF/NIC, secciones de la NIIF para las Pymes…); ↗ abre el PDF oficial. Etiqueta "CTCP" en la
  búsqueda (por tema, número `2024-0168`, ponente o norma). `scripts/ctcp.py` mantiene `data/ctcp_meta.json`
  (catálogo), `data/ctcp_txt/` (texto de cada PDF) y `data/ctcp/<año>.json` (fichas); en cada actualización revisa el
  año en curso y el anterior y trae solo los conceptos nuevos.
* **Texto completo de las sentencias de la relatoría tradicional.** Como la relatoría entrega cada sentencia solo
  como descarga, el sitio guarda una copia limpia del texto (`data/sentencias/<año>/<NR>.html`, generada por
  `scripts/textos_sentencias.py` desde el HTML o el Word oficial) y publica una página por sentencia
  (`sentencias/<NR>.html`): ficha, problemas jurídicos, titulación, normas que aplica y el texto completo, con enlace al
  original. Se abre en pestaña nueva con ↗ y también en la vista rápida.
* **Vista rápida.** Clic en cualquier artículo enlazado (concordancias o referencias dentro del texto):
  se abre un panel lateral con el texto completo sin salir de la página. Desde ahí: *Ir al artículo*,
  *Pestaña nueva ↗*, o seguir navegando con *←*. Ctrl/Cmd+clic abre directo en pestaña nueva.
* **Búsqueda en vivo** sobre el ET, el DUR y la Resolución 227: los resultados aparecen debajo del campo
  mientras se escribe, con la fuente (ET / DUR 1625 / Res. 227) en cada uno; ↑ ↓ y Enter para elegir. Funciona por número
  (`240`, `771-5`, `1.2.1.5.3.4`), por palabras o por frase exacta entre comillas. Filtros: fuente, incluir
  notas/concordancias/doctrina/jurisprudencia, excluir derogados. "Ver todos los resultados" abre la lista
  completa con botón **← Volver al inicio**; en todas las páginas hay botón **Inicio** en la barra.
* Una página por artículo con URL citable, índice navegable por libro/parte/título/capítulo/sección,
  filtros de desplegables y página **Novedades** con lo que cambió en cada actualización.

## Cómo se actualiza

```
normograma DIAN ──(GitHub Actions, 2 veces al día)──► scripts/actualizar.py
   <doc>.htm      (texto)                                 │ ¿cambió Last-Modified / contenido? (por documento)
   js/<doc>.js    (desplegables)                          ▼
   data/corte.txt (fecha de corte)                  scripts/parsear.py et|dur ──► data/estatuto.json, data/dur1625.json
                                                          │                         data/cambios.json
                                                          ▼
                                                    scripts/construir_sitio.py (+ concordar.py) ──► site/ ──► GitHub Pages
```

Solo se regenera cuando el normograma publica una versión nueva. Si una descarga llega incompleta o con
muchos menos artículos, no se publica nada.

## Estructura

| Ruta | Qué es |
|---|---|
| `scripts/actualizar.py` | Descarga ET y DUR y detecta cambios (usa `requests`). `--forzar` para regenerar siempre. |
| `scripts/documentos.py` | Registro de normas (ET, DUR 1625, Res. 227): archivos, carpetas y niveles del índice. |
| `scripts/parsear.py` | Fuente DIAN → JSON (árbol + artículos + desplegables). `python scripts/parsear.py et`, `dur` o `r227`. |
| `scripts/concordar.py` | Calcula la concordancia entre todas las normas registradas. |
| `scripts/doctrina.py` | Catálogo y fichas de la doctrina DIAN (conceptos y oficios); actualización incremental. |
| `scripts/construir_sitio.py` | JSON → sitio en `site/`. `--base-url` define la URL pública (canonical y sitemap). |
| `scripts/empaquetar_vista_previa.py` | Empaqueta el sitio en pocos archivos para vistas previas. |
| `plantillas/` | CSS y JS del sitio (marca navy/oro de Tribudata.co). |
| `data/fuente*/` | Última copia de los archivos del normograma (una carpeta por norma). |
| `data/doctrina/` | Fichas de los conceptos y oficios DIAN, un archivo por año. |
| `scripts/ctcp.py` | Conceptos y orientaciones técnicas del CTCP: texto de los PDF (OCR si son escaneados), citas y fichas. |
| `data/ctcp/`, `data/ctcp_txt/`, `data/ctcp_meta.json` | Fichas por año, texto de cada concepto y catálogo del CTCP. |
| `.github/workflows/actualizar.yml` | Programación y publicación automática. |
| `actualizar_local.bat` | Plan B: actualizar desde un PC Windows si GitHub no alcanza el normograma. |

El sitio incluye `api/et/<n>.json`, `api/dur/<n>.json`, `api/r227/<n>.json` (texto, desplegables y concordancias de cada artículo)
y `api/indice.json`: es la base para la fase de IA (RAG, chat o servidor MCP).

## Puesta en marcha (una sola vez)

tribudata.co está hecho en Google Sites, que no aloja archivos propios. Por eso el Estatuto se publica en
**GitHub Pages** con el subdominio **https://estatuto.tribudata.co/** y se enlaza desde el menú de Google Sites.

1. Crear el repositorio **público** `estatuto-tributario` en la cuenta/organización **Tribudata** y subir esta
   carpeta (con GitHub Desktop o `git push`; la carga web limita archivos a 25 MB).
2. *Settings → Actions → General → Workflow permissions*: **Read and write permissions**.
3. *Settings → Pages → Build and deployment → Source*: **GitHub Actions**.
4. *Actions → "Actualizar y publicar Estatuto Tributario concordado" → Run workflow*.
5. DNS del dominio (donde se administra tribudata.co): registro **CNAME** `estatuto` → `tribudata.github.io`.
6. *Settings → Pages → Custom domain*: `estatuto.tribudata.co` → Save; cuando el certificado esté listo,
   marcar **Enforce HTTPS**.
7. En Google Sites: agregar al menú un vínculo a `https://estatuto.tribudata.co/` (y, si se quiere, el
   buscador incrustado de `incrustar_google_sites.html`) y publicar.

Para otro dominio, defina la variable del repositorio `BASE_URL` (*Settings → Secrets and variables →
Actions → Variables*).

## Uso local

```bash
pip install -r requirements.txt
python scripts/actualizar.py --forzar     # descarga ET, DUR y Res. 227 del normograma
python scripts/construir_sitio.py         # genera site/
python -m http.server -d site 8000        # http://localhost:8000
```

## Nota sobre derechos

El texto de las normas es de libre uso. Las notas de vigencia, concordancias y demás anotaciones son
compilación editorial de Avance Jurídico Casa Editorial Ltda. para la DIAN; el sitio cita la fuente en cada
página y enlaza al normograma oficial. Revise los créditos y la reserva de derechos del normograma antes
de explotar comercialmente esas anotaciones.
