{
    'name': 'Loyalty Gift Card Custom Image',
    'version': '17.0.1.0.0',
    'summary': 'Overrides the gift card report to use a custom image',
    'description': """
        Inherits loyalty.gift_card_report to replace the default gift card
        image with a custom one located in this module's static folder.
    """,
    'category': 'Sales/Loyalty',
    'author': 'Anass',
    'depends': ['loyalty'],
    'data': [
        'report/gift_card_report_template.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
