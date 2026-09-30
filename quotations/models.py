import re
from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

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
    description = models.TextField(verbose_name="Description of Item")
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
        return f"{self.sr_no}. {self.description[:40]}"

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

