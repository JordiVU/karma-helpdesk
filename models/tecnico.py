import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)

# Bonus de karma que recibe el técnico al resolver según su nivel
# IMPACTO FUNCIONAL 3: técnicos con alto karma reciben mayor recompensa
BONUS_KARMA_POR_NIVEL = {
    'junior':  10,   # resuelve y gana 10
    'senior':  20,   # resuelve y gana 20
    'experto': 35,   # resuelve y gana 35
}


class Tecnico(models.Model):
    """
    Técnico que gestiona y resuelve incidencias.

    El karma refleja el desempeño del técnico:
      - Sube al resolver incidencias (más si es de alta gravedad)
      - Baja cuando una incidencia que resolvió es reabierta

    El nivel (junior / senior / experto) se deriva del karma y determina
    el bonus que recibe al resolver: cuanto más alto el nivel, mayor recompensa.
    Esto incentiva mantener el karma alto y trabajar bien.
    """
    _name = 'helpdesk.tecnico'
    _description = 'Técnico que resuelve incidencias'
    _rec_name = 'nombre'
    _order = 'karma desc, nombre asc'

    # ------------------------------------------------------------------
    # campos básicos
    # ------------------------------------------------------------------
    nombre = fields.Char(string="Nombre", required=True)
    email = fields.Char(string="Email")
    especialidad = fields.Selection(
        string="Especialidad",
        selection=[
            ('red',      'Redes'),
            ('hardware', 'Hardware'),
            ('software', 'Software'),
            ('acceso',   'Control de acceso'),
            ('general',  'General'),
        ],
        default='general'
    )
    activo = fields.Boolean(string="Activo", default=True)

    # ------------------------------------------------------------------
    # karma y nivel
    # ------------------------------------------------------------------
    karma = fields.Integer(
        string="Karma",
        default=100,
        help="Puntuación de desempeño del técnico. Mínimo 0."
    )

    nivel = fields.Selection(
        string="Nivel",
        selection=[
            ('junior',  'Junior'),   # karma < 80
            ('senior',  'Senior'),   # 80 – 199
            ('experto', 'Experto'),  # ≥ 200
        ],
        compute='_compute_nivel',
        store=True,
        help="Nivel derivado del karma. Determina el bonus al resolver incidencias."
    )

    bonus_resolucion = fields.Integer(
        string="Bonus karma por resolución",
        compute='_compute_bonus',
        store=True,
        help="Karma que gana este técnico cada vez que resuelve una incidencia."
    )

    # ------------------------------------------------------------------
    # estadísticas
    # ------------------------------------------------------------------
    incidencias_ids = fields.One2many(
        'helpdesk.incidencia', 'tecnico_id',
        string="Incidencias asignadas"
    )

    total_resueltas = fields.Integer(
        string="Total resueltas",
        compute='_compute_stats',
        store=True
    )

    incidencias_abiertas = fields.Integer(
        string="Incidencias abiertas",
        compute='_compute_stats',
        store=True
    )

    tiempo_medio_resolucion = fields.Float(
        string="Tiempo medio resolución (h)",
        compute='_compute_stats',
        store=True
    )

    # ------------------------------------------------------------------
    # campos calculados
    # ------------------------------------------------------------------

    @api.depends('karma')
    def _compute_nivel(self):
        for tecnico in self:
            k = tecnico.karma
            if k < 80:
                tecnico.nivel = 'junior'
            elif k < 200:
                tecnico.nivel = 'senior'
            else:
                tecnico.nivel = 'experto'

    @api.depends('nivel')
    def _compute_bonus(self):
        for tecnico in self:
            tecnico.bonus_resolucion = BONUS_KARMA_POR_NIVEL.get(tecnico.nivel, 10)

    @api.depends('incidencias_ids', 'incidencias_ids.estado', 'incidencias_ids.tiempo_resolucion')
    def _compute_stats(self):
        for tecnico in self:
            resueltas = tecnico.incidencias_ids.filtered(
                lambda i: i.estado in ['resuelto', 'cerrado']
            )
            tecnico.total_resueltas = len(resueltas)
            tiempos = [i.tiempo_resolucion for i in resueltas if i.tiempo_resolucion > 0]
            tecnico.tiempo_medio_resolucion = (
                sum(tiempos) / len(tiempos) if tiempos else 0.0
            )
            tecnico.incidencias_abiertas = len(
                tecnico.incidencias_ids.filtered(
                    lambda i: i.estado not in ['resuelto', 'cerrado']
                )
            )

    # ------------------------------------------------------------------
    # métodos de karma
    # ------------------------------------------------------------------

    def sumar_karma(self, puntos, motivo=''):
        """Añade puntos de karma al técnico y deja traza en log."""
        for tecnico in self:
            antes = tecnico.karma
            tecnico.karma += puntos
            _logger.info(
                "[KARMA TECNICO] %s: +%d (%d → %d) — %s",
                tecnico.nombre, puntos, antes, tecnico.karma, motivo
            )

    def restar_karma(self, puntos, motivo=''):
        """Resta puntos de karma al técnico (mínimo 0) y deja traza en log."""
        for tecnico in self:
            antes = tecnico.karma
            tecnico.karma = max(0, tecnico.karma - puntos)
            _logger.info(
                "[KARMA TECNICO] %s: -%d (%d → %d) — %s",
                tecnico.nombre, puntos, antes, tecnico.karma, motivo
            )
