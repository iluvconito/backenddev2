# Maquinarias Chile

Sitio de arriendo de maquinaria construido con Django. Incluye catálogo, cinco sedes, cuentas de clientes y solicitudes de arriendo con control de fechas y disponibilidad.

## Ejecutar en Windows

Se requiere PostgreSQL en ejecución y una base de datos y rol configurados. Define las credenciales en variables de entorno; no las guardes en el repositorio:

```powershell
py -m pip install -r requirements.txt
$env:POSTGRES_DB = "maquinarias_chile"
$env:POSTGRES_USER = "postgres"
$env:POSTGRES_PASSWORD = "tu_clave_local"
$env:POSTGRES_HOST = "127.0.0.1"
$env:POSTGRES_PORT = "5432"
py manage.py migrate
py manage.py runserver
```

La aplicación se conecta usando el motor nativo `django.db.backends.postgresql`. Crea la base de datos indicada en `POSTGRES_DB` antes de ejecutar las migraciones.

Abrir http://127.0.0.1:8000/. La primera migración carga las cinco sedes y ocho equipos de muestra. Las imágenes del catálogo se sirven desde Unsplash y requieren conexión a internet.

## API

La API está disponible en `/api/`:

- `GET /api/maquinarias/`: catálogo público; filtra por `category`, `brand`, `available`, `min_daily_rate` y `max_daily_rate`, y admite búsqueda con `search` y orden con `ordering`. Ejecutivos pueden usar también `POST`, `PUT /{id}/` y `DELETE /{id}/`.
- `/api/sedes/`: consulta pública de sedes; filtra por `region` y admite búsqueda por nombre, región o dirección con `search`.
- `/api/inventario/`: consulta de inventario restringida al Ejecutivo de Arriendos; filtra por `branch` y `equipment`.
- `GET/POST/DELETE /api/carro-arriendo/`: operaciones de carrito de la Empresa Constructora. POST recibe `equipment_id`, `branch_id`, `start_date`, `end_date` y `quantity`; DELETE recibe `item_id` para borrar una línea, o vacía el carrito propio si se omite.
- `POST /api/contratos/checkout/`: convierte el carrito autenticado en contratos pendientes después de validar inventario; acepta opcionalmente `customer_name`.
- `GET /api/mis-contratos/`: contratos del usuario autenticado con rol Empresa Constructora.
- `PATCH /api/contratos/{id}/estado/`: cambio de estado restringido al Ejecutivo de Arriendos; los valores son `pending`, `paid`, `delivered`, `completed` y `cancelled`, sujetos al flujo permitido.
- `/api/docs/`: documentación interactiva Swagger.
- `/api/schema/`: esquema OpenAPI.

Las rutas de maquinaria, carrito, checkout, contratos e inventario requieren el JWT y rol indicados; el catálogo de maquinaria y las sedes son públicos. Los endpoints de maquinaria se comportan como una API REST: creación en la colección y actualización/eliminación en `/api/maquinarias/{id}/`.

## Autenticación de la API

Obtén un par de tokens con `POST /api/token/` enviando `username` y `password`. El access token dura 15 minutos y el refresh token dura un día; renueva el access con `POST /api/token/refresh/` y el refresh token. Envía el access token en `Authorization: Bearer <access>`.

El claim JWT `role` contiene `Empresa Constructora` para usuarios normales y `Ejecutivo de Arriendos` para usuarios con `is_staff=True` (incluye superadministradores). La web continúa usando sus sesiones existentes.

El carrito tiene una relación persistente 1:1 con cada usuario. Agregar equipos o hacer checkout no descuenta el inventario físico: el stock se descuenta de forma transaccional al cambiar el contrato de `pending` a `paid`, y se reincorpora al cambiar desde `paid` o `delivered` a `cancelled` o `completed`. Las garantías y tarifas se copian al contrato y quedan congeladas para conservar el precio acordado. Los registros antiguos `approved` se migran a `paid` y descuentan unidades de la sede correspondiente; si no hay stock suficiente, la migración falla explícitamente.

Los clientes pueden crear una cuenta desde **Crear cuenta**. Las solicitudes quedan pendientes hasta que el equipo las confirme; personal autorizado puede revisarlas desde `/admin/` después de crear un usuario administrador con `py manage.py createsuperuser`.

## Pruebas

```powershell
py manage.py test catalog --settings=config.test_settings
```

La configuración de pruebas usa una base SQLite en memoria; la aplicación normal y sus migraciones usan PostgreSQL.
