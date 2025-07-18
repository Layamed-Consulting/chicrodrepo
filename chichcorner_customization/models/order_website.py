import requests
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from odoo import models, api

_logger = logging.getLogger(__name__)


class CustomerFetcher(models.TransientModel):
    _name = 'customer.fetch'
    _description = 'Customer Data Fetcher'

    '''
    API_BASE_URL = "https://www.premiumshop.ma/api"
    WS_KEY = "E93WGT9K8726WW7F8CWIXDH9VGFBLH6A"
    '''''
    '''
    @api.model
    def fetch_customer_data(self):
        _logger.info("Starting order data fetch...")

        orders_url = f"{self.API_BASE_URL}/orders?ws_key={self.WS_KEY}"

        try:
            _logger.info("Making API request to: %s", orders_url)
            response = requests.get(orders_url, timeout=30)

            if response.status_code == 200:
                _logger.info("SUCCESS: API call successful!")

                root = ET.fromstring(response.content)
                orders = root.find('orders')
                if orders is None:
                    _logger.warning("No <orders> element found in response.")
                    return

                order_elements = orders.findall('order')
                _logger.info("Total orders found: %d", len(order_elements))

                for i, order in enumerate(order_elements):
                    order_id = order.get('id')
                    href = order.get('{http://www.w3.org/1999/xlink}href')

                    # Check if order already exists in Odoo
                    if self.env['stock.website.order'].search([('ticket_id', '=', order_id)], limit=1):
                        _logger.info("Skipping existing order ID=%s", order_id)
                        continue

                    _logger.info("New Order %s: ID=%s, URL=%s", i + 1, order_id, href)
                    self._fetch_and_log_order_details(order_id)

            else:
                _logger.error("FAILED: Status %s - %s", response.status_code, response.text)

        except requests.exceptions.Timeout:
            _logger.error("TIMEOUT: API request timed out")

        except requests.exceptions.ConnectionError:
            _logger.error("🔌 CONNECTION ERROR: Unable to reach API")

        except Exception as e:
            _logger.exception("EXCEPTION: %s", str(e))

        _logger.info("Order data fetch completed")

    def _fetch_and_log_order_details(self, order_id):
        order_url = f"{self.API_BASE_URL}/orders/{order_id}?ws_key={self.WS_KEY}"
        try:
            response = requests.get(order_url, timeout=30)
            if response.status_code == 200:
                tree = ET.fromstring(response.content)
                order = tree.find('order')

                customer_elem = order.find('id_customer')
                address_delivery_elem = order.find('id_address_delivery')

                customer_url = customer_elem.attrib.get('{http://www.w3.org/1999/xlink}href')
                address_delivery_url = address_delivery_elem.attrib.get('{http://www.w3.org/1999/xlink}href')

                customer_details = self._get_complete_customer_details(customer_url, address_delivery_url)

                # Get or create contact
                email = customer_details.get('email')
                partner = self.env['res.partner'].search([('email', '=', email)], limit=1)
                if not partner:
                    partner = self.env['res.partner'].create({
                        'name': f"{customer_details.get('firstname', '')} {customer_details.get('lastname', '')}".strip(),
                        'email': email,
                        'phone': customer_details.get('phone') or customer_details.get('phone_mobile'),
                        'mobile': customer_details.get('phone_mobile'),
                        'company_name': customer_details.get('company'),
                        'street': customer_details.get('address1'),
                        'street2': customer_details.get('address2'),
                        'city': customer_details.get('city'),
                        'zip': customer_details.get('postcode'),
                        'country_id': self.env['res.country'].search([('name', '=', customer_details.get('country'))], limit=1).id if customer_details.get('country') else False,
                    })
                    _logger.info("Created new partner: %s", partner.name)
                else:
                    _logger.info("Partner already exists: %s", partner.name)

                # Order info
                date_commande_str = order.findtext('date_add', default='').strip()
                date_commande = datetime.strptime(date_commande_str, '%Y-%m-%d %H:%M:%S').date() if date_commande_str else None
                reference = order.findtext('reference', default='').strip()
                payment = order.findtext('payment', default='').strip()
                order_rec = self.env['stock.website.order'].create({
                    'ticket_id': order_id,
                    'reference': reference,
                    'client_name': partner.name,
                    'email': partner.email,
                    'phone': partner.phone,
                    'mobile': partner.mobile,
                    'adresse': partner.street,
                    'second_adresse': partner.street2,
                    'city': partner.city,
                    'postcode': partner.zip,
                    'pays': partner.country_id,
                    'date_commande': date_commande,
                    'payment_method': payment,
                })

                order_rows = order.findall('.//order_row')
                total_amount = 0

                for row in order_rows:
                    product_name = row.findtext('product_name', default='').strip()
                    product_reference = row.findtext('product_ean13', default='').strip()
                    quantity = row.findtext('product_quantity', default='0').strip()
                    price = row.findtext('product_price', default='0.00').strip()
                    unit_price_incl = row.findtext('unit_price_tax_incl', default='0.00').strip()
                    line_total = float(quantity) * float(unit_price_incl) if quantity and unit_price_incl else 0
                    total_amount += line_total

                    product = self.env['product.product'].search([('default_code', '=', product_reference)], limit=1)
                    if not product:
                        _logger.warning("No product found with reference: %s", product_reference)
                        continue

                    self.env['stock.website.order.line'].create({
                        'order_id': order_rec.id,
                        'product_id': product.id,
                        'code_barre':product_reference,
                        'product_name': product.name,
                        'quantity': float(quantity),
                        'discount': float(row.findtext('total_discounts', default='0.00')),
                        'price': float(price),
                    })

                total_paid = order.findtext('total_paid_tax_incl', default='0.00')
                payment_method = order.findtext('payment', default='')

                _logger.info("ORDER #%s Summary:", order_id)
                _logger.info("   Total Paid: %s MAD", total_paid)
                _logger.info("   Payment Method: %s", payment_method)
                _logger.info("=" * 80)

            else:
                _logger.error("Failed to fetch order details for %s, status code: %s", order_id, response.status_code)
        except Exception as e:
            _logger.exception("Exception fetching details for order %s: %s", order_id, str(e))

    def _get_complete_customer_details(self, customer_url, address_url):
        """Fetch complete customer details including address information"""
        customer_details = {}

        # Fetch customer basic info
        if customer_url:
            customer_data = self._fetch_api_data(f"{customer_url}?ws_key={self.WS_KEY}")
            if customer_data:
                tree = ET.fromstring(customer_data)
                customer_details.update({
                    'firstname': self._get_text_content(tree, './/firstname'),
                    'lastname': self._get_text_content(tree, './/lastname'),
                    'email': self._get_text_content(tree, './/email'),
                })

        # Fetch address details
        if address_url:
            address_data = self._fetch_api_data(f"{address_url}?ws_key={self.WS_KEY}")
            if address_data:
                tree = ET.fromstring(address_data)
                customer_details.update({
                    'phone': self._get_text_content(tree, './/phone'),
                    'phone_mobile': self._get_text_content(tree, './/phone_mobile'),
                    'company': self._get_text_content(tree, './/company'),
                    'address1': self._get_text_content(tree, './/address1'),
                    'address2': self._get_text_content(tree, './/address2'),
                    'city': self._get_text_content(tree, './/city'),
                    'postcode': self._get_text_content(tree, './/postcode'),
                })

                # Get country name if available
                country_elem = tree.find('.//id_country')
                if country_elem is not None:
                    country_url = country_elem.attrib.get('{http://www.w3.org/1999/xlink}href')
                    if country_url:
                        country_data = self._fetch_api_data(f"{country_url}?ws_key={self.WS_KEY}")
                        if country_data:
                            country_tree = ET.fromstring(country_data)
                            country_name = self._get_text_content(country_tree, './/name')
                            customer_details['country'] = country_name

        return customer_details

    def _fetch_api_data(self, url):
        """Helper method to fetch data from API"""
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                return response.content
            else:
                _logger.warning("Failed to fetch data from %s (status %s)", url, response.status_code)
                return None
        except Exception as e:
            _logger.exception("Exception fetching data from %s: %s", url, str(e))
            return None

    def _get_text_content(self, tree, xpath):
        """Helper method to safely extract text content from XML"""
        element = tree.find(xpath)
        return element.text.strip() if element is not None and element.text else ''

    def _get_customer_name(self, customer_url):
        """Legacy method - kept for compatibility"""
        if not customer_url:
            return "Unknown"

        url = f"{customer_url}?ws_key={self.WS_KEY}"
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                tree = ET.fromstring(response.content)
                firstname = tree.find('.//firstname')
                lastname = tree.find('.//lastname')
                firstname_text = firstname.text if firstname is not None else ''
                lastname_text = lastname.text if lastname is not None else ''
                return f"{firstname_text} {lastname_text}".strip()
            else:
                _logger.warning("Failed to fetch customer data at %s (status %s)", url, response.status_code)
                return "Unknown"
        except Exception as e:
            _logger.exception("Exception fetching customer data from %s: %s", url, str(e))
            return "Unknown"
    '''
    '''
    @api.model
    def fetch_customer_data(self):

        orders_url = f"{self.API_BASE_URL}/orders?ws_key={self.WS_KEY}"

        try:
            _logger.info("Making API request to: %s", orders_url)
            response = requests.get(orders_url, timeout=30)

            if response.status_code == 200:
                _logger.info("SUCCESS: API call successful!")

                root = ET.fromstring(response.content)
                orders = root.find('orders')
                if orders is None:
                    _logger.warning("No <orders> element found in response.")
                    return

                order_elements = orders.findall('order')
                _logger.info("Total orders found: %d", len(order_elements))

                for i, order in enumerate(order_elements):
                    order_id = order.get('id')
                    href = order.get('{http://www.w3.org/1999/xlink}href')

                    # Check if order already exists in Odoo
                    if self.env['stock.website.order'].search([('ticket_id', '=', order_id)], limit=1):
                        _logger.info("Skipping existing order ID=%s", order_id)
                        continue

                    _logger.info("New Order %s: ID=%s, URL=%s", i + 1, order_id, href)
                    self._fetch_and_log_order_details(order_id)

            else:
                _logger.error("FAILED: Status %s - %s", response.status_code, response.text)

        except requests.exceptions.Timeout:
            _logger.error("TIMEOUT: API request timed out")

        except requests.exceptions.ConnectionError:
            _logger.error("🔌 CONNECTION ERROR: Unable to reach API")

        except Exception as e:
            _logger.exception("EXCEPTION: %s", str(e))

        _logger.info("Order data fetch completed")

    def _fetch_and_log_order_details(self, order_id):
        order_url = f"{self.API_BASE_URL}/orders/{order_id}?ws_key={self.WS_KEY}"
        try:
            response = requests.get(order_url, timeout=30)
            if response.status_code == 200:
                tree = ET.fromstring(response.content)
                order = tree.find('order')

                customer_elem = order.find('id_customer')
                address_delivery_elem = order.find('id_address_delivery')

                customer_url = customer_elem.attrib.get('{http://www.w3.org/1999/xlink}href')
                address_delivery_url = address_delivery_elem.attrib.get('{http://www.w3.org/1999/xlink}href')

                customer_details = self._get_complete_customer_details(customer_url, address_delivery_url)

                # Get or create/update contact based on phone and email
                partner = self._find_or_create_partner(customer_details)

                # Order info
                date_commande_str = order.findtext('date_add', default='').strip()
                date_commande = datetime.strptime(date_commande_str,
                                                  '%Y-%m-%d %H:%M:%S').date() if date_commande_str else None
                reference = order.findtext('reference', default='').strip()
                payment = order.findtext('payment', default='').strip()
                if payment == "Paiement comptant à la livraison (Cash on delivery)":
                    payment = "COD"
                # Use PrestaShop data for order_rec, not Odoo partner data
                order_rec = self.env['stock.website.order'].create({
                    'ticket_id': order_id,
                    'reference': reference,
                    'client_name': f"{customer_details.get('firstname', '')} {customer_details.get('lastname', '')}".strip(),
                    'email': customer_details.get('email', ''),
                    'phone': customer_details.get('phone', ''),
                    'mobile': customer_details.get('phone_mobile', ''),
                    'adresse': customer_details.get('address1', ''),
                    'second_adresse': customer_details.get('address2', ''),
                    'city': customer_details.get('city', ''),
                    'postcode': customer_details.get('postcode', ''),
                    'pays': self.env['res.country'].search([('name', '=', customer_details.get('country'))],
                                                           limit=1) if customer_details.get('country') else False,
                    'date_commande': date_commande,
                    'payment_method': payment,
                })

                order_rows = order.findall('.//order_row')
                total_amount = 0

                for row in order_rows:
                    product_name = row.findtext('product_name', default='').strip()
                    product_reference = row.findtext('product_ean13', default='').strip()
                    quantity = row.findtext('product_quantity', default='0').strip()
                    price = row.findtext('product_price', default='0.00').strip()
                    unit_price_incl = row.findtext('unit_price_tax_incl', default='0.00').strip()
                    line_total = float(quantity) * float(unit_price_incl) if quantity and unit_price_incl else 0
                    total_amount += line_total

                    product = self.env['product.product'].search([('default_code', '=', product_reference)], limit=1)
                    if not product:
                        _logger.warning("No product found with reference: %s", product_reference)
                        continue

                    self.env['stock.website.order.line'].create({
                        'order_id': order_rec.id,
                        'product_id': product.id,
                        'code_barre': product_reference,
                        'product_name': product.name,
                        'quantity': float(quantity),
                        'discount': float(row.findtext('total_discounts', default='0.00')),
                        'price': float(price),
                    })

                total_paid = order.findtext('total_paid_tax_incl', default='0.00')
                payment_method = order.findtext('payment', default='')

                _logger.info("ORDER #%s Summary:", order_id)
                _logger.info("   Total Paid: %s MAD", total_paid)
                _logger.info("   Payment Method: %s", payment_method)
                _logger.info("=" * 80)

            else:
                _logger.error("Failed to fetch order details for %s, status code: %s", order_id, response.status_code)
        except Exception as e:
            _logger.exception("Exception fetching details for order %s: %s", order_id, str(e))

    def _find_or_create_partner(self, customer_details):
        """Find existing partner or create/update based on phone and email matching"""
        email = customer_details.get('email', '').strip().lower()
        phone = customer_details.get('phone', '').strip()
        phone_mobile = customer_details.get('phone_mobile', '').strip()
        firstname = customer_details.get('firstname', '').strip()
        lastname = customer_details.get('lastname', '').strip()
        full_name = f"{firstname} {lastname}".strip()

        partner = None

        # Search for existing partner by phone (mobile or phone) and email
        search_domain = []
        if phone:
            search_domain.append(('phone', '=', phone))
        if phone_mobile:
            if search_domain:
                search_domain = ['|'] + search_domain + [('mobile', '=', phone_mobile)]
            else:
                search_domain.append(('mobile', '=', phone_mobile))

        if email:
            if search_domain:
                search_domain = ['&', ('email', '=', email)] + search_domain
            else:
                search_domain.append(('email', '=', email))

        if search_domain:
            partners = self.env['res.partner'].search(search_domain)

            # If multiple partners found, try to match by name (case insensitive)
            if len(partners) > 1 and full_name:
                for p in partners:
                    if p.name and p.name.lower() == full_name.lower():
                        partner = p
                        break
                # If no exact name match, take the first one
                if not partner:
                    partner = partners[0]
            elif len(partners) == 1:
                partner = partners[0]

        # Prepare partner values with ALL PrestaShop data
        country_id = False
        if customer_details.get('country'):
            country = self.env['res.country'].search([('name', '=', customer_details.get('country'))], limit=1)
            if country:
                country_id = country.id

        partner_vals = {
            'name': full_name,
            'email': email,
            'phone': phone,
            'mobile': phone_mobile,
            'company_name': customer_details.get('company', ''),
            'street': customer_details.get('address1', ''),
            'street2': customer_details.get('address2', ''),
            'city': customer_details.get('city', ''),
            'zip': customer_details.get('postcode', ''),
            'country_id': country_id,
        }

        if partner:
            # Always update existing partner with PrestaShop data (overwrite existing)
            old_address = partner.street
            partner.write(partner_vals)

        else:
            # Create new partner with all PrestaShop data
            partner = self.env['res.partner'].create(partner_vals)
            _logger.info("Created new partner: %s with all PrestaShop details", partner.name)

        return partner

    def _get_complete_customer_details(self, customer_url, address_url):
        """Fetch complete customer details including address information"""
        customer_details = {}

        # Fetch customer basic info
        if customer_url:
            customer_data = self._fetch_api_data(f"{customer_url}?ws_key={self.WS_KEY}")
            if customer_data:
                tree = ET.fromstring(customer_data)
                customer_details.update({
                    'firstname': self._get_text_content(tree, './/firstname'),
                    'lastname': self._get_text_content(tree, './/lastname'),
                    'email': self._get_text_content(tree, './/email'),
                })

        # Fetch address details
        if address_url:
            address_data = self._fetch_api_data(f"{address_url}?ws_key={self.WS_KEY}")
            if address_data:
                tree = ET.fromstring(address_data)
                customer_details.update({
                    'phone': self._get_text_content(tree, './/phone'),
                    'phone_mobile': self._get_text_content(tree, './/phone_mobile'),
                    'company': self._get_text_content(tree, './/company'),
                    'address1': self._get_text_content(tree, './/address1'),
                    'address2': self._get_text_content(tree, './/address2'),
                    'city': self._get_text_content(tree, './/city'),
                    'postcode': self._get_text_content(tree, './/postcode'),
                })

                # Get country name if available
                country_elem = tree.find('.//id_country')
                if country_elem is not None:
                    country_url = country_elem.attrib.get('{http://www.w3.org/1999/xlink}href')
                    if country_url:
                        country_data = self._fetch_api_data(f"{country_url}?ws_key={self.WS_KEY}")
                        if country_data:
                            country_tree = ET.fromstring(country_data)
                            country_name = self._get_text_content(country_tree, './/name')
                            customer_details['country'] = country_name

        return customer_details

    def _fetch_api_data(self, url):
        """Helper method to fetch data from API"""
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                return response.content
            else:
                _logger.warning("Failed to fetch data from %s (status %s)", url, response.status_code)
                return None
        except Exception as e:
            _logger.exception("Exception fetching data from %s: %s", url, str(e))
            return None

    def _get_text_content(self, tree, xpath):
        """Helper method to safely extract text content from XML"""
        element = tree.find(xpath)
        return element.text.strip() if element is not None and element.text else ''

    def _get_customer_name(self, customer_url):
        """Legacy method - kept for compatibility"""
        if not customer_url:
            return "Unknown"

        url = f"{customer_url}?ws_key={self.WS_KEY}"
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                tree = ET.fromstring(response.content)
                firstname = tree.find('.//firstname')
                lastname = tree.find('.//lastname')
                firstname_text = firstname.text if firstname is not None else ''
                lastname_text = lastname.text if lastname is not None else ''
                return f"{firstname_text} {lastname_text}".strip()
            else:
                _logger.warning("Failed to fetch customer data at %s (status %s)", url, response.status_code)
                return "Unknown"
        except Exception as e:
            _logger.exception("Exception fetching customer data from %s: %s", url, str(e))
            return "Unknown"
    '''

    API_BASE_URL = "https://www.premiumshop.ma/api"
    TOKEN = "E93WGT9K8726WW7F8CWIXDH9VGFBLH6A"

    @api.model
    def fetch_customer_data(self):
        _logger.info("Starting order data fetch...")

        # Get yesterday and today dates
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        tomorrow = today + timedelta(days=1)
        # Format dates for API filter
        date_filter = f"[{yesterday},{tomorrow}]"
        orders_url = f"{self.API_BASE_URL}/orders?filter[date_add]={date_filter}&date=1"

        try:
            _logger.info("Making API request to: %s", orders_url)

            # Use basic authentication with token as username
            response = requests.get(orders_url, auth=(self.TOKEN, ''))

            if response.status_code == 200:
                _logger.info("SUCCESS: API call successful!")

                root = ET.fromstring(response.content)
                orders = root.find('orders')
                if orders is None:
                    _logger.warning("No <orders> element found in response.")
                    return

                order_elements = orders.findall('order')
                _logger.info("Total orders found: %d", len(order_elements))

                for i, order in enumerate(order_elements):
                    order_id = order.get('id')
                    href = order.get('{http://www.w3.org/1999/xlink}href')

                    # Check if order already exists in Odoo
                    if self.env['stock.website.order'].search([('ticket_id', '=', order_id)], limit=1):
                        _logger.info("Skipping existing order ID=%s", order_id)
                        continue

                    _logger.info("New Order %s: ID=%s, URL=%s", i + 1, order_id, href)
                    self._fetch_and_log_order_details(order_id)

            else:
                _logger.error("FAILED: Status %s - %s", response.status_code, response.text)

        except requests.exceptions.Timeout:
            _logger.error("TIMEOUT: API request timed out")

        except requests.exceptions.ConnectionError:
            _logger.error("🔌 CONNECTION ERROR: Unable to reach API")

        except Exception as e:
            _logger.exception("EXCEPTION: %s", str(e))

        _logger.info("Order data fetch completed")

    def _fetch_and_log_order_details(self, order_id):
        order_url = f"{self.API_BASE_URL}/orders/{order_id}"
        try:
            # Use basic authentication here too
            response = requests.get(order_url, auth=(self.TOKEN, ''), timeout=30)
            if response.status_code == 200:
                tree = ET.fromstring(response.content)
                order = tree.find('order')

                customer_elem = order.find('id_customer')
                address_delivery_elem = order.find('id_address_delivery')

                customer_url = customer_elem.attrib.get('{http://www.w3.org/1999/xlink}href')
                address_delivery_url = address_delivery_elem.attrib.get('{http://www.w3.org/1999/xlink}href')

                customer_details = self._get_complete_customer_details(customer_url, address_delivery_url)

                # Get or create/update contact based on phone and email
                partner = self._find_or_create_partner(customer_details)

                # Order info
                date_commande_str = order.findtext('date_add', default='').strip()
                date_commande = datetime.strptime(date_commande_str,
                                                  '%Y-%m-%d %H:%M:%S').date() if date_commande_str else None
                reference = order.findtext('reference', default='').strip()
                payment = order.findtext('payment', default='').strip()
                if payment == "Paiement comptant à la livraison (Cash on delivery)":
                    payment = "COD"
                # Use PrestaShop data for order_rec, not Odoo partner data
                order_rec = self.env['stock.website.order'].create({
                    'ticket_id': order_id,
                    'reference': reference,
                    'client_name': f"{customer_details.get('firstname', '')} {customer_details.get('lastname', '')}".strip(),
                    'email': customer_details.get('email', ''),
                    'phone': customer_details.get('phone', ''),
                    'mobile': customer_details.get('phone_mobile', ''),
                    'adresse': customer_details.get('address1', ''),
                    'second_adresse': customer_details.get('address2', ''),
                    'city': customer_details.get('city', ''),
                    'postcode': customer_details.get('postcode', ''),
                    'pays': self.env['res.country'].search([('name', '=', customer_details.get('country'))],
                                                           limit=1) if customer_details.get('country') else False,
                    'date_commande': date_commande,
                    'payment_method': payment,
                })

                order_rows = order.findall('.//order_row')
                total_amount = 0

                for row in order_rows:
                    product_name = row.findtext('product_name', default='').strip()
                    product_reference = row.findtext('product_ean13', default='').strip()
                    quantity = row.findtext('product_quantity', default='0').strip()
                    price = row.findtext('product_price', default='0.00').strip()
                    unit_price_incl = row.findtext('unit_price_tax_incl', default='0.00').strip()
                    line_total = float(quantity) * float(unit_price_incl) if quantity and unit_price_incl else 0
                    total_amount += line_total

                    product = self.env['product.product'].search([('default_code', '=', product_reference)], limit=1)
                    if not product:
                        _logger.warning("No product found with reference: %s", product_reference)
                        continue

                    self.env['stock.website.order.line'].create({
                        'order_id': order_rec.id,
                        'product_id': product.id,
                        'code_barre': product_reference,
                        'product_name': product.name,
                        'quantity': float(quantity),
                        'discount': float(row.findtext('total_discounts', default='0.00')),
                        'price': float(price),
                    })

                total_paid = order.findtext('total_paid_tax_incl', default='0.00')
                payment_method = order.findtext('payment', default='')

                _logger.info("ORDER #%s Summary:", order_id)
                _logger.info("   Total Paid: %s MAD", total_paid)
                _logger.info("   Payment Method: %s", payment_method)
                _logger.info("=" * 80)

            else:
                _logger.error("Failed to fetch order details for %s, status code: %s", order_id, response.status_code)
        except Exception as e:
            _logger.exception("Exception fetching details for order %s: %s", order_id, str(e))

    def _get_complete_customer_details(self, customer_url, address_url):
        """Fetch complete customer details including address information"""
        customer_details = {}

        # Fetch customer basic info
        if customer_url:
            customer_data = self._fetch_api_data(customer_url)
            if customer_data:
                tree = ET.fromstring(customer_data)
                customer_details.update({
                    'firstname': self._get_text_content(tree, './/firstname'),
                    'lastname': self._get_text_content(tree, './/lastname'),
                    'email': self._get_text_content(tree, './/email'),
                })

        # Fetch address details
        if address_url:
            address_data = self._fetch_api_data(address_url)
            if address_data:
                tree = ET.fromstring(address_data)
                customer_details.update({
                    'phone': self._get_text_content(tree, './/phone'),
                    'phone_mobile': self._get_text_content(tree, './/phone_mobile'),
                    'company': self._get_text_content(tree, './/company'),
                    'address1': self._get_text_content(tree, './/address1'),
                    'address2': self._get_text_content(tree, './/address2'),
                    'city': self._get_text_content(tree, './/city'),
                    'postcode': self._get_text_content(tree, './/postcode'),
                })

                # Get country name if available
                country_elem = tree.find('.//id_country')
                if country_elem is not None:
                    country_url = country_elem.attrib.get('{http://www.w3.org/1999/xlink}href')
                    if country_url:
                        country_data = self._fetch_api_data(country_url)
                        if country_data:
                            country_tree = ET.fromstring(country_data)
                            country_name = self._get_text_content(country_tree, './/name')
                            customer_details['country'] = country_name

        return customer_details

    def _fetch_api_data(self, url):
        """Helper method to fetch data from API"""
        try:
            # Use basic authentication instead of ws_key
            response = requests.get(url, auth=(self.TOKEN, ''), timeout=30)
            if response.status_code == 200:
                return response.content
            else:
                _logger.warning("Failed to fetch data from %s (status %s)", url, response.status_code)
                return None
        except Exception as e:
            _logger.exception("Exception fetching data from %s: %s", url, str(e))
            return None

    def _get_customer_name(self, customer_url):
        """Legacy method - kept for compatibility"""
        if not customer_url:
            return "Unknown"

        try:
            # Use basic authentication
            response = requests.get(customer_url, auth=(self.TOKEN, ''), timeout=30)
            if response.status_code == 200:
                tree = ET.fromstring(response.content)
                firstname = tree.find('.//firstname')
                lastname = tree.find('.//lastname')
                firstname_text = firstname.text if firstname is not None else ''
                lastname_text = lastname.text if lastname is not None else ''
                return f"{firstname_text} {lastname_text}".strip()
            else:
                _logger.warning("Failed to fetch customer data at %s (status %s)", customer_url, response.status_code)
                return "Unknown"
        except Exception as e:
            _logger.exception("Exception fetching customer data from %s: %s", customer_url, str(e))
            return "Unknown"

    def _find_or_create_partner(self, customer_details):
        """Find existing partner or create/update based on phone and email matching"""
        email = customer_details.get('email', '').strip().lower()
        phone = customer_details.get('phone', '').strip()
        phone_mobile = customer_details.get('phone_mobile', '').strip()
        firstname = customer_details.get('firstname', '').strip()
        lastname = customer_details.get('lastname', '').strip()
        full_name = f"{firstname} {lastname}".strip()

        partner = None

        # Search for existing partner by phone (mobile or phone) and email
        search_domain = []
        if phone:
            search_domain.append(('phone', '=', phone))
        if phone_mobile:
            if search_domain:
                search_domain = ['|'] + search_domain + [('mobile', '=', phone_mobile)]
            else:
                search_domain.append(('mobile', '=', phone_mobile))

        if email:
            if search_domain:
                search_domain = ['&', ('email', '=', email)] + search_domain
            else:
                search_domain.append(('email', '=', email))

        if search_domain:
            partners = self.env['res.partner'].search(search_domain)

            # If multiple partners found, try to match by name (case insensitive)
            if len(partners) > 1 and full_name:
                for p in partners:
                    if p.name and p.name.lower() == full_name.lower():
                        partner = p
                        break
                # If no exact name match, take the first one
                if not partner:
                    partner = partners[0]
            elif len(partners) == 1:
                partner = partners[0]

        # Prepare partner values with ALL PrestaShop data
        country_id = False
        if customer_details.get('country'):
            country = self.env['res.country'].search([('name', '=', customer_details.get('country'))], limit=1)
            if country:
                country_id = country.id

        partner_vals = {
            'name': full_name,
            'email': email,
            'phone': phone,
            'mobile': phone_mobile,
            'company_name': customer_details.get('company', ''),
            'street': customer_details.get('address1', ''),
            'street2': customer_details.get('address2', ''),
            'city': customer_details.get('city', ''),
            'zip': customer_details.get('postcode', ''),
            'country_id': country_id,
        }

        if partner:
            # Always update existing partner with PrestaShop data (overwrite existing)
            old_address = partner.street
            partner.write(partner_vals)
            _logger.info("UPDATED existing partner: %s", partner.name)
            _logger.info("  - Old Address: '%s'", old_address or 'Empty')
            _logger.info("  - New Address: '%s'", customer_details.get('address1', ''))
            _logger.info("  - Email: %s", email)
            _logger.info("  - Phone: %s", phone)
            _logger.info("  - Mobile: %s", phone_mobile)
            _logger.info("  - Address2: %s", customer_details.get('address2', ''))
            _logger.info("  - City: %s", customer_details.get('city', ''))
            _logger.info("  - PostCode: %s", customer_details.get('postcode', ''))
            _logger.info("  - Country: %s", customer_details.get('country', ''))
        else:
            # Create new partner with all PrestaShop data
            partner = self.env['res.partner'].create(partner_vals)
            _logger.info("Created new partner: %s with all PrestaShop details", partner.name)

        return partner

    def _get_text_content(self, tree, xpath):
        """Helper method to safely extract text content from XML"""
        element = tree.find(xpath)
        return element.text.strip() if element is not None and element.text else ''
