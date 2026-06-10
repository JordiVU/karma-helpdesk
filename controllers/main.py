import json
from odoo import http
from odoo.http import request


class KarmaHelpdeskController(http.Controller):
    """
    API REST del módulo Karma HelpDesk.

    Endpoints disponibles:
      GET /api/usuarios/<id>/incidencias   — incidencias de un usuario con impacto karma
      GET /api/tecnicos/<id>/estado        — métricas y nivel karma de un técnico
      GET /api/sistema/resumen             — resumen global del HelpDesk
    """

    # ------------------------------------------------------------------
    # Endpoint 1: incidencias de un usuario
    # GET /api/usuarios/<usuario_id>/incidencias
    # ------------------------------------------------------------------
    @http.route(
        '/api/usuarios/<int:usuario_id>/incidencias',
        type='http', auth='none', methods=['GET'], cors='*'
    )
    def incidencias_usuario(self, usuario_id):
        usuario = request.env['helpdesk.usuario'].sudo().browse(usuario_id)

        if not usuario.exists():
            return self._json_response({'error': 'Usuario no encontrado'}, status=404)

        incidencias = []
        for inc in usuario.incidencias_ids:
            # calcular impacto karma acumulado de esta incidencia
            impacto = 0
            if inc.gravedad == 'critica':
                impacto -= 5
            if inc.estado == 'cerrado':
                impacto += 10
            if inc.veces_reabierta > 0:
                impacto -= inc.veces_reabierta * 15

            incidencias.append({
                'id': inc.id,
                'titulo': inc.titulo,
                'estado': inc.estado,
                'gravedad': inc.gravedad,
                'categoria': inc.categoria,
                'prioridad': inc.prioridad,
                'fecha_creacion': str(inc.fecha_creacion) if inc.fecha_creacion else '',
                'fecha_resolucion': str(inc.fecha_resolucion) if inc.fecha_resolucion else '',
                'veces_reabierta': inc.veces_reabierta,
                'impacto_karma': impacto,
            })

        data = {
            'usuario': {
                'id': usuario.id,
                'nombre': usuario.nombre,
                'email': usuario.email or '',
                'karma': usuario.karma,
                'nivel_karma': usuario.nivel_karma,
                'puede_crear_incidencias': usuario.puede_crear_incidencias,
            },
            'total_incidencias': len(incidencias),
            'incidencias': incidencias,
        }
        return self._json_response(data)

    # ------------------------------------------------------------------
    # Endpoint 2: estado y rendimiento de un técnico
    # GET /api/tecnicos/<tecnico_id>/estado
    # ------------------------------------------------------------------
    @http.route(
        '/api/tecnicos/<int:tecnico_id>/estado',
        type='http', auth='none', methods=['GET'], cors='*'
    )
    def estado_tecnico(self, tecnico_id):
        tecnico = request.env['helpdesk.tecnico'].sudo().browse(tecnico_id)

        if not tecnico.exists():
            return self._json_response({'error': 'Técnico no encontrado'}, status=404)

        # describir el impacto funcional del nivel actual
        impactos = {
            'junior':  'Bonus de 10 karma por resolución.',
            'senior':  'Bonus de 20 karma por resolución.',
            'experto': 'Bonus de 35 karma por resolución. Máximo rendimiento.',
        }

        data = {
            'tecnico': {
                'id': tecnico.id,
                'nombre': tecnico.nombre,
                'especialidad': tecnico.especialidad,
                'activo': tecnico.activo,
            },
            'metricas': {
                'karma': tecnico.karma,
                'nivel': tecnico.nivel,
                'bonus_karma_por_resolucion': tecnico.bonus_resolucion,
                'total_resueltas': tecnico.total_resueltas,
                'incidencias_abiertas': tecnico.incidencias_abiertas,
                'tiempo_medio_resolucion_horas': round(tecnico.tiempo_medio_resolucion, 2),
            },
            'impacto_funcional': impactos.get(tecnico.nivel, ''),
        }
        return self._json_response(data)

    # ------------------------------------------------------------------
    # Endpoint 3: resumen global del sistema
    # GET /api/sistema/resumen
    # ------------------------------------------------------------------
    @http.route(
        '/api/sistema/resumen',
        type='http', auth='none', methods=['GET'], cors='*'
    )
    def resumen_sistema(self):
        incidencias = request.env['helpdesk.incidencia'].sudo().search([])
        usuarios = request.env['helpdesk.usuario'].sudo().search([])
        tecnicos = request.env['helpdesk.tecnico'].sudo().search([])

        # agrupar incidencias por estado y por gravedad
        por_estado = {}
        por_gravedad = {}
        for inc in incidencias:
            por_estado[inc.estado] = por_estado.get(inc.estado, 0) + 1
            por_gravedad[inc.gravedad] = por_gravedad.get(inc.gravedad, 0) + 1

        # tiempo medio de resolución global
        resueltas = incidencias.filtered(lambda i: i.estado in ['resuelto', 'cerrado'])
        tiempos = [i.tiempo_resolucion for i in resueltas if i.tiempo_resolucion > 0]
        tiempo_medio = round(sum(tiempos) / len(tiempos), 2) if tiempos else 0

        # estadísticas de karma
        u_penalizados = usuarios.filtered(lambda u: u.nivel_karma == 'penalizado')
        u_premium = usuarios.filtered(lambda u: u.nivel_karma == 'premium')
        t_expertos = tecnicos.filtered(lambda t: t.nivel == 'experto')

        data = {
            'resumen': {
                'total_incidencias': len(incidencias),
                'total_usuarios': len(usuarios),
                'total_tecnicos': len(tecnicos),
                'tiempo_medio_resolucion_horas': tiempo_medio,
            },
            'incidencias_por_estado': por_estado,
            'incidencias_por_gravedad': por_gravedad,
            'karma': {
                'usuarios_penalizados': len(u_penalizados),
                'usuarios_premium': len(u_premium),
                'tecnicos_expertos': len(t_expertos),
                'karma_medio_usuarios': round(
                    sum(u.karma for u in usuarios) / len(usuarios), 1
                ) if usuarios else 0,
                'karma_medio_tecnicos': round(
                    sum(t.karma for t in tecnicos) / len(tecnicos), 1
                ) if tecnicos else 0,
            },
        }
        return self._json_response(data)

    # ------------------------------------------------------------------
    # helper
    # ------------------------------------------------------------------
    def _json_response(self, data, status=200):
        return request.make_response(
            json.dumps(data, ensure_ascii=False),
            headers=[('Content-Type', 'application/json; charset=utf-8')],
            status=status
        )
