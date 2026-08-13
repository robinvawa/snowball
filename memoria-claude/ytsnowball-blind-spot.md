---
name: ytsnowball-blind-spot
description: El snowball por handle no puede ver distribuidores que no acreditan al creador; la búsqueda por frase de proyecto es el complemento necesario
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 3f338d17-5fc8-40da-8df5-32eae8532af0
  modified: 2026-08-11T13:35:37.917Z
---

Descubierto el 11 ago 2026 al contrastar la salida de [[ytsnowball-tool]] con una
lista que un trabajador de Quantum Makers había reunido a mano. De sus 24
canales, 22 ya estaban; los 2 que faltaban (`@worldtechyt`, 200k subs, y
`@survivalchallenge.2023`, 38k) tienen **2 % y 0 % de atribución**.

**Why:** todo el método se apoya en el patrón `by @creador` del título. Un canal
que no acredita es invisible por construcción, no por falta de cuota. Sin este
contraste no se habría detectado, porque internamente el método parecía
exhaustivo.

**How to apply:** usar siempre las dos vías. `phrase_snowball.py` busca una frase
distintiva del proyecto en vez del handle y encuentra a los que no acreditan;
tiene peor señal/ruido (en una búsqueda: 21 reuploaders diminutos y 1
distribuidor real de 248k subs). Y no confundir los dos agujeros: el de
*cobertura* (solo se buscaron 63 de 687 creadores) se cierra gastando cuota; el
de *atribución* solo con búsqueda por frase.

Lección general: cuando un método de descubrimiento se apoya en un patrón que el
propio objetivo elige emitir, contrastar contra una muestra humana antes de dar
la lista por cerrada.
