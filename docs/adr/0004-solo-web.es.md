# ADR 0004: Aplicación solo web, sin línea de comandos

- **Estado:** aceptada

## Contexto

La persona usuaria no debe depender de la terminal. Importar y descargar son tareas largas que tienen que seguir funcionando mientras se usa la app, y su progreso debe verse desde la web.

## Decisión

- Toda la operación se hace desde la web. `manage.py` queda solo para desarrollo.
- Las tareas se ejecutan con `ThreadPoolExecutor` dentro del proceso del servidor, con una tarea de cada tipo a la vez.
- El estado y las líneas de log se guardan en base de datos, así que la web puede leerlos en cualquier momento.
- La parada es cooperativa: se comprueba entre canción y canción.

## Consecuencias

- No hay cola externa (Celery, Redis). Basta con un proceso de servidor, que es el caso de uso previsto.
- Al arrancar, las tareas que quedaron a medias se marcan como interrumpidas y no se reanudan solas.
- Si algún día hace falta más de un proceso, este ADR se revisará antes de añadir una cola.
