from odoo import models, fields


class Historial(models.Model):
    """
    Registro de todas las acciones realizadas sobre una incidencia.
    Se crea automáticamente por el sistema; no requiere intervención manual.
    """
    _name = 'helpdesk.historial'
    _description = 'Historial de acciones sobre incidencias'
    _rec_name = 'accion'
    _order = 'fecha desc'

    incidencia_id = fields.Many2one(
        'helpdesk.incidencia',
        string="Incidencia",
        required=True,
        ondelete='cascade'
    )

    accion = fields.Char(string="Acción", required=True)
    descripcion = fields.Text(string="Descripción")

    fecha = fields.Datetime(
        string="Fecha",
        default=fields.Datetime.now,
        readonly=True
    )

    # usuario de Odoo que ejecutó la acción (se captura automáticamente)
    usuario_sistema_id = fields.Many2one(
        'res.users',
        string="Realizado por",
        default=lambda self: self.env.user,
        readonly=True
    )
