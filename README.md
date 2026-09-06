# VISRED — Challenge Full Stack

Sistema de gestión de pólizas de seguros construido con **Django 5.1**, **PostgreSQL 16**, **Tabler CSS** y **Docker**.

---

## Requisitos

- Docker y Docker Compose instalados. Nada más (no necesitás Python ni Postgres locales).

## Cómo levantarlo

1. Copiá el archivo de entorno de ejemplo:

   ```bash
   cp .env.example .env
   ```

2. Levantá los servicios:

   ```bash
   docker compose up --build
   ```

   La primera vez descarga imágenes y construye; puede tardar un poco. El
   contenedor espera a que Postgres esté listo, aplica las migraciones y arranca
   el servidor.

3. (Opcional) Cargá datos de prueba:

   ```bash
   docker compose exec web python manage.py seed_data
   ```

   Este comando crea 5 tipos de póliza, 5 clientes y 10 pólizas en distintos
   estados (vigentes, vencidas y renovadas) para facilitar la evaluación.

4. Abrí <http://localhost:8000> — deberías ver el **Dashboard** con las estadísticas.

---

## Estructura del proyecto

```
.
├── app/
│   ├── config/              # Proyecto Django (settings, urls, wsgi)
│   ├── policies/            # App principal
│   │   ├── models.py        # Client, PolicyType, Policy
│   │   ├── forms.py         # ClientForm, PolicyForm
│   │   ├── views.py         # Dashboard, CRUDs, Renovación, API JSON
│   │   ├── urls.py          # Rutas de la app
│   │   ├── admin.py         # Registro en Django Admin
│   │   ├── tests.py         # Suite de tests automatizados
│   │   └── management/
│   │       └── commands/
│   │           ├── seed_data.py   # Carga datos de prueba
│   │           └── wait_for_db.py # Espera a que Postgres esté listo
│   ├── templates/           # Templates HTML (Tabler CSS)
│   │   ├── base.html
│   │   ├── dashboard.html
│   │   ├── clients/
│   │   └── policies/
│   └── static/
│       └── vendor/tabler/   # CSS y JS de Tabler (local, sin CDN)
├── Dockerfile
├── docker-compose.yml
├── entrypoint.sh
└── .env.example
```

---

## Decisiones de diseño

### 1. `PolicyType` como modelo de base de datos (no un `TextChoices`)

Los tipos de póliza (Auto, Hogar, Vida, etc.) se modelan como una **tabla
catálogo** (`PolicyType`) en vez de un enum de Python (`TextChoices`).

**¿Por qué?** En un sistema de seguros real, los tipos de cobertura son datos
de negocio que evolucionan con el tiempo: se agregan nuevos productos, se
desactivan coberturas obsoletas. Almacenarlos en la base de datos permite:

- Agregar/editar/desactivar tipos desde el Django Admin o una futura UI de
  administración, **sin modificar código ni re-deployar**.
- Mantener integridad referencial con `ForeignKey` + `on_delete=PROTECT` (no se
  puede borrar un tipo si tiene pólizas asociadas).
- El campo `is_active` permite un soft-delete parcial: se oculta el tipo de la
  lista de opciones al crear pólizas, pero las pólizas existentes conservan su
  referencia.

### 2. Estado de la póliza y detección automática de vencimiento

El modelo `Policy` tiene un campo `status` almacenado en la base de datos con
tres valores posibles: `vigente`, `vencida` y `renovada`.

**El problema**: si una póliza está almacenada como "vigente" pero su
`end_date` ya pasó, el sistema debería reconocerla como "vencida"
automáticamente, sin depender de un cron job o tarea periódica.

**La solución** es un enfoque **híbrido**:

- **A nivel de base de datos**: Un `PolicyQuerySet` custom con métodos
  `.active()` y `.expired()` que aplican la lógica directamente en SQL:
  ```python
  def expired(self):
      return self.filter(
          Q(status="vencida")
          | Q(status="vigente", end_date__lt=date.today())
      )
  ```
- **A nivel de instancia**: Una propiedad `computed_status` que calcula el
  estado real en tiempo de ejecución:
  ```python
  @property
  def computed_status(self):
      if self.status == "vigente" and self.end_date < date.today():
          return "vencida"
      return self.status
  ```

Esto garantiza consistencia tanto en queries masivos (filtros, listados) como
en la visualización individual de cada póliza.

### 3. Renovación de póliza (transacción atómica)

La renovación es una operación de negocio que involucra dos escrituras:

1. Marcar la póliza original como `renovada`.
2. Crear una nueva póliza `vigente` con la misma cobertura y prima, fechas
   extendidas (+1 año desde el vencimiento original).

Ambas operaciones se ejecutan dentro de `transaction.atomic()`. Esto
garantiza que si algo falla (por ejemplo, un error al generar el nuevo
número de póliza), **ninguna de las dos operaciones se persiste** y la base
de datos queda en un estado consistente.

### 4. Validaciones en dos capas

Las validaciones se implementan tanto en el **modelo** como en el
**formulario**:

- **Modelo** (capa de datos): `RegexValidator` para campos como
  `document_number` (solo dígitos), `phone` y `name`. Método `clean()` para
  validar que `end_date > start_date`. Constraints `unique=True` para
  `document_number`, `email` y `policy_number`.
- **Formulario** (capa de presentación): Métodos `clean_*()` en los forms que
  repiten validaciones clave con mensajes amigables en español, y aplican
  clases CSS de Tabler (`form-control`, `is-invalid`) para feedback visual.

¿Por qué en dos capas? Porque el modelo es la última barrera de seguridad
(protege contra datos inválidos que entren por cualquier vía: shell, API,
scripts), mientras que el formulario es la primera línea de defensa que
ofrece retroalimentación inmediata al usuario.

### 5. Tabler CSS local (sin CDN)

Los assets de Tabler (CSS y JS) se incluyen localmente en
`static/vendor/tabler/` en vez de cargarlos desde un CDN. Esto cumple con
el requerimiento del challenge y además es una buena práctica para
aplicaciones productivas: elimina la dependencia de servicios externos y
garantiza que la aplicación funcione en entornos sin acceso a internet.

---

## Funcionalidades implementadas

| Funcionalidad | Detalle |
| --- | --- |
| Dashboard | Estadísticas agregadas (pólizas por estado, clientes, prima total) |
| CRUD Clientes | Crear, listar, ver detalle, editar, eliminar |
| CRUD Pólizas | Crear, listar, editar, eliminar |
| Renovación | Acción atómica que genera nueva póliza vigente |
| Filtrado server-side | Por estado (vigente/vencida/renovada) y búsqueda por texto |
| API JSON (Bonus) | Endpoint `/api/polizas/` para filtrado AJAX con Vanilla JS |
| Datos de prueba | Comando `seed_data` con datos realistas |
| Tests automatizados | Validaciones, renovación, filtros, QuerySet |

---

## Comandos útiles

Todo se ejecuta dentro del contenedor `web`:

```bash
# Crear migraciones después de tocar modelos
docker compose exec web python manage.py makemigrations

# Aplicar migraciones
docker compose exec web python manage.py migrate

# Cargar datos de prueba
docker compose exec web python manage.py seed_data

# Correr los tests
docker compose exec web python manage.py test policies

# Crear un superusuario para el admin
docker compose exec web python manage.py createsuperuser

# Abrir una shell de Django
docker compose exec web python manage.py shell

# Ver logs
docker compose logs -f web
```

Para frenar todo: `docker compose down` (agregá `-v` si querés borrar también la
base de datos).

---

## Qué dejaría para una segunda iteración

Con más tiempo, mejoraría o agregaría:

1. **Autenticación y permisos**: Implementar login con `django.contrib.auth` y
   restringir el acceso a las vistas con `LoginRequiredMixin`. Diferentes roles
   (operador, administrador) con permisos granulares por modelo.

2. **Paginación + AJAX completa**: Convertir el filtrado con live-search en
   tiempo real usando el endpoint `/api/polizas/` que ya existe. Actualizar la
   tabla dinámicamente con JavaScript sin recargar la página.

3. **Auditoría y trazabilidad**: Agregar campos `created_at` y `updated_at`
   (`auto_now_add`, `auto_now`) a todos los modelos. En la renovación,
   almacenar una `ForeignKey` a la póliza original (`renewed_from`) para
   mantener la cadena de renovaciones completa y consultable.

4. **Exportación de datos**: Botón para exportar listados a CSV o PDF,
   especialmente útil para reportes de pólizas vencidas o próximas a vencer.

5. **Alertas de vencimiento próximo**: Dashboard card que muestre pólizas
   que vencen en los próximos 30 días, con indicadores visuales.

6. **Mejor cobertura de tests**: Tests de integración para los templates
   (verificar que los badges de estado se renderizan correctamente), tests
   para el endpoint API JSON, y tests de edge cases en la renovación
   (ej: renovar una póliza ya vencida).

7. **Soft delete**: En vez de borrar registros de la base, marcarlos como
   inactivos con un campo `is_deleted` y filtrarlos del QuerySet por defecto.
   Esto es estándar en sistemas de gestión donde los datos históricos
   importan.

8. **Frontend más rico**: Gráficos con Chart.js para visualizar distribución
   de pólizas por tipo y estado, y un calendario de vencimientos.
