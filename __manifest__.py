{
    'name': "Karma HelpDesk",
    'summary': "Gestión de incidencias técnicas con sistema de karma y gamificación",
    'description': """
        Módulo de HelpDesk con gamificación basada en karma.
        Gestiona incidencias técnicas, usuarios y técnicos.
        El karma afecta funcionalmente al sistema:
          - Usuarios con bajo karma no pueden crear incidencias
          - La prioridad de cada incidencia depende del karma del usuario
          - Los técnicos con alto karma reciben bonus al resolver
    """,
    'author': "Jordi",
    'application': True,
    'category': 'Services/Helpdesk',
    'version': '19.0.1.0.0',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/menu_views.xml',
        'views/usuario_views.xml',
        'views/tecnico_views.xml',
        'views/incidencia_views.xml',
        'views/historial_views.xml',
        
    ],
    'demo': [
        'demo/demo_usuarios.xml',
        'demo/demo_tecnicos.xml',
        'demo/demo_incidencias.xml',
        'demo/demo_historial.xml',
    ],
    'installable': True,
    'license': 'LGPL-3',
}
