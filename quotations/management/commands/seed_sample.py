from django.core.management.base import BaseCommand
from quotations.models import Quotation, QuotationItem
from decimal import Decimal
from datetime import date

from django.contrib.auth.models import User

class Command(BaseCommand):
    help = 'Seeds sample quotation and demo user accounts'

    def handle(self, *args, **options):
        # 1. Create or update demo users
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@maxflowcontrols.com', 'admin123', first_name='DINENDRA', last_name='CHARI')
            self.stdout.write(self.style.SUCCESS('Created superuser: admin / admin123 (DINENDRA CHARI)'))
        else:
            u = User.objects.get(username='admin')
            u.first_name = 'DINENDRA'
            u.last_name = 'CHARI'
            u.save()

        if not User.objects.filter(username='manager').exists():
            User.objects.create_user('manager', 'manager@maxflowcontrols.com', 'manager123', first_name='RAJESH', last_name='SHARMA')
            self.stdout.write(self.style.SUCCESS('Created user: manager / manager123 (RAJESH SHARMA)'))

        if Quotation.objects.filter(quotation_number='MCIPL/2025-26/0270/JSW-VASIND').exists():
            self.stdout.write(self.style.WARNING('Sample quotation already exists.'))
            return

        quote = Quotation.objects.create(
            company_name='Maxflow Controls ( I ) Pvt. Ltd.',
            company_address='18, Unique Industrial Estate, Off. Veer Savarkar Marg, Prabhadevi, Mumbai – 400 025',
            company_phone='022-2436 0131 / 32, 2437 1847',
            company_fax='022-2430 6945',
            company_email='mumbai@maxflowcontrols.com',
            company_gstin='27AABCM8025D1ZQ',
            company_pan='AABCM8025D',
            quotation_number='MCIPL/2025-26/0270/JSW-VASIND',
            quotation_date=date(2026, 3, 31),
            salutation='DEAR SIR,',
            subject='WE ARE PLEASED TO QUOTE FOR THE DANFOSS HYDRAULIC ITEM AGAINST YOUR TENDER Doc5585419069 - RFP - 4000141742-2900200709 -REVENUE SUPPLY AS FOLLOWS:',
            customer_name='M/S. JSW STEEL LTD.',
            customer_address='VASIND.',
            price_terms='F.O.R., VASIND.',
            discount_terms='NET.',
            tax_terms='AS INDICATED ABOVE.',
            payment_terms='100% AGAINST DELIVERY WITHIN 30 DAYS',
            validity_terms='30 DAYS.',
            special_notes='IN CASE OF ANY PRICE INCREASE / ADDL. SURCHARGE LEVIED BY OUR PRINCIPALS AT THE TIME OF DELIVERY, SUCH REVISED PRICE ONLY WILL APPLY. ALSO P.O. ONCE PLACED CANNOT BE CANCELLED OR AMENDED UNDER ANY CIRCUMSTANCES AS THE ITEM IS IMPORTED & WE ARE NOT INSISTING FOR ANY ADVANCE PAYMENT AS IN THE CASE OF OTHERS.',
            signatory_company='MAXFLOW CONTROLS (I) PVT. LTD.',
            signatory_name='DINENDRA CHARI',
            signatory_designation='MANAGER TECHNICAL',
            signatory_phone='8928386419'
        )

        QuotationItem.objects.create(
            quotation=quote,
            sr_no='7.3',
            description='DANFOSS VICKERS ( FORMERLY EATON-VICKERS ) MAKE MODULAR VALVE MODEL : DGMPC 5 ABK BAK 30',
            hsn_code='84818090',
            quantity=Decimal('6.00'),
            unit='NOS',
            unit_rate=Decimal('9645.00'),
            delivery_schedule='EX STOCK OR 6 – 8 WEEKS',
            gst_rate=Decimal('18.00'),
            amount=Decimal('57870.00')
        )

        QuotationItem.objects.create(
            quotation=quote,
            sr_no='7.4',
            description='DANFOSS VICKERS ( FORMERLY EATON-VICKERS ) MAKE VALVE CARTRIDGE MODEL : RV3-10-S-0-36/17.5',
            hsn_code='84818090',
            quantity=Decimal('6.00'),
            unit='NOS',
            unit_rate=Decimal('6495.00'),
            delivery_schedule='4 PCS EX -0STOCK OR 14 – 16 WEEKS',
            gst_rate=Decimal('18.00'),
            amount=Decimal('38970.00')
        )

        quote.recalculate_totals()
        self.stdout.write(self.style.SUCCESS(f'Sample quotation created: {quote.quotation_number} (Grand Total: Rs. {quote.grand_total})'))
