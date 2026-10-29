# ADR 0005: Registros de solo añadir

- **Estado:** aceptada

## Contexto

El historial de actividad, las ejecuciones de tareas y las descargas tienen que ser fiables. Un error de código o una petición mal hecha no debe poder reescribir lo que ya pasó.

## Decisión

- Un modelo base abstracto, `AppendOnlyModel`, rechaza modificar una fila ya guardada, borrarla y las operaciones `update()` y `delete()` en bloque del manager.
- La API expone esos modelos solo en lectura (`ReadOnlyModelViewSet`).
- No se usan triggers de base de datos, para no depender del motor (ver [ADR 0003](0003-base-de-datos-intercambiable.es.md)).
- Cada tabla de este tipo tiene un test que comprueba que no se puede modificar ni borrar.

## Consecuencias

- Corregir un registro se hace añadiendo otro nuevo.
- La limpieza de logs técnicos de más de 30 días es la única excepción. Es una función de servicio explícita y no toca `ActivityLog`.
