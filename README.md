# Maquinarias Chile

Sitio de arriendo de maquinaria construido con Django. Incluye catálogo, cinco sedes, cuentas de clientes y solicitudes de arriendo con control de fechas y disponibilidad.

## Ejecutar en Windows

```powershell
py -m pip install -r requirements.txt
py manage.py migrate
py manage.py runserver
```

Abrir http://127.0.0.1:8000/. La primera migración carga las cinco sedes y ocho equipos de muestra. Las imágenes del catálogo se sirven desde Unsplash y requieren conexión a internet.

Los clientes pueden crear una cuenta desde **Crear cuenta**. Las solicitudes quedan pendientes hasta que el equipo las confirme; personal autorizado puede revisarlas desde `/admin/` después de crear un usuario administrador con `py manage.py createsuperuser`.

## Pruebas

```powershell
py manage.py test catalog
```
