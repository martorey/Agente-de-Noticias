# Agente de Noticias

Tres veces al día recolecta los titulares nacionales (Chile) e internacionales
de una veintena de medios, los deduplica, publica una página web con el
resultado y te manda el enlace por WhatsApp cuando hay volumen suficiente de
noticias nuevas.

Todo corre en GitHub Actions: no hace falta un servidor ni dejar el computador
encendido.

```
RSS de ~24 medios ──▶ deduplicar y ordenar ──▶ página en GitHub Pages
                                                      │
                                                      └──▶ WhatsApp (CallMeBot)
```

---

## Estado: en producción

El repositorio es público y GitHub Pages está activo. La página se actualiza
sola tres veces al día — no hace falta ninguna acción manual para que siga
funcionando.

La página publicada es pública: cualquiera con el enlace puede verla. Como
sólo contiene titulares y enlaces de medios públicos, no hay información
sensible — se puede compartir el enlace libremente.

---

## Configuración

### 1. Obtener la API key de CallMeBot

CallMeBot es gratuito y no requiere registro:

1. Agendá el número **+34 644 51 95 23** en tu teléfono (por ejemplo como "CallMeBot").
2. Mandale por WhatsApp el mensaje exacto: `I allow callmebot to send me messages`
3. Te responde con tu **API key** (unos 6-7 dígitos).

La respuesta llega en pocos minutos. La key queda asociada a tu número.

### 2. Cargar los secretos

En **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Valor | Ejemplo |
| --- | --- | --- |
| `CALLMEBOT_PHONE` | Tu número con código de país | `+56912345678` |
| `CALLMEBOT_APIKEY` | La key que te dio CallMeBot | `123456` |

### 3. Activar GitHub Pages

En **Settings → Pages → Build and deployment → Source**, elegí **GitHub Actions**
(no "Deploy from a branch").

El workflow intenta activarlo solo, pero con el repositorio privado GitHub
rechaza el intento (*"Create Pages site failed: Resource not accessible by
integration"*): el token de Actions no puede crear el sitio. Puede que funcione
una vez que el repositorio sea público; no está verificado, así que contá con
hacerlo a mano.

La página va a quedar en:
`https://martorey.github.io/Agente-de-Noticias/`

### 4. Probar

En la pestaña **Actions → Agente de noticias → Run workflow**. La primera corrida
publica la página y te manda el WhatsApp. En el resumen de la corrida vas a ver
cuántas fuentes respondieron.

Si preferís probar sin que llegue el mensaje, marcá la casilla
*"Publicar la página sin enviar el WhatsApp"*.

---

## Ajustes opcionales

Se configuran en **Settings → Secrets and variables → Actions → Variables**
(no son secretos, son variables normales):

| Variable | Por defecto | Para qué sirve |
| --- | --- | --- |
| `SITE_TITLE` | `Últimas noticias` | Título de la página y del WhatsApp |
| `TIMEZONE` | `America/Santiago` | Zona horaria de las horas mostradas |
| `NOTIFY_MODE` | `solo-nuevas` | Sólo avisa si hay titulares nuevos; `siempre` avisa en cada corrida |
| `NOTIFY_MIN_NEW` | `10` | Con `solo-nuevas`, mínimo de titulares nuevos para avisar (sólo importa mientras `NOTIFY_MODE=solo-nuevas`) |
| `NOTIFY_HEADLINES` | `3` | Cuántos titulares por sección van en el WhatsApp |
| `MAX_ITEMS_PER_SECTION` | `40` | Cuántas noticias muestra la página por sección |
| `MAX_AGE_HOURS` | `24` | Descarta noticias más viejas que esto |
| `FUENTES_EXTRA` | — | Habilita fuentes apagadas, separadas por coma (`Al Jazeera, The Guardian`) |
| `FUENTES_EXCLUIDAS` | — | Apaga fuentes por nombre (`Infobae, Publimetro`) |
| `SITE_URL` | se deduce | Sólo si usás un dominio propio |

### Cadencia de los avisos

La configuración actual: la página se actualiza **tres veces al día** (8:00,
13:00 y 20:00 hora de Chile) y el WhatsApp llega sólo cuando esa corrida trajo
**10 o más titulares nuevos** respecto de la anterior (`NOTIFY_MODE=solo-nuevas`
+ `NOTIFY_MIN_NEW=10`). Con volumen normal de noticias eso suele cumplirse casi
siempre; el umbral filtra sobre todo los días tranquilos, no cada corrida.

Dos perillas independientes, sin tocar código, ambas en **Settings → Secrets
and variables → Actions → Variables**:

- `NOTIFY_MIN_NEW` — subila para exigir más volumen antes de avisar (por
  ejemplo `20`), bajala a `1` para que cualquier titular nuevo dispare el
  aviso. Sólo tiene efecto con `NOTIFY_MODE=solo-nuevas`.
- `NOTIFY_MODE=siempre` — ignora el umbral y avisa en cada corrida, aunque no
  haya novedades.

Para cambiar la frecuencia, editá el cron en `.github/workflows/noticias.yml`:

| Cron | Frecuencia |
| --- | --- |
| `0 11,16,23 * * *` | 3 veces al día — 8:00, 13:00, 20:00 en Chile (actual) |
| `0 */2 * * *` | cada 2 horas |
| `*/30 * * * *` | cada 30 minutos |
| `0 */6 * * *` | cada 6 horas |

Ojo con dos cosas: el cron se interpreta en **UTC**, y Chile alterna entre
UTC-3 (horario de verano, septiembre-abril) y UTC-4 (invierno, abril-septiembre)
— la tabla de arriba asume horario de verano, así que en invierno el agente
corre una hora antes en el reloj chileno (7:00, 12:00, 19:00). Como el cron no
se ajusta solo, hay que recalcular la hora dos veces al año si el horario
exacto importa.

---

## Fuentes

Verificadas el 11-08-2026 con el workflow de diagnóstico.

**Chile** — La Tercera, ADN Radio, BioBioChile, Ex-Ante, La Nación y Google
News Chile.

**Internacional** — BBC Mundo, Euronews, France 24, El País, DW Español,
Infobae y Google News Mundo.

Emol, T13, Cooperativa, El Mostrador, 24 Horas, CNN Chile, Meganoticias,
El Dínamo y Diario Financiero **bloquean el acceso a su RSS** (404 en todas las
rutas conocidas; Emol directamente corta la conexión). Entran igual a la página
a través de Google News, que sí los indexa: el agente toma el medio real del
titular, así que las tarjetas dicen "Emol" o "T13", no "Google News".

Quedan declaradas pero apagadas para que el diagnóstico semanal las siga
revisando; si vuelven a publicar RSS basta con poner `enabled=True` en
`agente/sources.py`. Al Jazeera y The Guardian también están apagadas, por estar
en inglés: se habilitan con `FUENTES_EXTRA`.

Los medios cambian la ruta de sus feeds de vez en cuando, así que cada fuente
declara varias URLs candidatas y el agente usa la primera que responde. Si una
fuente se cae, la corrida sigue con el resto y la página muestra al pie cuántas
respondieron.

Varios medios chilenos devuelven 404 o cortan la conexión ante clientes que no
parecen un navegador, así que cada URL se reintenta con distintos User-Agent
antes de darla por muerta.

Para revisar el estado de los feeds: **Actions → Diagnóstico de fuentes → Run
workflow**, con dos modos:

- `check-feeds` — prueba las URLs configuradas (también corre solo cada lunes).
- `descubrir` — además lee la portada de cada medio buscando sus feeds
  declarados y prueba rutas habituales. Útil cuando un medio cambió de ruta y
  hay que averiguar la nueva.

---

## Uso local

```bash
pip install -r requirements.txt

# Ver qué fuentes responden
python -m agente.main check-feeds

# Buscar las URLs de feed reales (autodiscovery desde la portada)
python -m agente.main descubrir

# Generar la página en ./public sin mandar WhatsApp
DRY_RUN=1 python -m agente.main run

# Ver el mensaje que se enviaría
python -m agente.main preview

# Probar las credenciales de CallMeBot
CALLMEBOT_PHONE=+56912345678 CALLMEBOT_APIKEY=123456 \
  python -m agente.main test-whatsapp
```

Tests (no salen a internet: usan fixtures y un servidor HTTP local):

```bash
pip install pytest && python -m pytest tests/ -v
```

---

## Cómo funciona

| Archivo | Rol |
| --- | --- |
| `agente/sources.py` | Catálogo de medios con sus URLs candidatas |
| `agente/fetcher.py` | Descarga los feeds en paralelo, con fallback entre URLs |
| `agente/processing.py` | Limpia, deduplica, ordena y agrupa por sección |
| `agente/render.py` | Genera `index.html` y `feed.json` |
| `agente/notifier.py` | Arma y envía el WhatsApp por CallMeBot |
| `agente/state.py` | Recuerda qué titulares ya se vieron |
| `agente/main.py` | Orquesta todo y expone la CLI |

**Deduplicación.** Una misma noticia aparece en varios medios. Se agrupan por
enlace canónico (ignorando parámetros de tracking) y por parecido entre
titulares, midiendo qué palabras significativas comparten. Queda una sola
tarjeta, que muestra los otros medios que la cubrieron; esa corroboración
también sube la noticia en el orden, porque que tres medios cubran algo suele
indicar que importa.

**Orden.** Manda la frescura, con un empujón por cobertura múltiple.

**Estado.** Los identificadores de lo ya visto se guardan en la caché de Actions,
no en el repositorio, para no generar un commit por corrida. Si la caché se pierde,
la próxima corrida trata todo como nuevo: no se rompe nada.

---

## Limitaciones conocidas

- **El cron de GitHub no es puntual.** Las corridas programadas se encolan y
  pueden demorarse entre 5 y 20 minutos en horarios de alta demanda: una
  corrida programada para las 20:00 puede arrancar recién a las 20:15.
- **Actions se desactiva tras 60 días sin actividad** en el repositorio. GitHub
  avisa por correo antes; basta con volver a habilitar el workflow desde la
  pestaña Actions, o hacer cualquier commit.
- **CallMeBot es un servicio gratuito de un tercero**, sin garantía de
  disponibilidad ni soporte. Si un envío falla, el agente reintenta tres veces y
  deja constancia en el log; la página se publica igual.
- **Los feeds no se pudieron verificar contra los medios reales** al escribir
  esto, porque el entorno de desarrollo no tenía salida a internet. Por eso cada
  fuente declara varias URLs y existe el workflow de diagnóstico: conviene
  correrlo una vez al principio para ver cuáles responden de verdad.
