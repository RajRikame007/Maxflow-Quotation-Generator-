from django.test import TestCase, Client
from django.urls import reverse
from .models import Quotation, QuotationItem
from decimal import Decimal
from datetime import date

class QuotationTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.quotation = Quotation.objects.create(
            quotation_number='TEST-QTN-001',
            quotation_date=date.today(),
            customer_name='Test Client Pvt Ltd',
            customer_address='Test City'
        )
        self.item = QuotationItem.objects.create(
            quotation=self.quotation,
            sr_no='1',
            description='Test Hydraulic Valve',
            quantity=Decimal('2.00'),
            unit='NOS',
            unit_rate=Decimal('5000.00'),
            gst_rate=Decimal('18.00')
        )
        self.quotation.recalculate_totals()

    def test_home_view(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Maxflow Quotation Generator')

    def test_quotation_list_view(self):
        response = self.client.get(reverse('quotation_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'TEST-QTN-001')

    def test_quotation_detail_view(self):
        response = self.client.get(reverse('quotation_detail', args=[self.quotation.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Client Pvt Ltd')

    def test_pdf_download_view(self):
        response = self.client.get(reverse('quotation_pdf_download', args=[self.quotation.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(len(response.content) > 1000)

    def test_login_and_signatory_prefill(self):
        from django.contrib.auth.models import User
        from .models import UserProfile
        user = User.objects.create_user('testuser', 'test@example.com', 'password123', first_name='VIKRAM', last_name='MEHTA')
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.designation = 'CHIEF ENGINEER'
        profile.phone = '9876543210'
        profile.save()

        self.client.login(username='testuser', password='password123')
        
        response = self.client.get(reverse('quotation_create'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'VIKRAM MEHTA')
        self.assertContains(response, 'CHIEF ENGINEER')
        self.assertContains(response, '9876543210')

    def test_register_account_with_designation_and_cell_number(self):
        from django.contrib.auth.models import User
        from .models import UserProfile
        
        reg_data = {
            'first_name': 'Rahul',
            'last_name': 'Sharma',
            'username': 'rahul_s',
            'email': 'rahul@maxflowcontrols.com',
            'designation': 'Senior Sales Manager',
            'phone': '9820011223',
            'password1': 'StrongPass123!',
            'password2': 'StrongPass123!',
        }
        response = self.client.post(reverse('register'), data=reg_data, follow=True)
        self.assertEqual(response.status_code, 200)
        
        # Verify user was created
        user = User.objects.get(username='rahul_s')
        self.assertEqual(user.first_name, 'Rahul')
        self.assertEqual(user.last_name, 'Sharma')
        
        # Verify profile was created with designation and cell number
        profile = user.profile
        self.assertEqual(profile.designation, 'SENIOR SALES MANAGER')
        self.assertEqual(profile.phone, '9820011223')
        
        # Verify signatory details directly show in the quotation form
        qtn_response = self.client.get(reverse('quotation_create'))
        self.assertEqual(qtn_response.status_code, 200)
        self.assertContains(qtn_response, 'RAHUL SHARMA')
        self.assertContains(qtn_response, 'SENIOR SALES MANAGER')
        self.assertContains(qtn_response, '9820011223')

    def test_profile_update_view(self):
        from django.contrib.auth.models import User
        user = User.objects.create_user('edituser', 'edit@example.com', 'password123', first_name='Anil', last_name='Patel')
        self.client.login(username='edituser', password='password123')
        
        post_data = {
            'first_name': 'Anil Kumar',
            'last_name': 'Patel',
            'email': 'anil.patel@maxflow.com',
            'designation': 'Technical Director',
            'phone': '9123456789'
        }
        response = self.client.post(reverse('profile'), data=post_data, follow=True)
        self.assertEqual(response.status_code, 200)
        
        user.refresh_from_db()
        self.assertEqual(user.first_name, 'Anil Kumar')
        self.assertEqual(user.profile.designation, 'TECHNICAL DIRECTOR')
        self.assertEqual(user.profile.phone, '9123456789')

    def test_customer_list_and_search(self):
        from .models import Customer
        Customer.objects.create(
            name='JSW STEEL COATED PRODUCTS LIMITED',
            mobile='8709305772',
            gstin='27AACCM3988L1ZU',
            address='VILLAGE - VASIND, TALUKA - SHAHAPUR'
        )
        response = self.client.get(reverse('customer_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'JSW STEEL COATED PRODUCTS LIMITED')

        # Test search
        search_res = self.client.get(reverse('customer_list') + '?q=VASIND')
        self.assertContains(search_res, 'JSW STEEL COATED PRODUCTS LIMITED')

    def test_customer_search_api(self):
        from .models import Customer
        Customer.objects.create(
            name='ARV ENGINEERING CO. LLP',
            email='purchase1@arvengg.com',
            gstin='27ABJFA2735N1Z4'
        )
        response = self.client.get(reverse('customer_search_api') + '?q=ARV')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(len(data['customers']) > 0)
        self.assertEqual(data['customers'][0]['name'], 'ARV ENGINEERING CO. LLP')

    def test_product_search_api_and_list(self):
        from .models import Product
        Product.objects.create(
            category='EATON',
            model_code='6033556-001',
            description='24V DC COIL (EN124)',
            unit_rate=Decimal('2500.00'),
            is_active=True
        )
        Product.objects.create(
            category='HYDROLINE',
            model_code='003-SC3-020',
            description='STRAINER',
            unit_rate=Decimal('1200.00'),
            is_active=True
        )

        # 1. Search by code
        res1 = self.client.get(reverse('product_search_api') + '?q=6033556')
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()
        self.assertTrue(len(data1['products']) >= 1)
        self.assertEqual(data1['products'][0]['code'], '6033556-001')
        self.assertIn('24V DC COIL', data1['products'][0]['display_desc'])

        # 2. Search by flexible code ignoring hyphens, spaces, and letter case (e.g. v21051a)
        Product.objects.create(
            category='EATON',
            model_code='V210-5-1A-12-S214-INB',
            description='VANE PUMP',
            unit_rate=Decimal('12000.00'),
            is_active=True
        )
        res_v1 = self.client.get(reverse('product_search_api') + '?q=v21051a')
        self.assertEqual(res_v1.status_code, 200)
        v_codes = [p['code'] for p in res_v1.json()['products']]
        self.assertIn('V210-5-1A-12-S214-INB', v_codes)

        res_v2 = self.client.get(reverse('product_search_api') + '?q=v210 5 1a')
        self.assertEqual(res_v2.status_code, 200)
        self.assertIn('V210-5-1A-12-S214-INB', [p['code'] for p in res_v2.json()['products']])

        # 3. Search by brand
        res2 = self.client.get(reverse('product_search_api') + '?brand=HYDROLINE')
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertTrue(any(p['code'] == '003-SC3-020' for p in data2['products']))

        # 4. Product directory list page with flexible query
        res3 = self.client.get(reverse('product_list') + '?q=v21051a')
        self.assertEqual(res3.status_code, 200)
        self.assertContains(res3, 'V210-5-1A-12-S214-INB')

    def test_quotation_create_with_customer_id(self):
        from .models import Customer
        cust = Customer.objects.create(
            name='MAHINDRA & MAHINDRA LTD.',
            mobile='9821356433',
            gstin='27AAACM3025E1ZZ',
            address='Kandivli (E), Mumbai'
        )
        response = self.client.get(reverse('quotation_create') + f'?customer_id={cust.id}')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'MAHINDRA &amp; MAHINDRA LTD.')
        self.assertContains(response, '27AAACM3025E1ZZ')

    def test_customer_create_post(self):
        post_data = {
            'name': 'ZENITH VALVES INDIA',
            'gstin': '27AAACZ1234F1Z9',
            'mobile': '9820011223',
            'email': 'sales@zenithvalves.com',
            'address': 'Plot 45, Rabale MIDC, Navi Mumbai'
        }
        response = self.client.post(reverse('customer_create'), data=post_data, follow=True)
        self.assertEqual(response.status_code, 200)
        from .models import Customer
        self.assertTrue(Customer.objects.filter(name='ZENITH VALVES INDIA').exists())

    def test_customer_create_ajax(self):
        post_data = {
            'name': 'APEX HYDRAULICS LTD',
            'gstin': '27AAACA9999M1Z1',
            'mobile': '9876543210',
            'email': 'info@apex.com',
            'address': 'Thane West'
        }
        response = self.client.post(
            reverse('customer_create'),
            data=post_data,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['customer']['name'], 'APEX HYDRAULICS LTD')

    def test_exact_pf_freight_and_gst_calculation(self):
        q = Quotation.objects.create(
            quotation_number='TEST-CALC-PERFECT',
            quotation_date=date.today(),
            customer_name='CALC TEST CLIENT',
            discount_percentage=Decimal('5.00'),
            pf_percentage=Decimal('2.50'),
            freight_amount=Decimal('350.00')
        )
        QuotationItem.objects.create(
            quotation=q,
            sr_no='1',
            description='Hydraulic Pump Model A',
            quantity=Decimal('5.00'),
            unit='NOS',
            unit_rate=Decimal('1234.56'),
            gst_rate=Decimal('18.00')
        )
        q.recalculate_totals()

        self.assertEqual(q.subtotal, Decimal('6172.80'))
        self.assertEqual(q.discount_amount, Decimal('308.64'))
        self.assertEqual(q.pf_amount, Decimal('146.60'))
        self.assertEqual(q.freight_amount, Decimal('350.00'))
        self.assertEqual(q.taxable_amount, Decimal('6360.76'))
        self.assertEqual(q.tax_amount, Decimal('1144.94'))
        self.assertEqual(q.grand_total, Decimal('7505.70'))

    def test_quotation_edit_with_blank_pf_percentage(self):
        """Ensure submitting a quotation edit with blank/empty pf_percentage succeeds without NOT NULL error."""
        post_data = {
            'company_name': self.quotation.company_name,
            'company_address': self.quotation.company_address,
            'company_phone': self.quotation.company_phone,
            'company_email': self.quotation.company_email,
            'quotation_number': self.quotation.quotation_number,
            'quotation_date': str(self.quotation.quotation_date),
            'salutation': 'DEAR SIR,',
            'subject': 'QUOTATION NOTE',
            'customer_name': self.quotation.customer_name,
            'customer_address': self.quotation.customer_address,
            'price_terms': 'F.O.R., DESTINATION',
            'freight_terms': 'EXTRA',
            'pf_terms': 'NIL',
            'discount_terms': 'NET.',
            'tax_terms': '18% GST',
            'payment_terms': '30 DAYS',
            'validity_terms': '30 DAYS.',
            'signatory_company': 'MAXFLOW',
            'signatory_name': 'DINENDRA CHARI',
            'signatory_designation': 'MANAGER',
            # Blank/empty financial fields to reproduce the issue
            'discount_percentage': '',
            'discount_amount': '',
            'pf_percentage': '',
            'pf_amount': '',
            'freight_amount': '',
            'taxable_amount': '',
            'subtotal': '',
            'tax_amount': '',
            'grand_total': '',
            # Formset management form
            'items-TOTAL_FORMS': '1',
            'items-INITIAL_FORMS': '1',
            'items-MIN_NUM_FORMS': '0',
            'items-MAX_NUM_FORMS': '1000',
            'items-0-id': str(self.item.id),
            'items-0-sr_no': '1',
            'items-0-description': 'Testing Item Without PF',
            'items-0-quantity': '1',
            'items-0-unit': 'NOS',
            'items-0-unit_rate': '1000.00',
            'items-0-gst_rate': '18.00',
            'items-0-amount': '1000.00',
        }
        response = self.client.post(reverse('quotation_edit', args=[self.quotation.pk]), data=post_data)
        # Should redirect to quotation_detail on success
        self.assertEqual(response.status_code, 302)
        self.quotation.refresh_from_db()
        self.assertEqual(self.quotation.pf_percentage, Decimal('0.00'))
        self.assertEqual(self.quotation.subtotal, Decimal('1000.00'))

    def test_customer_edit_post(self):
        from .models import Customer
        cust = Customer.objects.create(
            name='DELTA ENGINEERING WORKS',
            mobile='9822001122',
            gstin='27AAACD1111E1Z0',
            address='Old Address, Pune'
        )
        post_data = {
            'name': 'DELTA ENGINEERING WORKS PVT LTD',
            'mobile': '9822998877',
            'email': 'contact@deltaengg.com',
            'gstin': '27AAACD1111E1Z0',
            'address': 'New Modern Facility, Hinjawadi Phase 2, Pune'
        }
        response = self.client.post(reverse('customer_edit', args=[cust.id]), data=post_data, follow=True)
        self.assertEqual(response.status_code, 200)

        cust.refresh_from_db()
        self.assertEqual(cust.name, 'DELTA ENGINEERING WORKS PVT LTD')
        self.assertEqual(cust.mobile, '9822998877')
        self.assertEqual(cust.email, 'contact@deltaengg.com')
        self.assertIn('Hinjawadi', cust.address)

    def test_customer_edit_ajax(self):
        from .models import Customer
        cust = Customer.objects.create(
            name='ALPHA PRECISION TOOLS',
            mobile='9123456789',
            gstin='27AAACA1234F1Z1',
            address='Nashik'
        )
        post_data = {
            'name': 'ALPHA PRECISION TOOLS & DIES',
            'mobile': '9988776655',
            'email': 'alpha@precision.com',
            'gstin': '27AAACA1234F1Z1',
            'address': 'Ambad MIDC, Nashik - 422010'
        }
        response = self.client.post(
            reverse('customer_edit', args=[cust.id]),
            data=post_data,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['customer']['name'], 'ALPHA PRECISION TOOLS & DIES')
        self.assertEqual(data['customer']['mobile'], '9988776655')

        cust.refresh_from_db()
        self.assertEqual(cust.name, 'ALPHA PRECISION TOOLS & DIES')

    def test_customer_edit_excel_sync(self):
        import tempfile
        import openpyxl
        from .models import Customer
        from .excel_sync import append_or_update_customer_in_excel

        # Create temporary workbook simulating customer address raj.xlsx
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.cell(row=2, column=1, value='PARTY NAME')
        ws.cell(row=2, column=2, value='EMAIL')
        ws.cell(row=2, column=3, value='MOBILE')
        ws.cell(row=2, column=4, value='PARTY GSTN')
        ws.cell(row=2, column=5, value='FULL ADDRESS IN TALLY')

        # Add initial row
        ws.cell(row=3, column=1, value='OMEGA VALVES')
        ws.cell(row=3, column=2, value='omega@old.com')
        ws.cell(row=3, column=3, value='9000000000')
        ws.cell(row=3, column=4, value='27AAACT9999M1Z9')
        ws.cell(row=3, column=5, value='Old Plant, Rabale')

        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
            tmp_path = tmp.name
        wb.save(tmp_path)

        try:
            cust = Customer.objects.create(
                name='OMEGA VALVES INTERNATIONAL',
                email='sales@omegavalves.com',
                mobile='9111111111',
                gstin='27AAACT9999M1Z9',
                address='New Global Center, Navi Mumbai'
            )

            success, msg = append_or_update_customer_in_excel(
                cust,
                original_name='OMEGA VALVES',
                filename=tmp_path
            )
            self.assertTrue(success)

            # Verify the same row 3 was updated rather than appending row 4
            updated_wb = openpyxl.load_workbook(tmp_path)
            updated_ws = updated_wb.active
            self.assertEqual(updated_ws.max_row, 3)
            self.assertEqual(updated_ws.cell(row=3, column=1).value, 'OMEGA VALVES INTERNATIONAL')
            self.assertEqual(updated_ws.cell(row=3, column=2).value, 'sales@omegavalves.com')
            self.assertEqual(updated_ws.cell(row=3, column=3).value, '9111111111')
            self.assertEqual(updated_ws.cell(row=3, column=5).value, 'New Global Center, Navi Mumbai')
        finally:
            import os
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_customer_delete_and_excel_sync(self):
        import tempfile
        import openpyxl
        from .models import Customer
        from .excel_sync import delete_customer_from_excel

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.cell(row=2, column=1, value='PARTY NAME')
        ws.cell(row=2, column=2, value='EMAIL')
        ws.cell(row=2, column=3, value='MOBILE')
        ws.cell(row=2, column=4, value='PARTY GSTN')
        ws.cell(row=2, column=5, value='FULL ADDRESS IN TALLY')

        ws.cell(row=3, column=1, value='ALPHA MOTORS PVT LTD')
        ws.cell(row=3, column=4, value='27AAACA1234A1Z1')
        ws.cell(row=4, column=1, value='BETA POWER LTD')
        ws.cell(row=4, column=4, value='27AAACB5678B1Z2')

        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
            tmp_path = tmp.name
        wb.save(tmp_path)

        try:
            cust = Customer.objects.create(
                name='ALPHA MOTORS PVT LTD',
                gstin='27AAACA1234A1Z1'
            )
            success, msg = delete_customer_from_excel(
                cust.name,
                gstin=cust.gstin,
                filename=tmp_path
            )
            self.assertTrue(success)

            updated_wb = openpyxl.load_workbook(tmp_path)
            updated_ws = updated_wb.active
            # After deleting row 3, row 4 (BETA POWER LTD) should now be row 3
            self.assertEqual(updated_ws.cell(row=3, column=1).value, 'BETA POWER LTD')
        finally:
            import os
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_product_create_and_excel_sync(self):
        import tempfile
        import openpyxl
        from .models import Product
        from .excel_sync import append_or_update_product_in_excel

        # Create temporary workbook
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.cell(row=2, column=1, value='Stock item Name')
        ws.cell(row=2, column=2, value='BRAND')
        ws.cell(row=2, column=3, value='DESCRIPTION')

        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
            tmp_path = tmp.name
        wb.save(tmp_path)

        try:
            prod = Product.objects.create(
                category='DANFOSS',
                model_code='OMM-32-151G0001',
                description='HYDRAULIC MOTOR 32CC',
                unit_rate=Decimal('14500.00'),
                is_active=True
            )
            success, msg = append_or_update_product_in_excel(prod, filename=tmp_path)
            self.assertTrue(success)

            updated_wb = openpyxl.load_workbook(tmp_path)
            updated_ws = updated_wb.active
            self.assertEqual(updated_ws.max_row, 3)
            self.assertEqual(updated_ws.cell(row=3, column=1).value, 'OMM-32-151G0001')
            self.assertEqual(updated_ws.cell(row=3, column=2).value, 'DANFOSS')
            self.assertEqual(updated_ws.cell(row=3, column=3).value, 'HYDRAULIC MOTOR 32CC')
        finally:
            import os
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_product_edit_and_excel_sync(self):
        import tempfile
        import openpyxl
        from .models import Product
        from .excel_sync import append_or_update_product_in_excel

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.cell(row=2, column=1, value='Stock item Name')
        ws.cell(row=2, column=2, value='BRAND')
        ws.cell(row=2, column=3, value='DESCRIPTION')

        ws.cell(row=3, column=1, value='OLD-CODE-100')
        ws.cell(row=3, column=2, value='EATON')
        ws.cell(row=3, column=3, value='OLD DESCRIPTION')

        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
            tmp_path = tmp.name
        wb.save(tmp_path)

        try:
            prod = Product.objects.create(
                category='EATON VICKERS',
                model_code='NEW-CODE-200',
                description='UPDATED VALVE 24V',
                unit_rate=Decimal('8200.00'),
                is_active=True
            )
            # Edit matching row 3 by original_code
            success, msg = append_or_update_product_in_excel(
                prod,
                original_code='OLD-CODE-100',
                filename=tmp_path
            )
            self.assertTrue(success)

            updated_wb = openpyxl.load_workbook(tmp_path)
            updated_ws = updated_wb.active
            self.assertEqual(updated_ws.max_row, 3) # Same row updated
            self.assertEqual(updated_ws.cell(row=3, column=1).value, 'NEW-CODE-200')
            self.assertEqual(updated_ws.cell(row=3, column=2).value, 'EATON VICKERS')
            self.assertEqual(updated_ws.cell(row=3, column=3).value, 'UPDATED VALVE 24V')
        finally:
            import os
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_product_delete_and_excel_sync(self):
        import tempfile
        import openpyxl
        from .excel_sync import delete_product_from_excel

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.cell(row=2, column=1, value='Stock item Name')
        ws.cell(row=2, column=2, value='BRAND')
        ws.cell(row=2, column=3, value='DESCRIPTION')

        ws.cell(row=3, column=1, value='PROD-TO-DELETE')
        ws.cell(row=3, column=2, value='HYDROLINE')
        ws.cell(row=3, column=3, value='FILTER ELEMENT')

        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
            tmp_path = tmp.name
        wb.save(tmp_path)

        try:
            success, msg = delete_product_from_excel('PROD-TO-DELETE', category='HYDROLINE', filename=tmp_path)
            self.assertTrue(success)

            updated_wb = openpyxl.load_workbook(tmp_path)
            updated_ws = updated_wb.active
            self.assertEqual(updated_ws.max_row, 2) # Row 3 deleted
        finally:
            import os
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_product_views_ajax_crud(self):
        from .models import Product

        # 1. Add Product via AJAX
        add_data = {
            'model_code': 'AJAX-VALVE-01',
            'category': 'YUKEN',
            'description': 'DIRECTIONAL VALVE DSG-01-3C2',
            'unit_rate': '4500.00',
            'hsn_code': '84812000',
            'unit': 'NOS',
            'gst_rate': '18.00'
        }
        res_add = self.client.post(
            reverse('product_create'),
            data=add_data,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(res_add.status_code, 200)
        data_add = res_add.json()
        self.assertTrue(data_add['success'])
        prod_id = data_add['product']['id']

        # Verify DB
        prod = Product.objects.get(id=prod_id)
        self.assertEqual(prod.model_code, 'AJAX-VALVE-01')

        # 2. Edit Product via AJAX
        edit_data = {
            'model_code': 'AJAX-VALVE-01-MOD',
            'category': 'YUKEN KOGYO',
            'description': 'MODIFIED VALVE DSG-01-3C2-A240',
            'unit_rate': '5200.00',
            'hsn_code': '84812000',
            'unit': 'NOS',
            'gst_rate': '18.00'
        }
        res_edit = self.client.post(
            reverse('product_edit', args=[prod_id]),
            data=edit_data,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(res_edit.status_code, 200)
        data_edit = res_edit.json()
        self.assertTrue(data_edit['success'])
        self.assertEqual(data_edit['product']['model_code'], 'AJAX-VALVE-01-MOD')

        prod.refresh_from_db()
        self.assertEqual(prod.model_code, 'AJAX-VALVE-01-MOD')

        # 3. Delete Product via AJAX
        res_del = self.client.post(
            reverse('product_delete', args=[prod_id]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(res_del.status_code, 200)
        data_del = res_del.json()
        self.assertTrue(data_del['success'])
        self.assertFalse(Product.objects.filter(id=prod_id).exists())




