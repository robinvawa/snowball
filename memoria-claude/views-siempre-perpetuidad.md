---
name: views-siempre-perpetuidad
description: "Cuando el usuario dice \"views\" comparando vídeos o canales, siempre se refiere a views proyectadas a perpetuidad, nunca crudas"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 3f338d17-5fc8-40da-8df5-32eae8532af0
  modified: 2026-08-11T14:43:24.432Z
---

Norma dada explícitamente el 11 ago 2026: «siempre que hablo de views me refiero
a views a la perpetuidad, siempre que estemos comparando vídeos views me refiero
a views perpetuidad».

**Why:** las views crudas castigan sistemáticamente a quien publicó más
recientemente. Un vídeo de 34 días lleva acumulado solo el 27 % de sus views
finales, así que cualquier media, suma o ranking sin proyectar mide antigüedad
en vez de rendimiento.

**How to apply:** por defecto usar `perpetuity_views` en toda media, suma,
mediana, outlier o comparación entre canales. Las views crudas solo se muestran
como dato informativo junto a la proyección, nunca como base de una comparación.
La fórmula está en `metrics.maturity()` — ver [[ytsnowball-tool]].
