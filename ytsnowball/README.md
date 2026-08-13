# Mapa de distribuidores — content sourcing

Encuentra los canales de YouTube que reeditan el mismo *source material* que
Quantum Makers, y construye el pool de creadores fuente que esos canales ya han
sintetizado y validado en mercado.

## Idea

Estos canales acreditan al creador original en el título (`... by @creador`).
Ese handle es un identificador exacto del raw material, así que:

1. De cada canal conocido se extraen sus atribuciones `@creador`.
2. Se busca cada creador en YouTube → aparecen todos los canales que lo cubrieron.
3. Los canales nuevos aportan más creadores → se repite (snowball).

Un canal se confirma como distribuidor si cubre 2+ creadores del pool, o si más
del 30 % de sus propios títulos usan el patrón de atribución.

## Puesta en marcha

Solo hace falta Python 3 (sin dependencias: todo con la librería estándar) y una
clave de la YouTube Data API v3, que se saca gratis en Google Cloud Console
activando esa API y creando una credencial de tipo *API key*.

```bash
echo "YOUTUBE_API_KEY=tu_clave_aqui" > .env
```

El `.env` está en `.gitignore` y **nunca se sube**. Los datos ya procesados vienen
en `data/`, así que para regenerar el dashboard no hace falta clave ni gastar
cuota:

```bash
python3 metrics.py && python3 creators.py && python3 model.py \
  && python3 qm_merge.py && python3 compare.py && python3 build_page.py
open out/distributor_map.html
```

La clave solo se necesita para **ampliar** el mapa (buscar creadores nuevos o
refrescar catálogos). `data/cache/` no se versiona porque son 64 MB y se
reconstruye sola.

## Uso completo

```bash
python3 resolve_seeds.py    # handles -> channel IDs (edita RAW para añadir seeds)
python3 harvest.py          # últimos 50 vídeos de cada seed + outlier score
python3 extract.py          # atribuciones @creador y topics
python3 snowball.py 40      # 40 búsquedas de creador (100 unidades cada una)
python3 classify.py         # resuelve stats y asigna tier A/B/C
python3 verify.py A         # harvest de los descubiertos: confirma y expande pool
python3 full_catalog.py     # catalogo COMPLETO de cada distribuidor, sin shorts
python3 report.py           # out/distributors.csv + out/source_creators.csv
python3 metrics.py          # perpetuidad, outlier age-neutral, consenso, score
python3 creators.py         # odds de que cada creador tenga un proyecto top
python3 qm.py               # catalogo propio de Quantum Makers (verdad de referencia)
python3 creator_channels.py # canales PROPIOS de los creadores (1 unidad c/u)
python3 model.py            # entrena con las etiquetas de QM y valida cruzado
python3 qm_merge.py         # cruza QM con el pool -> prioridad de sourcing
python3 compare.py          # analisis del ecosistema frente a QM
python3 build_page.py       # out/distributor_map.html (dashboard navegable)
```

Las columnas de la pestaña de distribuidores salen de `full_catalog.py`, que baja
el catálogo **entero** de cada canal en vez de una muestra de 50: 8.741 vídeos
largos tras excluir 3.859 shorts y directos, el **31 %** de lo que publican. Eso
cambia bastante las cifras — `TTI Build Stories` pasa de 16 creadores fuente
(según el snowball) a **113** reales, y `High speed Snail` resulta tener solo 14
vídeos largos de sus 370. Dos canales, MrDuck104 y MrDuck112, publican
**únicamente** shorts (mediana de 55 s) y quedan fuera de la lista: no tienen
contenido que exista para nosotros. Quedan 138.

### Detectar Shorts de verdad (`shorts.py`)

La duración sola no basta. YouTube subió el techo de los Shorts a **3 minutos**,
así que un vídeo de 180 s exactos *es* un Short, y por codificación algunos
devuelven 181 s. Verificado sobre uploads reales:

| duración | veredicto |
|---|---|
| ≤ 180 s | siempre Short |
| 181 s | todavía Short |
| ≥ 190 s | no es Short |

`shorts.py` corta por duración fuera de la franja dudosa y en la zona gris
(181-300 s) pregunta a YouTube: `/shorts/<id>` se queda en esa ruta si es Short y
redirige a `/watch` si no. No consume cuota de API y se cachea en disco.

**Por qué importa tanto:** con el filtro anterior (`< 180`) se colaban los Shorts
de 180 s exactos, y arrastraban millones de views. `TK Maker` figuraba con una
perpetuidad típica de **2,5 M**; con la detección real son **3.156**. Sus
millones eran íntegramente Shorts.

**Los shorts no existen.** `harvest.py` descarta en la cosecha cualquier vídeo de
menos de 3 minutos (`scope.MIN_SECONDS`), y también los de duración desconocida —
directos y estrenos vuelven como `P0D`. No es un filtro cosmético: la mediana de
cada canal es la base contra la que se mide todo outlier, y con shorts dentro
estaba deprimida en **47 de los 140 canales**. En el peor caso, `Gear Tech HD`
tenía mediana 66.234 en vez de 158.126, inflando cada uno de sus outliers por 2,4.
Al limpiarlo el AUC del modelo de creadores subió de 0,589 a 0,603.

`scope.py` no se ejecuta solo: lo usa `metrics.py` para marcar cada vídeo como
`in` / `unsure` / `out`. Sesgo conservador — solo descarta con señal negativa
fuerte (listicles de gadgets, celebrities, procesos de fábrica, memes) y **nunca**
descarta un vídeo que acredita a un creador fuente. La excepción es la duración:
`MIN_SECONDS = 180` es una regla dura que se evalúa antes que nada — por debajo
de 3 minutos queda fuera aunque acredite. El
vocabulario es multilingüe porque parte del material relevante no está en inglés.

Para seguir expandiendo, repite `snowball.py → classify.py → verify.py` cada día:
el pool de creadores crece en cada vuelta y el estado se acumula en
`data/snowball_state.json`.

## Punto ciego: los que no acreditan

El snowball de handles solo ve canales que escriben `by @creador` en el título.
Una revisión manual paralela encontró dos que nos faltaban — **World Tech**
(@worldtechyt, 200k subs) y **Survival Challenge** (38k) — y ambos tienen **2 % y
0 % de atribución**. Son estructuralmente invisibles al método.

De los 24 canales de esa revisión manual, 22 ya los teníamos (20 confirmados y 2
que eran seeds originales). Nuestra lista tiene 123 que la suya no. Pero el
agujero es real y no se puede tapar con más búsquedas de handle.

**La solución es `phrase_snowball.py`:** buscar el *proyecto* en vez del creador.
Se toma una frase distintiva de un título ya conocido y aparece cualquiera que
haya cubierto el mismo build, acredite o no.

Rendimiento medido en una sola búsqueda: 23 canales desconocidos, de los cuales
21 son reuploaders diminutos que copian el título literal (medianas de 26 views,
contenido inconexo) y **1 era un distribuidor real de 248k subs** — Living Ideas,
32 % de atribución y un vídeo de 12,4M. Peor relación señal/ruido que el método
de handles, pero encuentra lo que aquel no puede.

Nota: Living Ideas *sí* acredita, así que no era invisible — se nos escapó porque
solo se buscaron 63 de los 687 creadores. Son dos agujeros distintos: el de
cobertura se cierra gastando cuota, el de atribución solo con búsqueda por frase.

### La descripción como tercera vía

Los dos canales «invisibles» resultaron ser casos opuestos:

| canal | atribución en título | en descripción |
|---|---|---|
| World Tech | 2 % | **38 %** |
| Survival Challenge | 0 % | 0 % |

World Tech sí acredita, solo que repitiendo el título con el `@handle` en la
descripción. Survival Challenge no acredita en ningún sitio y solo la búsqueda
por frase lo alcanza.

**Bug encontrado al medir esto:** `handles()` capturaba direcciones de correo —
`alguien@gmail.com` produce el token `gmail.com`, y el filtro de stopwords
comparaba contra `gmail`, así que nunca disparaba. Inflaba la atribución por
descripción en 402 vídeos (Survival Challenge aparecía con un 92 % que era todo
emails). Ya corregido, junto con dominios tipo `.agency` e IDs crudos `UCxxx`
pegados en las descripciones. **Los rankings de creadores no estaban afectados**:
usan solo `source_handles_title`.

**Cuánto aporta la descripción:** poco en canales (solo 4 de 140 pasarían el
umbral del 30 % gracias a ella) pero mucho en pool — 502 creadores nuevos en
bruto. El problema es la calidad: 143 menciones son autopromoción del propio
canal y 135 son otros distribuidores cruzándose promoción. Quedan ~467
candidatos genuinos, de los que solo 84 aparecen 2 o más veces. Sirve como vía
secundaria con filtro estricto, nunca al mismo nivel que el título.

## Cuota

La API da 10.000 unidades/día, pero **las búsquedas tienen un contador propio y
más restrictivo** (~60/día en este proyecto) que devuelve HTTP 429. El resto de
llamadas son baratísimas: `channels`, `videos` y `playlistItems` cuestan 1 unidad
y van en lotes de 50.

Todas las respuestas se cachean en `data/cache/`, así que re-ejecutar un paso no
vuelve a gastar cuota. `data/quota.json` lleva el contador del día.

## Views a perpetuidad

```
z  = ((d+1) / 290.9357027) ** 0.672538774      # d = edad del vídeo en días
zH = (1279  / 290.9357027) ** 0.672538774
madurez(d)  = (z / (1+z)) / (zH / (1+zH))      # satura en d = 1278
perpetuidad = views / madurez(d)
```

Curva: 25 % de las views al mes, 43 % a los 3 meses, 74 % al año, 89 % a los
2 años. Un vídeo de 1 día recibe un multiplicador de x34, así que por debajo de
21 días la proyección es extrapolación agresiva; `metrics.py` la marca como
confianza `baja` y amortigua su score.

## Score de interés

Cuatro percentiles ponderados: outlier de perpetuidad (34 %), alcance proyectado
(28 %), **consenso entre distribuidores** (28 %) y engagement (10 %).

El consenso es la señal más difícil de falsear: de todos los canales que
cubrieron ese mismo creador fuente, cuántos superaron su propia línea base. Si 5
canales distintos ganan con el mismo proyecto, el mérito es del proyecto y no del
canal.

## Odds de proyecto top por creador

Solo hace falta **un** proyecto top por creador, así que el score lo manda su
mejor demostración, no su media. Las lecturas flojas nunca restan: solo dejan de
sumar. Un creador con un pico enorme y cinco fracasos ya ha demostrado que el
proyecto existe.

```
fuerza(lectura) = min( percentil del outlier , percentil del alcance )
fuerza(creador) = la mejor de sus lecturas
odds = 1 - (1 - fuerza) * 0.6 ** (nº de confirmaciones)
```

El `min` de los dos percentiles es el **ajuste por tamaño de canal**: una lectura
solo cuenta si superó la línea base de su canal *y* llegó a gente de verdad. Un
x400 que alcanzó 800 personas es un artefacto de una mediana minúscula; un x5 que
alcanzó 3,5M es un resultado real. Con esto `@ProcessK` (pico x137, 3.981 views
proyectadas) cae por debajo del 50 %.

Ese ajuste está medido, no supuesto:

- La dispersión interna del log-outlier es **plana** entre tamaños de canal
  (~0,67–0,80 sd en todos los tramos), así que normalizar por volatilidad del
  canal no habría servido de nada.
- Lo que sí separa a los canales es su **valor predictivo**: una lectura de un
  canal <10k subs correlaciona 0,030 con el resto de lecturas del mismo creador,
  frente a 0,120 en los de 10k–100k. El alcance es la variable que arrastra esa
  credibilidad, así que es el alcance lo que se exige.

Cada confirmación (otro distribuidor que también lo petó con ese creador) elimina
el 40 % de la duda restante. `evidence` = `débil` avisa de que todo se apoya en
una única lectura sin confirmar.

Modelos descartados por el camino, por si se reconsideran:

- **Mezcla de dos componentes por EM** — inestable, `pi` saltaba de 0,08 a 0,49
  según el umbral de hit.
- **Beta-Binomial sobre hits binarios** — el prior salía equivalente a 94
  observaciones y aplastaba a todos al 50 %.
- **Jerárquico gaussiano con contracción hacia la media** — estadísticamente
  correcto, pero responde a la pregunta equivocada: penalizaba justo el perfil de
  «un pico enorme + varios fracasos», que es el que nos interesa. Dejó un dato
  útil, eso sí: ICC = 0,127, o sea que solo el 13 % de la varianza del outlier es
  atribuible al creador y el 87 % es ejecución del distribuidor y azar.

## Quantum Makers como verdad de referencia

Todo lo demás en este proyecto es un proxy. El catálogo propio de QM (574 vídeos
en scope, 93 % con creador acreditado, mediana de 3,0M de views a perpetuidad) es
lo único que responde directamente a «¿le funcionaría esto a nuestro canal?».
Cruzarlo con el pool de distribuidores da tres resultados, y dos de ellos obligan
a matizar el resto del proyecto.

**1. Vuestro historial predice, y bien.** En los 82 creadores con 2+ vídeos de QM:

| primer vídeo de QM | P(otro acierto después) |
|---|---|
| fue outlier (x2+) | **58 %** |
| no lo fue | **27 %** |

Factor 2,1. Ranquear por creador tiene sentido, y el track record propio es con
diferencia el mejor predictor disponible.

**2. Las señales de distribuidores predicen poco.** Contra el resultado real de
QM correlacionan r ≈ 0,25 (6 % de varianza explicada).

**3. Y buena parte de eso era espejismo.** El mejor predictor aparente era el
*número* de distribuidores que cubren a un creador (AUC 0,673). Pero en el 88 %
de los 182 creadores solapados **QM publicó primero**: los distribuidores se
apilan sobre lo que ya funcionó. Contando solo coberturas *anteriores* al vídeo
de QM, el AUC cae a **0,510** — azar exacto.

Salvedad importante: solo 22 creadores tienen cobertura previa, así que esto no
demuestra que la señal no sirva; demuestra que no hay evidencia de que sirva y
que la que parecía fuerte era contaminación. Además hay sesgo de selección fuerte
— solo se observan creadores que QM eligió cubrir.

**Consecuencia práctica:** los distribuidores valen como *cobertura* (encuentran
creadores desconocidos) y no como *predicción*. `qm_merge.py` ordena primero por
situación respecto al canal propio y solo después por señal de distribuidor:

- `probado_ok` (117) — ya funcionó, minar su catálogo. La acción más rentable.
- `sin_explorar` (504) — donde está el descubrimiento; el orden interno es una
  lista de candidatos, no un ranking fiable.
- `probado_flojo` (244) — deprioritzar.

## Modelo entrenado con las etiquetas de QM

`creator_channels.py` resuelve el canal **propio** de cada creador fuente (824 de
865). Hasta entonces cada variable describía lo que los *distribuidores* hacían
con su material; ninguna describía al creador. `model.py` entrena una regresión
logística sobre las 358 etiquetas de QM.

AUC validado cruzado (5 folds), honesto:

| conjunto | AUC |
|---|---|
| todo el histórico | 0,59 |
| vídeos de QM recientes (<120 d) | **0,76** |

El régimen reciente es el que aplica: al puntuar hoy a un creador sin explorar,
su tamaño se mide en el momento de la decisión, igual que en un vídeo reciente.

### Descartar la causalidad inversa

QM tiene 18,7M de subs, así que featurear a alguien le infla el canal. Dos tests:

- **El test obvio es inválido.** Filtrar por «views de QM / views del creador
  < 0,1» sube el AUC de 0,60 a 0,77, pero ese filtro elimina justo los casos
  donde QM petó con un creador *pequeño* — los contraejemplos de la regla.
  Selección de colisionador; el resultado es gratis y no vale.
- **El test temporal sí vale.** Si la inflación mandara, la señal sería más
  fuerte cuanto más tiempo lleva publicado el vídeo. Sale al revés:

  | antigüedad del vídeo de QM | AUC de subs del creador |
  |---|---|
  | < 120 días | **0,828** (n=43) |
  | 120–400 días | 0,576 (n=105) |
  | > 400 días | 0,576 (n=208) |

  Control: el nº de vídeos del creador, que QM no puede inflar, no predice nada
  en ningún tramo (0,48 / 0,45 / 0,53).

### Qué aporta de verdad

Comparadas con validación cruzada en el régimen reciente, todas las señales
quedan entre 0,71 y 0,79 y **con n=43 no se pueden distinguir entre sí**. Así que
el modelo combinado se usa por robustez, no porque gane.

Lo concreto que aporta es rescatar creadores enormes que la señal de
distribuidores hundía:

| creador | subs | views/vídeo | señal distribuidores |
|---|---|---|---|
| `@marusya_outdoors` | 20,6M | 72M | x4, 7.951 de alcance |
| `@lifeinjungle78` | 3,69M | 8,4M | x2, 30.522 |

## El ecosistema frente a Quantum Makers

`compare.py` cruza los 140 distribuidores con el canal propio. Lo que sale:

**Escala.** No hay comparación. Los 140 juntos suman 356M de views frente a
3.469M vuestras, con cinco veces más vídeos publicados. El vídeo típico hace 834
views contra 2,09M — un factor de **2.507**.

**Solapamiento de pools.** 433 creadores son solo suyos, 178 compartidos, 183
solo vuestros. Ellos tocan el 49 % de vuestros creadores; vosotros el 29 % de los
suyos. La asimetría es la oportunidad.

**Radar o espejo.** La métrica operativa. Sobre creadores compartidos,
publicaron antes que QM **48** veces y después **716** — os siguen el 94 % del
tiempo. Solo 34 canales han llegado antes alguna vez; 89 no lo han hecho nunca.
Un canal que solo publica después es un espejo y no puede aportar señal, por muy
grande que sea. Los pocos que lideran (SwiftBuild y Survival Skills, 4 veces cada
uno) son los que merece la pena monitorizar de verdad.

**El hueco.** 433 creadores que ellos cubren y QM nunca ha tocado, 80 de ellos
pasados por 3 o más canales distintos. Es la lista de sourcing más directa que
produce todo el proyecto. Encabezan `@lifeanywhere` (24 distribuidores),
`@LetsBuildAHouse` (23) y `@ThisIsMyAlaska` (22).

**Suplantación de marca.** El detector exige el componente distintivo —
«quantum» o una variante a una letra, como *Quantam* — porque «maker» a secas es
vocabulario genérico del nicho y lo usa medio ecosistema. Con ese criterio son 5:
Quantum Markers TV, Q Makers, Quantum Build Studio, Quantum Builders y Quantam
Tech HD.

Salidas: `out/gap_creators.csv` y `out/distributor_roles.csv`.

## Norma: views = views a perpetuidad

**Siempre.** En toda media, suma, mediana, outlier o comparación entre canales se
usa `perpetuity_views`, nunca el contador crudo. Las views crudas castigan a
quien publicó hace poco: un vídeo de 34 días lleva acumulado solo el 27 % de sus
views finales, así que compararlas mide antigüedad y no rendimiento. El dato
crudo solo se muestra como referencia junto a la proyección.

## Métrica clave: outlier, no views absolutas

`outlier = perpetuidad del vídeo / mediana de perpetuidad del canal`. Un vídeo
con 80k proyectadas en un canal que hace 5k de mediana (x16) es señal fuerte; las
mismas 80k en un canal que hace 100k no dicen nada. La validación real es el
**mismo raw funcionando en varios canales distintos**, que es lo que mide la
columna *distribuidores* del pool de creadores.

## Salidas

- `out/distributors.csv` — 140 canales con subs, vídeos, views/vídeo, creadores
  cubiertos, tasa de atribución y flags (`is_seed`, `brand_lookalike`).
- `out/source_creators.csv` — 687 creadores fuente con cuántos distribuidores los
  cubrieron y los múltiplos outlier obtenidos.
- `out/distributor_map.html` — dashboard filtrable y ordenable.

## Nota sobre la API key

Está en `.env` (ignorado por git). Conviene restringirla en Google Cloud Console
a la YouTube Data API y rotarla si se ha compartido por canales no seguros.
