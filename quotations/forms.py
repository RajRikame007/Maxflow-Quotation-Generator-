from decimal import Decimal
from django import forms
from django.forms import inlineformset_factory
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import Quotation, QuotationItem, Customer, Product, UserProfile, Proforma, ProformaItem

class ProductForm(forms.ModelForm):
    unit = forms.CharField(
        max_length=30,
        required=False,
        initial='NOS',
        widget=forms.TextInput(attrs={'class': 'form-control text-uppercase', 'placeholder': 'NOS'})
    )
    category = forms.CharField(
        max_length=100,
        required=False,
        initial='GENERAL',
        widget=forms.TextInput(attrs={'class': 'form-control text-uppercase', 'placeholder': 'e.g. EATON, DANFOSS, HYDROLINE', 'list': 'brands-datalist'})
    )
    unit_rate = forms.DecimalField(
        required=False,
        min_value=0,
        decimal_places=2,
        widget=forms.TextInput(attrs={'class': 'form-control item-rate', 'placeholder': '0.00', 'inputmode': 'decimal', 'autocomplete': 'off'})
    )
    hsn_code = forms.CharField(
        max_length=50,
        required=False,
        initial='84136090',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '84136090'})
    )
    gst_rate = forms.DecimalField(
        required=False,
        initial=18.00,
        min_value=0,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': '18.00'})
    )

    class Meta:
        model = Product
        fields = ['model_code', 'category', 'description', 'unit_rate', 'unit', 'hsn_code', 'gst_rate']
        widgets = {
            'model_code': forms.TextInput(attrs={'class': 'form-control fw-bold font-monospace', 'placeholder': 'e.g. 6033556-001 or D45-VALVE', 'required': 'required'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Detailed Item Description (e.g. 24V DC COIL (EN124))'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            val = self.initial.get('unit_rate')
            if not self.instance.pk:
                if val in [0, Decimal('0.00'), Decimal('0'), '0.00', '0', None]:
                    self.initial['unit_rate'] = ''
            elif self.instance.unit_rate is not None:
                self.initial['unit_rate'] = f"{self.instance.unit_rate:.2f}"

    def clean_unit(self):
        val = self.cleaned_data.get('unit')
        if not val or not str(val).strip():
            return 'NOS'
        return str(val).strip().upper()

    def clean_category(self):
        val = self.cleaned_data.get('category')
        if not val or not str(val).strip():
            return 'GENERAL'
        return str(val).strip().upper()

    def clean_unit_rate(self):
        val = self.cleaned_data.get('unit_rate')
        if val is None or str(val).strip() == '':
            from decimal import Decimal
            return Decimal('0.00')
        return val

    def clean_hsn_code(self):
        val = self.cleaned_data.get('hsn_code')
        if not val or not str(val).strip():
            return '84136090'
        return str(val).strip()

    def clean_gst_rate(self):
        val = self.cleaned_data.get('gst_rate')
        if val is None or str(val).strip() == '':
            from decimal import Decimal
            return Decimal('18.00')
        return val

class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['name', 'gstin', 'mobile', 'email', 'address']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control fw-bold', 'placeholder': 'Party / Customer Name (e.g. TATA STEEL LTD.)', 'required': 'required'}),
            'gstin': forms.TextInput(attrs={'class': 'form-control text-uppercase', 'placeholder': 'e.g. 27AAACT2803M1ZB'}),
            'mobile': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 9820012345 / 022-24360131'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'e.g. purchase@company.com'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Full Registered Tally Address & Location'}),
        }


class UserRegistrationForm(UserCreationForm):
    first_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name (e.g. Dinendra)'}))
    last_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name (e.g. Chari)'}))
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'name@maxflowcontrols.com'}))
    designation = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control text-uppercase', 'placeholder': 'e.g. MANAGER TECHNICAL'})
    )
    phone = forms.CharField(
        max_length=50,
        required=False,
        label="Cell Number / Mobile",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 8928386419 / 9820012345'})
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Choose username'}),
        }

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            raw_desig = self.cleaned_data.get('designation', '')
            designation = raw_desig.strip().upper() if raw_desig else 'MANAGER TECHNICAL'
            phone = self.cleaned_data.get('phone', '').strip()
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.designation = designation
            profile.phone = phone
            profile.save()
        return user


class UserProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))

    class Meta:
        model = UserProfile
        fields = ['designation', 'phone']
        widgets = {
            'designation': forms.TextInput(attrs={'class': 'form-control text-uppercase', 'placeholder': 'e.g. MANAGER TECHNICAL'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 8928386419 / 9820012345'}),
        }

class QuotationForm(forms.ModelForm):
    class Meta:
        model = Quotation
        fields = [
            'company_name', 'company_address', 'company_phone', 'company_fax', 'company_email', 'company_gstin', 'company_pan',
            'quotation_number', 'quotation_date', 'salutation', 'subject',
            'customer_name', 'customer_address', 'customer_phone', 'customer_email', 'customer_gstin',
            'price_terms', 'freight_terms', 'pf_terms', 'discount_terms', 'tax_terms', 'payment_terms', 'validity_terms', 'special_notes',
            'signatory_company', 'signatory_name', 'signatory_designation', 'signatory_phone',
            'subtotal', 'discount_percentage', 'discount_amount',
            'pf_percentage', 'pf_amount', 'freight_amount', 'taxable_amount',
            'tax_amount', 'grand_total'
        ]
        widgets = {
            'company_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Company Name'}),
            'company_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Company Address'}),
            'company_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone Numbers'}),
            'company_fax': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Fax Number'}),
            'company_email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email Address'}),
            'company_gstin': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Company GSTIN'}),
            'company_pan': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Company PAN'}),

            'quotation_number': forms.TextInput(attrs={'class': 'form-control font-monospace fw-bold', 'placeholder': 'e.g. QTN/MCIPL/26-27/001'}),
            'quotation_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'salutation': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. DEAR SIR,'}),
            'subject': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Subject or opening quotation line'}),

            'customer_name': forms.TextInput(attrs={'class': 'form-control fw-bold', 'placeholder': 'e.g. JSW STEEL COATED PRODUCTS LIMITED', 'list': 'customer-name-datalist', 'autocomplete': 'off'}),
            'customer_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Customer Address & Plant Location'}),

            'customer_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Customer Phone'}),
            'customer_email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Customer Email'}),
            'customer_gstin': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Customer GSTIN'}),

            'price_terms': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. F.O.R., DESTINATION', 'list': 'price_terms_list'}),
            'freight_terms': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. EXTRA TO YOUR ACCOUNT', 'list': 'freight_terms_list'}),
            'pf_terms': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. NIL or 2%', 'list': 'pf_terms_list'}),
            'discount_terms': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. NET.'}),
            'tax_terms': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. AS INDICATED ABOVE (18% GST).'}),
            'payment_terms': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Payment terms (e.g. 100% ADVANCE AGAINST PROFORMA INVOICE...)'}),
            'validity_terms': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 30 DAYS.'}),
            'special_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Special note or P.N. clause...'}),

            'signatory_company': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Company representation'}),
            'signatory_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Signatory Name'}),
            'signatory_designation': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Signatory Designation'}),
            'signatory_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Mobile Number'}),

            'subtotal': forms.NumberInput(attrs={'class': 'form-control bg-light', 'readonly': 'readonly', 'id': 'id_subtotal'}),
            'discount_percentage': forms.NumberInput(attrs={'class': 'form-control', 'id': 'id_discount_percentage', 'step': '0.01', 'min': '0', 'max': '100', 'placeholder': '0.00'}),
            'discount_amount': forms.NumberInput(attrs={'class': 'form-control bg-light', 'readonly': 'readonly', 'id': 'id_discount_amount', 'step': '0.01'}),
            'pf_percentage': forms.NumberInput(attrs={'class': 'form-control', 'id': 'id_pf_percentage', 'step': '0.01', 'min': '0', 'max': '100', 'placeholder': '0.00'}),
            'pf_amount': forms.NumberInput(attrs={'class': 'form-control bg-light', 'readonly': 'readonly', 'id': 'id_pf_amount', 'step': '0.01'}),
            'freight_amount': forms.NumberInput(attrs={'class': 'form-control', 'id': 'id_freight_amount', 'step': '0.01', 'min': '0', 'placeholder': '0.00'}),
            'taxable_amount': forms.NumberInput(attrs={'class': 'form-control bg-light', 'readonly': 'readonly', 'id': 'id_taxable_amount', 'step': '0.01'}),
            'tax_amount': forms.NumberInput(attrs={'class': 'form-control bg-light', 'readonly': 'readonly', 'id': 'id_tax_amount'}),
            'grand_total': forms.NumberInput(attrs={'class': 'form-control bg-light fw-bold fs-5 text-primary', 'readonly': 'readonly', 'id': 'id_grand_total'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        from decimal import Decimal
        decimal_zero_fields = [
            'discount_percentage', 'discount_amount',
            'pf_percentage', 'pf_amount',
            'freight_amount', 'taxable_amount',
            'subtotal', 'tax_amount', 'grand_total'
        ]
        for field in decimal_zero_fields:
            if cleaned_data.get(field) is None:
                cleaned_data[field] = Decimal('0.00')
        return cleaned_data



class QuotationItemForm(forms.ModelForm):
    unit_rate = forms.DecimalField(
        required=False,
        min_value=0,
        decimal_places=2,
        widget=forms.TextInput(attrs={
            'class': 'form-control item-rate text-end',
            'placeholder': '0.00',
            'inputmode': 'decimal',
            'autocomplete': 'off'
        })
    )

    class Meta:
        model = QuotationItem
        fields = [
            'sr_no', 'description', 'hsn_code', 'quantity', 'unit', 'unit_rate', 'delivery_schedule', 'gst_rate', 'amount'
        ]
        widgets = {
            'sr_no': forms.TextInput(attrs={
                'class': 'form-control item-sr text-center fw-bold bg-light',
                'placeholder': '1',
                'style': 'min-width: 48px; padding-left: 2px; padding-right: 2px; font-size: 0.95rem; font-weight: bold;'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control item-desc',
                'rows': 2,
                'placeholder': 'Type description (Press Enter for new line)...',
                'autocomplete': 'off',
                'style': 'resize: vertical; min-height: 52px;'
            }),
            'hsn_code': forms.TextInput(attrs={'class': 'form-control item-hsn text-center', 'placeholder': 'HSN', 'list': 'hsn-code-list'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control item-qty text-center', 'step': 'any', 'min': '0'}),
            'unit': forms.Select(attrs={'class': 'form-select item-unit'}),
            'unit_rate': forms.TextInput(attrs={
                'class': 'form-control item-rate text-end',
                'placeholder': '0.00',
                'inputmode': 'decimal',
                'autocomplete': 'off'
            }),
            'delivery_schedule': forms.TextInput(attrs={'class': 'form-control item-del', 'placeholder': 'EX STOCK / 6-8 WEEKS'}),
            'gst_rate': forms.NumberInput(attrs={'class': 'form-control item-gst text-center', 'step': 'any', 'min': '0', 'placeholder': ''}),
            'amount': forms.TextInput(attrs={'class': 'form-control item-amount bg-light text-end', 'readonly': 'readonly'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            val = self.initial.get('unit_rate')
            if not self.instance.pk:
                if val in [0, Decimal('0.00'), Decimal('0'), '0.00', '0', None]:
                    self.initial['unit_rate'] = ''
            else:
                if val in [0, Decimal('0.00'), Decimal('0'), '0.00', '0', None] and (self.instance.unit_rate == 0 or self.instance.unit_rate is None):
                    self.initial['unit_rate'] = ''
                elif self.instance.unit_rate is not None:
                    self.initial['unit_rate'] = f"{self.instance.unit_rate:.2f}"

    def clean_unit_rate(self):
        val = self.cleaned_data.get('unit_rate')
        if val is None or str(val).strip() == '':
            return Decimal('0.00')
        return val

QuotationItemFormSet = inlineformset_factory(
    Quotation,
    QuotationItem,
    form=QuotationItemForm,
    extra=1,
    can_delete=True
)


class ProformaForm(forms.ModelForm):
    advance_amount = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control fw-bold text-danger text-end',
            'placeholder': '0.00',
            'id': 'id_advance_amount',
            'autocomplete': 'off'
        })
    )
    discount_amount = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control text-end',
            'placeholder': '0.00',
            'id': 'id_discount_amount',
            'autocomplete': 'off'
        })
    )
    tax_amount = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control text-end',
            'placeholder': '0.00',
            'id': 'id_tax_amount',
            'autocomplete': 'off'
        })
    )

    class Meta:
        model = Proforma
        fields = [
            'proforma_number', 'proforma_date', 'status', 'quotation_number_ref',
            'company_name', 'company_address', 'company_contact',
            'customer_name', 'customer_address', 'customer_contact', 'customer_gstin', 'customer_email', 'attention_to',
            'salutation', 'po_reference', 'po_date', 'subject_note',
            'freight_label', 'freight_amount',
            'tax_type', 'tax_rate',
            'subtotal', 'discount_percentage', 'discount_amount', 'subtotal_after_discount', 'taxable_amount',
            'cgst_amount', 'sgst_amount', 'igst_amount', 'tax_amount', 'grand_total',
            'round_off_enabled', 'round_off_amount', 'rounded_total',
            'advance_label', 'advance_date', 'advance_amount', 'balance_payable',
            'amount_in_words',
            'bank_name', 'bank_branch', 'bank_address', 'bank_telephone',
            'bank_account_name', 'bank_account_no', 'bank_ifsc', 'bank_micr',
            'request_note', 'signatory_company', 'signatory_name', 'signatory_designation'
        ]
        widgets = {
            'proforma_number': forms.TextInput(attrs={'class': 'form-control font-monospace fw-bold', 'placeholder': 'e.g. MCIPL/09/2627/0106/HSE'}),
            'proforma_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'status': forms.Select(attrs={'class': 'form-select fw-semibold'}),
            'quotation_number_ref': forms.TextInput(attrs={'class': 'form-control font-monospace', 'placeholder': 'Source Quotation Ref'}),

            'company_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Company Name'}),
            'company_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Company Address'}),
            'company_contact': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Phone, Email, GST'}),

            'customer_name': forms.TextInput(attrs={'class': 'form-control fw-bold', 'placeholder': 'Customer / Company Name', 'list': 'customer-name-datalist', 'autocomplete': 'off'}),
            'customer_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Full Billing / Delivery Address'}),
            'customer_contact': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 9804736661/ 9903555608'}),
            'customer_gstin': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Customer GSTIN'}),
            'customer_email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Customer Email'}),
            'attention_to': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. MR. RAJU GUPTA'}),

            'salutation': forms.TextInput(attrs={'class': 'form-control text-uppercase', 'placeholder': 'DEAR SIR,'}),
            'po_reference': forms.TextInput(attrs={'class': 'form-control text-uppercase', 'placeholder': 'e.g. VERBAL P.O. THROUGH EMAIL'}),
            'po_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'subject_note': forms.Textarea(attrs={'class': 'form-control text-uppercase', 'rows': 3, 'placeholder': 'WE ACKNOWLEDGE WITH THANKS RECEIPT OF YOUR {po_reference} DT. {po_date}, PLEASE FIND BELOW OUR PROFORMA INVOICE FOR YOUR KIND REFERENCE.'}),

            'freight_label': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. DTDC BY AIR / COURIER CHARGES'}),
            'freight_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'id': 'id_freight_amount'}),

            'tax_type': forms.Select(attrs={'class': 'form-select fw-semibold', 'id': 'id_tax_type'}),
            'tax_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'id': 'id_tax_rate'}),

            'subtotal': forms.NumberInput(attrs={'class': 'form-control bg-light', 'readonly': 'readonly', 'id': 'id_subtotal'}),
            'discount_percentage': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'max': '100', 'placeholder': '0.00', 'id': 'id_discount_percentage'}),
            'subtotal_after_discount': forms.NumberInput(attrs={'class': 'form-control bg-light', 'readonly': 'readonly', 'id': 'id_subtotal_after_discount'}),
            'taxable_amount': forms.NumberInput(attrs={'class': 'form-control bg-light', 'readonly': 'readonly', 'id': 'id_taxable_amount'}),

            'cgst_amount': forms.NumberInput(attrs={'class': 'form-control bg-light', 'readonly': 'readonly', 'id': 'id_cgst_amount'}),
            'sgst_amount': forms.NumberInput(attrs={'class': 'form-control bg-light', 'readonly': 'readonly', 'id': 'id_sgst_amount'}),
            'igst_amount': forms.NumberInput(attrs={'class': 'form-control bg-light', 'readonly': 'readonly', 'id': 'id_igst_amount'}),
            'grand_total': forms.NumberInput(attrs={'class': 'form-control bg-light fw-bold fs-5 text-primary', 'readonly': 'readonly', 'id': 'id_grand_total'}),

            'round_off_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'id_round_off_enabled'}),
            'round_off_amount': forms.NumberInput(attrs={'class': 'form-control bg-light text-end', 'readonly': 'readonly', 'id': 'id_round_off_amount'}),
            'rounded_total': forms.NumberInput(attrs={'class': 'form-control bg-light fw-bold fs-5 text-dark text-end', 'readonly': 'readonly', 'id': 'id_rounded_total'}),

            'advance_label': forms.TextInput(attrs={'class': 'form-control text-uppercase', 'placeholder': 'e.g. ADVANCE RECEIVED ON OUR A/C', 'id': 'id_advance_label'}),
            'advance_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'id': 'id_advance_date'}),
            'balance_payable': forms.NumberInput(attrs={'class': 'form-control bg-light fw-bold fs-5 text-success text-end', 'readonly': 'readonly', 'id': 'id_balance_payable'}),

            'amount_in_words': forms.TextInput(attrs={'class': 'form-control bg-light font-monospace', 'readonly': 'readonly', 'id': 'id_amount_in_words'}),

            'bank_name': forms.TextInput(attrs={'class': 'form-control'}),
            'bank_branch': forms.TextInput(attrs={'class': 'form-control'}),
            'bank_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'bank_telephone': forms.TextInput(attrs={'class': 'form-control'}),
            'bank_account_name': forms.TextInput(attrs={'class': 'form-control'}),
            'bank_account_no': forms.TextInput(attrs={'class': 'form-control'}),
            'bank_ifsc': forms.TextInput(attrs={'class': 'form-control'}),
            'bank_micr': forms.TextInput(attrs={'class': 'form-control'}),

            'request_note': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'signatory_company': forms.TextInput(attrs={'class': 'form-control'}),
            'signatory_name': forms.TextInput(attrs={'class': 'form-control'}),
            'signatory_designation': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        optional_fields = [
            'company_name', 'company_address', 'company_contact',
            'salutation', 'po_reference', 'po_date', 'subject_note',
            'quotation_number_ref', 'customer_contact', 'customer_gstin', 'customer_email', 'attention_to',
            'freight_label', 'freight_amount', 'tax_type', 'tax_rate',
            'subtotal', 'discount_percentage', 'discount_amount', 'subtotal_after_discount',
            'taxable_amount', 'cgst_amount', 'sgst_amount', 'igst_amount', 'tax_amount', 'grand_total',
            'round_off_enabled', 'round_off_amount', 'rounded_total',
            'advance_label', 'advance_date', 'advance_amount', 'balance_payable',
            'amount_in_words', 'bank_name', 'bank_branch', 'bank_address', 'bank_telephone',
            'bank_account_name', 'bank_account_no', 'bank_ifsc', 'bank_micr',
            'request_note', 'signatory_company', 'signatory_name', 'signatory_designation'
        ]
        for f in optional_fields:
            if f in self.fields:
                self.fields[f].required = False

    def clean_advance_amount(self):
        val = self.cleaned_data.get('advance_amount')
        if val is None or str(val).strip() == '':
            val = self.data.get('advance_amount', '0.00')
        val_str = str(val).replace(',', '').replace('₹', '').replace(' ', '').strip()
        try:
            return Decimal(val_str) if val_str else Decimal('0.00')
        except Exception:
            return Decimal('0.00')

    def clean_discount_amount(self):
        val = self.cleaned_data.get('discount_amount')
        if val is None or str(val).strip() == '':
            val = self.data.get('discount_amount', '0.00')
        val_str = str(val).replace(',', '').replace('₹', '').replace(' ', '').strip()
        try:
            return Decimal(val_str) if val_str else Decimal('0.00')
        except Exception:
            return Decimal('0.00')

    def clean_tax_amount(self):
        val = self.cleaned_data.get('tax_amount')
        if val is None or str(val).strip() == '':
            val = self.data.get('tax_amount', '0.00')
        val_str = str(val).replace(',', '').replace('₹', '').replace(' ', '').strip()
        try:
            return Decimal(val_str) if val_str else Decimal('0.00')
        except Exception:
            return Decimal('0.00')

    def clean(self):
        cleaned_data = super().clean()
        from decimal import Decimal
        decimal_zero_fields = [
            'freight_amount', 'tax_rate', 'discount_percentage', 'discount_amount', 'subtotal_after_discount',
            'subtotal', 'taxable_amount',
            'cgst_amount', 'sgst_amount', 'igst_amount', 'tax_amount', 'grand_total',
            'round_off_amount', 'rounded_total', 'advance_amount', 'balance_payable'
        ]
        for field in decimal_zero_fields:
            if cleaned_data.get(field) is None or str(cleaned_data.get(field)).strip() == '':
                cleaned_data[field] = Decimal('0.00')

        if not cleaned_data.get('tax_type'):
            cleaned_data['tax_type'] = 'GST'

        if cleaned_data.get('salutation'):
            cleaned_data['salutation'] = cleaned_data['salutation'].strip().upper()
        if cleaned_data.get('po_reference'):
            cleaned_data['po_reference'] = cleaned_data['po_reference'].strip().upper()
        if cleaned_data.get('subject_note'):
            cleaned_data['subject_note'] = cleaned_data['subject_note'].strip().upper()

        return cleaned_data


class ProformaItemForm(forms.ModelForm):
    unit_rate = forms.DecimalField(
        required=False,
        min_value=0,
        decimal_places=2,
        widget=forms.TextInput(attrs={
            'class': 'form-control item-rate text-end',
            'placeholder': '0.00',
            'inputmode': 'decimal',
            'autocomplete': 'off'
        })
    )

    class Meta:
        model = ProformaItem
        fields = ['sr_no', 'description', 'quantity', 'unit', 'unit_rate', 'amount']
        widgets = {
            'sr_no': forms.TextInput(attrs={'class': 'form-control item-sr text-center', 'placeholder': '01.'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control item-desc',
                'rows': 2,
                'placeholder': 'Item Description (e.g. Cartridge Valve – Part# 406AA00066A\nModel# 1CEB120P35S3)',
                'autocomplete': 'off',
                'style': 'resize: vertical; min-height: 52px;'
            }),
            'quantity': forms.NumberInput(attrs={'class': 'form-control item-qty text-center', 'step': 'any', 'min': '0'}),
            'unit': forms.TextInput(attrs={'class': 'form-control item-unit text-center', 'placeholder': 'No / PCS / SET', 'list': 'proforma-units-list'}),
            'unit_rate': forms.TextInput(attrs={
                'class': 'form-control item-rate text-end',
                'placeholder': '0.00',
                'inputmode': 'decimal',
                'autocomplete': 'off'
            }),
            'amount': forms.TextInput(attrs={'class': 'form-control item-amount bg-light text-end', 'readonly': 'readonly'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'amount' in self.fields:
            self.fields['amount'].required = False
        if not self.is_bound:
            val = self.initial.get('unit_rate')
            if not self.instance.pk:
                if val in [0, Decimal('0.00'), Decimal('0'), '0.00', '0', None]:
                    self.initial['unit_rate'] = ''
            else:
                if val in [0, Decimal('0.00'), Decimal('0'), '0.00', '0', None] and (self.instance.unit_rate == 0 or self.instance.unit_rate is None):
                    self.initial['unit_rate'] = ''
                elif self.instance.unit_rate is not None:
                    self.initial['unit_rate'] = f"{self.instance.unit_rate:.2f}"

    def has_changed(self):
        # Ignore blank extra rows added dynamically or with empty description
        has_desc = bool(self.data.get(self.add_prefix('description'), '').strip())
        if not self.instance.pk and not has_desc:
            return False
        return super().has_changed()

    def clean_unit_rate(self):
        val = self.cleaned_data.get('unit_rate')
        if val is None or str(val).strip() == '':
            return Decimal('0.00')
        return val

    def clean_amount(self):
        val = self.cleaned_data.get('amount')
        if val is None or str(val).strip() == '':
            return Decimal('0.00')
        return val


ProformaItemFormSet = inlineformset_factory(
    Proforma,
    ProformaItem,
    form=ProformaItemForm,
    extra=0,
    can_delete=True
)


