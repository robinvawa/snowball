---
name: quantum-makers-scale
description: "Quantum Makers tiene 18,7M subs y su propio historial predice el éxito futuro mucho mejor que las señales de los canales distribuidores"
metadata: 
  node_type: memory
  type: project
  originSessionId: 3f338d17-5fc8-40da-8df5-32eae8532af0
  modified: 2026-08-11T12:56:10.643Z
---

Medido el 11 ago 2026 sobre el catálogo completo del canal (574 vídeos en scope,
93 % acreditan al creador fuente en el título, mediana de 3,0M de views a
perpetuidad). El canal tiene 18,7M de suscriptores — 6 veces el mayor
distribuidor del ecosistema.

**El dato que manda para sourcing:** en los 82 creadores de los que QM ha
publicado 2+ vídeos, si el primero fue outlier hubo otro acierto el **58 %** de
las veces; si no lo fue, solo el **27 %**. Factor 2,1.

**El dato que desinfla la tesis de los distribuidores:** sus señales solo
correlacionan r ≈ 0,25 con el resultado real de QM. Y el mejor predictor
aparente (número de distribuidores que cubren a un creador, AUC 0,673) resultó
ser contaminación: en el 88 % de los casos solapados QM publicó primero y los
distribuidores se apilaron después. Contando solo coberturas previas al vídeo de
QM, el AUC cae a 0,510 — azar puro.

**Why:** cambia dónde invertir el tiempo de sourcing. Minar el catálogo de los
117 creadores que ya funcionaron rinde más que cualquier ranking derivado de
distribuidores.

**How to apply:** tratar a los distribuidores como capa de *cobertura*
(encuentran creadores desconocidos, 504 sin explorar) y nunca como capa de
*predicción*. Ver [[ytsnowball-tool]] y
[[quantum-makers-distributor-strategy]] — esta medición matiza esa estrategia
sin invalidarla.
