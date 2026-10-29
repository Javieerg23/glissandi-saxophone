# ADR 0003: Base de datos intercambiable (SQLite y PostgreSQL)

- **Estado:** aceptada

## Contexto

Un uso personal funciona bien con SQLite, pero una instalación compartida necesita PostgreSQL. El código no debe depender de un motor concreto.

## Decisión

- El motor se elige con `DATABASE_URL` (dj-database-url).
- Solo se usa el ORM: nada de SQL a mano ni `RunSQL`.
- La CI ejecuta la suite completa en SQLite y en PostgreSQL.
- Los cambios de motor se hacen con `dumpdata` y `loaddata`.

## Consecuencias

- No se usan funciones propias de un motor. Si hace falta una, se documenta y se aísla con su propio ADR.
- Cada migración se prueba en los dos motores antes de fusionarse.
