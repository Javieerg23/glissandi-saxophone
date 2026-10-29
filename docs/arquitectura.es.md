# Arquitectura

Glissandi es una aplicación web responsive para crear y gestionar una biblioteca musical. El backend expone una API REST; el frontend la consume desde el navegador. Toda la operación se hace desde la web: no hay línea de comandos para el usuario final.

## Componentes

| Componente | Ruta | Responsabilidad |
|---|---|---|
| Configuración | `backend/config/` | Ajustes base, de desarrollo y de pruebas; URLs raíz; `DATABASE_URL`. |
| Núcleo | `backend/core/` | Salud del servicio, modelo base `AppendOnlyModel`, utilidades comunes. |
| Cuentas | `backend/accounts/` | Usuarios, sesiones, grupos y permisos. |
| Catálogo | `backend/catalog/` | Artistas, álbumes, canciones, bloqueos y descargas. |
| Tareas | `backend/jobs/` | Ejecuciones en segundo plano, su estado y sus líneas de log. |
| Novedades | `backend/watches/` | Búsquedas programadas de novedades por artista. |
| Proxies | `backend/proxies/` | Proxies usados en las descargas y sus contadores. |
| Actividad | `backend/activity/` | Historial de acciones y logs técnicos. |
| Ajustes | `backend/preferences/` | Preferencias del usuario con valores por defecto en código. |
| Integraciones | `backend/integrations/` | Deezer, MusicBrainz, YouTube (yt-dlp) y audio. Sin dependencia de Django. |
| Frontend | `frontend/` | Vue 3 con Vite y TypeScript. |
| Documentación | `docs/` | Sitio MkDocs en español e inglés. |

Cada app de Django expone su API bajo `/api/v1/<app>/`. Las integraciones son código Python puro: reciben y devuelven `dataclasses` propias, así que se prueban sin base de datos y sin red.

## Flujo de una importación

1. La web lanza una tarea de importación con el artista elegido.
2. `jobs` crea un `JobRun` y lo entrega al ejecutor de hilos del servidor.
3. El servicio de importación pide el artista, sus álbumes y sus canciones a `integrations.deezer`, y descarta lo que está en `BlockedItem`.
4. Cada elemento se guarda en `catalog` con el ORM. Cada paso deja una línea en `JobRunLine` y una entrada en `ActivityLog`.
5. La web consulta el estado y las líneas de log desde una posición concreta, así que sigue el progreso sin recargar.

## Flujo de una descarga

1. Se seleccionan las canciones pendientes.
2. `integrations.youtube` busca el mejor resultado para cada canción con yt-dlp, usando un proxy de la rotación.
3. El audio se descarga con un callback de progreso.
4. `integrations.audio` lo convierte con ffmpeg y lo etiqueta con mutagen.
5. Se registra un `Download`, que es de solo añadir. «Descargada» no es una casilla: se calcula a partir de esos registros.

## Datos

- **Inmutable:** lo que viene de Deezer o MusicBrainz (`deezer_id`, `musicbrainz_id`, `isrc`) y los registros que describen algo ya ocurrido (actividad, ejecuciones, descargas). Los identificadores externos son únicos y se comprueban en `save()`.
- **Mutable:** lo que edita el usuario, con historial de cambios, y el estado operativo.
- Cada tabla tiene `id` propio. El esquema y los datos se cambian con migraciones reversibles, una por cambio.

El detalle de cada decisión está en los [ADR](adr/0001-django-drf.es.md).

## Seguridad

- Sesiones en cookie `Secure`, `HttpOnly` y `SameSite=Lax`, con caducidad por inactividad.
- CSRF por cabecera `X-CSRFToken`.
- Content Security Policy sin `unsafe-inline` ni `unsafe-eval` para scripts.
- Bloqueo temporal de cuentas tras varios intentos fallidos (django-axes).
- Ningún registro guarda contraseñas, tokens ni cookies, y hay un test que lo comprueba.

## Pruebas

- Integraciones: HTTP simulado con `responses` y respuestas reales grabadas en `backend/tests/fixtures/`.
- Backend: pytest con modelos, servicios y API; ejecución en SQLite y en PostgreSQL.
- Frontend: Vitest con Vue Test Utils y la API simulada con MSW.
- Extremo a extremo: Playwright en 390, 768 y 1440 px.
