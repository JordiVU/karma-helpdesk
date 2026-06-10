import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class Usuario(models.Model):
    """
    Usuario que reporta incidencias al HelpDesk.

    El karma refleja el comportamiento del usuario:
      - Sube al cerrar incidencias correctamente
      - Baja al crear incidencias críticas o reabrir resueltas
      - Si cae por debajo de 20, el usuario queda bloqueado (nivel: penalizado)
        y no puede abrir nuevas incidencias hasta que recupere karma.

    El nivel_karma también determina el bonus de prioridad que se aplica
    a sus incidencias en el modelo Incidencia.
    """
    _name = 'helpdesk.usuario'
    _description = 'Usuario que reporta incidencias'
    _rec_name = 'nombre'
    _order = 'karma desc, nombre asc'

    # ------------------------------------------------------------------
    # campos básicos
    # ------------------------------------------------------------------
    nombre = fields.Char(string="Nombre", required=True)
    email = fields.Char(string="Email")
    telefono = fields.Char(string="Teléfono")
    activo = fields.Boolean(string="Activo", default=True)

    # ------------------------------------------------------------------
    # karma y nivel
    # ------------------------------------------------------------------
    karma = fields.Integer(
        string="Karma",
        default=100,
        help="Puntuación de comportamiento del usuario. Mínimo 0."
    )

    nivel_karma = fields.Selection(
        string="Nivel karma",
        selection=[
            ('penalizado', 'Penalizado'),   # karma < 20
            ('basico',     'Básico'),        # 20 – 79
            ('confiable',  'Confiable'),     # 80 – 149
            ('premium',    'Premium'),       # ≥ 150
        ],
        compute='_compute_nivel_karma',
        store=True,
        help="Nivel derivado automáticamente del karma."
    )

    # IMPACTO FUNCIONAL 1: usuarios penalizados no pueden crear incidencias
    puede_crear_incidencias = fields.Boolean(
        string="Puede crear incidencias",
        compute='_compute_puede_crear',
        store=True,
        help="False si el karma cae por debajo de 20."
    )

    # ------------------------------------------------------------------
    # estadísticas
    # ------------------------------------------------------------------
    incidencias_ids = fields.One2many(
        'helpdesk.incidencia', 'usuario_id',
        string="Incidencias"
    )

    total_incidencias = fields.Integer(
        string="Total incidencias",
        compute='_compute_stats',
        store=True
    )

    incidencias_resueltas = fields.Integer(
        string="Resueltas / Cerradas",
        compute='_compute_stats',
        store=True
    )

    # ------------------------------------------------------------------
    # campos calculados
    # ------------------------------------------------------------------

    @api.depends('karma')
    def _compute_nivel_karma(self):
        for usuario in self:
            k = usuario.karma
            if k < 20:
                usuario.nivel_karma = 'penalizado'
            elif k < 80:
                usuario.nivel_karma = 'basico'
            elif k < 150:
                usuario.nivel_karma = 'confiable'
            else:
                usuario.nivel_karma = 'premium'

    @api.depends('karma')
    def _compute_puede_crear(self):
        for usuario in self:
            usuario.puede_crear_incidencias = usuario.karma >= 20

    @api.depends('incidencias_ids', 'incidencias_ids.estado')
    def _compute_stats(self):
        for usuario in self:
            usuario.total_incidencias = len(usuario.incidencias_ids)
            usuario.incidencias_resueltas = len(
                usuario.incidencias_ids.filtered(
                    lambda i: i.estado in ['resuelto', 'cerrado']
                )
            )

    # ------------------------------------------------------------------
    # métodos de karma
    # ------------------------------------------------------------------

    def sumar_karma(self, puntos, motivo=''):
        """Añade puntos de karma al usuario y deja traza en log."""
        for usuario in self:
            antes = usuario.karma
            usuario.karma += puntos
            _logger.info(
                "[KARMA USUARIO] %s: +%d (%d → %d) — %s",
                usuario.nombre, puntos, antes, usuario.karma, motivo
            )

    def restar_karma(self, puntos, motivo=''):
        """Resta puntos de karma al usuario (mínimo 0) y deja traza en log."""
        for usuario in self:
            antes = usuario.karma
            usuario.karma = max(0, usuario.karma - puntos)
            _logger.info(
                "[KARMA USUARIO] %s: -%d (%d → %d) — %s",
                usuario.nombre, puntos, antes, usuario.karma, motivo
            )
