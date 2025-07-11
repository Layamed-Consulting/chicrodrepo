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


class SalesOrderAPI(http.Controller):

    @http.route("/api/pos_orders/<int:id>", auth='none', type='http', methods=['GET'], csrf=False)
    def get_pos_orders(self, id):
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

            pos_order = request.env['pos.order'].sudo().search([('id', '=', id)], limit=1)

            if not pos_order:
                return request.make_json_response({
                    "message": "ID not found",
                }, status=400)

            products = []
            for line in pos_order.lines:
                products.append({
                    "Product": line.full_product_name,
                    "price": line.price_unit,
                    "quantity": line.qty
                })

            payments = []
            for payment in pos_order.payment_ids:
                payments.append({
                    "payment_date": payment.payment_date,
                    "payment_method_id": payment.payment_method_id.id,
                    "payment_method_name": payment.payment_method_id.name,
                    "amount": payment.amount
                })

            response_data = {
                "id": pos_order.id,
                "session_id": pos_order.session_id.id,
                "date_order": pos_order.date_order,
                "employee_id": pos_order.employee_id,
                "products": products,
                "payments": payments
            }
            return request.make_json_response(response_data, status=200)

        except Exception as e:
            error_message = f"Error fetching POS orders: {str(e)}"
            request.env.cr.rollback()
            return http.Response(
                json.dumps({"error": "Internal Server Error", "details": error_message}),
                status=500,
                content_type="application/json"
            )