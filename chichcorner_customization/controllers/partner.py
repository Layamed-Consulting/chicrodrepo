from odoo import http
from odoo.http import request
import json


def validate_api_key(api_key):
    """Validate the API key and return the associated user if valid"""
    if not api_key:
        return None
    api_key_record = request.env['api.key'].sudo().search([
        ('key', '=', api_key),
        ('active', '=', True)
    ], limit=1)
    return api_key_record.user_id if api_key_record else None


class DimensionClientAPI(http.Controller):

    @http.route("/api/dimension_client", auth='none', type='http', methods=['GET'], csrf=False)
    def get_dimension_client(self, **params):
        try:
            api_key = request.httprequest.headers.get('Authorization')

            user = validate_api_key(api_key)
            if not user:
                return http.Response(
                    json.dumps({"error": "Invalid or missing API key"}),
                    status=401,
                    content_type="application/json"
                )

            request.update_env(user=user)

            clients = request.env['res.partner'].sudo().search([])
            client_data = []

            for client in clients:
                client_data.append({
                    "customer_id": client.id,
                    "phone": client.phone,
                    "email": client.email,
                    "function": client.function,
                    "cin": client.vat,
                    "name": client.name,
                })

            return request.make_json_response(client_data, status=200)

        except Exception as e:
            error_message = f"Error fetching Dimension_client: {str(e)}"
            request.env.cr.rollback()
            return http.Response(
                json.dumps({"error": "Internal Server Error", "details": error_message}),
                status=500,
                content_type="application/json"
            )