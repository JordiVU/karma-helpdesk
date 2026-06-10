# Karma HelpDesk

Módulo de gestión de incidencias técnicas para **Odoo 19** con sistema de gamificación basado en karma.

## Descripción

Karma HelpDesk permite registrar, gestionar y resolver incidencias técnicas. Incorpora un sistema de karma que evalúa el comportamiento de usuarios y técnicos, con impacto funcional real en el sistema.

## Requisitos

- Odoo 19.0
- PostgreSQL
- Python 3.10+

## Instalación

1. Copia la carpeta `karma_helpdesk` en tu directorio de addons personalizados.
2. Asegúrate de que la ruta esté incluida en `addons_path` del `odoo.conf`:
   ```ini
   addons_path = .../odoo/addons,.../custom_addons
   ```
3. Activa el modo desarrollador en Odoo → **Settings → Activate developer mode**.
4. Ve a **Apps → Update Apps List**.
5. Busca **Karma HelpDesk** e instala.

> Si tu base de datos tiene demo data activado, se cargarán automáticamente usuarios, técnicos e incidencias de prueba.

## Estructura

```
karma_helpdesk/
├── models/
│   ├── usuario.py       # Usuarios que reportan incidencias
│   ├── tecnico.py       # Técnicos que resuelven incidencias
│   ├── incidencia.py    # Modelo central con lógica de karma
│   └── historial.py     # Registro automático de acciones
├── views/
│   ├── usuario_views.xml
│   ├── tecnico_views.xml
│   ├── incidencia_views.xml
│   ├── historial_views.xml
│   └── menu_views.xml
├── controllers/
│   └── main.py          # API REST (3 endpoints)
├── security/
│   └── ir.model.access.csv
├── demo/
│   ├── demo_usuarios.xml
│   ├── demo_tecnicos.xml
│   ├── demo_incidencias.xml
│   └── demo_historial.xml
└── __manifest__.py
```

## Sistema de karma

### Usuarios

| Nivel | Karma | Impacto funcional |
|---|---|---|
| Penalizado | < 20 | No puede crear incidencias |
| Básico | 20 – 79 | Prioridad normal |
| Confiable | 80 – 149 | +5 de prioridad en sus incidencias |
| Premium | ≥ 150 | +15 de prioridad en sus incidencias |

**Acciones que modifican el karma de usuario:**
- Crea incidencia crítica → **-5**
- Reabre una incidencia → **-15**
- Cierra una incidencia resuelta → **+10**

### Técnicos

| Nivel | Karma | Bonus por resolución |
|---|---|---|
| Junior | < 80 | +10 |
| Senior | 80 – 199 | +20 |
| Experto | ≥ 200 | +35 |

**Acciones que modifican el karma de técnico:**
- Resuelve una incidencia → **+bonus según nivel**
- Resolución en menos de 24h → **+10 extra**
- Su incidencia es reabierta → **-25**

## Flujo de estados

```
nuevo → asignado → en_proceso → resuelto → cerrado
                                    ↑           ↓
                                 reabierto ←────┘
```

## API REST

Todas las llamadas requieren la cabecera:
```
X-Odoo-Database: <nombre_bd>
```

| Endpoint | Descripción |
|---|---|
| `GET /api/usuarios/{id}/incidencias` | Incidencias de un usuario con impacto karma |
| `GET /api/tecnicos/{id}/estado` | Métricas y nivel karma de un técnico |
| `GET /api/sistema/resumen` | Resumen global del HelpDesk |

### Ejemplo

```bash
curl http://localhost:8069/api/sistema/resumen \
  -H "X-Odoo-Database: jordiDemo"
```

## Autor

Jordi — M10 SGE, UD5 Desenvolupament de Components
