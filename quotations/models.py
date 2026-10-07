import re
from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from .utils import number_to_words_inr, get_customer_code

def get_next_quotation_number(prefix="QTN/MCIPL/26-27/"):
    """
    Auto-generates sequential quotation number like QTN/MCIPL/26-27/001, QTN/MCIPL/26-27/002, etc.
    Finds the highest existing sequence number with this prefix and increments by 1.
    """
    existing_numbers = Quotation.objects.filter(quotation_number__startswith=prefix).values_list('quotation_number', flat=True)
    max_num = 0
    pattern = re.compile(rf"^{re.escape(prefix)}(\d+)$")
    
    for num_str in existing_numbers:
        match = pattern.match(num_str.strip())
        if match:
            try:
                num = int(match.group(1))
                if num > max_num:
                    max_num = num
            except ValueError:
                pass
                
    next_num = max_num + 1
    return f"{prefix}{next_num:03d}"

class Quotation(models.Model):
    # Company Details (Pre-filled with defaults matching reference, but editable)
    company_name = models.CharField(max_length=255, default='Maxflow Controls ( I ) Pvt. Ltd.')
    company_address = models.TextField(default='18, Unique Industrial Estate, Off. Veer Savarkar Marg, Prabhadevi, Mumbai – 400 025')
    company_phone = models.CharField(max_length=100, default='022-2436 0131 / 32, 2437 1847')
    company_fax = models.CharField(max_length=100, default='022-2430 6945', blank=True, null=True)
    company_email = models.EmailField(default='mumbai@maxflowcontrols.com')
    company_gstin = models.CharField(max_length=50, default='27AABCM8025D1ZQ', blank=True, null=True, verbose_name="Company GSTIN")
    company_pan = models.CharField(max_length=50, default='AABCM8025D', blank=True, null=True, verbose_name="Company PAN")

    # Quotation Metadata
    quotation_number = models.CharField(max_length=100, unique=True, default=get_next_quotation_number, verbose_name="Quotation / Ref. No.")
    quotation_date = models.DateField(default=timezone.now, verbose_name="Quotation Date")
    salutation = models.CharField(max_length=100, default='DEAR SIR,')
    subject = models.TextField(
        default='WE ARE PLEASED TO QUOTE FOR THE DANFOSS HYDRAULIC ITEM AGAINST YOUR TENDER / INQUIRY AS FOLLOWS:',
        verbose_name="Subject / Opening Note"
    )

    # Customer Details
    customer_name = models.CharField(max_length=255, verbose_name="Customer / Company Name")
    customer_address = models.TextField(verbose_name="Customer Address")
    customer_phone = models.CharField(max_length=50, blank=True, null=True)
    customer_email = models.EmailField(blank=True, null=True)
    customer_gstin = models.CharField(max_length=50, blank=True, null=True, verbose_name="Customer GSTIN")

    # Commercial Terms & Conditions
    price_terms = models.CharField(max_length=255, default='F.O.R., DESTINATION', verbose_name="Prices Terms")
    freight_terms = models.CharField(max_length=255, default='EXTRA TO YOUR ACCOUNT', verbose_name="Freight Terms")
    pf_terms = models.CharField(max_length=255, default='NIL', verbose_name="P&F Terms")
    discount_terms = models.CharField(max_length=255, default='NET.', verbose_name="Discount Terms")
    tax_terms = models.CharField(max_length=255, default='AS INDICATED ABOVE (GST Extra)', verbose_name="Tax Terms")
    payment_terms = models.CharField(max_length=255, default='100% AGAINST DELIVERY WITHIN 30 DAYS', verbose_name="Payment Terms")
    validity_terms = models.CharField(max_length=255, default='30 DAYS.', verbose_name="Validity")
    special_notes = models.TextField(
        default='IN CASE OF ANY PRICE INCREASE / ADDL. SURCHARGE LEVIED BY OUR PRINCIPALS AT THE TIME OF DELIVERY, SUCH REVISED PRICE ONLY WILL APPLY. ALSO P.O. ONCE PLACED CANNOT BE CANCELLED OR AMENDED UNDER ANY CIRCUMSTANCES AS THE ITEM IS IMPORTED & WE ARE NOT INSISTING FOR ANY ADVANCE PAYMENT AS IN THE CASE OF OTHERS.',
        blank=True, null=True,
        verbose_name="Special / P.N. Notes"
    )

    # Authorized Signatory
    signatory_company = models.CharField(max_length=255, default='MAXFLOW CONTROLS (I) PVT. LTD.')
    signatory_name = models.CharField(max_length=100, default='DINENDRA CHARI')
    signatory_designation = models.CharField(max_length=100, default='MANAGER TECHNICAL')
    signatory_phone = models.CharField(max_length=50, default='8928386419', blank=True, null=True)

    # Calculated Financial Totals
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), blank=True, null=True)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), blank=True, null=True, verbose_name="Discount %")
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), blank=True, null=True)
    pf_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), blank=True, null=True, verbose_name="P&F %")
    pf_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), blank=True, null=True, verbose_name="P&F Amount (Rs.)")
    freight_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), blank=True, null=True, verbose_name="Freight (Rs.)")
    taxable_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), blank=True, null=True, verbose_name="Taxable Amount (Rs.)")
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), blank=True, null=True)
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), blank=True, null=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Quotation"
        verbose_name_plural = "Quotations"

    @property
    def gst_rates_display(self):
        """Returns clean string of GST rates on items, e.g. '18%' or '18%, 12%'"""
        rates = []
        for item in self.items.all():
            if item.gst_rate is not None and item.gst_rate > 0:
                rate_val = int(item.gst_rate) if item.gst_rate == int(item.gst_rate) else item.gst_rate
                rate_str = f"{rate_val}%"
                if rate_str not in rates:
                    rates.append(rate_str)
        if rates:
            return ", ".join(rates)
        return ""

    def __str__(self):
        return f"{self.quotation_number} - {self.customer_name}"

    def recalculate_totals(self):
        """
        Calculates financial totals with exact 2-decimal precision:
        1. Subtotal = sum of (qty * unit_rate)
        2. Discount = subtotal * (discount_percentage / 100)
        3. P&F = (subtotal - discount) * (pf_percentage / 100)
        4. Freight in Rupees = freight_amount
        5. Taxable Amount = (subtotal - discount) + P&F + Freight
        6. GST calculated on Taxable Amount based on item GST rates
        7. Grand Total = Taxable Amount + GST
        """
        from decimal import Decimal, ROUND_HALF_UP

        items = self.items.all()
        calc_subtotal = Decimal('0.00')
        raw_item_tax = Decimal('0.00')

        for item in items:
            qty = item.quantity if item.quantity is not None else Decimal('0.00')
            rate = item.unit_rate if item.unit_rate is not None else Decimal('0.00')
            item_amt = (Decimal(str(qty)) * Decimal(str(rate))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            calc_subtotal += item_amt
            if item.gst_rate is not None and item.gst_rate > 0:
                raw_item_tax += (item_amt * Decimal(str(item.gst_rate))) / Decimal('100.00')

        self.subtotal = calc_subtotal

        # 1. Discount
        disc_pct = Decimal(str(self.discount_percentage)) if self.discount_percentage else Decimal('0.00')
        self.discount_amount = ((calc_subtotal * disc_pct) / Decimal('100.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        after_discount = calc_subtotal - self.discount_amount

        # 2. P&F with percentage
        pf_pct = Decimal(str(self.pf_percentage)) if self.pf_percentage else Decimal('0.00')
        self.pf_amount = ((after_discount * pf_pct) / Decimal('100.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # 3. Freight in rupees
        frt_amt = Decimal(str(self.freight_amount)) if self.freight_amount else Decimal('0.00')
        self.freight_amount = frt_amt.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # 4. Taxable Price (Base after discount + P&F + Freight)
        calc_taxable = after_discount + self.pf_amount + self.freight_amount
        self.taxable_amount = calc_taxable.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # 5. GST calculation on the final taxable price
        if calc_subtotal > Decimal('0.00'):
            effective_gst_rate = (raw_item_tax * Decimal('100.00')) / calc_subtotal
            calc_tax = (self.taxable_amount * effective_gst_rate) / Decimal('100.00')
        else:
            calc_tax = Decimal('0.00')

        self.tax_amount = calc_tax.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # 6. Grand total (exact precision, no integer rounding)
        self.grand_total = (self.taxable_amount + self.tax_amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        self.save()

    def save(self, *args, **kwargs):
        from decimal import Decimal
        decimal_zero_fields = [
            'discount_percentage', 'discount_amount',
            'pf_percentage', 'pf_amount',
            'freight_amount', 'taxable_amount',
            'subtotal', 'tax_amount', 'grand_total'
        ]
        for field in decimal_zero_fields:
            if getattr(self, field, None) is None:
                setattr(self, field, Decimal('0.00'))
        super().save(*args, **kwargs)



class QuotationItem(models.Model):
    UNIT_CHOICES = [
        ('PCS', 'PCS'),
        ('SET', 'SET'),
        ('NOS', 'NOS'),
        ('MTR', 'MTR'),
        ('KG', 'KG'),
        ('LOT', 'LOT'),
        ('PAIR','PAIR'),
    ]

    quotation = models.ForeignKey(Quotation, related_name='items', on_delete=models.CASCADE)
    sr_no = models.CharField(max_length=20, default='1', verbose_name="Sr. #")
    description = models.TextField(blank=True, default='', verbose_name="Description of Item")
    hsn_code = models.CharField(max_length=50, blank=True, default='', verbose_name="HSN Code")
    quantity = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=None, verbose_name="Qty.")
    unit = models.CharField(max_length=30, choices=UNIT_CHOICES, default='NOS', verbose_name="Unit")
    unit_rate = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), blank=True, null=True, verbose_name="Unit Rate (Rs.)")
    delivery_schedule = models.CharField(max_length=150, blank=True, default='EX STOCK', verbose_name="Del. Schedule")
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, default=None, verbose_name="GST %")
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), blank=True, null=True, verbose_name="Amount (Rs.)")

    class Meta:
        ordering = ['id']

    def __str__(self):
        desc = self.description or "No description"
        return f"{self.sr_no}. {desc[:40]}"

    def save(self, *args, **kwargs):
        from decimal import Decimal
        qty = self.quantity if self.quantity is not None else Decimal('0.00')
        rate = self.unit_rate if self.unit_rate is not None else Decimal('0.00')
        self.unit_rate = rate
        self.amount = Decimal(str(qty)) * Decimal(str(rate))
        super().save(*args, **kwargs)


class Product(models.Model):
    category = models.CharField(max_length=100, default='GENERAL', blank=True, verbose_name="Category / Brand")
    model_code = models.CharField(max_length=200, db_index=True, verbose_name="Stock Item Name / Model Code")
    clean_code = models.CharField(max_length=200, db_index=True, blank=True, default='', verbose_name="Normalized Code (Alphanumeric)")
    description = models.TextField(blank=True, default='', verbose_name="Detailed Description")
    unit_rate = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), blank=True, null=True, verbose_name="Unit Rate (Rs.)")
    hsn_code = models.CharField(max_length=50, blank=True, default='84136090', verbose_name="HSN Code")
    unit = models.CharField(max_length=30, default='NOS', blank=True, verbose_name="Default Unit")
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('18.00'), blank=True, null=True, verbose_name="GST %")
    is_active = models.BooleanField(default=True, verbose_name="Active")

    class Meta:
        ordering = ['category', 'model_code']
        verbose_name = "Product / Price List Item"
        verbose_name_plural = "Products / Price List"
        indexes = [
            models.Index(fields=['model_code']),
            models.Index(fields=['clean_code']),
            models.Index(fields=['category']),
        ]

    def __str__(self):
        if self.description:
            return f"{self.model_code} - {self.description}"
        return self.model_code

    def save(self, *args, **kwargs):
        if not self.category or not str(self.category).strip():
            self.category = 'GENERAL'
        else:
            self.category = str(self.category).strip().upper()

        if self.model_code:
            self.clean_code = re.sub(r'[^A-Za-z0-9]', '', str(self.model_code)).upper()
        else:
            self.clean_code = ''

        if not self.unit or not str(self.unit).strip():
            self.unit = 'NOS'
        else:
            self.unit = str(self.unit).strip().upper()

        if self.unit_rate is None:
            self.unit_rate = Decimal('0.00')

        if not self.hsn_code or not str(self.hsn_code).strip():
            self.hsn_code = '84136090'

        if self.gst_rate is None:
            self.gst_rate = Decimal('18.00')

        super().save(*args, **kwargs)


class Customer(models.Model):
    name = models.CharField(max_length=255, unique=True, verbose_name="Party / Customer Name")
    email = models.CharField(max_length=150, blank=True, default='', verbose_name="Email")
    mobile = models.CharField(max_length=100, blank=True, default='', verbose_name="Mobile / Phone")
    gstin = models.CharField(max_length=50, blank=True, default='', verbose_name="GSTIN")
    address = models.TextField(blank=True, default='', verbose_name="Full Address")
    is_active = models.BooleanField(default=True, verbose_name="Active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = "Customer / Client"
        verbose_name_plural = "Customers / Clients"

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    designation = models.CharField(max_length=100, blank=True, default='MANAGER TECHNICAL', verbose_name="Designation")
    phone = models.CharField(max_length=50, blank=True, default='', verbose_name="Cell Number / Mobile")

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

    def __str__(self):
        return f"{self.user.username} Profile ({self.designation})"


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)


def get_next_proforma_number(customer_name=None, date=None):
    """
    Auto-generates sequential Proforma number matching company pattern:
    e.g. MCIPL/09/2627/0106/HSE
    Pattern: MCIPL/{MM}/{FY}/{SEQ:04d}/{CUST_CODE}
    """
    now = date or timezone.now()
    month_str = now.strftime('%m')
    year = now.year
    if now.month >= 4:
        fy_str = f"{str(year)[-2:]}{str(year + 1)[-2:]}"
    else:
        fy_str = f"{str(year - 1)[-2:]}{str(year)[-2:]}"

    base_prefix = f"MCIPL/{month_str}/{fy_str}/"
    existing = Proforma.objects.filter(proforma_number__startswith=base_prefix).values_list('proforma_number', flat=True)

    max_seq = 105  # Default baseline sequence so next starts at 0106 matching reference series
    pattern = re.compile(rf"^{re.escape(base_prefix)}(\d+)")
    for p_num in existing:
        m = pattern.search(p_num)
        if m:
            try:
                seq = int(m.group(1))
                if seq > max_seq:
                    max_seq = seq
            except ValueError:
                pass

    next_seq = max_seq + 1
    cust_code = get_customer_code(customer_name) if customer_name else "GEN"
    return f"{base_prefix}{next_seq:04d}/{cust_code}"


class Proforma(models.Model):
    STATUS_CHOICES = [
        ('Draft', 'Draft'),
        ('Final', 'Final'),
        ('Cancelled', 'Cancelled'),
    ]

    TAX_TYPE_CHOICES = [
        ('GST', 'GST (18%)'),
        ('IGST', 'IGST (Inter-State 18%)'),
        ('CGST_SGST', 'CGST + SGST (Intra-State / Maharashtra 9% + 9%)'),
        ('EXEMPT', 'Exempt / No Tax (0%)'),
    ]

    # Reference to original quotation
    quotation = models.ForeignKey(
        Quotation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='proformas',
        verbose_name="Source Quotation"
    )
    quotation_number_ref = models.CharField(max_length=100, blank=True, default='', verbose_name="Quotation Reference No.")

    # Metadata & Status
    proforma_number = models.CharField(max_length=100, unique=True, verbose_name="Proforma Invoice No.")
    proforma_date = models.DateField(default=timezone.now, verbose_name="Proforma Date")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Draft', verbose_name="Status")

    # Company Details (Matching reference PDF)
    company_name = models.CharField(max_length=255, default='MAXFLOW CONTROLS (INDIA) PVT. LTD.')
    company_address = models.TextField(default='18, UNIQUE INDUSTRIAL ESTATE, OFF. VEER SAVARKAR MARG, PRABHADEVI, MUMBAI – 400 025')
    company_contact = models.TextField(default='TEL: 022 – 24360131 / 32, EMAIL: mumbai@maxflowcontrols.com / Cell:8928386417 / GST NO. 27AABCM8025D1ZQ')

    # Customer Details
    customer_name = models.CharField(max_length=255, verbose_name="Customer / Company Name")
    customer_address = models.TextField(verbose_name="Customer Address")
    customer_contact = models.CharField(max_length=100, blank=True, default='', verbose_name="Contact No.")
    customer_gstin = models.CharField(max_length=50, blank=True, default='', verbose_name="Customer GSTIN")
    customer_email = models.EmailField(blank=True, null=True, verbose_name="Customer Email")
    attention_to = models.CharField(max_length=150, blank=True, default='', verbose_name="Kind Attn.")

    # Salutation & PO/Opening Reference
    salutation = models.CharField(max_length=50, default='DEAR SIR,')
    po_reference = models.CharField(max_length=150, default='VERBAL P.O. THROUGH EMAIL', verbose_name="PO / Reference No.")
    po_date = models.DateField(default=timezone.now, verbose_name="PO Date")
    subject_note = models.TextField(
        default="WE ACKNOWLEDGE WITH THANKS RECEIPT OF YOUR {po_reference} DT. {po_date}, PLEASE FIND BELOW OUR PROFORMA INVOICE FOR YOUR KIND REFERENCE.",
        verbose_name="Reference / Subject Opening Note"
    )

    # Freight & Courier
    freight_label = models.CharField(max_length=100, default='DTDC BY AIR', verbose_name="Freight / Courier Charge Label")
    freight_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), blank=True, null=True, verbose_name="Freight / Courier (Rs.)")

    # Tax & Calculations
    tax_type = models.CharField(max_length=20, choices=TAX_TYPE_CHOICES, default='GST', blank=True, verbose_name="Tax Type")
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('18.00'), blank=True, null=True, verbose_name="Tax Rate %")

    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), blank=True, null=True, verbose_name="Item Subtotal (Rs.)")
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), blank=True, null=True, verbose_name="Discount %")
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), blank=True, null=True, verbose_name="Discount (Rs.)")
    subtotal_after_discount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), blank=True, null=True, verbose_name="Sub-Total after Discount (Rs.)")
    taxable_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), blank=True, null=True, verbose_name="Taxable Amount (Rs.)")

    cgst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), blank=True, null=True, verbose_name="CGST (Rs.)")
    sgst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), blank=True, null=True, verbose_name="SGST (Rs.)")
    igst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), blank=True, null=True, verbose_name="IGST (Rs.)")
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), blank=True, null=True, verbose_name="Total Tax (Rs.)")
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), blank=True, null=True, verbose_name="Total (Rs.)")

    # Rounding Off Total
    round_off_enabled = models.BooleanField(default=True, verbose_name="Enable Rounding Off Total")
    round_off_amount = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'), blank=True, null=True, verbose_name="Round Off (+/-)")
    rounded_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), blank=True, null=True, verbose_name="Rounding Off Total (Rs.)")

    # Advance Received & Balance Payable
    advance_label = models.CharField(max_length=200, default='ADVANCE RECEIVED IN OUR A/C', blank=True, verbose_name="Advance Received Description")
    advance_date = models.DateField(null=True, blank=True, verbose_name="Advance Received Date")
    advance_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), blank=True, null=True, verbose_name="Advance Received (Rs.)")
    balance_payable = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), blank=True, null=True, verbose_name="Balance Amount Payable by You (Rs.)")

    amount_in_words = models.CharField(max_length=500, blank=True, default='', verbose_name="Amount in Words")

    # Bank Details (Pre-filled with master reference details)
    bank_name = models.CharField(max_length=150, default='ICICI BANK LIMITED.')
    bank_branch = models.CharField(max_length=150, default='PRABHADEVI BRANCH.')
    bank_address = models.TextField(default='KALA ACADEMY, RAVINDRA NATYA MANDIR, PRABHADEVI,\nMUMBAI – 400 028.')
    bank_telephone = models.CharField(max_length=100, default='022 6819 1509.')
    bank_account_name = models.CharField(max_length=200, default='MAXFLOW CONTROLS INDIA PRIVATE LIMITED.')
    bank_account_no = models.CharField(max_length=100, default='005705027366')
    bank_ifsc = models.CharField(max_length=50, default='ICIC0000057')
    bank_micr = models.CharField(max_length=50, default='400229013')

    # Terms & Signatory
    request_note = models.TextField(default='WE KINDLY REQUEST YOU TO ACKNOWLEDGE THE RECEIPT OF THE ABOVE PROFORMA INVOICE.')
    signatory_company = models.CharField(max_length=200, default='MAXFLOW CONTROLS (I) PVT. LTD.')
    signatory_name = models.CharField(max_length=100, default='Jitendra Desai')
    signatory_designation = models.CharField(max_length=100, default='Manager-Sales (Mumbai)')

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_proformas')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Proforma Invoice"
        verbose_name_plural = "Proforma Invoices"

    def __str__(self):
        return f"{self.proforma_number} - {self.customer_name}"

    @property
    def formatted_ref_text(self):
        """Generates dynamic PO reference note if template placeholder is used. Formatted in capital letters for Proforma."""
        from datetime import datetime
        p_date = ''
        if self.po_date:
            if hasattr(self.po_date, 'strftime'):
                p_date = self.po_date.strftime('%d/%m/%Y')
            else:
                try:
                    str_val = str(self.po_date).strip()
                    dt = datetime.strptime(str_val, '%Y-%m-%d').date()
                    p_date = dt.strftime('%d/%m/%Y')
                except Exception:
                    p_date = str(self.po_date)

        po_ref = (self.po_reference or 'VERBAL P.O. THROUGH EMAIL').strip().upper()
        note = (self.subject_note or '').strip()

        # If previous wording exists or blank, replace with master wording
        if not note or 'Ref to your Purchase Order#:' in note:
            note = "WE ACKNOWLEDGE WITH THANKS RECEIPT OF YOUR {po_reference} DT. {po_date}, PLEASE FIND BELOW OUR PROFORMA INVOICE FOR YOUR KIND REFERENCE."

        # Case-insensitive replacement for placeholders
        for ph in ['{po_reference}', '{PO_REFERENCE}', '{po_ref}', '{PO_REF}']:
            note = note.replace(ph, po_ref)
        for ph in ['{po_date}', '{PO_DATE}']:
            note = note.replace(ph, p_date)

        return note.strip().upper()

    @property
    def half_tax_rate(self):
        """Half of tax rate for CGST/SGST display (e.g. 18% -> 9%)"""
        rate = self.tax_rate if self.tax_rate else Decimal('18.00')
        return rate / Decimal('2.00')

    @property
    def has_advance(self):
        """Returns True if a valid positive advance amount is entered."""
        try:
            from decimal import Decimal
            return bool(self.advance_amount and Decimal(str(self.advance_amount)) > Decimal('0.00'))
        except Exception:
            return False

    @property
    def advance_display_label(self):
        """Formats advance received line, e.g. 'ADVANCE RECEIVED ON OUR A/C DT 13.03.26'"""
        base = (self.advance_label or "ADVANCE RECEIVED IN OUR A/C").strip()
        if self.advance_date:
            from datetime import date, datetime
            if hasattr(self.advance_date, 'strftime'):
                d_formatted = self.advance_date.strftime('%d.%m.%y')
                d_full = self.advance_date.strftime('%d.%m.%Y')
            else:
                try:
                    str_val = str(self.advance_date).strip()
                    dt = datetime.strptime(str_val, '%Y-%m-%d').date()
                    d_formatted = dt.strftime('%d.%m.%y')
                    d_full = dt.strftime('%d.%m.%Y')
                except Exception:
                    d_formatted = str(self.advance_date)
                    d_full = d_formatted
            date_str = f"DT {d_formatted}"
            if date_str not in base and f"DT {d_full}" not in base:
                return f"{base} {date_str}".strip()
        return base

    @property
    def discount_display_label(self):
        """Formats discount label, e.g. 'DISCOUNT 15% LESS'"""
        if self.discount_percentage and self.discount_percentage > Decimal('0.00'):
            pct = int(self.discount_percentage) if self.discount_percentage == int(self.discount_percentage) else self.discount_percentage
            return f"DISCOUNT {pct}% LESS"
        return "DISCOUNT LESS"

    @property
    def gst_display_label(self):
        """Formats GST line, e.g. 'GST ADD @18%', 'GST ADD @12%', or 'GST ADD'"""
        if self.tax_rate is not None and self.tax_rate > Decimal('0.00'):
            pct = int(self.tax_rate) if self.tax_rate == int(self.tax_rate) else self.tax_rate
            return f"GST ADD @{pct}%"
        elif self.tax_amount and self.tax_amount > Decimal('0.00'):
            return "GST ADD"
        return "GST ADD @0%"


    def recalculate_totals(self, commit=True):
        """
        Recalculates financial totals with exact 2-decimal precision:
        1. Subtotal = sum of (qty * unit_rate)
        2. Discount % / Discount Amount -> Subtotal after Discount
        3. Taxable Amount = Subtotal after Discount + Freight
        4. GST (Unified GST, customizable by rate % or manual amount)
        5. Total = Taxable Amount + GST
        6. Rounding Off Total = nearest whole rupee (round_off_amount = rounded_total - grand_total)
        7. Advance Received -> Balance Amount Payable by You
        8. Amount in words updated (balance if advance exists, else rounded total)
        """
        from decimal import Decimal, ROUND_HALF_UP

        items = self.items.all()
        calc_subtotal = Decimal('0.00')
        for item in items:
            qty = item.quantity if item.quantity is not None else Decimal('0.00')
            rate = item.unit_rate if item.unit_rate is not None else Decimal('0.00')
            item_amt = (Decimal(str(qty)) * Decimal(str(rate))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            calc_subtotal += item_amt

        self.subtotal = calc_subtotal

        # 2. Discount
        disc_pct = Decimal(str(self.discount_percentage)) if self.discount_percentage else Decimal('0.00')
        if disc_pct > Decimal('0.00'):
            self.discount_amount = ((self.subtotal * disc_pct) / Decimal('100.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        else:
            disc = Decimal(str(self.discount_amount)) if self.discount_amount else Decimal('0.00')
            self.discount_amount = disc.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        self.subtotal_after_discount = (self.subtotal - self.discount_amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        if self.subtotal_after_discount < Decimal('0.00'):
            self.subtotal_after_discount = Decimal('0.00')

        # 3. Taxable Amount (Subtotal after discount - courier/freight charges removed)
        self.freight_amount = Decimal('0.00')
        self.taxable_amount = self.subtotal_after_discount

        # 4. GST Tax (Unified GST without CGST/SGST split, customizable by user)
        rate = Decimal(str(self.tax_rate)) if self.tax_rate is not None else Decimal('18.00')
        if rate > Decimal('0.00'):
            calc_tax = ((self.taxable_amount * rate) / Decimal('100.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            # If manual tax amount is provided and matches within tolerance (e.g. rate precision rounding)
            if self.tax_amount and abs(self.tax_amount - calc_tax) <= Decimal('1.00'):
                pass
            else:
                self.tax_amount = calc_tax
        else:
            tax = Decimal(str(self.tax_amount)) if self.tax_amount else Decimal('0.00')
            self.tax_amount = tax.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        self.igst_amount = self.tax_amount
        self.cgst_amount = Decimal('0.00')
        self.sgst_amount = Decimal('0.00')

        # 5. Grand Total (Before Rounding)
        self.grand_total = (self.taxable_amount + self.tax_amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # 6. Rounding Off
        if self.round_off_enabled:
            self.rounded_total = self.grand_total.quantize(Decimal('1'), rounding=ROUND_HALF_UP).quantize(Decimal('0.01'))
            self.round_off_amount = (self.rounded_total - self.grand_total).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        else:
            self.round_off_amount = Decimal('0.00')
            self.rounded_total = self.grand_total

        # 7. Advance & Balance
        adv = Decimal(str(self.advance_amount)) if self.advance_amount else Decimal('0.00')
        self.advance_amount = adv.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        self.balance_payable = (self.rounded_total - self.advance_amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # 8. Amount in words
        final_for_words = self.balance_payable if self.advance_amount > Decimal('0.00') else self.rounded_total
        self.amount_in_words = number_to_words_inr(final_for_words)

        if commit:
            self.save()


class ProformaItem(models.Model):
    proforma = models.ForeignKey(Proforma, related_name='items', on_delete=models.CASCADE)
    sr_no = models.CharField(max_length=20, default='01.', verbose_name="Sr. #")
    description = models.TextField(blank=True, default='', verbose_name="Item Description")
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('1.00'), verbose_name="Qty.")
    unit = models.CharField(max_length=30, default='No', verbose_name="Unit")
    unit_rate = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), blank=True, null=True, verbose_name="Unit Rate (Rs.)")
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), blank=True, null=True, verbose_name="Amount (Rs.)")

    class Meta:
        ordering = ['id']

    def __str__(self):
        desc = self.description or "No description"
        return f"{self.sr_no} {desc[:40]}"

    @property
    def qty_display(self):
        """Formats quantity e.g. '01 No' or '5 PCS' like in the reference PDF."""
        if self.quantity is None:
            return ""
        qty_int = int(self.quantity) if self.quantity == int(self.quantity) else self.quantity
        if isinstance(qty_int, int) and 0 < qty_int < 10:
            qty_str = f"{qty_int:02d}"
        else:
            qty_str = f"{qty_int}"
        unit_str = f" {self.unit}" if self.unit else ""
        return f"{qty_str}{unit_str}".strip()

    def save(self, *args, **kwargs):
        from decimal import Decimal
        qty = self.quantity if self.quantity is not None else Decimal('0.00')
        rate = self.unit_rate if self.unit_rate is not None else Decimal('0.00')
        self.unit_rate = rate
        self.amount = Decimal(str(qty)) * Decimal(str(rate))
        super().save(*args, **kwargs)


