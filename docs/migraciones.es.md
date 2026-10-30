# Migraciones y cambio de motor

Esta guía describe cómo cambiar el esquema de la base de datos y cómo pasar los datos de SQLite a PostgreSQL (o al revés). Las pruebas de `backend/tests/migrations/` comprueban los dos procedimientos en cada cambio.

## Reglas de las migraciones

- **Una migración por cambio**, con un nombre descriptivo (`0003_add_watch_interval.py`). Nunca se edita una migración ya fusionada en `main`: si hay un error, se añade otra.
- **Esquema y datos por separado.** Una migración de datos (`RunPython`) no mezcla cambios de tabla, para que cada una pueda revertirse por su cuenta.
- **Siempre reversibles.** Toda `RunPython` lleva `reverse_code`, y toda operación de esquema debe poder deshacerse. La prueba de ida y vuelta lo verifica en cada app.
- **Expandir y contraer** para lo destructivo. Primero se añade lo nuevo y el código escribe en ambos sitios; después se migran los datos; y solo en una migración posterior se borra lo antiguo.
- **Solo ORM.** Nada de `RunSQL` ni SQL escrito a mano, para que la misma migración funcione en SQLite y en PostgreSQL.
- **Squash periódico**, cuando el historial de una app sea largo.

## Comandos para ver y revertir

```bash
python manage.py showmigrations                 # estado de cada migración
python manage.py sqlmigrate catalog 0002        # SQL que generaría, sin aplicarla
python manage.py sqlmigrate catalog 0002 --backwards
python manage.py migrate catalog 0001           # revierte hasta 0001
python manage.py migrate                        # aplica todo lo pendiente
```

Antes de fusionar una migración, la CI comprueba que `makemigrations --check` no encuentra cambios sin migrar, que `lintmigrations` no detecta operaciones peligrosas y que la prueba de ida y vuelta pasa en los dos motores.

## Cambiar de SQLite a PostgreSQL

Los datos se pasan con `dumpdata` y `loaddata`, nunca con SQL. Hazlo con el servicio parado.

1. **Exporta desde el motor actual** (SQLite, por defecto):

   ```bash
   python manage.py dumpdata --exclude contenttypes --exclude auth.permission \
       --indent 2 --output datos.json
   ```

   Los tipos de contenido y los permisos los regenera Django; no se exportan.

2. **Prepara la base de datos nueva** con el esquema aplicado y vacía:

   ```bash
   export DATABASE_URL=postgres://usuario:clave@servidor:5432/glissandi
   python manage.py migrate
   ```

3. **Carga los datos**:

   ```bash
   python manage.py loaddata datos.json
   ```

4. **Comprueba** que los recuentos coinciden entre los dos motores (por ejemplo, con `python manage.py shell -c "from catalog.models import Track; print(Track.objects.count())"`).

`loaddata` debe ejecutarse solo sobre una base de datos vacía. Si ya hay filas con la misma clave primaria, las sobrescribe, y los registros de solo añadir (actividad, ejecuciones, logs) no deben alterarse.

Para volver de PostgreSQL a SQLite, el procedimiento es el mismo, cambiando `DATABASE_URL`.

## Pruebas relacionadas

- `backend/tests/migrations/test_round_trip.py`: revierte cada app a cero, la vuelve a aplicar y comprueba que no quedan migraciones pendientes.
- `backend/tests/migrations/test_empty_database.py`: una base recién migrada solo tiene los roles de usuario y `/api/health/` responde.
- `backend/tests/migrations/test_dump_load.py`: el volcado y la carga conservan los datos.
