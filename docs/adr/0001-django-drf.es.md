# ADR 0001: Django y Django REST Framework para el backend

- **Estado:** aceptada

## Contexto

El backend necesita usuarios, sesiones, protección CSRF, permisos por ruta, un ORM con migraciones y una API documentada. Se valoraron FastAPI y Flask.

## Decisión

Usar Django 6.x con Django REST Framework y drf-spectacular para el esquema OpenAPI.

## Consecuencias

- La seguridad (sesiones, CSRF, cabeceras, CSP, hashing de contraseñas) viene integrada y mantenida por el propio framework.
- El ORM y el sistema de migraciones evitan escribir SQL a mano y facilitan cambiar de motor de base de datos.
- Es más pesado que FastAPI. Las integraciones externas son I/O bloqueante y se ejecutan en hilos, así que el modelo asíncrono no aporta ventajas aquí.
