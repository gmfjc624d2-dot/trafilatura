# Crítica técnica breve: proceso abstracto de contexto en una biblioteca local histórica

* **Solicitud:** `public-library-context-critique-20261020-01` (2026-10-20).
* **Objeto:** solo el texto abstracto de `QUESTION.txt`, guardado tal como se recibió, con las
  comillas «» y un salto de línea final.
* **Supuestos:** ninguna implementación privada. Todos los ejemplos son sintéticos.
* **Estado de la evidencia: hipótesis analítica.** No se ejecutó nada contra ningún sistema. El
  contraejemplo es una especificación con una respuesta esperada, no un resultado observado.

## 1. Limitación más importante (hipótesis)

La **vigencia** de una decisión es una propiedad *relacional y negativa*: equivale a decir que
ninguna fuente posterior la deja sin efecto, la sustituye o la modifica. Ninguno de los controles
descritos puede atestiguar algo así:
* las citas literales y los hashes prueban qué dice una fuente y que no cambió;
* la verificación de destinos prueba que la ruta resuelve.

El mecanismo de fallo es este:

1. La relación "por contenido/procedencia" no enlaza una revocación redactada solo por referencia,
   por ejemplo «Se deja sin efecto el acuerdo 14/2019». Esa frase no comparte vocabulario con el
   acuerdo. También puede enlazarla, pero como un "relacionado" sin tipo, sin la semántica *deja sin
   efecto*.
2. La entrada existente recibe una ruta a la decisión original. El destino existe, el hash coincide
   y la cita está presente, así que cada estado (inventario, lectura, comprensión, integración)
   pasa su propia comprobación.
3. El desconocido decisivo, *¿hay algo posterior que la anule?*, nunca se enumera. Por eso no puede
   «permanecer pendiente». La regla de pendientes solo cubre los desconocidos que el sistema llega a
   formular.
4. En el consumo, la pregunta posterior recibe una respuesta segura, citada y verificable, pero
   falsa: una **falsa comprensión útil**.

La causa raíz es un **cierre implícito**: la ausencia de una revocación *observada* se consume como
ausencia de revocación, sin que el sistema declare en qué ámbito buscó.

## 2. Contraprueba contenida (sintética, con respuesta esperada)

La biblioteca sintética contiene cuatro ficheros de texto:

| fichero | contenido literal |
|---|---|
| `actas/2019-03-acta-12.txt` (A) | «Propuesta: trasladar la sala de lectura al edificio norte.» |
| `actas/2019-05-acta-14.txt` (B) | «Acuerdo 14/2019: se aprueba trasladar la sala de lectura al edificio norte.» |
| `actas/2020-02-acta-03.txt` (C) | «Punto 2. Se deja sin efecto el acuerdo 14/2019.» |
| `indice/sala-de-lectura.md` (entrada existente) | «Sala de lectura: ver actas.» |

La pregunta posterior es: «¿Está vigente el traslado de la sala de lectura al edificio norte?».

**Condición 1: las cuatro fuentes están presentes.** Respuesta esperada:

> **No.** A es una propuesta. B aprobó el traslado. C, posterior, dejó B sin efecto.
>
> En la entrada deben quedar rutas a B y a C, con la relación tipada `C deja sin efecto B`. Que la
> sala esté hoy en otro sitio no lo afirma ninguna fuente: queda **pendiente**.

**Condición 2: C se retira de la copia de la biblioteca.** Respuesta esperada:

> B aprobó el traslado. Su vigencia queda **pendiente**, porque el inventario no declara cubrir las
> actas posteriores a 2019-05.

La contraprueba detecta el fallo si en cualquiera de las dos condiciones la respuesta es «sí, está
vigente» o «edificio norte», aunque traiga la cita literal y el hash de B. Las dos condiciones
separan los dos modos del mismo fallo:
* el enlace por referencia que se pierde (condición 1);
* la ausencia que se toma por negación (condición 2).

## 3. Mejora mínima que conviene probar después

**Barrido inverso de referencias con ámbito declarado.** Es una condición previa para que una
afirmación de vigencia alcance el estado "comprendido". No requiere dependencias nuevas.

* **El barrido.** Para cada fuente clasificada como decisión o versión, se recorren las fuentes ya
  inventariadas de fecha posterior. Se buscan sus identificadores (número de acuerdo, fecha, título)
  y verbos de supersesión: *deja sin efecto, deroga, sustituye, modifica, corrige*.
* **Lo que se registra.** La relación tipada encontrada, o «ninguna», junto con el **ámbito
  barrido**: la lista de fuentes, el intervalo de fechas y el hash del inventario.
* **Lo que puede responder el consumo.** Solo «vigente *en el ámbito X*». Sin ámbito, o con huecos
  conocidos (por ejemplo, numeración de actas salteada), la respuesta es **pendiente**.

La mejora se prueba con la contraprueba anterior, más un **control negativo**: una fuente D con
«En cumplimiento del acuerdo 14/2019 se encargan planos.». D menciona a B sin revocarlo. Con D
presente y C ausente, B debe seguir sin revocar (vigencia limitada al ámbito declarado). Así se
comprueba que la mejora clasifica la relación y no se limita a detectar menciones.

## 4. Qué no puede establecer el contraejemplo

* **No dice nada de un sistema concreto.** No muestra que una implementación concreta tenga este
  defecto, ni con qué frecuencia lo tendría: no se ejecutó nada. Solo muestra que el proceso, tal
  como está descrito, permite el fallo sin que ningún estado lo note.
* **Superarlo no prueba que el proceso sea correcto en general.** Quedan fuera:
  * revocaciones implícitas (una decisión posterior contradictoria que no cita la anterior);
  * modificaciones parciales;
  * revocaciones que están fuera de la biblioteca;
  * identificadores ambiguos (dos «14/2019» de órganos distintos) o mal transcritos;
  * fechas inciertas.
* **No puede probar que el inventario esté completo.** Ninguna prueba finita puede. Solo comprueba
  que la ausencia no se consume como negación sin un ámbito declarado.
* **Con cuatro ficheros cortos no mide nada más.** No mide el coste, la escala ni los falsos
  positivos del barrido léxico sobre textos reales. El control negativo D solo cubre el caso más
  simple.

## 5. Procedencia y recuperación

* **Base:** `b825cb4cc4514ae2d10d1d80bbff17e693833733`, rama `claude/adoring-turing-3ekxhe` del fork
  público `https://github.com/gmfjc624d2-dot/trafilatura`. Al empezar, local y remoto coincidían, no
  había divergencia y el árbol estaba limpio.
* **Este directorio es aditivo.** No se editó ni se re-ejecutó ninguna investigación anterior.
* **Contenido:** `QUESTION.txt`, `REPORT.md`, `SHA256SUMS`.
* **Commit:** el que añade este fichero,
  `git log -1 --format=%H -- research/public-library-context-critique-20261020-01/REPORT.md`.

Recuperación:

```sh
git clone --branch claude/adoring-turing-3ekxhe https://github.com/gmfjc624d2-dot/trafilatura.git trafilatura-critique
cd trafilatura-critique/research/public-library-context-critique-20261020-01
sha256sum -c SHA256SUMS        # macOS: shasum -a 256 -c SHA256SUMS
```
