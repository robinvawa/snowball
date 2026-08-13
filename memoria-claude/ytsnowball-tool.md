---
name: ytsnowball-tool
description: Herramienta en /Users/valero/Cloude code/ytsnowball que descubre canales distribuidores de YouTube por snowball sobre atribuciones @creador
metadata: 
  node_type: memory
  type: project
  originSessionId: 3f338d17-5fc8-40da-8df5-32eae8532af0
  modified: 2026-08-11T11:31:24.983Z
---

Construida el 11 ago 2026 para [[quantum-makers-distributor-strategy]]. Python 3
con solo stdlib (urllib), sin dependencias.

**El insight que la hace funcionar:** estos canales acreditan al creador original
en el propio título (`... | Start to Finish by @creador`), en el 57 % de los
casos. Ese handle identifica el raw material de forma exacta, así que el snowball
va creador → canales que lo cubrieron → sus creadores → etc. Sin matching difuso.

Resultado de la primera pasada: 13 seeds → **140 distribuidores confirmados** y
687 creadores fuente, con solo 63 búsquedas.

**Why:** el método por plantilla de título o por "canales similares" da mucho
ruido; la atribución `@creador` es lo único que identifica el pool compartido.

**How to apply:** para seguir expandiendo, repetir
`snowball.py → classify.py → verify.py` en días sucesivos. Ojo: la YouTube API
tiene un **contador diario propio para búsquedas** (~60/día, HTTP 429) aparte de
las 10.000 unidades generales; el resto de endpoints cuestan 1 unidad en lotes de
50. Todo se cachea en `data/cache/`, así que re-ejecutar no gasta cuota.
