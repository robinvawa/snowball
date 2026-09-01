# Snowball — mapa de distribuidores de Quantum Makers

Herramienta de content sourcing: encuentra los canales de YouTube
("distribuidores") que re-editan el mismo source material que Quantum Makers
(18,8M subs) y rankea a los creadores fuente por el valor demostrado de su
material. Todo el codigo vive en `ytsnowball/`; `memoria-claude/` guarda las
decisiones y aprendizajes destilados — leelos antes de cambiar metodologia.

## Ejecutar

- Python 3 estandar, sin dependencias (el unico extra es `yt-dlp` para
  `snowball_dlp.py`, que corre las busquedas sin gastar API).
- `python3 build_page.py` regenera el dashboard (`out/distributor_map.html`)
  desde los datos versionados; no gasta API.
- `python3 refresh.py` refresca todo contra la API (~600 unidades de las
  10.000 diarias): rota snapshots de views, re-descarga catalogos, rebuild.
- Expandir el mapa: `snowball.py N` (100 u/busqueda, tope ~60 busquedas/dia
  aparte de las unidades) o `snowball_dlp.py` en local sin cuota; despues
  `classify.py && verify.py A && full_catalog.py && build_page.py`.
- Necesita `ytsnowball/.env` con `YOUTUBE_API_KEY=...` (gitignored) solo para
  refrescar o expandir.
- `data/hubspot_all.csv` (export del CRM, gitignored por datos de contacto)
  alimenta el cruce de estados; sin el, `qfm.py` fallara — reponer el CSV o
  preguntar antes de tocar ese modulo.

## Decisiones que ya estan tomadas (no relitigar sin datos)

- **Views siempre a perpetuidad** al comparar (norma explicita del usuario);
  la proyeccion es fiable a partir de ~21 dias.
- **El ranking mide views atribuibles** (perpetuidad menos mediana del canal,
  sumado por distribuidor), no probabilidades: 8M demuestra mas que 2,6M y el
  fracaso nunca resta. Las "odds v1" quedan como columna de contraste.
- **Los distribuidores son capa de cobertura, no de prediccion** (r~0,25 con
  el resultado real de QM; el mejor predictor aparente era contaminacion).
- Shorts (<3 min reales) no entran en la base de datos.
- Los creditos se resuelven titulo primero, descripcion despues
  (`credits.py`, niveles pool/kw/unico + filtro de boilerplate por canal).
- El snowball re-busca creadores a los 14 dias (`searched_at`), compitiendo
  con los nuevos por views atribuibles.

## Dashboard

`out/distributor_map.html` esta publicado como Artifact de Claude:
https://claude.ai/code/artifact/a1330fbe-23d3-409a-b802-d5d4fd26f178
Para actualizar ese enlace desde otra sesion, publicar pasando esa URL como
`url`; publicar sin `url` crearia un artifact nuevo.
