from odoo import models, fields, api
from odoo.exceptions import ValidationError


# IMPACTO FUNCIONAL 2: la prioridad base depende de la gravedad
PRIORIDAD_BASE = {
    'baja':    10,
    'media':   20,
    'alta':    40,
    'critica': 80,
}

# IMPACTO FUNCIONAL 2: bonus/penalización de prioridad según nivel karma del usuario
BONUS_PRIORIDAD_USUARIO = {
    'penalizado': -10,  # sus incidencias bajan de prioridad
    'basico':       0,
    'confiable':    5,
    'premium':     15,  # sus incidencias suben de prioridad
}


class Incidencia(models.Model):
    """
    Incidencia técnica gestionada por el HelpDesk.

    Flujo de estados:
        nuevo → asignado → en_proceso → resuelto → cerrado
                                      ↑              ↓
                                   reabierto ←───────┘

    Reglas de karma aplicadas automáticamente:
      - Al crear: si el usuario no puede crear (karma < 20) → ValidationError
      - Al crear: incidencia crítica penaliza -5 karma al usuario
      - Al resolver: el técnico gana karma según su nivel (bonus_resolucion)
                     + bonus extra si resolvió en menos de 24h
      - Al cerrar: el usuario gana +10 karma
      - Al reabrir: el técnico pierde -25 karma; el usuario pierde -15 karma
    """
    _name = 'helpdesk.incidencia'
    _description = 'Incidencia técnica'
    _rec_name = 'titulo'
    _order = 'prioridad desc, fecha_creacion desc'

    # ------------------------------------------------------------------
    # campos básicos
    # ------------------------------------------------------------------
    titulo = fields.Char(string="Título", required=True)
    descripcion = fields.Text(string="Descripción")

    estado = fields.Selection(
        string="Estado",
        selection=[
            ('nuevo',      'Nuevo'),
            ('asignado',   'Asignado'),
            ('en_proceso', 'En proceso'),
            ('resuelto',   'Resuelto'),
            ('cerrado',    'Cerrado'),
            ('reabierto',  'Reabierto'),
        ],
        default='nuevo',
        required=True
    )

    gravedad = fields.Selection(
        string="Gravedad",
        selection=[
            ('baja',    'Baja'),
            ('media',   'Media'),
            ('alta',    'Alta'),
            ('critica', 'Crítica'),
        ],
        default='media',
        required=True
    )

    categoria = fields.Selection(
        string="Categoría",
        selection=[
            ('red',      'Red'),
            ('hardware', 'Hardware'),
            ('software', 'Software'),
            ('acceso',   'Acceso'),
            ('otro',     'Otro'),
        ],
        default='otro'
    )

    # ------------------------------------------------------------------
    # relaciones
    # ------------------------------------------------------------------
    usuario_id = fields.Many2one(
        'helpdesk.usuario',
        string="Usuario",
        required=True,
        ondelete='restrict'
    )

    tecnico_id = fields.Many2one(
        'helpdesk.tecnico',
        string="Técnico asignado",
        ondelete='set null'
    )

    historial_ids = fields.One2many(
        'helpdesk.historial', 'incidencia_id',
        string="Historial de acciones"
    )

    # ------------------------------------------------------------------
    # campos calculados
    # ------------------------------------------------------------------

    # IMPACTO FUNCIONAL 2: prioridad = base gravedad + bonus karma usuario
    prioridad = fields.Integer(
        string="Prioridad",
        compute='_compute_prioridad',
        store=True,
        help="Calculado automáticamente: base por gravedad + ajuste según karma del usuario."
    )

    fecha_creacion = fields.Datetime(
        string="Fecha creación",
        default=fields.Datetime.now,
        readonly=True
    )

    fecha_resolucion = fields.Datetime(string="Fecha resolución", readonly=True)

    tiempo_resolucion = fields.Float(
        string="Tiempo resolución (h)",
        compute='_compute_tiempo',
        store=True,
        help="Horas transcurridas entre creación y resolución."
    )

    veces_reabierta = fields.Integer(string="Veces reabierta", default=0, readonly=True)

    # ------------------------------------------------------------------
    # lógica de campos calculados
    # ------------------------------------------------------------------

    @api.depends('gravedad', 'usuario_id', 'usuario_id.nivel_karma')
    def _compute_prioridad(self):
        for inc in self:
            base = PRIORIDAD_BASE.get(inc.gravedad, 20)
            bonus = 0
            if inc.usuario_id:
                bonus = BONUS_PRIORIDAD_USUARIO.get(inc.usuario_id.nivel_karma, 0)
            inc.prioridad = max(0, base + bonus)

    @api.depends('fecha_creacion', 'fecha_resolucion')
    def _compute_tiempo(self):
        for inc in self:
            if inc.fecha_creacion and inc.fecha_resolucion:
                delta = inc.fecha_resolucion - inc.fecha_creacion
                inc.tiempo_resolucion = round(delta.total_seconds() / 3600, 2)
            else:
                inc.tiempo_resolucion = 0.0

    # ------------------------------------------------------------------
    # override create / write para aplicar lógica de karma
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('usuario_id'):
                usuario = self.env['helpdesk.usuario'].browse(vals['usuario_id'])
                if not usuario.puede_crear_incidencias:
                    raise ValidationError(
                        f"El usuario '{usuario.nombre}' tiene karma insuficiente "
                        f"({usuario.karma} pts) y no puede abrir nuevas incidencias. "
                        f"Karma mínimo requerido: 20."
                    )

        records = super().create(vals_list)

        for record in records:
            if record.gravedad == 'critica' and record.usuario_id:
                record.usuario_id.restar_karma(5, f"abrió incidencia crítica: {record.titulo}")
            record._log(
                'Creación',
                f"Incidencia creada. Gravedad: {record.gravedad}. "
                f"Prioridad calculada: {record.prioridad}."
            )

        return records

    def write(self, vals):
        # capturamos los estados anteriores antes de la escritura
        estados_prev = {r.id: r.estado for r in self}

        result = super().write(vals)

        if 'estado' in vals:
            for inc in self:
                estado_prev = estados_prev.get(inc.id)
                estado_nuevo = vals['estado']
                if estado_nuevo != estado_prev:
                    inc._gestionar_cambio_estado(estado_prev, estado_nuevo)

        if 'tecnico_id' in vals:
            for inc in self:
                if inc.tecnico_id:
                    inc._log('Asignación', f"Técnico asignado: {inc.tecnico_id.nombre}")

        return result

    # ------------------------------------------------------------------
    # lógica de negocio al cambiar estado
    # ------------------------------------------------------------------

    def _gestionar_cambio_estado(self, estado_anterior, estado_nuevo):
        """Aplica karma y registra historial según la transición de estado."""

        if estado_nuevo == 'asignado':
            self._log('Asignación', "Incidencia marcada como asignada a técnico.")

        elif estado_nuevo == 'en_proceso':
            self._log('Inicio', "El técnico ha comenzado a trabajar en la incidencia.")

        elif estado_nuevo == 'resuelto':
            # registrar fecha de resolución
            self.fecha_resolucion = fields.Datetime.now()

            if self.tecnico_id:
                # IMPACTO FUNCIONAL 3: bonus según nivel del técnico
                bonus = self.tecnico_id.bonus_resolucion
                self.tecnico_id.sumar_karma(
                    bonus,
                    f"resolvió '{self.titulo}' (nivel {self.tecnico_id.nivel}, bonus {bonus})"
                )
                # bonus adicional por resolución rápida (< 24 h)
                if self.tiempo_resolucion > 0 and self.tiempo_resolucion < 24:
                    self.tecnico_id.sumar_karma(
                        10,
                        f"resolución rápida en {self.tiempo_resolucion:.1f}h"
                    )

            self._log(
                'Resolución',
                f"Incidencia resuelta. Tiempo: {self.tiempo_resolucion:.1f}h. "
                f"Bonus karma técnico: {self.tecnico_id.bonus_resolucion if self.tecnico_id else 0}."
            )

        elif estado_nuevo == 'cerrado':
            # el usuario gana karma por cerrar correctamente
            if self.usuario_id and estado_anterior == 'resuelto':
                self.usuario_id.sumar_karma(10, f"cerró correctamente '{self.titulo}'")
            self._log('Cierre', "Incidencia cerrada por el usuario.")

        elif estado_nuevo == 'reabierto':
            self.veces_reabierta += 1
            # penalizar técnico: la solución no fue válida
            if self.tecnico_id:
                self.tecnico_id.restar_karma(
                    25,
                    f"incidencia reabierta: '{self.titulo}'"
                )
            # penalizar usuario: reabrió sin justificación suficiente
            if self.usuario_id:
                self.usuario_id.restar_karma(
                    15,
                    f"reabrió incidencia: '{self.titulo}'"
                )
            self._log(
                'Reapertura',
                f"Incidencia reabierta (vez nº {self.veces_reabierta})."
            )

    # ------------------------------------------------------------------
    # helper historial
    # ------------------------------------------------------------------

    def _log(self, accion, descripcion):
        """Crea un registro de historial para esta incidencia."""
        self.env['helpdesk.historial'].create({
            'incidencia_id': self.id,
            'accion': accion,
            'descripcion': descripcion,
        })

    # ------------------------------------------------------------------
    # botones del formulario (flujo de estados)
    # ------------------------------------------------------------------

    def action_asignar(self):
        self.estado = 'asignado'

    def action_iniciar(self):
        self.estado = 'en_proceso'

    def action_resolver(self):
        self.estado = 'resuelto'

    def action_cerrar(self):
        self.estado = 'cerrado'

    def action_reabrir(self):
        self.estado = 'reabierto'
