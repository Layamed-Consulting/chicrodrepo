from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import requests
import json
import xml.etree.ElementTree as ET
_logger = logging.getLogger(__name__)

class WebsiteOrder(models.Model):
    _name = 'stock.website.order'
    _description = 'Stock Website Order Synced from API'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    ticket_id = fields.Char(string="Id Commande", required=True, unique=True)
    reference = fields.Char(string="Référence de la commande")
    payment_method = fields.Char(string="Mode de Paiement")
    store_id = fields.Integer(string="Store ID")
    client_name = fields.Char(string="Nom du Client")
    date_commande = fields.Date(string="Date de Commande")
    line_ids = fields.One2many('stock.website.order.line', 'order_id', string="Lignes de Commande")
    email = fields.Char(string="Email")
    phone = fields.Char(string="Phone")
    mobile = fields.Char(string="Mobile")
    adresse = fields.Char(string="Adresse 1")
    second_adresse = fields.Char(string="Adresse 2")
    city = fields.Char(string="Ville")
    postcode = fields.Char(string="Postcode")
    pays= fields.Char(string="Pays")
    status = fields.Selection([
        ('initial', 'Initial'),
        ('prepare', 'Préparé'),
        ('delivered', 'Livré'),
        ('en_cours_preparation', 'En cours de préparation'),
        ('encourdelivraison', 'En cours de Livraison'),
        ('annuler', 'Annulé'),
    ], string="Statut", default='initial')
    pos_order_id = fields.Many2one('pos.order', string="POS Order")
    '''added 07/07/2025'''
    colis_created = fields.Boolean(string="Colis Created", default=False, help="Indicates if colis have been created via SendIt API")
    colis_codes = fields.Text(string="Colis Codes", help="Store colis codes from SendIt API (JSON format)")
    label_url = fields.Char(string="Imprimer étiquette", help="URL of the generated labels PDF")
    '''
    def action_send_to_pos(self):
        for order in self:
            if not order.line_ids:
                raise UserError("Cette commande n'a pas de lignes de commande.")
            if order.pos_order_id:
                raise UserError("Cette commande a déjà été traité.")

            self._update_order_lines_with_warehouse_info(order)
            # Group lines by warehouse/stock location
            warehouse_groups = self._group_lines_by_warehouse(order)

            if not warehouse_groups:
                raise UserError("Aucun produit en stock trouvé pour cette commande.")

            created_pos_orders = []

            # Create separate POS orders for each warehouse
            for warehouse, lines_data in warehouse_groups.items():
                try:
                    pos_order = self._create_pos_order_for_warehouse(order, warehouse, lines_data)
                    created_pos_orders.append(pos_order)
                except Exception as e:
                    # If there's an error, clean up already created orders
                    for created_order in created_pos_orders:
                        created_order.unlink()
                    raise UserError(f"Erreur lors de la création de la commande POS pour {warehouse.name}: {str(e)}")

            # Update order status and link to the first POS order (or you could link to all)
            order.status = 'en_cours_preparation'
            if created_pos_orders:
                order.pos_order_id = created_pos_orders[0].id

            # Create success message with details of all created orders
            message_parts = []
            for pos_order in created_pos_orders:
                warehouse_name = pos_order.config_id.name
                message_parts.append(f"- {warehouse_name}")

            success_message = f"Commande {order.ticket_id} divisée et envoyée vers {len(created_pos_orders)} POS:\n" + "\n".join(
                message_parts)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Succès',
                    'message': success_message,
                    'type': 'success',
                }
            }
'''
    API_BASE_URL = "https://www.premiumshop.ma/api"
    WS_KEY = "E93WGT9K8726WW7F8CWIXDH9VGFBLH6A"
    '''added in 07/07/2025'''
    def _check_and_update_order_status(self):
        """Check if all order lines are cancelled and update order status accordingly"""
        for order in self:
            if order.line_ids:
                # Check if all lines have status 'annuler'
                all_cancelled = all(line.status_ligne_commande == 'annuler' for line in order.line_ids)

                if all_cancelled and order.status != 'annuler':
                    order.status = 'annuler'
                    # Log the change in chatter
                    order.message_post(
                        body="Statut de la commande automatiquement mis à jour vers 'Annuler' car toutes les lignes de commande sont annulées.",
                        message_type='notification'
                    )

    def action_create_colis(self):
        # Check if colis already created
        if self.colis_created:
            raise UserError("Les colis ont déjà été créés pour cette commande.")

        # Check if order has lines
        if not self.line_ids:
            raise UserError("Aucune ligne de commande trouvée.")

        # Get unique colis numbers from order lines (excluding cancelled ones)
        active_lines = self.line_ids.filtered(lambda l: l.status_ligne_commande != 'annuler')
        colis_numbers = list(set(active_lines.mapped('numero_colis')))
        colis_numbers = [num for num in colis_numbers if num and num > 0]

        if not colis_numbers:
            raise UserError("Aucun numéro de colis trouvé dans les lignes de commande actives (non annulées).")

        # Liste ville
        city_codes = {
            1: "Casablanca", 38: "Bouskoura-Centre", 39: "Errahma", 40: "Dar Bouaza", 41: "Mohamadia",
            42: "Berrechid", 43: "Settat", 44: "Mediouna", 45: "Nouacer", 47: "Had Soualem",
            49: "Bouznika", 51: "Sidi rahal", 52: "Tanger", 53: "Rabat", 54: "Agadir", 55: "El jadida",
            56: "Marrakech", 57: "Ahfir", 58: "Ain Harrouda", 60: "Al Aaroui", 61: "Al Hoceima",
            63: "Beni Ensar", 64: "Benslimane", 65: "Berkane", 66: "Biougra", 68: "Chellalat Mohammedia",
            69: "Fnideq", 70: "Khemisset", 71: "Martil", 72: "Nador", 73: "Oujda", 76: "Selouane",
            81: "Taza", 86: "Ain El Aouda", 87: "Ain Attig", 94: "Ain Taoujdate", 96: "Ait Melloul",
            100: "Anza", 102: "Arfoud", 104: "Assilah", 105: "Azemmour", 106: "Azilal", 107: "Azrou",
            108: "Bab Berred", 110: "Bejaad", 111: "Belfaa", 113: "Benguerir", 115: "Beni Mellal",
            118: "Boujdour", 119: "Boujniba", 122: "Chefchaouen", 123: "Chichaoua", 124: "Dakhla",
            126: "Demnate", 130: "Drarga", 132: "Haj Kaddour", 133: "El Kelaa Des Sraghna", 135: "Er-Rich",
            136: "Errachidia", 137: "Essaouira", 139: "Fes", 141: "Fquih Ben Salah", 142: "Guelmim",
            143: "Guercif", 145: "Ifran", 147: "Imouzzer du Kandar", 148: "Inzegane", 149: "Jamaat Shaim",
            153: "Kasba Tadla", 154: "Kelaat M'Gouna", 155: "Kenitra", 156: "Khemis Des Zemamra",
            157: "Khenifra", 158: "Khouribga", 159: "Ksar El Kebir", 161: "Laattaouia", 162: "La2youne",
            164: "Laarache", 165: "Mdiq", 167: "Meknes", 168: "Merzouga", 170: "Midelt", 172: "Moulay Abdellah",
            174: "Moulay Idriss zerhouni", 175: "Mrirt", 177: "Ouarzazate", 180: "Oued Zem", 181: "Oulad Teima",
            186: "Rissani", 188: "Safi", 189: "Saidia", 190: "Sale", 191: "Sala El Jadida", 192: "Sebt El Guerdane",
            193: "Sebt Gzoula", 195: "Sebt Oulad Nemma", 196: "Sefrou", 198: "Sidi Addi", 200: "Sidi Allal El Bahraoui",
            201: "Sidi Bennour", 202: "Sidi Bibi", 203: "Sidi Bouzid", 204: "Sidi Ifni", 205: "Sidi Kacem",
            206: "Sidi Slimane", 208: "Skhirat", 209: "Souk El Arbaa Du Gharb", 211: "Tamansourt", 212: "Tamesna",
            214: "Tan-Tan", 215: "Taounate", 216: "Taourirt", 218: "Taroudant", 220: "Temara", 222: "Tetouan",
            223: "Tiflet", 224: "Tinghir", 225: "Tit Melil", 226: "Tiznit", 228: "Youssoufia", 229: "Zagoura",
            232: "Zaouiat Cheikh", 233: "Sidi Bouknadel", 253: "Boufakrane", 255: "Goulmima", 257: "El Hajeb",
            260: "Ksar Sghir", 261: "Deroua", 262: "Sidi Hrazem", 263: "Oulad Tayeb", 264: "Skhinate",
            265: "Mejat", 266: "Ouislane", 268: "Ain chkaf", 269: "zaer", 270: "Sidi Yahya El Gharb",
            271: "Bounoir", 272: "Hettan", 273: "Bni yakhlef", 274: "Sidi Hajjaj", 275: "Ben Ahmed",
            276: "Dar Essalam", 278: "Tssoultante", 279: "Tameslouht", 280: "Chwiter", 282: "Souihla",
            283: "Ouled Hassoune", 284: "Sidi Moussa", 285: "Lahbichat", 286: "Sidi Abdellah Ghiyat",
            287: "Douar Lahna", 288: "Tamellalt", 290: "Echemmaia", 291: "Skoura", 292: "Taznakht",
            293: "Agds", 294: "Tikiwin", 295: "Temsia", 296: "Ait Amira", 297: "Chtouka", 303: "Essemara",
            304: "Zeghanghane", 307: "Oualidia", 308: "Talmest", 309: "Ounagha", 310: "Souira Guedima",
            311: "Tlat Bouguedra", 313: "Sakia El hamra", 314: "Ain-Cheggag", 315: "Moulay Yaakoub",
            316: "Saiss", 317: "Mechra Bel Ksiri", 318: "El Gara", 319: "Tinejdad", 320: "Agourai",
            322: "Tata", 323: "Ouazzane", 324: "Boumalen dades", 325: "Jerada", 326: "Tamaris",
            327: "Zaida", 328: "Boumia", 329: "Missour", 330: "Aoufous", 331: "Ait Aissa Ou Brahim",
            332: "Tarzout", 333: "Alnif", 334: "Ait Sedrate Sahl Gharbia", 336: "Ayt Ihya", 337: "Zaio",
            338: "Aklim", 339: "el aioun charqiya", 340: "Ain-Bni-Mathar", 341: "Jorf El Melha",
            343: "Khenichet", 344: "El Ksiba", 347: "Oued Amlil", 349: "Aknoul", 351: "Tizi Ouasli",
            352: "El Mansouria", 353: "Oued laou", 354: "Boulman", 355: "Ait ourir", 356: "Ourika",
            357: "Imzouren", 358: "Tahla", 362: "Bab Taza", 364: "Tahanaout", 365: "Mers El Kheir",
            366: "Harhoura", 367: "Mehdia", 368: "Moulay Bousselham", 371: "El Aarjate", 372: "Oulmas",
            374: "Aourir", 375: "Loudaya", 376: "Tarast", 377: "Leqliaa", 378: "Dcheira El Jihadia",
            379: "Aoulouz", 380: "Ait Aiaaza", 381: "Ghazoua", 382: "Ghafsai", 383: "Gueznaia",
            384: "Sidi Hssain", 385: "Mnar", 386: "Jebila", 387: "Khandagour", 388: "Laaouamera",
            389: "Cabo Negro", 390: "Rencon", 391: "Lagfifat", 392: "Massa", 393: "Oulad Berhil",
            394: "Taliouine", 395: "Oulad Yaich", 396: "Ighrem", 397: "Tagzirt", 398: "Oulad Youssef",
            400: "Oulad Ali", 401: "Oulad Zmam", 402: "Sidi Jaber", 403: "Souk Sebt", 404: "Dar Ould Zidouh",
            405: "Oulad Ayad", 406: "Sidi Aissa", 407: "Oulad M'barek", 408: "Afourar", 409: "Timoulilt",
            410: "Beni Ayat", 411: "Ouaouizeght", 412: "Aguelmous", 413: "Tighassaline", 414: "Ait Ishaq",
            415: "Bradia", 416: "Had Boumoussa", 417: "Foum Oudi", 418: "Laayayta", 439: "Assahrij",
            440: "Touima", 441: "farkhana", 442: "Driouch", 443: "Midar", 444: "Ben Taieb",
            445: "Tiztoutine", 446: "Beni Chiker", 447: "Imintanout", 448: "Sid L'Mokhtar",
            449: "Sidi bou zid Chichaoua", 450: "Mzoudia", 451: "Mejjat", 452: "Ait hadi",
            453: "Sidi chiker", 454: "Ighoud", 455: "Bouaboud", 456: "Agouidir", 457: "Ouled Moumna",
            458: "Tamraght", 459: "Ouled Dahhou", 462: "Taghazout", 479: "Madagh", 481: "Ain Erreggada",
            482: "Dar-El Kebdani", 483: "Boudinar", 484: "Tamsamane", 485: "Telat Azlaf",
            486: "Kassita", 487: "Tafersit", 488: "Ouled Settout", 489: "Kariat Arekmane",
            490: "Beni Sidal Jbel", 491: "Mariouari", 492: "Bouarg", 493: "Afra", 494: "Jaadar",
            495: "Bassatine El Menzeh", 496: "Ajdir", 497: "Boukidaren", 498: "Ait-Kamara",
            499: "Bni Hadifa", 500: "Targuist", 501: "Issaguen", 502: "Bni Bouayach", 503: "Timezgadiouine",
            504: "Ain Leuh", 505: "Sidi Allal Tazi", 506: "El Kebab", 507: "Outat El Haj",
            508: "Azrou ait melloul", 509: "Tissa", 510: "Ain Aicha", 511: "Bani Walid",
            512: "Bouhouda", 513: "Ain Mediouna", 515: "Sidi El Ayedi", 516: "Oulad Said",
            517: "Oulad Abbou", 518: "El Borouj", 519: "Guisser", 520: "Tiddas", 521: "Marnissa",
            522: "Bab Marzouka", 523: "Bir Jdid", 524: "Oulad Frej", 525: "Sidi Smail",
            526: "Messawerr Rasso", 527: "El Haouzia", 528: "Oulad Amrane", 529: "Afsou",
            530: "Khemis du Sahel", 531: "Zouada", 532: "Timahdite", 533: "Bouderbala",
            534: "Sebt Jahjouhe", 535: "Dlalha", 536: "Lalla Mimouna", 537: "Bouskoura-Ville Verte",
            538: "Bouskoura-Ouled Saleh", 539: "Ouahat Sidi Brahim", 540: "Sidi Taibi", 541: "Sidi Kaouki",
            542: "Tidzi", 543: "Smimou", 544: "Tamanar", 545: "Ait Daoud", 546: "Douar laarab",
            547: "Tleta-El Henchane", 548: "Meskala", 549: "Tafetachte", 550: "Had Draa", 551: "Birkouate",
            552: "Tamegroute", 553: "Beni zoli", 554: "Bleida", 555: "Agdez", 556: "Tagounite",
            557: "Ait Boudaoud", 558: "Errouha", 559: "Fezouata", 560: "Nkoub", 561: "M'Hamid El Ghizlane",
            562: "Tazarine", 563: "Ternata", 564: "Tamezmoute", 565: "Tinzouline", 566: "Tansifte",
            567: "Achakkar", 568: "Tinzouline", 577: "Belaaguid", 578: "Agafay", 579: "Asni",
            580: "Ben Rahmoun", 581: "Sidi Bou Othmane", 582: "Chrifia", 583: "Sidi Zouine",
            584: "Sebt Ben Sassi", 585: "Kariat Ba Mohamed", 586: "Khlalfa", 587: "Fricha",
            588: "Ourtzagh", 589: "Hajria Ouled Daoud", 590: "Bni Oulid", 591: "Ben Karrich",
            592: "Stehat", 593: "El Jebeha", 594: "KAA ASRASS", 595: "Bni Ahmed Cherqia",
            596: "Azla", 597: "Belyounech", 598: "Beni Hassane", 600: "Ain Lahcen", 601: "Mirleft",
            602: "Imi Ouaddar"
        }
        district_id = 1  # Default to Casablanca
        if self.city:
            city_lower = self.city.strip().lower()
            for code, city_name in city_codes.items():
                if city_name.lower() == city_lower:
                    district_id = code
                    break
        # SendIt API configuration
        api_url = "https://app.sendit.ma/api/v1/deliveries"
        labels_api_url = "https://app.sendit.ma/api/v1/deliveries/getlabels"
        headers = {
            'Authorization': 'Bearer 19801906|DW6w2VmqOijIei5q9JCiD3x3BrY6Uyy2YvIeubIO',
            'Content-Type': 'application/json'
        }

        created_colis = []
        failed_colis = []
        delivery_codes = []

        for colis_num in colis_numbers:
            try:
                # Get lines for this colis (excluding cancelled ones)
                colis_lines = active_lines.filtered(lambda l: l.numero_colis == colis_num)

                # Calculate total amount for this colis
                total_amount = sum(line.price * line.quantity for line in colis_lines)

                # Prepare products description with name and barcode
                products_description = ", ".join([
                    f"{line.product_name} - Code: {line.code_barre or 'N/A'} (Qty: {line.quantity})"
                    for line in colis_lines
                ])

                # Prepare API payload
                payload = {
                    "pickup_district_id": "1",
                    "district_id": district_id,
                    "name": self.client_name or "",
                    "amount": total_amount,
                    "address": f"{self.adresse or ''} {self.second_adresse or ''}".strip(),
                    "phone": self.phone or self.mobile or "",
                    "comment": f"Commande: {self.reference or self.ticket_id} - Colis #{colis_num}",
                    "reference": f"{self.ticket_id}-COLIS-{colis_num}",
                    "allow_open": 1,
                    "allow_try": 0,
                    "products_from_stock": 0,
                    "products": products_description,
                    "packaging_id": 1,
                    "option_exchange": 0,
                    "delivery_exchange_id": 1
                }

                # Make API call
                response = requests.post(api_url, headers=headers, json=payload, timeout=30)

                if response.status_code == 200 or response.status_code == 201:
                    response_data = response.json()
                    created_colis.append({
                        'colis_num': colis_num,
                        'response': response_data
                    })

                    # Extract delivery code from response for label printing
                    if 'data' in response_data and 'code' in response_data['data']:
                        delivery_codes.append(response_data['data']['code'])
                    elif 'code' in response_data:
                        delivery_codes.append(response_data['code'])

                else:
                    failed_colis.append({
                        'colis_num': colis_num,
                        'error': f"HTTP {response.status_code}: {response.text}"
                    })

            except Exception as e:
                failed_colis.append({
                    'colis_num': colis_num,
                    'error': str(e)
                })

        # Print labels if any colis were created successfully
        label_url = None
        if delivery_codes:
            try:
                # Prepare label printing payload
                label_payload = {
                    "codesToPrint": ",".join(delivery_codes),
                    "printFormat": 1
                }

                # Make label printing API call
                label_response = requests.post(labels_api_url, headers=headers, json=label_payload, timeout=30)

                if label_response.status_code == 200:
                    label_data = label_response.json()
                    if label_data.get('success') and 'data' in label_data and 'fileUrl' in label_data['data']:
                        label_url = label_data['data']['fileUrl']

            except Exception as e:
                # Log label printing error but don't fail the whole process
                self.message_post(
                    body=f"Erreur lors de l'impression des étiquettes: {str(e)}",
                    message_type='notification'
                )

        # Update order status
        if created_colis:
            self.colis_created = True

            # Store colis codes for future reference
            if delivery_codes:
                self.colis_codes = json.dumps(delivery_codes)

            # Store label URL if available
            if label_url:
                self.label_url = label_url

            # Log success message
            success_message = f"Colis créés avec succès:\n"
            for colis in created_colis:
                success_message += f"- Colis #{colis['colis_num']}\n"

            if label_url:
                success_message += f"\nÉtiquettes générées: {label_url}\n"

            if failed_colis:
                success_message += f"\nErreurs pour certains colis:\n"
                for colis in failed_colis:
                    success_message += f"- Colis #{colis['colis_num']}: {colis['error']}\n"

            self.message_post(
                body=success_message,
                message_type='notification'
            )

            # Show success message to user with label URL
            if failed_colis:
                message = f"{len(created_colis)} colis créés avec succès, {len(failed_colis)} échecs."
            else:
                message = f"{len(created_colis)} colis créés avec succès!"

            if label_url:
                message += f" Étiquettes générées!"

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Création de Colis',
                    'message': message,
                    'type': 'success' if not failed_colis else 'warning',
                    'sticky': False,
                }
            }

        else:
            # All failed
            error_message = "Échec de création de tous les colis:\n"
            for colis in failed_colis:
                error_message += f"- Colis #{colis['colis_num']}: {colis['error']}\n"

            raise UserError(error_message)

    def action_print_labels(self):
        """Print labels for existing colis"""
        if not self.colis_created:
            raise UserError("Aucun colis créé pour cette commande. Créez d'abord les colis.")

        if not self.colis_codes:
            raise UserError("Aucun code de colis trouvé. Les colis doivent être créés via l'API SendIt.")

        try:
            # Parse stored colis codes
            colis_codes = json.loads(self.colis_codes)

            if not colis_codes:
                raise UserError("Aucun code de colis valide trouvé.")

            # SendIt API configuration
            labels_api_url = "https://app.sendit.ma/api/v1/deliveries/getlabels"
            headers = {
                'Authorization': 'Bearer 19801906|DW6w2VmqOijIei5q9JCiD3x3BrY6Uyy2YvIeubIO',
                'Content-Type': 'application/json'
            }

            # Prepare label printing payload
            label_payload = {
                "codesToPrint": ",".join(colis_codes),
                "printFormat": 1
            }

            # Make label printing API call
            label_response = requests.post(labels_api_url, headers=headers, json=label_payload, timeout=30)

            if label_response.status_code == 200:
                label_data = label_response.json()

                if label_data.get('success') and 'data' in label_data and 'fileUrl' in label_data['data']:
                    label_url = label_data['data']['fileUrl']

                    # Update stored label URL
                    self.label_url = label_url

                    # Log success message
                    self.message_post(
                        body=f"Étiquettes générées avec succès: {label_url}",
                        message_type='notification'
                    )

                    # Show success message to user
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': 'Impression des Étiquettes',
                            'message': f'Étiquettes générées avec succès! URL: {label_url}',
                            'type': 'success',
                            'sticky': False,
                        }
                    }
                else:
                    raise UserError(f"Erreur dans la réponse API: {label_data.get('message', 'Réponse invalide')}")
            else:
                raise UserError(f"Erreur API: HTTP {label_response.status_code} - {label_response.text}")

        except json.JSONDecodeError:
            raise UserError("Erreur lors du décodage des codes de colis. Veuillez recréer les colis.")
        except Exception as e:
            raise UserError(f"Erreur lors de l'impression des étiquettes: {str(e)}")

    def action_get_colis_status(self):
        """Get status of existing colis from SendIt API"""
        if not self.colis_created:
            raise UserError("Aucun colis créé pour cette commande.")

        if not self.colis_codes:
            raise UserError("Aucun code de colis trouvé.")

        try:
            # Parse stored colis codes
            colis_codes = json.loads(self.colis_codes)

            if not colis_codes:
                raise UserError("Aucun code de colis valide trouvé.")

            # SendIt API configuration
            api_url = "https://app.sendit.ma/api/v1/deliveries"
            headers = {
                'Authorization': 'Bearer 19801906|DW6w2VmqOijIei5q9JCiD3x3BrY6Uyy2YvIeubIO',
                'Content-Type': 'application/json'
            }

            # Get colis status
            response = requests.get(api_url, headers=headers, timeout=30)

            if response.status_code == 200:
                response_data = response.json()

                if response_data.get('success') and 'data' in response_data:
                    # Filter colis that belong to this order
                    order_colis = []
                    for colis in response_data['data']:
                        if colis.get('code') in colis_codes:
                            order_colis.append(colis)

                    if order_colis:
                        # Prepare status message
                        status_message = "Statut des colis:\n"
                        for colis in order_colis:
                            status_message += f"- Code: {colis.get('code', 'N/A')}\n"
                            status_message += f"  Statut: {colis.get('status', 'N/A')}\n"
                            status_message += f"  Nom: {colis.get('name', 'N/A')}\n"
                            status_message += f"  Téléphone: {colis.get('phone', 'N/A')}\n"
                            status_message += f"  Montant: {colis.get('amount', 'N/A')} MAD\n"
                            status_message += f"  Dernière action: {colis.get('last_action_at', 'N/A')}\n\n"

                        # Log status message
                        self.message_post(
                            body=status_message,
                            message_type='notification'
                        )

                        return {
                            'type': 'ir.actions.client',
                            'tag': 'display_notification',
                            'params': {
                                'title': 'Statut des Colis',
                                'message': f'Statut récupéré pour {len(order_colis)} colis.',
                                'type': 'info',
                                'sticky': True,
                            }
                        }
                    else:
                        raise UserError("Aucun colis trouvé pour cette commande dans l'API SendIt.")
                else:
                    raise UserError(f"Erreur dans la réponse API: {response_data.get('message', 'Réponse invalide')}")
            else:
                raise UserError(f"Erreur API: HTTP {response.status_code} - {response.text}")

        except json.JSONDecodeError:
            raise UserError("Erreur lors du décodage des codes de colis.")
        except Exception as e:
            raise UserError(f"Erreur lors de la récupération du statut: {str(e)}")

    def action_open_label_url(self):
        """Open the label URL in a new window"""
        if not self.label_url:
            raise UserError("Aucune URL d'étiquette disponible. Imprimez d'abord les étiquettes.")

        return {
            'type': 'ir.actions.act_url',
            'url': self.label_url,
            'target': 'new',
        }

    def action_update_colis_status(self):
        """Update colis status for each order line"""
        if not self.colis_created:
            raise UserError("Aucun colis créé pour cette commande.")

        if not self.colis_codes:
            raise UserError("Aucun code de colis trouvé.")

        try:
            # Parse stored colis codes
            colis_codes = json.loads(self.colis_codes)

            if not colis_codes:
                raise UserError("Aucun code de colis valide trouvé.")

            # SendIt API configuration
            headers = {
                'Authorization': 'Bearer 19801906|DW6w2VmqOijIei5q9JCiD3x3BrY6Uyy2YvIeubIO',
                'Content-Type': 'application/json'
            }

            updated_lines = 0
            failed_updates = []

            # Get active lines (non-cancelled)
            active_lines = self.line_ids.filtered(lambda l: l.status_ligne_commande != 'annuler').filtered(
                lambda l: l.status_ligne_commande != 'annuler')

            # Group lines by colis number
            colis_groups = {}
            for line in active_lines:
                if line.numero_colis:
                    if line.numero_colis not in colis_groups:
                        colis_groups[line.numero_colis] = []
                    colis_groups[line.numero_colis].append(line)

            # Update status for each colis
            for i, colis_code in enumerate(colis_codes):
                try:
                    # Get colis details from SendIt API
                    api_url = f"https://app.sendit.ma/api/v1/deliveries/{colis_code}"
                    response = requests.get(api_url, headers=headers, timeout=30)

                    if response.status_code == 200:
                        response_data = response.json()

                        if response_data.get('success') and 'data' in response_data:
                            colis_data = response_data['data']
                            status = colis_data.get('status', 'PENDING')

                            # Map the colis number (i+1 because colis_codes is 0-indexed)
                            colis_num = i + 1

                            # Update lines for this colis
                            if colis_num in colis_groups:
                                for line in colis_groups[colis_num]:
                                    line.write({
                                        'status_colis': status,
                                        'colis_code': colis_code,
                                        'last_status_update': fields.Datetime.now()
                                    })
                                    updated_lines += 1
                        else:
                            failed_updates.append(
                                f"Colis {colis_code}: {response_data.get('message', 'Réponse invalide')}")
                    else:
                        failed_updates.append(f"Colis {colis_code}: HTTP {response.status_code}")

                except Exception as e:
                    failed_updates.append(f"Colis {colis_code}: {str(e)}")

            # Update order status based on colis statuses
            self._update_order_status()

            # Prepare result message
            if updated_lines > 0:
                message = f"Statut mis à jour pour {updated_lines} ligne(s) de commande."
                if failed_updates:
                    message += f"\nÉchecs: {len(failed_updates)}"

                # Log success message
                success_msg = f"Mise à jour du statut des colis:\n- {updated_lines} ligne(s) mise(s) à jour avec succès\n"
                if failed_updates:
                    success_msg += f"- {len(failed_updates)} échec(s):\n"
                    for error in failed_updates:
                        success_msg += f"  * {error}\n"

                self.message_post(
                    body=success_msg,
                    message_type='notification'
                )

                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Mise à jour du Statut',
                        'message': message,
                        'type': 'success' if not failed_updates else 'warning',
                        'sticky': False,
                    }
                }
            else:
                raise UserError("Aucune ligne n'a pu être mise à jour.")

        except json.JSONDecodeError:
            raise UserError("Erreur lors du décodage des codes de colis.")
        except Exception as e:
            raise UserError(f"Erreur lors de la mise à jour du statut: {str(e)}")

    def _update_order_status(self):
        """Update order status based on colis statuses"""
        if not self.line_ids:
            return

        colis_statuses = self.line_ids.mapped('status_colis')

        # Map colis status to order status
        if any(status == 'PENDING' for status in colis_statuses):
            self.status = 'prepare'
        elif any(status == 'PICKEDUP' for status in colis_statuses):
            self.status = 'encourdelivraison'
        elif all(status == 'WAREHOUSE' for status in colis_statuses):
            self.status = 'encourdelivraison'
        elif all(status == 'TRANSIT' for status in colis_statuses):
            self.status = 'encourdelivraison'
        elif all(status == 'DISTRIBUTED' for status in colis_statuses):
            self.status = 'encourdelivraison'
        elif all(status == 'DELIVERED' for status in colis_statuses):
            self.status = 'delivered'

        for line in self.line_ids:
            if line.status_colis == 'PENDING':
                line.status_ligne_commande = 'prepare'
            elif line.status_colis in ['PICKEDUP', 'WAREHOUSE', 'TRANSIT', 'DISTRIBUTED']:
                line.status_ligne_commande = 'encourdelivraison'
            elif line.status_colis == 'DELIVERED':
                line.status_ligne_commande = 'delivered'
            elif line.status_colis in ['CANCELED', 'REJECTED']:
                line.status_ligne_commande = 'annuler'

    @api.model
    def cron_update_colis_status(self):
        """Cron job to update colis status for orders with specific statuses"""
        try:
            # Find orders with status 'prepare' or 'encourdelivraison' that have colis created
            orders = self.search([
                ('status', 'in', ['prepare', 'encourdelivraison', 'encoursdepreparation']),
                ('colis_created', '=', True),
                ('colis_codes', '!=', False)
            ])

            _logger.info(f"Cron job: Found {len(orders)} orders to update colis status")

            for order in orders:
                try:
                    # Call the existing update method but handle exceptions to continue with other orders
                    order.action_update_colis_status()
                    _logger.info(f"Successfully updated colis status for order {order.ticket_id}")
                except Exception as e:
                    _logger.error(f"Failed to update colis status for order {order.ticket_id}: {str(e)}")
                    continue

        except Exception as e:
            _logger.error(f"Cron job error: {str(e)}")
    #ramassage
    def action_create_pickup_request(self):
        """Create pickup request via SendIt API"""
        # Check if colis are created
        if not self.colis_created:
            raise UserError("Aucun colis créé pour cette commande. Créez d'abord les colis.")

        # Check if colis codes exist
        if not self.colis_codes:
            raise UserError("Aucun code de colis trouvé. Les colis doivent être créés via l'API SendIt.")

        try:
            # Parse stored colis codes
            colis_codes = json.loads(self.colis_codes)

            if not colis_codes:
                raise UserError("Aucun code de colis valide trouvé.")

            pickup_api_url = "https://app.sendit.ma/api/v1/pickups"
            headers = {
                'Authorization': 'Bearer 19801906|DW6w2VmqOijIei5q9JCiD3x3BrY6Uyy2YvIeubIO',
                'Content-Type': 'application/json'
            }

            # Prepare pickup request payload
            pickup_payload = {
                "district_id": 3,
                "name": "CHICCORNER CHICCORNER",
                "phone": "0666089558",
                "address": "Morocco Mall Ain Diab boutique 1 ère étage",
                "note": f"Merci de m'appeler avons d'arrivé",
                "deliveries": ",".join(colis_codes)
            }

            # Make pickup request API call
            response = requests.post(pickup_api_url, headers=headers, json=pickup_payload, timeout=30)

            if response.status_code == 200 or response.status_code == 201:
                response_data = response.json()

                if response_data.get('success'):
                    # Store pickup information
                    pickup_info = {
                        'pickup_id': response_data.get('data', {}).get('id'),
                        'pickup_code': response_data.get('data', {}).get('code'),
                        'pickup_status': response_data.get('data', {}).get('status'),
                        'created_at': fields.Datetime.now()
                    }

                    # You can add fields to store pickup information
                    # For now, we'll use the message system to log the information
                    success_message = f"Demande de ramassage créée avec succès:\n"
                    success_message += f"- Codes Colis: {', '.join(colis_codes)}\n"

                    self.message_post(
                        body=success_message,
                        message_type='notification'
                    )

                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': 'Demande de Ramassage',
                            'message': f'Demande de ramassage créée avec succès',
                            'type': 'success',
                            'sticky': False,
                        }
                    }
                else:
                    raise UserError(f"Erreur dans la réponse API: {response_data.get('message', 'Réponse invalide')}")
            else:
                raise UserError(f"Erreur API: HTTP {response.status_code} - {response.text}")

        except json.JSONDecodeError:
            raise UserError("Erreur lors du décodage des codes de colis. Veuillez recréer les colis.")
        except Exception as e:
            raise UserError(f"Le ramassage de ce colis a déjà été effectué. Veuillez consulter votre plateforme Sendit et vérifier les informations. Merci.")
    '''end 07/07/2025'''
    @api.model
    def sync_status_to_prestashop(self):
        """
        Cron job to sync Odoo order status to PrestaShop.
        Updates these Odoo statuses:
        - 'en_cours_preparation' => PrestaShop status ID 11
        - 'prepare'              => PrestaShop status ID 9
        - 'encourdelivraison'    => PrestaShop status ID 4
        - 'delivered'            => PrestaShop status ID 5
        """
        _logger.info("Starting PrestaShop status synchronization...")

        # Sync only the supported statuses
        orders_to_sync = self.search([
            ('status', 'in', ['en_cours_preparation', 'prepare', 'encourdelivraison', 'delivered']),
            ('reference', '!=', False),
        ])

        _logger.info(f"Found {len(orders_to_sync)} orders to sync")

        synced_count = 0
        error_count = 0

        for order in orders_to_sync:
            try:
                if self._update_prestashop_order_status(order):
                    synced_count += 1
                    _logger.info(f"Successfully synced order {order.reference} with status {order.status}")
                else:
                    error_count += 1
                    _logger.error(f"Failed to sync order {order.reference}")
            except Exception as e:
                error_count += 1
                _logger.error(f"Error syncing order {order.reference}: {str(e)}")

        _logger.info(f"Sync completed. Synced: {synced_count}, Errors: {error_count}")
        return {
            'synced': synced_count,
            'errors': error_count,
            'total': len(orders_to_sync)
        }

    def _find_prestashop_order_by_reference(self, reference):
        """
        Find PrestaShop order ID by reference using basic authentication
        """
        try:
            url = f"{self.API_BASE_URL}/orders"
            params = {
                'filter[reference]': reference,
            }

            response = requests.get(url, auth=(self.WS_KEY, ''), params=params, timeout=30)
            response.raise_for_status()

            root = ET.fromstring(response.content)
            order_elem = root.find('.//order')

            if order_elem is not None and 'id' in order_elem.attrib:
                order_id = order_elem.attrib['id']
                _logger.info(f"Found PrestaShop order ID {order_id} for reference {reference}")
                return order_id
            else:
                _logger.warning(f"No order found in PrestaShop with reference {reference}")
                return None

        except requests.exceptions.RequestException as e:
            _logger.error(f"HTTP error while searching for order: {str(e)}")
            return None
        except ET.ParseError as e:
            _logger.error(f"XML parsing error: {str(e)}")
            return None
        except Exception as e:
            _logger.error(f"Unexpected error while searching for order: {str(e)}")
            return None

    def _update_prestashop_order_status(self, order):
        """
        Update PrestaShop order status based on Odoo order status
        """
        try:
            prestashop_order_id = self._find_prestashop_order_by_reference(order.reference)

            if not prestashop_order_id:
                _logger.warning(f"Order with reference '{order.reference}' not found in PrestaShop")
                return False

            # Mapping Odoo status to PrestaShop current_state ID
            status_mapping = {
                'en_cours_preparation': 12,
                'prepare': 9,
                'encourdelivraison': 4,
                'delivered': 5,
            }

            prestashop_status_id = status_mapping.get(order.status)

            if not prestashop_status_id:
                _logger.warning(f"No PrestaShop status mapping for Odoo status '{order.status}'")
                return False

            return self._update_prestashop_order_status_by_id(prestashop_order_id, prestashop_status_id)

        except Exception as e:
            _logger.error(f"Error updating PrestaShop order status: {str(e)}")
            return False

    def _update_prestashop_order_status_by_id(self, order_id, status_id):
        """
        Update the current_state of a PrestaShop order
        """
        try:
            url = f"{self.API_BASE_URL}/orders/{order_id}"
            response = requests.get(url, auth=(self.WS_KEY, ''))
            response.raise_for_status()

            root = ET.fromstring(response.content)

            current_state = root.find('.//current_state')
            if current_state is not None:
                current_state.text = str(status_id)
            else:
                _logger.error(f"Could not find current_state field in order {order_id}")
                return False

            xml_data = ET.tostring(root, encoding='utf-8', method='xml')

            headers = {'Content-Type': 'application/xml'}

            update_response = requests.put(
                url,
                auth=(self.WS_KEY, ''),
                data=xml_data,
                headers=headers
            )
            update_response.raise_for_status()

            _logger.info(f"Successfully updated PrestaShop order {order_id} to status {status_id}")
            return True

        except requests.exceptions.RequestException as e:
            _logger.error(f"HTTP error while updating order status: {str(e)}")
            return False
        except ET.ParseError as e:
            _logger.error(f"XML parsing error: {str(e)}")
            return False
        except Exception as e:
            _logger.error(f"Unexpected error while updating order status: {str(e)}")
            return False

    '''added'''
    @api.model
    def auto_process_initial_orders(self):

        try:
            # Find all orders with 'initial' status
            initial_orders = self.search([('status', '=', 'initial')])

            processed_count = 0
            failed_count = 0

            for order in initial_orders:
                try:
                    # Check if any products have stock_count = 0
                    out_of_stock_products = []
                    for line in order.line_ids:
                        if line.stock_count == 0:
                            product_name = line.product_name or (
                                line.product_id.name if line.product_id else 'Produit inconnu')
                            out_of_stock_products.append(product_name)

                    # Call the action_send_to_pos method
                    result = order.action_send_to_pos()

                    # Add chatter message based on stock situation
                    if out_of_stock_products:
                        stock_message = f"Traitement le {fields.Datetime.now().strftime('%d/%m/%Y à %H:%M')}: "
                        stock_message += f"Produits sans stock:\n"
                        for product in out_of_stock_products:
                            stock_message += f"- {product} n'existe pas en stock\n"

                        order.message_post(
                            body=stock_message,
                            subject="Traitement- Rupture de Stock"
                        )
                    else:
                        order.message_post(
                            body=f"Commande traitée le {fields.Datetime.now().strftime('%d/%m/%Y à %H:%M')}",
                            subject="Traitement Automatique"
                        )

                    _logger.info(f"Auto-processed order {order.ticket_id}")
                    processed_count += 1

                except Exception as e:
                    # Log the error but continue with other orders
                    _logger.error(f"Failed to auto-process order {order.ticket_id}: {str(e)}")
                    failed_count += 1

                    # Add error note to the order's chatter
                    order.message_post(
                        body=f"Échec du traitement automatique le {fields.Datetime.now().strftime('%d/%m/%Y à %H:%M')}: {str(e)}",
                        subject="Erreur Traitement Automatique"
                    )

            # Log summary
            _logger.info(f"Auto-processing completed: {processed_count} orders processed, {failed_count} orders failed")

            return {
                'processed': processed_count,
                'failed': failed_count,
                'total': len(initial_orders)
            }

        except Exception as e:
            _logger.error(f"Error in auto_process_initial_orders: {str(e)}")
            return {'error': str(e)}

    def action_send_to_pos(self):
        for order in self:
            if not order.line_ids:
                raise UserError("Cette commande n'a pas de lignes de commande.")
            if order.pos_order_id:
                raise UserError("Cette commande a déjà été traité.")

            # Separate in-stock and out-of-stock lines
            in_stock_lines, out_of_stock_lines = self._separate_lines_by_stock(order)

            # Update out-of-stock lines status to 'annuler'
            for line in out_of_stock_lines:
                line.write({'status_ligne_commande': 'annuler'})

            # If no products are in stock, update order status and show message
            if not in_stock_lines:
                order.status = 'initial'  # or whatever status you prefer
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Attention',
                        'message': f'Commande {order.ticket_id}: Aucun produit en stock. Tous les produits ont été annulés.',
                        'type': 'warning',
                    }
                }

            # Process only in-stock lines
            self._update_order_lines_with_warehouse_info_selective(order, in_stock_lines)

            # Group in-stock lines by warehouse
            warehouse_groups = self._group_lines_by_warehouse_selective(in_stock_lines)

            created_pos_orders = []

            # Create separate POS orders for each warehouse
            for warehouse, lines_data in warehouse_groups.items():
                try:
                    pos_order = self._create_pos_order_for_warehouse(order, warehouse, lines_data)
                    created_pos_orders.append(pos_order)

                    # Update in-stock lines status to 'en_cours_preparation'
                    for line in lines_data:
                        line.write({'status_ligne_commande': 'en_cours_preparation'})

                except Exception as e:
                    # If there's an error, clean up already created orders
                    for created_order in created_pos_orders:
                        created_order.unlink()
                    raise UserError(f"Erreur lors de la création de la commande POS pour {warehouse.name}: {str(e)}")

            # Update order status and link to the first POS order
            order.status = 'en_cours_preparation'
            if created_pos_orders:
                order.pos_order_id = created_pos_orders[0].id

            # Show warning notification if some products are out of stock
            if out_of_stock_lines:
                out_of_stock_products = []
                for line in out_of_stock_lines:
                    product_name = line.product_name or (line.product_id.name if line.product_id else 'Produit inconnu')
                    out_of_stock_products.append(f"- {product_name}")

                warning_message = f"Attention! Produit(s) à quantité 0 en stock:\n"
                warning_message += "\n".join(out_of_stock_products)
                warning_message += f"\n\nMais la commande {order.ticket_id} a été traitée pour les autres produits disponibles."

                # Return warning notification first
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Attention - Rupture de stock',
                        'message': warning_message,
                        'type': 'warning',
                        'sticky': True  # Make it stay visible longer
                    }
                }

            # If all products were in stock, show success message
            else:
                # Create success message with details
                message_parts = []
                for pos_order in created_pos_orders:
                    warehouse_name = pos_order.config_id.name
                    message_parts.append(f"- {warehouse_name}")

                success_message = f"Commande {order.ticket_id} traitée avec succès!\n"
                success_message += f"Tous les produits envoyés vers {len(created_pos_orders)} POS:\n"
                success_message += "\n".join(message_parts)

                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Succès',
                        'message': success_message,
                        'type': 'success',
                    }
                }

    def action_check_pos_status(self):
        """Manual action to check and update order status based on POS order state"""
        for order in self:
            order._check_and_update_status()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Vérification terminée',
                'message': 'Statut des commandes vérifié et mis à jour si nécessaire.',
                'type': 'info',
            }
        }
    @api.model
    def _cron_check_pos_orders_status(self):
        """Cron job to automatically check and update order status"""
        orders_to_check = self.search([
            ('status', '=', 'en_cours_preparation')
        ])

        for order in orders_to_check:
            order._check_and_update_status()
    def _separate_lines_by_stock(self, order):
        """Separate order lines into in-stock and out-of-stock lists"""
        in_stock_lines = []
        out_of_stock_lines = []

        for line in order.line_ids:
            if not line.product_id:
                out_of_stock_lines.append(line)
                continue

            if not line.quantity or line.quantity <= 0:
                out_of_stock_lines.append(line)
                continue

            if not line.price or line.price < 0:
                out_of_stock_lines.append(line)
                continue

            # Check if product has stock
            warehouse = self._find_warehouse_for_product(line.product_id)
            if warehouse:
                in_stock_lines.append(line)
            else:
                out_of_stock_lines.append(line)

        return in_stock_lines, out_of_stock_lines

    def _group_lines_by_warehouse_selective(self, lines):
        """Group given lines by their warehouse based on product stock location"""
        warehouse_groups = {}

        for line in lines:
            # Find warehouse for this product based on stock
            warehouse = self._find_warehouse_for_product(line.product_id)

            if warehouse:  # We already filtered for in-stock items, so this should always be true
                # Group lines by warehouse
                if warehouse not in warehouse_groups:
                    warehouse_groups[warehouse] = []
                warehouse_groups[warehouse].append(line)

        return warehouse_groups

    def _update_order_lines_with_warehouse_info_selective(self, order, lines):
        """Update only the given lines with warehouse information and colis numbers"""
        warehouse_to_colis = {}  # Map warehouse to colis number
        colis_counter = 1

        for line in lines:
            if not line.product_id:
                continue

            # Find warehouse for this product
            warehouse = self._find_warehouse_for_product(line.product_id)

            if warehouse:
                # Assign colis number based on warehouse
                if warehouse.id not in warehouse_to_colis:
                    warehouse_to_colis[warehouse.id] = colis_counter
                    colis_counter += 1

                # Update the order line with warehouse info
                line.write({
                    'magasin_name': warehouse.name,
                    'numero_colis': warehouse_to_colis[warehouse.id],
                    # 'code_barre': line.product_id.barcode or line.product_id.default_code or '',
                })

    def _check_and_update_status(self):
        """Check if all related POS orders are paid and update status accordingly"""
        if self.status != 'en_cours_preparation':
            return

        # Get all pos_reference values from order lines
        pos_references = self.line_ids.mapped('numero_recu')
        pos_references = [ref for ref in pos_references if ref]  # Remove empty values

        if not pos_references:
            _logger.warning(f"No POS references found for order {self.ticket_id}")
            return

        # Check if all POS orders with these references are paid
        all_paid = True
        for pos_reference in pos_references:
            pos_orders = self.env['pos.order'].search([
                ('pos_reference', '=', pos_reference)
            ])

            if not pos_orders:
                _logger.warning(f"No POS order found with reference {pos_reference}")
                all_paid = False
                break

            # Check if any of the POS orders with this reference is not paid
            unpaid_orders = pos_orders.filtered(lambda o: o.state not in ['paid', 'done', 'invoiced'])
            if unpaid_orders:
                all_paid = False
                break

        # Update status if all related POS orders are paid
        if all_paid:
            self.status = 'prepare'
            _logger.info(f"Order {self.ticket_id} status updated to 'prepare' - all POS orders are paid")
    def _group_lines_by_warehouse(self, order):
        """Group order lines by their warehouse based on product stock location"""
        warehouse_groups = {}

        for line in order.line_ids:
            if not line.product_id:
                raise UserError(f"Produit manquant ou invalide dans la ligne: {line.product_name or 'Unknown'}")

            if not line.quantity or line.quantity <= 0:
                raise UserError(f"Quantité invalide pour le produit '{line.product_id.name}': {line.quantity}")

            if not line.price or line.price < 0:
                raise UserError(f"Prix invalide pour le produit '{line.product_id.name}': {line.price}")

            # Find warehouse for this product based on stock
            warehouse = self._find_warehouse_for_product(line.product_id)

            if not warehouse:
                raise UserError(
                    f"Aucun stock disponible trouvé pour le produit '{line.product_id.name}' dans tous les entrepôts.")

            # Group lines by warehouse
            if warehouse not in warehouse_groups:
                warehouse_groups[warehouse] = []

            warehouse_groups[warehouse].append(line)

        return warehouse_groups

    def _update_order_lines_with_warehouse_info(self, order):
        """Update order lines with warehouse information and colis numbers"""
        warehouse_to_colis = {}  # Map warehouse to colis number
        colis_counter = 1

        for line in order.line_ids:
            if not line.product_id:
                continue

            # Find warehouse for this product
            warehouse = self._find_warehouse_for_product(line.product_id)

            if warehouse:
                # Assign colis number based on warehouse
                if warehouse.id not in warehouse_to_colis:
                    warehouse_to_colis[warehouse.id] = colis_counter
                    colis_counter += 1

                # Update the order line with warehouse info
                line.write({
                    'magasin_name': warehouse.name,
                    'numero_colis': warehouse_to_colis[warehouse.id],
                    #'code_barre': line.product_id.barcode or line.product_id.default_code or '',
                })
    def _find_warehouse_for_product(self, product):
        """Find the warehouse that has stock for the given product"""
        # Search for stock quants with available quantity
        quants = self.env['stock.quant'].search([
            ('product_id', '=', product.id),
            ('quantity', '>', 0),
            ('location_id.usage', '=', 'internal')
        ])

        if not quants:
            return None

        # Find warehouse for the first available quant

        for quant in quants:
            warehouse = self.env['stock.warehouse'].search([
                ('lot_stock_id', '=', quant.location_id.id)
            ], limit=1)

            if warehouse:
                return warehouse

        return None
    def _create_pos_order_for_warehouse(self, order, warehouse, lines):
        """Create a POS order for a specific warehouse with given lines"""

        # Find POS config for this warehouse
        pos_config = self.env['pos.config'].search([
            ('name', '=', warehouse.name)
        ], limit=1)

        if not pos_config:
            pos_config = self.env['pos.config'].search([
                ('company_id', '=', self.env.company.id)
            ], limit=1)

        if not pos_config:
            raise UserError(f"Aucune configuration POS trouvée pour l'entrepôt '{warehouse.name}'.")

        # Find open session for this POS config
        session = self.env['pos.session'].search([
            ('config_id', '=', pos_config.id),
            ('state', '=', 'opened')
        ], limit=1)

        if not session:
            raise UserError(
                f"Aucune session POS ouverte pour le point de vente '{pos_config.name}'. Veuillez ouvrir une session POS d'abord.")

        # Prepare order lines for this warehouse
        order_lines = []
        total_amount = 0.0
        tax_amount = 0.0

        for line in lines:
            discount_amount = (line.discount or 0.0) / 100.0
            price_unit = float(line.price)
            qty = float(line.quantity)
            taxes = line.product_id.taxes_id.filtered(lambda t: t.company_id == self.env.company)
            tax_rate = taxes[0].amount / 100.0 if taxes else 0.20

            line_total = qty * price_unit * (1 - discount_amount)
            subtotal_incl = line_total
            subtotal_excl = subtotal_incl / (1 + tax_rate)

            total_amount += line_total
            tax_amount += line_total - (line_total / 1.20)

            order_lines.append((0, 0, {
                'product_id': line.product_id.id,
                'full_product_name': line.product_id.display_name,
                'qty': qty,
                'price_unit': price_unit,
                'discount': line.discount or 0.0,
                'price_subtotal': subtotal_excl,
                'price_subtotal_incl': subtotal_incl,
                'tax_ids': [(6, 0, taxes.ids)] if taxes else False,
            }))

        if not order_lines:
            raise UserError("Aucune ligne de commande valide trouvée pour cet entrepôt.")

        # Find or create partner
        partner = self._find_or_create_partner(order)

        # Find employee
        employee = self.env['hr.employee'].search([('name', '=', 'SBIHI SALMA')], limit=1)
        if not employee:
            raise UserError("Employee not found.")

        # Generate sequence and reference
        #sequence = self._generate_pos_sequence(pos_config, session)
        pos_reference = self._generate_pos_reference(order, warehouse.name)

        pos_user = session.user_id or self.env.user

        pos_order_vals = {
            #'name': sequence,
            'state': 'draft',
            'partner_id': partner.id if partner else False,
            'lines': order_lines,
            'amount_total': float(total_amount),
            'amount_paid': 0.0,
            'amount_return': 0.0,
            'amount_tax': float(tax_amount),
            'config_id': pos_config.id,
            'session_id': session.id,
            'employee_id': employee.id,
            'company_id': session.config_id.company_id.id,
            'pricelist_id': session.config_id.pricelist_id.id if session.config_id.pricelist_id else self.env.company.currency_id.id,
            'fiscal_position_id': partner.property_account_position_id.id if partner and partner.property_account_position_id else False,
            'note': f"Commande importée du site web - Ticket: {order.ticket_id} - Entrepôt: {warehouse.name} - Cashier: {pos_user.name}",
            'date_order': order.date_commande or fields.Datetime.now(),
            'pos_reference': pos_reference,
        }

        pos_order = self.env['pos.order'].create(pos_order_vals)
        for line in lines:
            line.write({
                'numero_recu': pos_reference,
            })
        return pos_order

    def _generate_pos_reference(self, order, warehouse_name=None):
        """
        Generate a POS reference with a UID that matches the expected 14-character format
        The format should be: YYYY-MM-DD-HHH where HHH is a 3-digit counter
        """
        # Try to use the existing reference if it already has the right format
        if order.reference:
            import re
            if re.match(r'^.+[0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]{3}$', order.reference):
                base_reference = order.reference
            else:
                base_reference = order.reference
        else:
            base_reference = order.ticket_id or "WEB"

        # Generate a new reference with proper UID format
        current_time = fields.Datetime.now()
        date_part = current_time.strftime('%Y-%m-%d')

        # Generate a 3-digit sequence number based on milliseconds or random
        import random
        sequence_num = str(random.randint(100, 999))

        # Create the UID in the expected format: YYYY-MM-DD-NNN (14 characters including dashes)
        uid = f"{date_part}-{sequence_num}"

        # Include warehouse name in reference if provided
        if warehouse_name:
            return f"WEB-{base_reference}-{warehouse_name}-{uid}"
        else:
            return f"{base_reference}-{uid}"
    def _update_order_lines_with_receipt_number(self, lines, order, warehouse_name):
        """Update order lines with receipt number using the generated POS reference"""
        receipt_number = self._generate_pos_reference(order, warehouse_name)

        for line in lines:
            line.write({
                'numero_recu': receipt_number,
            })
    def _find_or_create_partner(self, order):
        partner = None
        if order.email:
            partner = self.env['res.partner'].search([
                ('email', '=', order.email)
            ], limit=1)

        if not partner and order.client_name:
            partner = self.env['res.partner'].search([
                ('name', '=', order.client_name)
            ], limit=1)

        if not partner:
            partner_vals = {
                'name': order.client_name or 'Client Web',
                'email': order.email or False,
                'phone': order.phone or False,
                'mobile': order.mobile or False,
                'street': order.adresse or False,
                'street2': order.second_adresse or False,
                'city': order.city or False,
                'zip': order.postcode or False,
                'is_company': False,
                'customer_rank': 1,
                'supplier_rank': 0,
            }
            if order.pays:
                country = self.env['res.country'].search([
                    '|',
                    ('name', 'ilike', order.pays),
                    ('code', '=', order.pays)
                ], limit=1)
                if country:
                    partner_vals['country_id'] = country.id

            partner = self.env['res.partner'].create(partner_vals)

        return partner
    '''
    def _generate_pos_sequence(self, pos_config, session):
        return self.env['ir.sequence'].next_by_code('pos.order') or '/'
        '''

class StockWebsiteOrderLine(models.Model):
    _name = 'stock.website.order.line'
    _description = 'Ligne de commande du site'

    order_id = fields.Many2one('stock.website.order', string="Commande")
    product_id = fields.Many2one('product.product', string="Produit")
    product_name = fields.Char(string="Nom du Produit")
    quantity = fields.Float(string="Quantité")
    price = fields.Float(string="Prix", compute="_compute_price_from_pricelist", store=True)
    discount = fields.Float(string="Remise")
    magasin_name = fields.Char(string="Magasin", compute="_compute_magasin_and_stock", store=True,
                               help="Nom du magasin où le produit est stocké")
    stock_count = fields.Float(string="Stock Disponible", compute="_compute_magasin_and_stock", store=True,
                               help="Quantité disponible en stock dans l'entrepôt")
    numero_colis = fields.Integer(string="Numéro Colis", help="Numéro de colis basé sur l'entrepôt de stock",readonly=True)
    code_barre = fields.Char(string="Code Barre", help="Code barre du produit")
    numero_recu = fields.Char(string="Numéro De Ticket", help="Numéro de reçu/ticket de la commande POS",readonly=True)
    status_ligne_commande = fields.Selection([
        ('initial', 'Initial'),
        ('prepare', 'Préparé'),
        ('delivered', 'Livré'),
        ('en_cours_preparation', 'En cours de préparation'),
        ('encourdelivraison', 'En cours de Livraison'),
        ('annuler', 'Annulé')
    ], string="Statut", default='initial')

    status_colis = fields.Selection([
        ('PENDING', 'En attente'),
        ('TO_PREPARE', 'Preparer'),
        ('NEW_DESTINATION', 'Changer'),
        ('TOPICKUP', 'Ramassage en cours'),
        ('PICKEDUP', 'Ramassué'),
        ('WAREHOUSE', 'Entrepôt'),
        ('TRANSIT', 'En transit'),
        ('DISTRIBUTED', 'Distribué'),
        ('UNREACHABLE', 'Injoignable'),
        ('POSTPONED', 'Reporté'),
        ('DELIVERING', 'En cours de livraison'),
        ('CANCELED', 'Annulé'),
        ('REJECTED', 'Refusé'),
        ('DELIVERED', 'Livré'),
    ], string="Statut de la Colis", help="Statut du colis depuis l'API SendIt")

    colis_code = fields.Char(string="Code Colis", help="Code unique du colis depuis SendIt API",readonly=True)
    last_status_update = fields.Datetime(string="Dernière mise à jour du statut",help="Date de la dernière mise à jour du statut du colis",readonly=True)
    #payment = fields.Char(string="Mode de paiment")
    '''added 07/07/2025'''

    def write(self, vals):
        """Override write method to check order status when line status changes"""
        result = super().write(vals)

        # If status_ligne_commande is being updated, check if we need to update order status
        if 'status_ligne_commande' in vals:
            orders_to_check = self.mapped('order_id')
            orders_to_check._check_and_update_order_status()

        return result
    @api.model
    def create(self, vals):
        """Override create method to check order status when new line is created"""
        result = super().create(vals)

        # Check order status after creating new line
        if result.order_id:
            result.order_id._check_and_update_order_status()

        return result
    '''end of add 07/07/2025'''
    @api.depends('product_id')
    def _compute_price_from_pricelist(self):
        """Compute price from product pricelist based on barcode"""
        for line in self:
            if line.product_id:
                # Search for pricelist item by product barcode
                pricelist_item = self.env['product.pricelist.item'].search([
                    ('product_id', '=', line.product_id.id)
                ], limit=1)

                if pricelist_item:
                    # Use the fixed price from pricelist
                    line.price = pricelist_item.fixed_price
                else:
                    # Fallback to product list price if not found in pricelist
                    line.price = line.product_id.list_price
            else:
                line.price = 0.0
    @api.depends('product_id')
    def _compute_magasin_and_stock(self):
        """Compute warehouse name and stock count for each product"""
        for line in self:
            if line.product_id:
                warehouse, stock_qty = line._get_warehouse_and_stock_for_product(line.product_id)
                line.magasin_name = warehouse.name if warehouse else "Aucun stock"
                line.stock_count = stock_qty
            else:
                line.magasin_name = ""
                line.stock_count = 0.0

    def action_refresh_stock(self):
        """Manual action to refresh stock information"""
        for line in self:
            if line.product_id:
                warehouse, stock_qty = line._get_warehouse_and_stock_for_product(line.product_id)
                line.magasin_name = warehouse.name if warehouse else "Aucun stock"
                line.stock_count = stock_qty
        return True

    @api.depends('product_id')
    def _compute_code_barre(self):
        """Compute barcode for each product"""
        for line in self:
            if line.product_id:
                line.code_barre = line.product_id.default_code or line.product_id.barcode or ''
            else:
                line.code_barre = ''

    def _get_warehouse_and_stock_for_product(self, product):
        """Find the warehouse that has the most stock for the given product and return stock quantity"""
        # Search for stock quants with available quantity
        quants = self.env['stock.quant'].search([
            ('product_id', '=', product.id),
            ('quantity', '>', 0),
            ('location_id.usage', '=', 'internal')
        ])

        if not quants:
            return None, 0.0

        # Find warehouse with the highest stock quantity
        best_warehouse = None
        best_stock_qty = 0.0

        # Group quants by warehouse and sum quantities
        warehouse_stock = {}

        for quant in quants:
            warehouse = self.env['stock.warehouse'].search([
                ('lot_stock_id', '=', quant.location_id.id)
            ], limit=1)

            if warehouse:
                if warehouse.id not in warehouse_stock:
                    warehouse_stock[warehouse.id] = {
                        'warehouse': warehouse,
                        'total_qty': 0.0
                    }
                warehouse_stock[warehouse.id]['total_qty'] += quant.quantity

        # Find warehouse with stock
        for warehouse_data in warehouse_stock.values():
            if warehouse_data['total_qty'] > best_stock_qty:
                best_warehouse = warehouse_data['warehouse']
                best_stock_qty = warehouse_data['total_qty']

        return best_warehouse, best_stock_qty

    '''added'''

    @api.model
    def cron_update_stock_disponible(self):
        """
        Simple cron job to update stock disponible for all order lines
        """
        _logger.info("Starting stock update cron...")

        # Get all order lines with barcode
        order_lines = self.search([
            ('code_barre', '!=', False),
            ('code_barre', '!=', '')
        ])

        updated_count = 0

        for line in order_lines:
            try:
                # Find product by barcode
                product = self.env['product.product'].search([
                    ('default_code', '=', line.code_barre)
                ], limit=1)

                if product:
                    # Get stock quantity
                    stock_qty = self._get_stock_quantity(product)

                    # Update stock count
                    line.stock_count = stock_qty
                    updated_count += 1

            except Exception as e:
                _logger.error("Error updating stock for line %d: %s", line.id, str(e))
                continue

        _logger.info("Stock update completed: %d lines updated", updated_count)

    def _get_stock_quantity(self, product):
        """Get total available stock for product"""
        stock_quants = self.env['stock.quant'].search([
            ('product_id', '=', product.id),
            ('location_id.usage', '=', 'internal')
        ])

        total_qty = sum(quant.quantity for quant in stock_quants)
        return total_qty
