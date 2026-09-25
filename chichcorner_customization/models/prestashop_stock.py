from odoo import models, api, fields
import requests
from xml.etree import ElementTree as ET
import logging
import time
from datetime import datetime, timedelta
import base64

_logger = logging.getLogger(__name__)

class PrestashopStockCron(models.Model):
    _name = 'prestashop.stock.cron'
    _description = 'Cron job to update Prestashop stock'

    # Add field to track where we left off
    last_processed_index = fields.Integer(default=0, help="Last processed product index")
    '''
    @api.model
    def update_prestashop_stock_via_products(self):
        """Sync stock using products API to get EAN13 and stock_availables IDs"""
        BASE_URL = "https://www.premiumshop.ma/api"
        WS_KEY = "E93WGT9K8726WW7F8CWIXDH9VGFBLH6A"
        headers = {'Content-Type': 'application/xml'}

        # Get or create singleton record to track progress
        sync_record = self.search([], limit=1)
        if not sync_record:
            sync_record = self.create({'last_processed_index': 0})

        # Time limit: 90 seconds (30 seconds buffer before Odoo's 120s limit)
        start_time = time.time()
        TIME_LIMIT = 90

        def get_xml(url):
            try:
                resp = requests.get(url, timeout=30)
                if resp.status_code != 200:
                    _logger.warning(f"GET failed: {url} | Status: {resp.status_code}")
                    return None
                return ET.fromstring(resp.content)
            except Exception as e:
                _logger.warning(f"Exception during GET: {url} | Error: {e}")
                return None

        def put_xml(url, data):
            try:
                resp = requests.put(url, data=data, headers=headers, timeout=30)
                if resp.status_code not in (200, 201):
                    _logger.warning(f"PUT failed: {url} | Status: {resp.status_code}")
                    return None
                return resp
            except Exception as e:
                _logger.warning(f"Exception during PUT: {url} | Error: {e}")
                return None

        def get_products_with_pagination(start=0, limit=50):
            """Get products with pagination"""
            try:
                products_url = f"{BASE_URL}/products?ws_key={WS_KEY}&limit={start},{limit}"
                products_root = get_xml(products_url)

                if products_root is None:
                    return []

                product_ids = [prod.attrib['id'] for prod in products_root.findall('.//product')]
                return product_ids
            except Exception as e:
                _logger.error(f"Error getting products: {e}")
                return []

        # Start processing
        _logger.info("=== Starting PrestaShop Stock Sync via Products API ===")
        _logger.info(f"Resuming from index: {sync_record.last_processed_index}")

        processed_count = 0
        updated_count = 0
        not_found_in_odoo_count = 0
        error_count = 0

        # Process products in batches
        batch_size = 20  # Small batch size to avoid timeouts
        start_index = sync_record.last_processed_index  # Resume from where we left off

        while True:
            # Check time limit
            if time.time() - start_time > TIME_LIMIT:
                _logger.info(f"Time limit reached. Saving progress at index {start_index}")
                sync_record.last_processed_index = start_index
                break

            # Get batch of product IDs
            product_ids = get_products_with_pagination(start_index, batch_size)

            if not product_ids:
                _logger.info("No more products to process - SYNC COMPLETED!")
                sync_record.last_processed_index = 0  # Reset for next full sync
                break

            _logger.info(f"Processing batch: products {start_index} to {start_index + len(product_ids)}")

            for product_id in product_ids:
                try:
                    # Get product details including EAN13 and stock_availables
                    product_url = f"{BASE_URL}/products/{product_id}?ws_key={WS_KEY}"
                    product_detail = get_xml(product_url)

                    if product_detail is None:
                        error_count += 1
                        continue

                    # Extract EAN13
                    ean13_node = product_detail.find('.//ean13')
                    if ean13_node is None or not ean13_node.text:
                        _logger.info(f"Product {product_id}: No EAN13 found, skipping")
                        processed_count += 1
                        continue

                    ean13 = ean13_node.text.strip()
                    if not ean13:
                        _logger.info(f"Product {product_id}: Empty EAN13, skipping")
                        processed_count += 1
                        continue

                    _logger.info(f"Processing PrestaShop Product {product_id} | EAN13: {ean13}")

                    # Search for this EAN13 in Odoo
                    odoo_product = self.env['product.product'].search([('default_code', '=', ean13)], limit=1)

                    if not odoo_product:
                        _logger.info(f"EAN13 {ean13}: not found in Odoo, skipping")
                        not_found_in_odoo_count += 1
                        processed_count += 1
                        continue

                    odoo_qty = odoo_product.qty_available
                    _logger.info(f"EAN13 {ean13}: found in Odoo with quantity {odoo_qty}")

                    # Get stock_availables from the product XML
                    stock_availables = product_detail.findall('.//associations/stock_availables/stock_available')

                    if not stock_availables:
                        _logger.warning(f"Product {product_id}: No stock_availables found")
                        error_count += 1
                        processed_count += 1
                        continue

                    # Process each stock_available for this product
                    product_updated = False
                    for stock_available_elem in stock_availables:
                        stock_id_node = stock_available_elem.find('id')
                        if stock_id_node is None:
                            continue

                        stock_id = stock_id_node.text
                        _logger.info(f"Updating stock_available ID: {stock_id}")

                        # Get current stock_available details
                        stock_url = f"{BASE_URL}/stock_availables/{stock_id}?ws_key={WS_KEY}"
                        stock_detail = get_xml(stock_url)

                        if stock_detail is None:
                            _logger.warning(f"Failed to get stock_available {stock_id}")
                            continue

                        stock_available_node = stock_detail.find('stock_available')
                        if stock_available_node is None:
                            continue

                        # Update quantity
                        quantity_node = stock_available_node.find('quantity')
                        if quantity_node is not None:
                            old_qty = quantity_node.text
                            quantity_node.text = str(int(odoo_qty))

                            # Prepare update XML
                            updated_doc = ET.Element('prestashop', xmlns_xlink="http://www.w3.org/1999/xlink")
                            updated_doc.append(stock_available_node)
                            updated_data = ET.tostring(updated_doc, encoding='utf-8', xml_declaration=True)

                            # Send update
                            response = put_xml(stock_url, updated_data)

                            if response and response.status_code in (200, 201):
                                _logger.info(
                                    f"✔ Updated stock {stock_id} for EAN13 {ean13}: {old_qty} → {int(odoo_qty)}")
                                product_updated = True
                            else:
                                _logger.warning(f"Failed to update stock {stock_id} for EAN13 {ean13}")

                    if product_updated:
                        updated_count += 1

                    processed_count += 1

                    # Small delay to avoid overwhelming the API
                    time.sleep(0.1)

                except Exception as e:
                    _logger.error(f"Error processing product {product_id}: {e}")
                    error_count += 1
                    processed_count += 1
                    continue

            # Move to next batch
            start_index += batch_size

            # Add delay between batches
            time.sleep(0.5)

        # Final summary
        _logger.info("=== SYNC SUMMARY ===")
        _logger.info(f"Total processed this run: {processed_count}")
        _logger.info(f"Successfully updated: {updated_count}")
        _logger.info(f"Not found in Odoo: {not_found_in_odoo_count}")
        _logger.info(f"Errors: {error_count}")
        _logger.info(f"Next run will start from index: {sync_record.last_processed_index}")
        _logger.info("=== END SYNC ===")

        return True

    @api.model
    def update_prestashop_stock(self):
        """Main method - calls the products API sync"""
        return self.update_prestashop_stock_via_products()
    '''

    @api.model
    def update_prestashop_stock_via_ean13_filter(self):
        """Sync stock using EAN13 filter - only process products that exist in Odoo"""
        BASE_URL = "https://www.premiumshop.ma/api"
        WS_KEY = "E93WGT9K8726WW7F8CWIXDH9VGFBLH6A"

        # Create basic auth header
        auth_string = f"{WS_KEY}:"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        headers = {
            'Authorization': f'Basic {auth_b64}',
            'Content-Type': 'application/xml'
        }

        # Get or create singleton record to track progress
        sync_record = self.search([], limit=1)
        if not sync_record:
            sync_record = self.create({'last_processed_odoo_id': 0})

        # Time limit: 90 seconds (30 seconds buffer before Odoo's 120s limit)
        start_time = time.time()
        TIME_LIMIT = 90

        def get_xml(url):
            try:
                resp = requests.get(url, headers=headers, timeout=30)
                if resp.status_code != 200:
                    _logger.warning(f"GET failed: {url} | Status: {resp.status_code}")
                    return None
                return ET.fromstring(resp.content)
            except Exception as e:
                _logger.warning(f"Exception during GET: {url} | Error: {e}")
                return None

        def put_xml(url, data):
            try:
                resp = requests.put(url, data=data, headers=headers, timeout=30)
                if resp.status_code not in (200, 201):
                    _logger.warning(f"PUT failed: {url} | Status: {resp.status_code}")
                    return None
                return resp
            except Exception as e:
                _logger.warning(f"Exception during PUT: {url} | Error: {e}")
                return None

        def search_prestashop_product_by_ean13(ean13):
            """Search for a product in PrestaShop by EAN13"""
            try:
                search_url = f"{BASE_URL}/products?filter[ean13]={ean13}&display=full"
                products_root = get_xml(search_url)

                if products_root is None:
                    return None

                # Check if any products were found
                products = products_root.findall('.//product')
                if not products:
                    return None

                # Return the first product found
                return products[0]
            except Exception as e:
                _logger.error(f"Error searching for EAN13 {ean13}: {e}")
                return None

        def update_stock_availables(product_element, new_quantity):
            """Update all stock_availables for a product"""
            updated_count = 0

            try:
                # Find all stock_available elements
                stock_availables = product_element.findall('.//associations/stock_availables/stock_available')

                if not stock_availables:
                    _logger.warning("No stock_availables found in product")
                    return 0

                for stock_available_elem in stock_availables:
                    stock_id_node = stock_available_elem.find('id')
                    if stock_id_node is None:
                        continue

                    stock_id = stock_id_node.text
                    _logger.info(f"Updating stock_available ID: {stock_id}")

                    # Get current stock_available details
                    stock_url = f"{BASE_URL}/stock_availables/{stock_id}"
                    stock_detail = get_xml(stock_url)

                    if stock_detail is None:
                        _logger.warning(f"Failed to get stock_available {stock_id}")
                        continue

                    stock_available_node = stock_detail.find('stock_available')
                    if stock_available_node is None:
                        continue

                    # Update quantity
                    quantity_node = stock_available_node.find('quantity')
                    if quantity_node is not None:
                        old_qty = quantity_node.text
                        quantity_node.text = str(int(new_quantity))

                        # Prepare update XML
                        updated_doc = ET.Element('prestashop', xmlns_xlink="http://www.w3.org/1999/xlink")
                        updated_doc.append(stock_available_node)
                        updated_data = ET.tostring(updated_doc, encoding='utf-8', xml_declaration=True)

                        # Send update
                        response = put_xml(stock_url, updated_data)

                        if response and response.status_code in (200, 201):
                            _logger.info(f"✔ Updated stock {stock_id}: {old_qty} → {int(new_quantity)}")
                            updated_count += 1
                        else:
                            _logger.warning(f"Failed to update stock {stock_id}")

                    # Small delay between stock updates
                    time.sleep(0.1)

            except Exception as e:
                _logger.error(f"Error updating stock_availables: {e}")

            return updated_count

        # Start processing
        _logger.info("=== Starting PrestaShop Stock Sync via EAN13 Filter ===")
        _logger.info(f"Resuming from Odoo product ID: {sync_record.last_processed_odoo_id}")

        processed_count = 0
        updated_count = 0
        not_found_in_prestashop_count = 0
        error_count = 0

        # Get Odoo products with EAN13 (default_code) starting from last processed ID
        batch_size = 10  # Smaller batch size for better performance

        while True:
            # Check time limit
            if time.time() - start_time > TIME_LIMIT:
                _logger.info(f"Time limit reached. Saving progress at Odoo ID {sync_record.last_processed_odoo_id}")
                break

            # Get batch of Odoo products with EAN13
            odoo_products = self.env['product.product'].search([
                ('default_code', '!=', False),
                ('default_code', '!=', ''),
                ('id', '>', sync_record.last_processed_odoo_id)
            ], limit=batch_size, order='id asc')

            if not odoo_products:
                _logger.info("No more Odoo products to process - SYNC COMPLETED!")
                sync_record.last_processed_odoo_id = 0  # Reset for next full sync
                break

            _logger.info(f"Processing batch of {len(odoo_products)} Odoo products")

            for odoo_product in odoo_products:
                try:
                    ean13 = odoo_product.default_code.strip()
                    odoo_qty = odoo_product.qty_available

                    _logger.info(f"Processing Odoo Product ID {odoo_product.id} | EAN13: {ean13} | Qty: {odoo_qty}")

                    # Search for this product in PrestaShop
                    prestashop_product = search_prestashop_product_by_ean13(ean13)

                    if prestashop_product is None:
                        _logger.info(f"EAN13 {ean13}: not found in PrestaShop, skipping")
                        not_found_in_prestashop_count += 1
                        processed_count += 1
                        sync_record.last_processed_odoo_id = odoo_product.id
                        continue

                    # Extract PrestaShop product ID for logging
                    prestashop_id_node = prestashop_product.find('id')
                    prestashop_id = prestashop_id_node.text if prestashop_id_node is not None else 'Unknown'

                    _logger.info(f"Found PrestaShop Product ID: {prestashop_id}")

                    # Update all stock_availables for this product
                    stock_updates = update_stock_availables(prestashop_product, odoo_qty)

                    if stock_updates > 0:
                        updated_count += 1
                        _logger.info(f"✔ Successfully updated {stock_updates} stock_availables for EAN13 {ean13}")
                    else:
                        _logger.warning(f"No stock_availables were updated for EAN13 {ean13}")

                    processed_count += 1
                    sync_record.last_processed_odoo_id = odoo_product.id

                    # Small delay between products
                    time.sleep(0.2)

                except Exception as e:
                    _logger.error(f"Error processing Odoo product {odoo_product.id}: {e}")
                    error_count += 1
                    processed_count += 1
                    sync_record.last_processed_odoo_id = odoo_product.id
                    continue

            # Add delay between batches
            time.sleep(0.5)

        # Final summary
        _logger.info("=== SYNC SUMMARY ===")
        _logger.info(f"Total processed this run: {processed_count}")
        _logger.info(f"Successfully updated: {updated_count}")
        _logger.info(f"Not found in PrestaShop: {not_found_in_prestashop_count}")
        _logger.info(f"Errors: {error_count}")
        _logger.info(f"Next run will start from Odoo ID: {sync_record.last_processed_odoo_id}")
        _logger.info("=== END SYNC ===")

        return True

    @api.model
    def update_prestashop_stock(self):
        """Main method - calls the EAN13 filter sync"""
        return self.update_prestashop_stock_via_ean13_filter()

    @api.model
    def reset_sync_progress(self):
        """Reset the sync progress to start from the beginning"""
        sync_record = self.search([], limit=1)
        if sync_record:
            sync_record.last_processed_odoo_id = 0
        _logger.info("Sync progress has been reset")
        return True

    '''added'''

    @api.model
    def cron_monitor_stock_changes(self):
        """Monitor stock changes and sync to PrestaShop"""
        _logger.info("=== CRON: Stock Monitor Started ===")

        try:
            affected_products = self.get_products_from_stock_move_lines()
            if affected_products:
                _logger.info(f"CRON: {len(affected_products)} products to sync")
                self.sync_affected_products_to_prestashop(affected_products)
            else:
                _logger.info("CRON: No products to sync")
        except Exception as e:
            _logger.error(f"CRON Error: {e}")

        _logger.info("=== CRON: Stock Monitor Completed ===")
        return True

    @api.model
    def get_products_from_stock_move_lines(self, minutes_ago=5):
        """Get products affected by stock moves in last X minutes"""
        time_threshold = datetime.now() - timedelta(minutes=minutes_ago)
        time_threshold2 = datetime.now() + timedelta(minutes=minutes_ago)

        _logger.info(f"=== CRON: Start from : {time_threshold} to {time_threshold2}")
        # Find recent stock move lines
        recent_move_lines = self.env['stock.move.line'].search([
            '|', ('create_date', '>=', time_threshold), ('write_date', '>=', time_threshold),
            ('product_id.default_code', '!=', False),
            ('product_id.default_code', '!=', ''),
            ('state', '=', 'done'),
        ])

        if not recent_move_lines:
            return []

        # Get unique products
        product_ids = list(set(line.product_id.id for line in recent_move_lines))
        products = self.env['product.product'].browse(product_ids)

        # Return product data
        return [{
            'id': p.id,
            'name': p.name,
            'ean13': p.default_code,
            'qty_available': p.qty_available,
        } for p in products if p.default_code]

    @api.model
    def log_stock_move_lines_for_product(self, ean13, minutes_ago=10):
        """
        Log stock move lines for a specific product by EAN13
        """
        time_threshold = datetime.now() - timedelta(minutes=minutes_ago)

        # Find the product
        product = self.env['product.product'].search([
            ('default_code', '=', ean13)
        ], limit=1)

        if not product:
            _logger.info(f"Product with EAN13 {ean13} not found")
            return False

        # Check recent move lines for this product
        recent_move_lines = self.env['stock.move.line'].search([
            ('product_id', '=', product.id),
            '|',
            ('create_date', '>=', time_threshold),
            ('write_date', '>=', time_threshold),
        ], order='write_date desc')

        if recent_move_lines:
            for move_line in recent_move_lines:
                _logger.info(
                    f"  - Qty: {move_line.qty_done} | {move_line.location_id.name} → {move_line.location_dest_id.name}")
                _logger.info(f"    Date: {move_line.write_date} | State: {move_line.state}")
        else:
            _logger.info("No recent move lines found for this product")

        return True

    @api.model
    def sync_affected_products_to_prestashop(self, products_list):
        """Sync products to PrestaShop, then deactivate any parent product
        whose combinations are all at 0 (no automatic reactivation)."""
        BASE_URL = "https://www.premiumshop.ma/api"
        WS_KEY = "E93WGT9K8726WW7F8CWIXDH9VGFBLH6A"

        # Auth header
        auth_b64 = base64.b64encode(f"{WS_KEY}:".encode()).decode()
        headers = {'Authorization': f'Basic {auth_b64}', 'Content-Type': 'application/xml'}

        def api_request(method, url, data=None):
            try:
                resp = requests.request(method, url, headers=headers, data=data, timeout=50)
                if resp.status_code in (200, 201):
                    return ET.fromstring(resp.content)
                else:
                    _logger.warning(
                        f"API request FAILED [{method} {url}] status={resp.status_code} "
                        f"body={resp.content[:1000]!r}"
                    )
                    return None
            except Exception as e:
                _logger.warning(f"API request exception [{method} {url}]: {e}", exc_info=True)
                return None

        def update_stock(ean13, new_qty):
            """Update stock for EAN13, return the PrestaShop id_product it belongs to (or None)"""
            # Search combinations
            search_url = f"{BASE_URL}/combinations?filter[ean13]={ean13}&display=full"
            combinations_root = api_request('GET', search_url)

            if not combinations_root:
                return None

            combinations = combinations_root.findall('.//combination')
            if not combinations:
                return None

            combination_id = combinations[0].find('.//id').text.strip()

            id_product_node = combinations[0].find('.//id_product')
            id_product = id_product_node.text.strip() if id_product_node is not None else None

            # Get stock_available
            stock_url = f"{BASE_URL}/stock_availables?filter[id_product_attribute]={combination_id}&display=full"
            stock_root = api_request('GET', stock_url)

            if not stock_root:
                return id_product

            stock_availables = stock_root.findall('.//stock_available')
            if not stock_availables:
                return id_product

            # Update each stock_available
            updated = False
            for stock_elem in stock_availables:
                stock_id = stock_elem.find('.//id').text.strip()

                # Get full details and update
                detail_url = f"{BASE_URL}/stock_availables/{stock_id}"
                detail = api_request('GET', detail_url)

                if detail:
                    stock_node = detail.find('stock_available')
                    qty_node = stock_node.find('quantity')
                    if qty_node is not None:
                        qty_node.text = str(int(new_qty))

                        # Prepare XML
                        updated_doc = ET.Element('prestashop', xmlns_xlink="http://www.w3.org/1999/xlink")
                        updated_doc.append(stock_node)
                        xml_data = ET.tostring(updated_doc, encoding='utf-8', xml_declaration=True)

                        # Send update
                        if api_request('PUT', detail_url, xml_data):
                            _logger.info(f"✔ Updated stock for EAN13 {ean13}: {new_qty}")
                            updated = True

                time.sleep(0.1)  # Small delay

            return id_product if updated else id_product

        def get_total_quantity_for_product(id_product):
            """Get total quantity for a product: sum every <quantity> value
            returned by stock_availables?filter[id_product]=X"""
            url = f"{BASE_URL}/stock_availables?filter[id_product]={id_product}&display=full"
            _logger.info(f"STEP2: fetching stock_availables for id_product={id_product} -> {url}")
            root = api_request('GET', url)
            if not root:
                _logger.warning(f"STEP2: no response / failed to parse XML for id_product={id_product}")
                return None

            total = 0
            found_any = False
            for qty_node in root.findall('.//quantity'):
                if qty_node.text is not None:
                    found_any = True
                    total += int(qty_node.text.strip())

            _logger.info(f"STEP2: id_product={id_product} total_quantity={total if found_any else 'N/A'}")
            return total if found_any else None

        def set_product_active_state(id_product, active):
            """Set the 'active' flag on a PrestaShop product.
            - Skips the PUT if the product already has the expected value.
            - Keeps the FULL root document returned by GET, mutates only the
              target node in place, and PUTs the whole tree back, except for
              a few fields PrestaShop's webservice rejects on write.
            - If the PUT returns an error (often HTTP 500 caused by PHP 8.2
              deprecation notices even though the write succeeded), verifies
              the real state with a GET before reporting failure."""
            detail_url = f"{BASE_URL}/products/{id_product}"
            expected = '1' if active else '0'

            _logger.info(f"STEP2: fetching product detail for id_product={id_product}")
            root = api_request('GET', detail_url)
            if root is None:
                _logger.warning(f"STEP2: failed to GET product {id_product} before update")
                return False

            product_node = root.find('.//product')
            if product_node is None:
                _logger.warning(f"STEP2: no <product> node found for id_product={id_product}")
                return False

            # Already in the expected state -> nothing to do
            active_node = product_node.find('active')
            if active_node is not None and (active_node.text or '').strip() == expected:
                _logger.info(f"STEP2: product {id_product} already active={active}, nothing to do")
                return True

            # Fields PrestaShop rejects on PUT for this shop (error 93 / error 135)
            for tag in ('manufacturer_name', 'position_in_category', 'quantity'):
                node = product_node.find(tag)
                if node is not None:
                    product_node.remove(node)

            if active_node is None:
                active_node = ET.SubElement(product_node, 'active')
            active_node.text = expected

            updated_xml = ET.tostring(root, encoding='utf-8', method='xml')

            result = api_request('PUT', detail_url, updated_xml)
            if result is not None:
                _logger.info(f"STEP2: PUT product {id_product} active={active} -> OK")
                return True

            # PUT returned an error -> check the real state on PrestaShop
            verify_root = api_request('GET', detail_url)
            if verify_root is not None:
                verify_node = verify_root.find('.//product/active')
                if verify_node is not None and (verify_node.text or '').strip() == expected:
                    _logger.info(
                        f"STEP2: PUT product {id_product} returned an error but "
                        f"active={active} is confirmed on PrestaShop -> OK"
                    )
                    return True

            _logger.warning(f"STEP2: PUT product {id_product} active={active} -> FAILED")
            return False

        # --- Step 1: update stock for every combination, collect touched products ---
        success_count = 0
        touched_product_ids = set()

        for product in products_list:
            try:
                id_product = update_stock(product['ean13'], product['qty_available'])
                if id_product:
                    success_count += 1
                    touched_product_ids.add(id_product)
                time.sleep(0.2)
            except Exception as e:
                _logger.error(f"Error syncing {product.get('ean13')}: {e}", exc_info=True)

        _logger.info(f"SYNC SUMMARY: {success_count}/{len(products_list)} products synced")
        _logger.info(f"STEP2: products to check for deactivation: {touched_product_ids}")

        # --- Step 2: for each touched parent product, deactivate if total stock is 0 ---
        # (no auto-reactivation here — reactivating a product is left manual)
        for id_product in touched_product_ids:
            try:
                total_qty = get_total_quantity_for_product(id_product)
                if total_qty is None:
                    _logger.warning(f"STEP2: could not determine quantity for id_product={id_product}, skipping")
                    continue

                if total_qty <= 0:
                    set_product_active_state(id_product, active=False)
                else:
                    _logger.info(f"STEP2: id_product={id_product} still has stock ({total_qty}), leaving active")
            except Exception as e:
                _logger.error(f"STEP2: error checking/deactivating product {id_product}: {e}", exc_info=True)

        return True