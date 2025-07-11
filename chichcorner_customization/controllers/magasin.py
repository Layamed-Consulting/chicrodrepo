from odoo import http, fields, models,api
from odoo.http import request
import json
import odoo
from odoo.api import SUPERUSER_ID

class APIKey(models.Model):
    _name = 'api.key'
    _description = 'API Keys'

    name = fields.Char('Key Name', required=True)
    key = fields.Char('API Key', required=True)
    active = fields.Boolean('Active', default=True)
    user_id = fields.Many2one('res.users', string='Associated User', required=True)


def validate_api_key(api_key):
    """Validate the API key and return the associated user if valid"""
    if not api_key:
        return None
    api_key_record = request.env['api.key'].sudo().search([
        ('key', '=', api_key),
        ('active', '=', True)
    ], limit=1)

    return api_key_record.user_id if api_key_record else None


class DimensionMagasinAPI(http.Controller):

    @http.route("/api/<string:db>/dimension_magasin", auth='none', type='http', methods=['GET'], csrf=False)
    def get_dimension_magasin(self, db, **kwargs):
        try:

            if db not in http.db_list():
                return http.Response(
                    json.dumps({"error": "Invalid database"}),
                    status=400,
                    content_type="application/json"
                )

            registry = odoo.modules.registry.Registry(db)

            api_key = request.httprequest.headers.get('Authorization')
            if not api_key:
                return http.Response(
                    json.dumps({"error": "Missing API key"}),
                    status=401,
                    content_type="application/json"
                )

            with registry.cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})

                # Validate API key
                user = validate_api_key(api_key)
                if not user:
                    return http.Response(
                        json.dumps({"error": "Invalid API key"}),
                        status=401,
                        content_type="application/json"
                    )

                # Use the environment with the specific database
                magasins = env['pos.config'].sudo().search([])
                magasin_data = []

                for magasin in magasins:
                    basic_employees = magasin.basic_employee_ids
                    advanced_employees = magasin.advanced_employee_ids

                    magasin_data.append({
                        "magasin_id": magasin.id,
                        "nom": magasin.name,
                        "employes_de_base": [employee.name for employee in basic_employees],
                        "employes_avances": [employee.name for employee in advanced_employees],
                    })

                return http.Response(
                    json.dumps(magasin_data),
                    status=200,
                    content_type="application/json"
                )

        except Exception as e:
            error_message = f"Error fetching Dimension_magasin: {str(e)}"
            if 'cr' in locals():
                cr.rollback()
            return http.Response(
                json.dumps({"error": "anass error", "details": error_message}),
                status=500,
                content_type="application/json"
            )