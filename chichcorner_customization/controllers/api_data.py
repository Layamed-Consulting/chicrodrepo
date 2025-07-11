from odoo import http, api
from odoo.http import request
import json
import requests
from odoo.exceptions import AccessDenied
import werkzeug.exceptions


def validate_api_key(api_key):
    """Validate the API key and return the associated user if valid"""
    if not api_key:
        return None
    api_key_record = request.env['api.key'].sudo().search([
        ('key', '=', api_key),
        ('active', '=', True)
    ], limit=1)
    return api_key_record.user_id if api_key_record else None

#product_list_api -- id existe -- done
class DimensionProduitAPI(http.Controller):
    @http.route("/api/dimension_product", auth='none', type='http', methods=['GET'], csrf=False)
    def get_combined_dimension_produit(self, id_pdt_start=None, id_pdt_end=None, **kwargs):
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

            # Get data from current instance (10018)
            local_data = self._get_local_dimension_products(id_pdt_start, id_pdt_end)

            # Get data from second instance (10014)
            remote_data = self._get_remote_dimension_products(id_pdt_start, id_pdt_end)

            # Combine both datasets
            combined_data = local_data + remote_data

            return request.make_json_response(combined_data, status=200)

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
            error_message = f"Error fetching combined dimension products: {str(e)}"
            request.env.cr.rollback()
            return http.Response(
                json.dumps({"error": "Internal Server Error", "details": error_message}),
                status=500,
                content_type="application/json"
            )

    def _get_local_dimension_products(self, id_pdt_start=None, id_pdt_end=None):
        """Get dimension products from current instance"""
        domain = []
        if id_pdt_start and id_pdt_end:
            domain.append(('id', '>=', int(id_pdt_start)))
            domain.append(('id', '<=', int(id_pdt_end)))

        products = request.env['product.template'].sudo().search(domain)
        produit_data = []

        for product in products:
            pos_categories = [category.name for category in product.pos_categ_ids] if product.pos_categ_ids else None
            taxes = [tax.name for tax in product.taxes_id] if product.taxes_id else None

            supplier_info = [
                {
                    "Nom du fournisseur": supplier.display_name,
                    "Prix": supplier.price,
                    "Devise": supplier.currency_id.name if supplier.currency_id else None
                }
                for supplier in product.seller_ids
            ]

            pricelist_item = request.env['product.pricelist.item'].sudo().search([
                ('product_tmpl_id', '=', product.id),
                ('pricelist_id.active', '=', True)
            ], limit=1)
            product_price = pricelist_item.fixed_price if pricelist_item else None

            stock_quantities = {}
            stock_records = request.env['stock.quant'].sudo().search([
                ('product_id', '=', product.product_variant_id.id)
            ])
            for stock in stock_records:
                location_name = stock.location_id.complete_name
                stock_quantities[location_name] = stock.quantity

            category_path = []
            current_category = product.categ_id
            while current_category:
                category_path.insert(0, current_category.name)
                current_category = current_category.parent_id

            def get_cat_level(level):
                return category_path[level - 1] if len(category_path) >= level else None

            produit_data.append({
                "Id du produit": product.id,
                "Nom du Produit": product.name,
                "Code barre": product.barcode,
                "default code": product.default_code,
                "Item ID": product.x_studio_item_id,
                "Coût": product.standard_price,
                "Prix de vente": product_price,
                "HS Code": product.x_studio_hs_code,
                "Pays Origine": product.x_studio_origine_pays,
                "Magasin": get_cat_level(1),
                "Gender": get_cat_level(2),
                "Type d'article": get_cat_level(3),
                "Sous-Marque": get_cat_level(4),
                "Collection": get_cat_level(5),
                "Catégorie d'article": get_cat_level(6),
                "Composition": product.x_studio_composition,
                "Type de produit": product.detailed_type,
                "Politique de fabrication": product.invoice_policy,
                "Stock selon l'emplacement": stock_quantities,
                "Catégorie de produit": product.categ_id.name,
                "Marque du produit": pos_categories,
                "Disponible en POS": product.available_in_pos,
                "Taxes": taxes,
                "Informations fournisseur": supplier_info,
                "Instance": "10018",
                "Instance_Product_ID": f"10018_{product.id}",
            })

        return produit_data

    def _get_remote_dimension_products(self, id_pdt_start=None, id_pdt_end=None):
        """Get dimension products from remote instance (10014)"""
        try:
            params = {}
            if id_pdt_start:
                params['id_pdt_start'] = id_pdt_start
            if id_pdt_end:
                params['id_pdt_end'] = id_pdt_end

            headers = {'Authorization': 'ae8d3cc8f89aeda68b87423d8d32a2e6019cc43b'}

            response = requests.get(
                'http://135.125.204.41:10014/api/dimension_product',
                params=params,
                headers=headers
            )

            if response.status_code == 200:
                remote_data = response.json()

                if isinstance(remote_data, dict):
                    remote_data = [remote_data]

                return remote_data
            else:
                print(f"Error fetching products from remote instance: {response.status_code}")
                return []

        except Exception as e:
            print(f"Error connecting to remote instance for products: {str(e)}")
            return []
    '''
    @http.route("/api/dimension_product", auth='none', type='http', methods=['GET'], csrf=False)
    def get_dimension_produit(self, id_pdt_start=None, id_pdt_end=None, **kwargs):
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

            domain = []
            if id_pdt_start and id_pdt_end:
                domain.append(('id', '>=', int(id_pdt_start)))
                domain.append(('id', '<=', int(id_pdt_end)))

            products = request.env['product.template'].sudo().search(domain)

            produit_data = []

            for product in products:
                pos_categories = [category.name for category in product.pos_categ_ids] if product.pos_categ_ids else None

                taxes = [tax.name for tax in product.taxes_id] if product.taxes_id else None

                supplier_info = [
                    {
                        "Nom du fournisseur": supplier.display_name,
                        "Prix": supplier.price,
                        "Devise": supplier.currency_id.name if supplier.currency_id else None
                    }
                    for supplier in product.seller_ids
                ]

                pricelist_item = request.env['product.pricelist.item'].sudo().search([
                    ('product_tmpl_id', '=', product.id),
                    ('pricelist_id.active', '=', True)
                ], limit=1)
                product_price = pricelist_item.fixed_price if pricelist_item else None

                stock_quantities = {}
                stock_records = request.env['stock.quant'].sudo().search([
                    ('product_id', '=', product.product_variant_id.id)
                ])
                for stock in stock_records:
                    location_name = stock.location_id.complete_name
                    stock_quantities[location_name] = stock.quantity

                category_path = []
                current_category = product.categ_id
                while current_category:
                    category_path.insert(0, current_category.name)
                    current_category = current_category.parent_id

                def get_cat_level(level):
                    return category_path[level - 1] if len(category_path) >= level else None

                produit_data.append({
                    "Id du produit": product.id,
                    "Nom du Produit": product.name,
                    "Code barre": product.barcode,
                    "default code": product.default_code,
                    "Item ID": product.x_studio_item_id,
                    "Coût": product.standard_price,
                    "Prix de vente": product_price,
                    "HS Code": product.x_studio_hs_code,
                    "Pays Origine": product.x_studio_origine_pays,
                    "Magasin": get_cat_level(1),
                    "Gender": get_cat_level(2),
                    "Type d'article": get_cat_level(3),
                    "Sous-Marque": get_cat_level(4),
                    "Collection": get_cat_level(5),
                    "Catégorie d'article": get_cat_level(6),
                    "Composition": product.x_studio_composition,
                    "Type de produit": product.detailed_type,
                    "Politique de fabrication": product.invoice_policy,
                    "Stock selon l'emplacement": stock_quantities,
                    "Catégorie de produit": product.categ_id.name,
                    "Marque du produit": pos_categories,
                    "Disponible en POS": product.available_in_pos,
                    "Taxes": taxes,
                    "Informations fournisseur": supplier_info,
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
    '''
#sales_api -- id existe -- done
class PosOrderAPI(http.Controller):
    @http.route("/api/pos_ventes", auth='none', type='http', methods=['GET'], csrf=False)
    def get_pos_orders(self, id_produit=None, id_magasin=None, id_client=None, id_debut=None, id_fin=None, **kwargs):
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

            # Get local POS orders
            local_data = self._get_local_pos_orders(id_produit, id_magasin, id_client, id_debut, id_fin)

            # Get remote POS orders
            remote_data = self._get_remote_pos_orders(api_key, id_produit, id_magasin, id_client, id_debut, id_fin)

            combined_data = local_data + remote_data

            return request.make_json_response(combined_data, status=200)

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
            error_message = f"Error fetching POS orders: {str(e)}"
            request.env.cr.rollback()
            return http.Response(
                json.dumps({"error": "Internal Server Error", "details": error_message}),
                status=500,
                content_type="application/json"
            )

    def _get_local_pos_orders(self, id_produit, id_magasin, id_client, id_debut, id_fin):
        domain = []

        if id_magasin:
            domain.append(('config_id', '=', int(id_magasin)))

        if id_client:
            domain.append(('partner_id', '=', int(id_client)))

        if id_debut and id_fin:
            domain.append(('date_order', '>=', id_debut))
            domain.append(('date_order', '<=', id_fin))

        pos_orders = request.env['pos.order'].sudo().search(domain)

        pos_data = []
        for order in pos_orders:
            order_lines = []
            for line in order.lines:
                if id_produit and line.product_id.id != int(id_produit):
                    continue

                order_lines.append({
                    "id_produit": line.product_id.id,
                    "Nom": line.product_id.display_name,
                    "Quantité": line.qty,
                    "Note du client": line.customer_note or "",
                    "discount": line.discount,
                    "Prix": line.price_subtotal_incl,
                })

            if not order_lines:
                continue

            pos_data.append({
                "Ref": order.name,
                "Session": order.session_id.id if order.session_id else "None",
                "Date de commande": order.date_order.strftime("%Y-%m-%d %H:%M:%S") if order.date_order else None,
                "Id Magasin": order.config_id.id if order.config_id else None,
                "Nom du Magasin": order.config_id.name if order.config_id else "None",
                "Id Ticket": order.id,
                "Ticket de caisse": order.pos_reference,
                "Id Client": order.partner_id.id if order.partner_id else None,
                "Nom du client": order.partner_id.name if order.partner_id else "",
                "Caissier": order.employee_id.name if order.employee_id else "",
                "Nom du vendeur": order.suggestion if order.suggestion else "",
                "Produits achetés": order_lines,

            })

        return pos_data

    def _get_remote_pos_orders(self, api_key, id_produit, id_magasin, id_client, id_debut, id_fin):
        try:
            params = {}
            if id_produit:
                params['id_produit'] = id_produit
            if id_magasin:
                params['id_magasin'] = id_magasin
            if id_client:
                params['id_client'] = id_client
            if id_debut:
                params['id_debut'] = id_debut
            if id_fin:
                params['id_fin'] = id_fin

            headers = {'Authorization': 'ae8d3cc8f89aeda68b87423d8d32a2e6019cc43b'}

            response = requests.get(
                'http://135.125.204.41:10014/api/pos_ventes',
                params=params,
                headers=headers
            )

            if response.status_code == 200:
                remote_data = response.json()

                if isinstance(remote_data, dict):
                    remote_data = [remote_data]

                return remote_data
            else:
                print(f"Error fetching POS orders from remote instance: {response.status_code}")
                return []

        except Exception as e:
            print(f"Error connecting to remote instance for POS orders: {str(e)}")
            return []

    '''
    @http.route("/api/pos_ventes", auth='none', type='http', methods=['GET'], csrf=False)
    def get_pos_orders(self,id_produit=None, id_magasin=None, id_client=None, id_debut=None, id_fin=None, **kwargs):
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

            domain = []

            if id_magasin:
                domain.append(('config_id', '=', int(id_magasin)))

            if id_client:
                domain.append(('partner_id', '=', int(id_client)))

            if id_debut and id_fin:
                domain.append(('date_order', '>=', id_debut))
                domain.append(('date_order', '<=', id_fin))

            pos_orders = request.env['pos.order'].sudo().search(domain)

            pos_data = []
            for order in pos_orders:
                order_lines = []
                for line in order.lines:
                    if id_produit and line.product_id.id != int(id_produit):
                        continue

                    order_lines.append({
                        "id_produit": line.product_id.id,
                        "Nom": line.product_id.display_name,
                        "Quantité": line.qty,
                        "Note du client": line.customer_note or "",
                        "discount": line.discount,
                        "Prix": line.price_subtotal_incl,
                    })

                if not order_lines:
                    continue
                pos_data.append({
                    "Ref": order.name,
                    "Session": order.session_id.id if order.session_id else "None",
                    "Date de commande": order.date_order,
                    "Id Magasin": order.config_id.id if order.config_id else None,
                    "Nom du Magasin": order.config_id.name if order.config_id else "None",# ID du magasin
                    "Id Ticket": order.id,
                    "Ticket de caisse": order.pos_reference,
                    "Id Client": order.partner_id.id if order.partner_id else None,  # ID du client
                    "Nom du client": order.partner_id.name if order.partner_id else "",
                    "Caissier": order.employee_id.name if order.employee_id else "",
                    "Nom du vendeur": order.suggestion if order.suggestion else "",
                    #"amount_total": order.amount_total,
                    "Produits achetés": order_lines,
                })

            return request.make_json_response(pos_data, status=200)

        except Exception as e:
            error_message = f"Error fetching POS orders: {str(e)}"
            request.env.cr.rollback()
            return http.Response(
                json.dumps({"error": "Internal Server Error", "details": error_message}),
                status=500,
                content_type="application/json"
            )
    '''
#payment_methedo_api -- id existe - done
class PosPaymentAPI(http.Controller):
    @http.route("/api/pos_payments", auth='none', type='http', methods=['GET'], csrf=False)
    def get_pos_payments(self, id_order_start=None, id_order_end=None, id_magasin=None, id_client=None, id_produit=None,id_debut=None, id_fin=None, **kwargs):
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

            # Get local POS payments
            local_data = self._get_local_pos_payments(id_order_start, id_order_end, id_magasin, id_client, id_produit,id_debut, id_fin)

            # Get remote POS payments
            remote_data = self._get_remote_pos_payments(api_key, id_order_start, id_order_end, id_magasin, id_client,id_produit, id_debut, id_fin)

            combined_data = local_data + remote_data

            return request.make_json_response(combined_data, status=200)

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
            error_message = f"Error fetching POS payments: {str(e)}"
            request.env.cr.rollback()
            return http.Response(
                json.dumps({"error": "Internal Server Error", "details": error_message}),
                status=500,
                content_type="application/json"
            )

    def _get_local_pos_payments(self, id_order_start, id_order_end, id_magasin, id_client, id_produit, id_debut,id_fin):
        domain = []

        if id_order_start and id_order_end:
            domain.append(('id', '>=', int(id_order_start)))
            domain.append(('id', '<=', int(id_order_end)))

        if id_magasin:
            domain.append(('session_id.config_id', '=', int(id_magasin)))

        if id_client:
            domain.append(('partner_id', '=', int(id_client)))

        if id_debut and id_fin:
            domain.append(('date_order', '>=', id_debut))
            domain.append(('date_order', '<=', id_fin))

        if id_produit:
            domain.append(('lines.product_id', '=', int(id_produit)))

        pos_orders = request.env['pos.order'].sudo().search(domain)

        payment_data = []
        for order in pos_orders:
            payment_methods = {}

            for payment in order.payment_ids:
                payment_methods[payment.payment_method_id.name] = payment.amount

            payment_data.append({
                "Nom du Magasin": order.config_id.name if order.config_id else "None",
                "Session": order.session_id.name if order.session_id else "None",
                "Id Ticket": order.id,
                "Ticket de caisse": order.pos_reference,
                "Caissier": order.employee_id.name if order.employee_id else "None",
                "Date de commande": order.date_order.strftime("%Y-%m-%d %H:%M:%S") if order.date_order else None,
                "Vendeur": order.suggestion if order.suggestion else "",
                "Nom du Client": order.partner_id.name if order.partner_id else "None",
                "Méthodes de paiement": payment_methods,
            })

        return payment_data

    def _get_remote_pos_payments(self, api_key, id_order_start, id_order_end, id_magasin, id_client, id_produit,id_debut, id_fin):
        try:
            params = {}
            if id_order_start:
                params['id_order_start'] = id_order_start
            if id_order_end:
                params['id_order_end'] = id_order_end
            if id_magasin:
                params['id_magasin'] = id_magasin
            if id_client:
                params['id_client'] = id_client
            if id_produit:
                params['id_produit'] = id_produit
            if id_debut:
                params['id_debut'] = id_debut
            if id_fin:
                params['id_fin'] = id_fin

            headers = {'Authorization': 'ae8d3cc8f89aeda68b87423d8d32a2e6019cc43b'}

            response = requests.get(
                'http://135.125.204.41:10014/api/pos_payments',
                params=params,
                headers=headers

            )

            if response.status_code == 200:
                remote_data = response.json()

                if isinstance(remote_data, dict):
                    remote_data = [remote_data]

                return remote_data
            else:
                print(f"Error fetching POS payments from remote instance: {response.status_code}")
                return []

        except Exception as e:
            print(f"Error connecting to remote instance for POS payments: {str(e)}")
            return []

    '''
    @http.route("/api/pos_payments", auth='none', type='http', methods=['GET'], csrf=False)
    def get_pos_payments(self,id_order_start=None,id_order_end=None, id_magasin=None, id_client=None, id_produit=None, id_debut=None, id_fin=None, **kwargs):
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

            domain = []

            if id_order_start and id_order_end:
                domain.append(('id', '>=', id_order_start))
                domain.append(('id', '<=', id_order_end))

            if id_magasin:
                domain.append(('session_id.config_id', '=', int(id_magasin)))

            if id_client:
                domain.append(('partner_id', '=', int(id_client)))

            if id_debut and id_fin:
                domain.append(('date_order', '>=', id_debut))
                domain.append(('date_order', '<=', id_fin))

            if id_produit:
                domain.append(('lines.product_id', '=', int(id_produit)))

            pos_orders = request.env['pos.order'].sudo().search(domain)

            payment_data = []
            for order in pos_orders:
                payment_methods = {}

                for payment in order.payment_ids:
                    payment_methods[payment.payment_method_id.name] = payment.amount

                payment_data.append({
                    "Nom du Magasin": order.config_id.name if order.config_id else "None",
                    "Session": order.session_id.name if order.session_id else "None",
                    "Id Ticket": order.id,
                    "Ticket de caisse": order.pos_reference,
                    "Caissier": order.employee_id.name if order.employee_id else "None",
                    "Date de commande": order.date_order,
                    "Vendeur": order.suggestion if order.suggestion else "",
                    #"id_client": order.partner_id.id if order.partner_id else None,
                    "Nom du Client": order.partner_id.name if order.partner_id else "None",
                    "Méthodes de paiement": payment_methods
                })

            return request.make_json_response(payment_data, status=200)

        except Exception as e:
            error_message = f"Error fetching POS payments: {str(e)}"
            request.env.cr.rollback()
            return http.Response(
                json.dumps({"error": "Internal Server Error", "details": error_message}),
                status=500,
                content_type="application/json"
            )
    '''
#achat -- vente delete order_id - done
class PurchaseOrderAPI(http.Controller):
    @http.route("/api/purchase_orders", auth='none', type='http', methods=['GET'], csrf=False)
    def get_purchase_orders(self, id_fournisseur=None, id_user=None, id_debut=None, id_fin=None, **kwargs):
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

            # Get local purchase orders
            local_data = self._get_local_purchase_orders(id_fournisseur, id_user, id_debut, id_fin)

            # Get remote purchase orders
            remote_data = self._get_remote_purchase_orders(api_key, id_fournisseur, id_user, id_debut, id_fin)

            combined_data = local_data + remote_data

            return request.make_json_response(combined_data, status=200)

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
            error_message = f"Error fetching purchase orders: {str(e)}"
            request.env.cr.rollback()
            return http.Response(
                json.dumps({"error": "Internal Server Error", "details": error_message}),
                status=500,
                content_type="application/json"
            )

    def _get_local_purchase_orders(self, id_fournisseur, id_user, id_debut, id_fin):
        domain = []

        if id_fournisseur:
            domain.append(('partner_id', '=', int(id_fournisseur)))

        if id_user:
            domain.append(('user_id', '=', int(id_user)))

        if id_debut and id_fin:
            domain.append(('date_approve', '>=', id_debut))
            domain.append(('date_approve', '<=', id_fin))

        domain.append(('state', 'not in', ['cancel', 'done']))
        purchase_orders = request.env['purchase.order'].sudo().search(domain)

        purchase_data = []
        for po in purchase_orders:
            total_qty = sum(po.order_line.mapped('product_qty'))
            total_received = sum(po.order_line.mapped('qty_received'))
            warehouse = po.picking_type_id.warehouse_id if po.picking_type_id else None
            currency = po.currency_id.name
            supplier_name = po.partner_id.name if po.partner_id else ""

            # Add "MA - " only if it's EUR
            if currency == "MAD" and not supplier_name.startswith("MA - "):
                supplier_name = "MA - " + supplier_name

            # Manual exchange rate conversion
            if po.currency_id.name == 'MAD':
                converted_total = po.amount_total
            elif po.currency_id.name == 'EUR':
                converted_total = po.amount_total * 11.200000000
            elif po.currency_id.name == 'USD':
                converted_total = po.amount_total * 9.7500000000
            else:
                converted_total = po.amount_total  # fallback if unknown currency

            purchase_data.append({
                "Bon De Commande": po.name,
                "Date de confirmation": po.date_approve.strftime("%Y-%m-%d %H:%M:%S") if po.date_approve else None,
                "Fournisseur": supplier_name,
                "Livrer à": po.picking_type_id.name if po.picking_type_id else "",
                "Id du Magasin": warehouse.id if warehouse else "",
                "Nom du Magasin": warehouse.name if warehouse else "",
                "Document D'origine": po.x_studio_dd_impot if hasattr(po,'x_studio_dd_impot') and po.x_studio_dd_impot else "",
                "DD Impot": po.x_studio_dd_impot if hasattr(po, 'x_studio_dd_impot') and po.x_studio_dd_impot else "",
                "Num Fact Fournisseur": po.x_studio_num_fact_frs if hasattr(po,'x_studio_num_fact_frs') and po.x_studio_num_fact_frs else "",
                "Total": converted_total,
                "Quantité commandée": total_qty,
                "Quantité reçue": total_received,
            })

        return purchase_data

    def _get_remote_purchase_orders(self, api_key, id_fournisseur, id_user, id_debut, id_fin):
        try:
            params = {}
            if id_fournisseur:
                params['id_fournisseur'] = id_fournisseur
            if id_user:
                params['id_user'] = id_user
            if id_debut:
                params['id_debut'] = id_debut
            if id_fin:
                params['id_fin'] = id_fin

            headers = {'Authorization': 'ae8d3cc8f89aeda68b87423d8d32a2e6019cc43b'}

            response = requests.get(
                'http://135.125.204.41:10014/api/purchase_orders',
                params=params,
                headers=headers

            )

            if response.status_code == 200:
                remote_data = response.json()

                if isinstance(remote_data, dict):
                    remote_data = [remote_data]


                return remote_data
            else:
                print(f"Error fetching purchase orders from remote instance: {response.status_code}")
                return []

        except Exception as e:
            print(f"Error connecting to remote instance for purchase orders: {str(e)}")
            return []
    '''
    @http.route("/api/purchase_orders", auth='none', type='http', methods=['GET'], csrf=False)
    def get_purchase_orders(self,id_fournisseur=None, id_user=None, id_debut=None, id_fin=None, **kwargs):
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

            domain = []

            if id_fournisseur:
                domain.append(('partner_id', '=', int(id_fournisseur)))

            if id_user:
                domain.append(('user_id', '=', int(id_user)))

            if id_debut and id_fin:
                domain.append(('date_approve', '>=', id_debut))
                domain.append(('date_approve', '<=', id_fin))

            domain.append(('state', 'not in', ['cancel', 'done']))
            purchase_orders = request.env['purchase.order'].sudo().search(domain)

            purchase_data = []
            for po in purchase_orders:
                total_qty = sum(po.order_line.mapped('product_qty'))
                total_received = sum(po.order_line.mapped('qty_received'))
                warehouse = po.picking_type_id.warehouse_id if po.picking_type_id else None
                currency = po.currency_id.name
                supplier_name = po.partner_id.name if po.partner_id else ""

                # Add "MA - " only if it's EUR
                if currency == "MAD" and not supplier_name.startswith("MA - "):
                    supplier_name = "MA - " + supplier_name

                # Manual exchange rate conversion
                if po.currency_id.name == 'MAD':
                    converted_total = po.amount_total
                elif po.currency_id.name == 'EUR':
                    converted_total = po.amount_total * 11.200000000
                elif po.currency_id.name == 'USD':
                    converted_total = po.amount_total * 9.7500000000
                else:
                    converted_total = po.amount_total  # fallback if unknown currency
                purchase_data.append({
                    "Bon De Commande": po.name,
                    "Date de confirmation": po.date_approve,
                    "Fournisseur": supplier_name,
                    "Livrer à" : po.picking_type_id.name if po.picking_type_id else "",
                    "Id du Magasin": warehouse.id if warehouse else "",
                    "Nom du Magasin": warehouse.name if warehouse else "",
                    #"partner_name": po.partner_id.name if po.partner_id else None,
                    #"user_id": po.user_id.id if po.user_id else None,
                    #"Utilisateur": po.user_id.name if po.user_id else None,
                    "Document D'origine": po.origin if po.origin else "",
                    "DD Impot": po.x_studio_dd_impot if po.x_studio_dd_impot else "",
                    "Num Fact Fournisseur": po.x_studio_num_fact_frs if po.x_studio_num_fact_frs else "",
                    "Total": converted_total,
                    "Quantité commandée": total_qty,
                    "Quantité reçue": total_received
                })

            return request.make_json_response(purchase_data, status=200)

        except Exception as e:
            error_message = f"Error fetching purchase orders: {str(e)}"
            request.env.cr.rollback()
            return http.Response(
                json.dumps({"error": "Internal Server Error", "details": error_message}),
                status=500,
                content_type="application/json"
            )
    '''
# stock :
class InventoryAPI(http.Controller):
    @http.route("/api/inventory", auth='none', type='http', methods=['GET'], csrf=False)
    def get_inventory(self, id_debut=None, id_fin=None, **kwargs):
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

            # Get local inventory data
            local_data = self._get_local_inventory(id_debut, id_fin)

            # Get remote inventory data
            remote_data = self._get_remote_inventory(api_key, id_debut, id_fin)

            combined_data = local_data + remote_data

            return request.make_json_response(combined_data, status=200)

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
            error_message = f"Error fetching inventory data: {str(e)}"
            request.env.cr.rollback()
            return http.Response(
                json.dumps({"error": "Internal Server Error", "details": error_message}),
                status=500,
                content_type="application/json"
            )

    def _get_local_inventory(self, id_debut, id_fin):
        domain = []
        if id_debut and id_fin:
            domain.append(('in_date', '>=', id_debut))
            domain.append(('in_date', '<=', id_fin))

        inventory_lines = request.env['stock.quant'].sudo().search(domain)

        inventory_data = []
        for line in inventory_lines:
            product = line.product_id
            category_path = []
            category = product.categ_id
            while category:
                category_path.insert(0, category.name)  # Ajouter au début pour avoir le bon ordre
                category = category.parent_id

            pricelist_item = request.env['product.pricelist.item'].sudo().search([
                ('product_tmpl_id', '=', product.product_tmpl_id.id),
                ('pricelist_id.active', '=', True)
            ], limit=1)

            product_price = pricelist_item.fixed_price if pricelist_item else None
            pos_categories = [category.name for category in product.pos_categ_ids] if product.pos_categ_ids else []

            inventory_data.append({
                "L'emplacement": line.location_id.complete_name if line.location_id else "",
                "ID du Produit": product.id,
                "Nom du produit": product.display_name if product else "",
                "Id Magasin": line.warehouse_id.id if line.warehouse_id and line.warehouse_id.id else "Aucun",
                "Nom du Magasin": line.warehouse_id.name if line.warehouse_id and line.warehouse_id.name else "Aucun",
                "Categorie POS": ", ".join(pos_categories) if pos_categories else "Aucune",
                "Categorie": " / ".join(category_path) if category_path else "Non classé",
                "Quantité en stock": line.inventory_quantity_auto_apply,
                "Valeur en MAD": line.value,
                "Item ID": product.x_studio_item_id if hasattr(product, 'x_studio_item_id') else None,
                "Prix de vente": product_price,
            })

        return inventory_data

    def _get_remote_inventory(self, api_key, id_debut, id_fin):
        try:
            params = {}
            if id_debut:
                params['id_debut'] = id_debut
            if id_fin:
                params['id_fin'] = id_fin

            headers = {'Authorization': 'ae8d3cc8f89aeda68b87423d8d32a2e6019cc43b'}

            response = requests.get(
                'http://135.125.204.41:10014/api/inventory',
                params=params,
                headers=headers

            )

            if response.status_code == 200:
                remote_data = response.json()

                if isinstance(remote_data, dict):
                    remote_data = [remote_data]


                return remote_data
            else:
                print(f"Error fetching inventory from remote instance: {response.status_code}")
                return []

        except Exception as e:
            print(f"Error connecting to remote instance for inventory: {str(e)}")
            return []
    '''
    @http.route("/api/inventory", auth='none', type='http', methods=['GET'], csrf=False)
    def get_inventory(self,id_debut=None, id_fin=None, **kwargs):
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

            domain = []
            if id_debut and id_fin:
                domain.append(('in_date', '>=', id_debut))
                domain.append(('in_date', '<=', id_fin))

            inventory_lines = request.env['stock.quant'].sudo().search(domain)

            inventory_data = []
            for line in inventory_lines:
                product = line.product_id
                category_path = []
                category = product.categ_id
                while category:
                    category_path.insert(0, category.name)  # Ajouter au début pour avoir le bon ordre
                    category = category.parent_id

                pricelist_item = request.env['product.pricelist.item'].sudo().search([
                    ('product_tmpl_id', '=', product.product_tmpl_id.id),
                    ('pricelist_id.active', '=', True)
                ], limit=1)

                product_price = pricelist_item.fixed_price if pricelist_item else None
                pos_categories = [category.name for category in product.pos_categ_ids] if product.pos_categ_ids else []
                inventory_data.append({
                    "L'emplacement": line.location_id.complete_name if line.location_id else "",
                    "ID du Produit": product.id,
                    "Nom du produit": product.display_name if product else "",
                    "Id Magasin": line.warehouse_id.id if line.warehouse_id.id else "Aucun",
                    "Nom du Magasin": line.warehouse_id.name if line.warehouse_id.name else "Aucun",
                    "Categorie POS": ", ".join(pos_categories) if pos_categories else "Aucune",
                    "Categorie": " / ".join(category_path) if category_path else "Non classé",
                    "Quantité en stock": line.inventory_quantity_auto_apply,
                    "Valeur en MAD": line.value,
                    "Item ID": product.x_studio_item_id if hasattr(product, 'x_studio_item_id') else None,
                    "Prix de vente": product_price
                })

            return request.make_json_response(inventory_data, status=200)

        except Exception as e:
            error_message = f"Error fetching inventory data: {str(e)}"
            request.env.cr.rollback()
            return http.Response(
                json.dumps({"error": "Internal Server Error", "details": error_message}),
                status=500,
                content_type="application/json"
            )   
    '''
#stock valorisation
class StockValuationAPI(http.Controller):
    @http.route("/api/stock_valuation", auth='none', type='http', methods=['GET'], csrf=False)
    def get_stock_valuation(self, id_val_start=None, id_debut=None, id_fin=None, id_val_end=None, **kwargs):
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

            # Get local stock valuation data
            local_data = self._get_local_stock_valuation(id_val_start, id_debut, id_fin, id_val_end)

            # Get remote stock valuation data
            remote_data = self._get_remote_stock_valuation(api_key, id_val_start, id_debut, id_fin, id_val_end)

            # Combine data and calculate total
            combined_data = local_data + remote_data

            # Calculate combined total value
            total_value = 0
            for record in combined_data:
                if "Valeur en MAD" in record and isinstance(record["Valeur en MAD"], (int, float)):
                    total_value += record["Valeur en MAD"]

            # Add total at the end
            combined_data.append({
                "Total Valeur en MAD": total_value,
            })

            return request.make_json_response(combined_data, status=200)

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
            error_message = f"Error fetching stock valuation data: {str(e)}"
            request.env.cr.rollback()
            return http.Response(
                json.dumps({"error": "Internal Server Error", "details": error_message}),
                status=500,
                content_type="application/json"
            )

    def _get_local_stock_valuation(self, id_val_start, id_debut, id_fin, id_val_end):
        domain = []

        if id_debut and id_fin:
            domain.append(('create_date', '>=', id_debut))
            domain.append(('create_date', '<=', id_fin))

        if id_val_start and id_val_end:
            domain.append(('id', '>=', int(id_val_start)))
            domain.append(('id', '<=', int(id_val_end)))

        valuation_records = request.env['stock.valuation.layer'].sudo().search(domain)

        valuation_data = []

        for record in valuation_records:
            product = record.product_id
            pos_category_names = [cat.name for cat in product.pos_categ_ids] if product.pos_categ_ids else ["Aucune"]

            valuation_data.append({
                "Date de création": record.create_date.strftime("%Y-%m-%d %H:%M:%S") if record.create_date else None,
                "Référence": record.reference,
                "ID Du Produit": record.product_id.id if record.product_id else "",
                "Nom Produit": record.product_id.display_name if record.product_id else "",
                "Magasin": " / ".join(pos_category_names),
                "Quantité": record.quantity,
                "Quantité restante": record.remaining_qty,
                "Valeur en MAD": record.value,
                "Valeur restante en MAD": record.remaining_value,
            })

        return valuation_data

    def _get_remote_stock_valuation(self, api_key, id_val_start, id_debut, id_fin, id_val_end):
        try:
            params = {}
            if id_val_start:
                params['id_val_start'] = id_val_start
            if id_debut:
                params['id_debut'] = id_debut
            if id_fin:
                params['id_fin'] = id_fin
            if id_val_end:
                params['id_val_end'] = id_val_end

            headers = {'Authorization': 'ae8d3cc8f89aeda68b87423d8d32a2e6019cc43b'}

            response = requests.get(
                'http://135.125.204.41:10014/api/stock_valuation',
                params=params,
                headers=headers

            )

            if response.status_code == 200:
                remote_data = response.json()

                if isinstance(remote_data, dict):
                    remote_data = [remote_data]

                # Filter out the total record from remote data (if it exists)
                filtered_data = []
                for record in remote_data:
                    # Skip records that only contain total information
                    if "Total Valeur en MAD" in record and len(record) <= 2:
                        continue

                    # Add instance tracking to actual valuation records
                    if "ID Du Produit" in record or "Référence" in record:
                        record_id = record.get("ID Du Produit") or record.get("Référence") or "UNKNOWN"

                        filtered_data.append(record)

                return filtered_data
            else:
                print(f"Error fetching stock valuation from remote instance: {response.status_code}")
                return []

        except Exception as e:
            print(f"Error connecting to remote instance for stock valuation: {str(e)}")
            return []
    '''
    @http.route("/api/stock_valuation", auth='none', type='http', methods=['GET'], csrf=False)
    def get_stock_valuation(self,id_val_start=None, id_debut=None, id_fin=None, id_val_end=None, **kwargs):
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

            domain = []

            if id_debut and id_fin:
                domain.append(('create_date', '>=', id_debut))
                domain.append(('create_date', '<=', id_fin))

            if id_val_start and id_val_end:
                domain.append(('id', '>=', id_val_start))
                domain.append(('id', '<=', id_val_end))

            valuation_records = request.env['stock.valuation.layer'].sudo().search(domain)

            valuation_data = []
            total_value = 0

            for record in valuation_records:
                product = record.product_id
                pos_category_names = [cat.name for cat in product.pos_categ_ids] if product.pos_categ_ids else [
                    "Aucune", ]

                valuation_data.append({
                    "Date de création": record.create_date,
                    "Référence": record.reference,
                    "ID Du Produit": record.product_id.id if record.product_id else "",
                    "Nom Produit": record.product_id.display_name if record.product_id else "",
                    "Magasin": " / ".join(pos_category_names),
                    "Quantité": record.quantity,
                    "Quantité restante": record.remaining_qty,
                    "Valeur en MAD": record.value,
                    "Valeur restante en MAD": record.remaining_value,
                })
                total_value += record.value


            valuation_data.append({
                "Total Valeur en MAD": total_value
            })

            return request.make_json_response(valuation_data, status=200)

        except Exception as e:
            error_message = f"Error fetching stock valuation data: {str(e)}"
            request.env.cr.rollback()
            return http.Response(
                json.dumps({"error": "Internal Server Error", "details": error_message}),
                status=500,
                content_type="application/json"
            )
    '''