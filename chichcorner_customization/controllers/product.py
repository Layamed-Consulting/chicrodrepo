from odoo import http
from odoo.http import request
import json
from odoo.exceptions import AccessDenied
import werkzeug.exceptions


def validate_api_key(api_key):

    if not api_key:
        return None
    api_key_record = request.env['api.key'].sudo().search([
        ('key', '=', api_key),
        ('active', '=', True)
    ], limit=1)
    return api_key_record.user_id if api_key_record else None


class DimensionProduitAPI(http.Controller):

    @http.route("/api/dimension_produit", auth='none', type='http', methods=['GET'], csrf=False)
    def get_dimension_produit(self, **kwargs):
        try:
            api_key = request.httprequest.headers.get('Authorization')

            user = validate_api_key(api_key)
            if not user:
                return http.Response(
                    json.dumps({"error": "Invalid or missing API key"}),
                    status=401,
                    content_type="application/json"
                )

            if not user.has_group('base.group_system'):
                return http.Response(
                    json.dumps({"error": "Access Denied", "details": "This API requires admin access"}),
                    status=403,
                    content_type="application/json"
                )

            request.update_env(user=user)

            products = request.env['product.template'].sudo().search([])

            produit_data = []
            for product in products:
                pos_categories = [category.name for category in
                                  product.pos_categ_ids] if product.pos_categ_ids else None
                produit_data.append({
                    "produit_id": product.id,
                    "product_type": product.type,
                    "invoicing_policy": product.invoice_policy,
                    "sales_price": product.list_price,
                    "cost": product.standard_price,
                    "barcode": product.barcode,
                    "default_code": product.default_code,
                    "product_category": product.categ_id.name,
                    "pos_category": pos_categories,
                    "available_in_pos": product.available_in_pos
                })

            return request.make_json_response(produit_data, status=200)

        except werkzeug.exceptions.Unauthorized as e:
            return http.Response(
                json.dumps({"error": "Authentication Required", "details": str(e)}),
                status=401,
                content_type="application/json"
            )
        except werkzeug.exceptions.Forbidden as e:
            return http.Response(
                json.dumps({"error": "Access Denied", "details": str(e)}),
                status=403,
                content_type="application/json"
            )
        except Exception as e:
            error_message = f"Error fetching Dimension_produit: {str(e)}"
            request.env.cr.rollback()
            return http.Response(
                json.dumps({"error": "Internal Server Error", "details": error_message}),
                status=500,
                content_type="application/json"
            )