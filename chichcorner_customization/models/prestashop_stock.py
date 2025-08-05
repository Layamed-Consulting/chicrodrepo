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
        """
        Cron job function that runs every 5 minutes to monitor stock changes
        This is the main entry point for the scheduled action
        """
        try:
            # Monitor stock move lines in the last 10 minutes
            affected_products = self.get_products_from_stock_move_lines(minutes_ago=10)

            if affected_products:
                # Trigger PrestaShop sync for affected products
                self.sync_affected_products_to_prestashop(affected_products)
            else:
                _logger.info("CRON: No products affected by stock moves in the last 10 minutes")

        except Exception as e:
            _logger.error(f"CRON: Error in stock change monitor: {e}")

        _logger.info("=== CRON: Stock Change Monitor Completed ===")
        return True

    @api.model
    def get_products_from_stock_move_lines(self, minutes_ago=10):
        """
        Get products affected by stock move lines in the last X minutes
        Returns list of products with their current stock quantities
        """
        # Calculate the time threshold
        time_threshold = datetime.now() - timedelta(minutes=minutes_ago)

        # Search for stock move lines that were updated in the last X minutes
        # We check both create_date and write_date to catch all changes
        recent_move_lines = self.env['stock.move.line'].search([
            '|',
            ('create_date', '>=', time_threshold),
            ('write_date', '>=', time_threshold),
            ('product_id.default_code', '!=', False),  # Only products with EAN13
            ('product_id.default_code', '!=', ''),
            ('state', '=', 'done'),  # Only confirmed moves
        ], order='write_date desc')

        if not recent_move_lines:
            _logger.info("No stock move lines found in the specified time period")
            return []
        # Get unique products from the move lines
        product_ids = set()
        for move_line in recent_move_lines:
            product_ids.add(move_line.product_id.id)

        # Get current stock quantities for these products
        affected_products = []
        for product_id in product_ids:
            product = self.env['product.product'].browse(product_id)
            if product and product.default_code:
                affected_products.append({
                    'id': product.id,
                    'name': product.name,
                    'ean13': product.default_code,
                    'qty_available': product.qty_available,
                    'write_date': product.write_date
                })
                _logger.info(
                    f"Product affected: {product.name} (EAN13: {product.default_code}) - Current Stock: {product.qty_available}")

        _logger.info(f"=== END STOCK MOVE LINES MONITOR - {len(affected_products)} products to sync ===")
        return affected_products

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
        """
        Sync specific products to PrestaShop that had stock changes
        """

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

        def search_and_update_combination_stock(ean13, new_quantity):
            """Search for combination by EAN13 and update its stock directly"""
            try:
                # Step 1: Search for combinations by EAN13
                search_url = f"{BASE_URL}/combinations?filter[ean13]={ean13}&display=full"
                _logger.info(f"Searching combinations: {search_url}")
                combinations_root = get_xml(search_url)

                if combinations_root is None:
                    _logger.warning(f"Failed to get combinations response for EAN13 {ean13}")
                    return False

                # Check if any combinations were found
                combinations = combinations_root.findall('.//combination')
                if not combinations:
                    _logger.warning(f"No combinations found for EAN13 {ean13}")
                    return False

                # Get the first combination
                combination = combinations[0]

                # Extract the combination ID
                combination_id_elem = combination.find('.//id')
                if combination_id_elem is None:
                    _logger.warning(f"No combination ID found for EAN13 {ean13}")
                    return False

                combination_id = combination_id_elem.text.strip()

                # Step 2: Get stock_available by combination ID
                stock_search_url = f"{BASE_URL}/stock_availables?filter[id_product_attribute]={combination_id}&display=full"
                stock_root = get_xml(stock_search_url)

                if stock_root is None:
                    _logger.warning(f"Failed to get stock_availables for combination ID {combination_id}")
                    return False

                # Find stock_available elements
                stock_availables = stock_root.findall('.//stock_available')
                if not stock_availables:
                    _logger.warning(f"No stock_availables found for combination ID {combination_id}")
                    return False

                updated_count = 0

                # Step 3: Update each stock_available
                for stock_available_elem in stock_availables:
                    stock_id_elem = stock_available_elem.find('.//id')
                    if stock_id_elem is None:
                        continue

                    stock_id = stock_id_elem.text.strip()

                    # Get current quantity for logging
                    current_qty_elem = stock_available_elem.find('.//quantity')
                    old_qty = current_qty_elem.text if current_qty_elem is not None else "unknown"

                    _logger.info(f"Updating stock_available ID {stock_id} for combination {combination_id}")

                    # Get the full stock_available details for update
                    stock_detail_url = f"{BASE_URL}/stock_availables/{stock_id}"
                    stock_detail = get_xml(stock_detail_url)

                    if stock_detail is None:
                        _logger.warning(f"Failed to get stock_available details for ID {stock_id}")
                        continue

                    stock_available_node = stock_detail.find('stock_available')
                    if stock_available_node is None:
                        continue

                    # Update quantity
                    quantity_node = stock_available_node.find('quantity')
                    if quantity_node is not None:
                        quantity_node.text = str(int(new_quantity))

                        # Prepare update XML
                        updated_doc = ET.Element('prestashop', xmlns_xlink="http://www.w3.org/1999/xlink")
                        updated_doc.append(stock_available_node)
                        updated_data = ET.tostring(updated_doc, encoding='utf-8', xml_declaration=True)

                        # Send update
                        response = put_xml(stock_detail_url, updated_data)

                        if response and response.status_code in (200, 201):
                            _logger.info(
                                f"✔ PRESTASHOP SYNC: Updated stock_available {stock_id} for EAN13 {ean13} (combination {combination_id}): {old_qty} → {int(new_quantity)}")
                            updated_count += 1
                        else:
                            _logger.warning(f"Failed to update stock_available {stock_id}")

                    # Small delay between updates
                    time.sleep(0.1)

                return updated_count > 0

            except Exception as e:
                _logger.error(f"Error processing combination for EAN13 {ean13}: {e}")
                return False

        sync_success = 0
        sync_failed = 0

        for product_info in products_list:
            try:
                ean13 = product_info['ean13']
                new_qty = product_info['qty_available']

                # Search for combination and update stock directly
                success = search_and_update_combination_stock(ean13, new_qty)

                if success:
                    sync_success += 1
                else:
                    _logger.warning(f"PRESTASHOP SYNC: Failed to update stock for EAN13 {ean13}")
                    sync_failed += 1

                # Small delay between products
                time.sleep(0.2)

            except Exception as e:
                _logger.error(f"PRESTASHOP SYNC: Error processing {product_info.get('ean13', 'unknown')}: {e}")
                sync_failed += 1

        return True