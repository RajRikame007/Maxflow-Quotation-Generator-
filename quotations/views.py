import os
from django.conf import settings
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, Http404, JsonResponse
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
import re
from django.utils import timezone
from django.db import transaction
from django.db.models import Q, Case, When, Value, IntegerField
from .models import (
    Quotation, QuotationItem, Product, Customer, UserProfile, get_next_quotation_number,
    Proforma, ProformaItem, get_next_proforma_number
)
from .forms import (
    QuotationForm, QuotationItemFormSet, UserRegistrationForm, CustomerForm, ProductForm, UserProfileForm,
    ProformaForm, ProformaItemFormSet
)
from .utils import render_to_pdf, number_to_words_inr
from .excel_sync import (
    append_or_update_customer_in_excel, delete_customer_from_excel, sync_all_customers_to_excel,
    append_or_update_product_in_excel, delete_product_from_excel, sync_all_products_to_excel
)



def register_view(request):
    """User account registration view."""
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            user_display = f"{user.first_name} {user.last_name}".strip() or user.username
            messages.success(request, f"Account created successfully! Welcome, {user_display}.")
            return redirect('quotation_create')
        else:
            messages.error(request, "Please correct the registration errors below.")
    else:
        form = UserRegistrationForm()

    return render(request, 'quotations/register.html', {'form': form})

def login_view(request):
    """User login view."""
    if request.user.is_authenticated:
        return redirect('home')
        
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            user_display = f"{user.first_name} {user.last_name}".strip() or user.username
            messages.success(request, f"Welcome back, {user_display}!")
            next_url = request.GET.get('next', 'home')
            return redirect(next_url)
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()
        
    return render(request, 'quotations/login.html', {'form': form})

def logout_view(request):
    """User logout view."""
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('login')

@login_required
def profile_view(request):
    """View and update profile details (first name, last name, designation, cell number)."""
    user = request.user
    profile, _ = UserProfile.objects.get_or_create(user=user)
    
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        designation = request.POST.get('designation', '').strip().upper()
        phone = request.POST.get('phone', '').strip()
        
        user.first_name = first_name
        user.last_name = last_name
        if email:
            user.email = email
        user.save()
        
        profile.designation = designation if designation else 'MANAGER TECHNICAL'
        profile.phone = phone
        profile.save()
        
        messages.success(request, "Profile updated successfully! Authorized Signatory will now auto-fill with these details.")
        return redirect('quotation_create')
        
    return render(request, 'quotations/profile.html', {
        'profile': profile,
    })

@login_required
def home(request):
    """Dashboard / Homepage with recent quotations, proformas and summary statistics."""
    from django.utils import timezone
    now = timezone.now()
    recent_quotations = Quotation.objects.all()[:5]
    total_count = Quotation.objects.count()

    # Proforma Statistics
    total_proformas = Proforma.objects.count()
    proformas_this_month = Proforma.objects.filter(
        proforma_date__year=now.year,
        proforma_date__month=now.month
    ).count()
    latest_proforma = Proforma.objects.first()
    recent_proformas = Proforma.objects.all()[:5]

    return render(request, 'quotations/home.html', {
        'recent_quotations': recent_quotations,
        'total_count': total_count,
        'total_proformas': total_proformas,
        'proformas_this_month': proformas_this_month,
        'latest_proforma': latest_proforma,
        'recent_proformas': recent_proformas,
    })


@login_required
def quotation_list(request):
    """List all quotations with search and action options."""
    from django.core.paginator import Paginator
    from django.db.models import Count
    query = request.GET.get('q', '').strip()
    if query:
        quotations_qs = Quotation.objects.filter(
            Q(quotation_number__icontains=query) |
            Q(customer_name__icontains=query)
        )
    else:
        quotations_qs = Quotation.objects.all()

    quotations_qs = quotations_qs.annotate(item_count=Count('items')).order_by('-created_at')

    total_count = quotations_qs.count()
    paginator = Paginator(quotations_qs, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'quotations/quotation_list.html', {
        'page_obj': page_obj,
        'quotations': page_obj,
        'query': query,
        'total_count': total_count,
    })

LAST_EXCEL_SYNC_MTIME = 0
LAST_PRODUCT_EXCEL_SYNC_MTIME = 0

def auto_sync_excel_if_modified():
    """Checks if 'customer address raj.xlsx' has been edited or saved, and automatically syncs new data."""
    global LAST_EXCEL_SYNC_MTIME
    excel_path = os.path.join(settings.BASE_DIR, 'customer address raj.xlsx')
    if not os.path.exists(excel_path):
        return
    try:
        current_mtime = os.path.getmtime(excel_path)
        if LAST_EXCEL_SYNC_MTIME == 0:
            LAST_EXCEL_SYNC_MTIME = current_mtime
            return
        if current_mtime > LAST_EXCEL_SYNC_MTIME:
            from django.core.management import call_command
            call_command('import_customers')
            LAST_EXCEL_SYNC_MTIME = current_mtime
    except Exception as e:
        print(f"Excel auto-sync check error: {e}")

def auto_sync_product_excel_if_modified():
    """Checks if 'Product List.xlsx' has been edited or saved, and automatically syncs new products."""
    global LAST_PRODUCT_EXCEL_SYNC_MTIME
    excel_path = os.path.join(settings.BASE_DIR, 'Product List.xlsx')
    if not os.path.exists(excel_path):
        return
    try:
        current_mtime = os.path.getmtime(excel_path)
        if LAST_PRODUCT_EXCEL_SYNC_MTIME == 0:
            LAST_PRODUCT_EXCEL_SYNC_MTIME = current_mtime
            return
        if current_mtime > LAST_PRODUCT_EXCEL_SYNC_MTIME:
            from django.core.management import call_command
            call_command('import_products')
            LAST_PRODUCT_EXCEL_SYNC_MTIME = current_mtime
    except Exception as e:
        print(f"Product Excel auto-sync check error: {e}")

def sync_quotation_customer_to_master(customer_name, customer_address='', customer_phone='', customer_email='', customer_gstin=''):
    """
    Saves or updates customer details into Customer master model and customer address raj.xlsx.
    Matches case-insensitively by name.
    """
    name = (customer_name or '').strip()
    if not name:
        return None, False, "Customer name is empty"

    existing = Customer.objects.filter(name__iexact=name).first()
    is_new = False
    original_name = None
    if existing:
        customer = existing
        original_name = customer.name
        if customer_address and customer_address.strip():
            customer.address = customer_address.strip()
        if customer_phone and customer_phone.strip():
            customer.mobile = customer_phone.strip()
        if customer_email and customer_email.strip():
            customer.email = customer_email.strip()
        if customer_gstin and customer_gstin.strip():
            customer.gstin = customer_gstin.strip()
        customer.save()
    else:
        is_new = True
        customer = Customer.objects.create(
            name=name,
            address=(customer_address or '').strip(),
            mobile=(customer_phone or '').strip(),
            email=(customer_email or '').strip(),
            gstin=(customer_gstin or '').strip(),
        )

    try:
        excel_saved, excel_msg = append_or_update_customer_in_excel(customer, original_name=original_name)
    except Exception as e:
        excel_saved = False
        excel_msg = f"Excel update skipped: {e}"
    global LAST_EXCEL_SYNC_MTIME
    excel_path = os.path.join(settings.BASE_DIR, 'customer address raj.xlsx')
    if os.path.exists(excel_path):
        LAST_EXCEL_SYNC_MTIME = os.path.getmtime(excel_path)

    return customer, is_new, excel_msg

def resequence_quotation_items(quotation):
    """Ensure any items with missing/blank serial numbers receive sequential numbering without overwriting custom serial numbers."""
    for idx, item in enumerate(quotation.items.all().order_by('id'), start=1):
        if not item.sr_no or not str(item.sr_no).strip():
            QuotationItem.objects.filter(pk=item.pk).update(sr_no=str(idx))

@login_required
def quotation_create(request):
    """Create a new quotation with dynamic item rows and auto-populated signatory name."""
    total_customers_count = Customer.objects.filter(is_active=True).count()
    initial_customers = list(Customer.objects.filter(is_active=True).order_by('name')[:30])
    brands = [b for b in Product.objects.filter(is_active=True).values_list('category', flat=True).distinct().order_by('category') if b]
    initial_products = Product.objects.filter(is_active=True)[:30]

    if request.method == 'POST':
        form = QuotationForm(request.POST)
        formset = QuotationItemFormSet(request.POST)
        
        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    quotation = form.save()
                    formset.instance = quotation
                    formset.save()
                    resequence_quotation_items(quotation)
                    quotation.refresh_from_db()
                    # Recalculate totals automatically on the backend
                    quotation.recalculate_totals()
                    quotation.refresh_from_db()
                
                # Check if user opted to save/update customer in Master & Excel
                if request.POST.get('save_customer_to_master') in ['on', 'true', '1']:
                    c_obj, is_new, excel_msg = sync_quotation_customer_to_master(
                        customer_name=quotation.customer_name,
                        customer_address=quotation.customer_address,
                        customer_phone=quotation.customer_phone,
                        customer_email=quotation.customer_email,
                        customer_gstin=quotation.customer_gstin
                    )
                    if c_obj:
                        action_str = "saved to" if is_new else "updated in"
                        messages.success(request, f"Customer '{c_obj.name}' {action_str} Master & Excel ({excel_msg})")

                messages.success(request, f"Quotation '{quotation.quotation_number}' created successfully!")
                if request.POST.get('action') == 'save_detail':
                    return redirect('quotation_detail', pk=quotation.pk)
                return redirect('quotation_pdf_preview', pk=quotation.pk)
            except Exception as e:
                messages.error(request, f"An error occurred while saving: {str(e)}")
        else:
            err_list = []
            for field, errs in form.errors.items():
                label = form.fields.get(field).label if field in form.fields and form.fields.get(field).label else field
                err_list.append(f"{label}: {', '.join(errs)}")
            for form_err in formset.errors:
                if form_err:
                    for field, errs in form_err.items():
                        err_list.append(f"Item {field}: {', '.join(errs)}")
            for non_form_err in formset.non_form_errors():
                err_list.append(str(non_form_err))
            err_msg = "Please correct the errors below: " + " | ".join(err_list) if err_list else "Please correct the errors in the form below."
            messages.error(request, err_msg)
    else:
        initial_data = {
            'quotation_number': get_next_quotation_number(),
            'quotation_date': timezone.now().date().strftime('%Y-%m-%d'),
        }
        # Pre-populate customer details if customer_id passed in URL
        customer_id = request.GET.get('customer_id')
        if customer_id:
            try:
                cust = Customer.objects.get(pk=customer_id)
                if not any(c.id == cust.id for c in initial_customers):
                    initial_customers.insert(0, cust)
                initial_data['customer_name'] = cust.name
                initial_data['customer_address'] = cust.address
                initial_data['customer_phone'] = cust.mobile
                initial_data['customer_email'] = cust.email
                initial_data['customer_gstin'] = cust.gstin
            except Customer.DoesNotExist:
                pass

        # Pre-populate authorized signatory details (Name, Designation, Cell Number) from logged-in user's profile
        if request.user.is_authenticated:
            full_name = f"{request.user.first_name} {request.user.last_name}".strip()
            initial_data['signatory_name'] = full_name.upper() if full_name else request.user.username.upper()
            try:
                profile = getattr(request.user, 'profile', None)
                if not profile:
                    profile, _ = UserProfile.objects.get_or_create(user=request.user)
                if profile:
                    if profile.designation:
                        initial_data['signatory_designation'] = profile.designation.upper()
                    if profile.phone:
                        initial_data['signatory_phone'] = profile.phone
            except Exception:
                pass

        form = QuotationForm(initial=initial_data)
        formset = QuotationItemFormSet()

    return render(request, 'quotations/quotation_form.html', {
        'form': form,
        'formset': formset,
        'products': initial_products,
        'brands': brands,
        'customers': initial_customers,
        'initial_customers': initial_customers,
        'total_customers_count': total_customers_count,
        'customer_form': CustomerForm(),
        'product_form': ProductForm(),
        'title': 'Create New Quotation'
    })

@login_required
def quotation_edit(request, pk):
    """Edit an existing quotation."""
    quotation = get_object_or_404(Quotation, pk=pk)
    total_customers_count = Customer.objects.filter(is_active=True).count()
    initial_customers = list(Customer.objects.filter(is_active=True).order_by('name')[:30])
    if quotation.customer_name:
        existing_cust = Customer.objects.filter(name__iexact=quotation.customer_name.strip(), is_active=True).first()
        if existing_cust and not any(c.id == existing_cust.id for c in initial_customers):
            initial_customers.insert(0, existing_cust)
    brands = [b for b in Product.objects.filter(is_active=True).values_list('category', flat=True).distinct().order_by('category') if b]
    initial_products = Product.objects.filter(is_active=True)[:30]

    if request.method == 'POST':
        form = QuotationForm(request.POST, instance=quotation)
        formset = QuotationItemFormSet(request.POST, instance=quotation)
        
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                quotation = form.save()
                formset.save()
                resequence_quotation_items(quotation)
                quotation.refresh_from_db()
                quotation.recalculate_totals()
                quotation.refresh_from_db()

            # Check if user opted to save/update customer in Master & Excel
            if request.POST.get('save_customer_to_master') in ['on', 'true', '1']:
                c_obj, is_new, excel_msg = sync_quotation_customer_to_master(
                    customer_name=quotation.customer_name,
                    customer_address=quotation.customer_address,
                    customer_phone=quotation.customer_phone,
                    customer_email=quotation.customer_email,
                    customer_gstin=quotation.customer_gstin
                )
                if c_obj:
                    action_str = "saved to" if is_new else "updated in"
                    messages.success(request, f"Customer '{c_obj.name}' {action_str} Master & Excel ({excel_msg})")

            messages.success(request, f"Quotation '{quotation.quotation_number}' updated successfully!")
            if request.POST.get('action') == 'save_detail':
                return redirect('quotation_detail', pk=quotation.pk)
            return redirect('quotation_pdf_preview', pk=quotation.pk)
        else:
            err_list = []
            for field, errs in form.errors.items():
                label = form.fields.get(field).label if field in form.fields and form.fields.get(field).label else field
                err_list.append(f"{label}: {', '.join(errs)}")
            for form_err in formset.errors:
                if form_err:
                    for field, errs in form_err.items():
                        err_list.append(f"Item {field}: {', '.join(errs)}")
            for non_form_err in formset.non_form_errors():
                err_list.append(str(non_form_err))
            err_msg = "Please correct the errors below: " + " | ".join(err_list) if err_list else "Please correct the errors below."
            messages.error(request, err_msg)
    else:
        form = QuotationForm(instance=quotation)
        formset = QuotationItemFormSet(instance=quotation)

    return render(request, 'quotations/quotation_form.html', {
        'form': form,
        'formset': formset,
        'quotation': quotation,
        'products': initial_products,
        'brands': brands,
        'customers': initial_customers,
        'initial_customers': initial_customers,
        'total_customers_count': total_customers_count,
        'customer_form': CustomerForm(),
        'product_form': ProductForm(),
        'title': f'Edit Quotation: {quotation.quotation_number}'
    })

@login_required
def customer_list(request):
    """Customer Directory view to search and manage customers."""
    from django.core.paginator import Paginator
    query = request.GET.get('q', '').strip()
    if query:
        customers_qs = Customer.objects.filter(
            Q(name__icontains=query) |
            Q(gstin__icontains=query) |
            Q(address__icontains=query) |
            Q(mobile__icontains=query) |
            Q(email__icontains=query)
        ).order_by('name')
    else:
        customers_qs = Customer.objects.all().order_by('name')

    total_count = customers_qs.count()
    paginator = Paginator(customers_qs, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'quotations/customer_list.html', {
        'page_obj': page_obj,
        'customers': page_obj,
        'customer_form': CustomerForm(),
        'query': query,
        'total_count': total_count,
    })

@login_required
def customer_create(request):
    """Add a new customer, saving directly into database and customer address raj.xlsx."""
    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            customer = form.save()
            try:
                excel_saved, excel_msg = append_or_update_customer_in_excel(customer)
            except Exception as e:
                excel_saved = False
                excel_msg = f"Excel update skipped: {e}"

            global LAST_EXCEL_SYNC_MTIME
            excel_path = os.path.join(settings.BASE_DIR, 'customer address raj.xlsx')
            if os.path.exists(excel_path):
                LAST_EXCEL_SYNC_MTIME = os.path.getmtime(excel_path)

            is_ajax = (
                request.headers.get('x-requested-with') == 'XMLHttpRequest' or
                'application/json' in request.headers.get('accept', '')
            )

            if is_ajax:
                return JsonResponse({
                    'success': True,
                    'customer': {
                        'id': customer.id,
                        'name': customer.name,
                        'gstin': customer.gstin or '',
                        'mobile': customer.mobile or '',
                        'email': customer.email or '',
                        'address': customer.address or '',
                    },
                    'excel_saved': excel_saved,
                    'message': f"Customer '{customer.name}' saved! {excel_msg}"
                })

            if excel_saved:
                messages.success(request, f"Customer '{customer.name}' added successfully and saved directly into 'customer address raj.xlsx'!")
            else:
                messages.warning(request, f"Customer '{customer.name}' saved to database! ({excel_msg})")

            # If came from quotation form
            next_url = request.POST.get('next') or request.GET.get('next')
            if next_url:
                return redirect(next_url)
            return redirect('customer_list')
        else:
            is_ajax = (
                request.headers.get('x-requested-with') == 'XMLHttpRequest' or
                'application/json' in request.headers.get('accept', '')
            )
            if is_ajax:
                return JsonResponse({'success': False, 'errors': form.errors.get_json_data()}, status=400)
            messages.error(request, "Failed to add customer. Please review the errors in the form.")
    return redirect('customer_list')

@login_required
def customer_edit(request, pk):
    """
    Edit an existing customer master record.
    Directly reflects into database master and 'customer address raj.xlsx'.
    Supports both AJAX modal editing and direct page editing.
    """
    customer = get_object_or_404(Customer, pk=pk)
    original_name = customer.name

    is_ajax = (
        request.headers.get('x-requested-with') == 'XMLHttpRequest' or
        'application/json' in request.headers.get('accept', '') or
        request.GET.get('format') == 'json'
    )

    if request.method == 'GET' and is_ajax:
        return JsonResponse({
            'success': True,
            'customer': {
                'id': customer.id,
                'name': customer.name,
                'gstin': customer.gstin or '',
                'mobile': customer.mobile or '',
                'email': customer.email or '',
                'address': customer.address or '',
            }
        })

    if request.method == 'POST':
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            customer = form.save()
            try:
                excel_saved, excel_msg = append_or_update_customer_in_excel(customer, original_name=original_name)
            except Exception as e:
                excel_saved = False
                excel_msg = f"Excel update skipped: {e}"

            global LAST_EXCEL_SYNC_MTIME
            excel_path = os.path.join(settings.BASE_DIR, 'customer address raj.xlsx')
            if os.path.exists(excel_path):
                LAST_EXCEL_SYNC_MTIME = os.path.getmtime(excel_path)

            if is_ajax:
                return JsonResponse({
                    'success': True,
                    'customer': {
                        'id': customer.id,
                        'name': customer.name,
                        'gstin': customer.gstin or '',
                        'mobile': customer.mobile or '',
                        'email': customer.email or '',
                        'address': customer.address or '',
                    },
                    'excel_saved': excel_saved,
                    'message': f"Customer '{customer.name}' updated! {excel_msg}"
                })

            if excel_saved:
                messages.success(request, f"Customer '{customer.name}' updated successfully and saved directly into 'customer address raj.xlsx'!")
            else:
                messages.warning(request, f"Customer '{customer.name}' updated in database! ({excel_msg})")

            next_url = request.POST.get('next') or request.GET.get('next')
            if next_url:
                return redirect(next_url)
            return redirect('customer_list')
        else:
            if is_ajax:
                return JsonResponse({'success': False, 'errors': form.errors.get_json_data()}, status=400)
            messages.error(request, "Failed to update customer. Please review the errors in the form.")
    else:
        form = CustomerForm(instance=customer)

    return render(request, 'quotations/customer_edit.html', {
        'customer': customer,
        'form': form,
    })


@login_required
def customer_delete(request, pk):
    """
    Delete a customer from the database master and remove from 'customer address raj.xlsx'.
    Supports both AJAX modal delete and POST submission.
    """
    customer = get_object_or_404(Customer, pk=pk)
    name = customer.name
    gstin = customer.gstin

    if request.method == 'POST':
        customer.delete()
        excel_deleted, excel_msg = delete_customer_from_excel(name, gstin=gstin)

        global LAST_EXCEL_SYNC_MTIME
        excel_path = os.path.join(settings.BASE_DIR, 'customer address raj.xlsx')
        if os.path.exists(excel_path):
            LAST_EXCEL_SYNC_MTIME = os.path.getmtime(excel_path)

        is_ajax = (
            request.headers.get('x-requested-with') == 'XMLHttpRequest' or
            'application/json' in request.headers.get('accept', '')
        )

        if is_ajax:
            return JsonResponse({
                'success': True,
                'deleted_id': pk,
                'name': name,
                'excel_deleted': excel_deleted,
                'message': f"Customer '{name}' deleted! {excel_msg}"
            })

        if excel_deleted:
            messages.success(request, f"Customer '{name}' deleted successfully and removed from 'customer address raj.xlsx'!")
        else:
            messages.warning(request, f"Customer '{name}' deleted from database! ({excel_msg})")

        return redirect('customer_list')

    return render(request, 'quotations/customer_confirm_delete.html', {'customer': customer})


@login_required
def customer_export_excel(request):
    """Sync/Write all customers from database into customer address raj.xlsx."""
    success, msg = sync_all_customers_to_excel()
    if success:
        messages.success(request, msg)
    else:
        messages.warning(request, msg)
    return redirect('customer_list')

@login_required
def customer_sync_excel(request):
    """Re-sync customer master database directly from 'customer address raj.xlsx'."""
    from django.core.management import call_command
    try:
        call_command('import_customers')
        messages.success(request, "Customers have been successfully synchronized from 'customer address raj.xlsx'!")
    except Exception as e:
        messages.error(request, f"Failed to sync customers from Excel: {str(e)}")
    return redirect('customer_list')

@login_required
def customer_search_api(request):
    """JSON API to search customers dynamically."""
    query = request.GET.get('q', '').strip()


    qs = Customer.objects.filter(is_active=True)
    if query:
        qs = qs.filter(
            Q(name__icontains=query) |
            Q(gstin__icontains=query) |
            Q(address__icontains=query) |
            Q(mobile__icontains=query)
        )
    data = [
        {
            'id': c.id,
            'name': c.name,
            'email': c.email or '',
            'phone': c.mobile or '',
            'gstin': c.gstin or '',
            'address': c.address or '',
        }
        for c in qs[:50]
    ]
    return JsonResponse({'customers': data})


@login_required
def customer_quick_save(request):
    """
    AJAX endpoint to quickly save or update a customer into Master database and customer address raj.xlsx
    directly from the Quotation Form without leaving or submitting the quotation.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST method required.'}, status=405)

    name = request.POST.get('name', '').strip()
    address = request.POST.get('address', '').strip()
    phone = request.POST.get('phone', '').strip()
    email = request.POST.get('email', '').strip()
    gstin = request.POST.get('gstin', '').strip()

    if not name:
        return JsonResponse({'success': False, 'message': 'Customer / Company Name is required.'}, status=400)

    try:
        customer, is_new, excel_msg = sync_quotation_customer_to_master(
            customer_name=name,
            customer_address=address,
            customer_phone=phone,
            customer_email=email,
            customer_gstin=gstin
        )

        if not customer:
            return JsonResponse({'success': False, 'message': excel_msg or 'Could not save customer.'}, status=400)

        action_word = "created and saved to" if is_new else "updated in"
        return JsonResponse({
            'success': True,
            'is_new': is_new,
            'customer': {
                'id': customer.id,
                'name': customer.name,
                'address': customer.address or '',
                'phone': customer.mobile or '',
                'email': customer.email or '',
                'gstin': customer.gstin or '',
            },
            'message': f"Customer '{customer.name}' successfully {action_word} Master & 'customer address raj.xlsx'!"
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)



def get_filtered_product_queryset(query='', brand=None):
    """
    Intelligent, fast product search that ignores hyphens, spaces, special symbols,
    and letter casing when matching product codes, while supporting brand and description filtering.
    """
    qs = Product.objects.filter(is_active=True)
    if brand and brand.strip().upper() != 'ALL':
        qs = qs.filter(category__iexact=brand.strip())

    raw_query = (query or '').strip()
    if not raw_query:
        return qs.order_by('category', 'model_code')

    clean_full_q = re.sub(r'[^A-Za-z0-9]', '', raw_query).upper()
    tokens = [t.strip() for t in raw_query.split() if t.strip()]

    # Main search filter
    main_filter = (
        Q(model_code__icontains=raw_query) |
        Q(description__icontains=raw_query) |
        Q(category__icontains=raw_query)
    )

    if clean_full_q:
        main_filter |= Q(clean_code__icontains=clean_full_q)

    # Multi-token match: e.g. "Danfoss v21051a" or "v210 5"
    if len(tokens) > 1:
        token_and_filter = Q()
        for tok in tokens:
            clean_tok = re.sub(r'[^A-Za-z0-9]', '', tok).upper()
            t_q = (
                Q(model_code__icontains=tok) |
                Q(description__icontains=tok) |
                Q(category__icontains=tok)
            )
            if clean_tok:
                t_q |= Q(clean_code__icontains=clean_tok)
            token_and_filter &= t_q

        main_filter |= token_and_filter

    qs = qs.filter(main_filter)

    # Ranking: exact/prefix code matches rank highest
    priority_whens = []
    if clean_full_q:
        priority_whens.append(When(clean_code__iexact=clean_full_q, then=Value(1)))
        priority_whens.append(When(clean_code__istartswith=clean_full_q, then=Value(2)))
        priority_whens.append(When(clean_code__icontains=clean_full_q, then=Value(3)))

    priority_whens.append(When(model_code__iexact=raw_query, then=Value(1)))
    priority_whens.append(When(model_code__istartswith=raw_query, then=Value(2)))
    priority_whens.append(When(model_code__icontains=raw_query, then=Value(3)))
    priority_whens.append(When(category__icontains=raw_query, then=Value(4)))
    priority_whens.append(When(description__icontains=raw_query, then=Value(5)))

    qs = qs.annotate(
        search_rank=Case(
            *priority_whens,
            default=Value(10),
            output_field=IntegerField()
        )
    ).order_by('search_rank', 'model_code')

    return qs


@login_required
def product_search_api(request):
    """
    JSON API for real-time live product searching across Item Name, Brand, and Description.
    Supports flexible matching ignoring hyphens, spaces, and letter case.
    Supports filtering by query (?q=...) and brand (?brand=...).
    Returns top 50 ranked matches.
    """
    query = request.GET.get('q', '').strip()
    brand = request.GET.get('brand', '').strip()

    qs = get_filtered_product_queryset(query=query, brand=brand)

    products = []
    for p in qs[:50]:
        if p.description and p.description.strip():
            display_desc = f"{p.model_code} - {p.description.strip()}"
        else:
            display_desc = p.model_code

        products.append({
            'id': p.id,
            'code': p.model_code,
            'brand': p.category,
            'description': p.description or '',
            'display_desc': display_desc,
            'unit_rate': str(p.unit_rate),
            'hsn': p.hsn_code or '84136090',
            'unit': p.unit or 'NOS',
            'gst_rate': str(p.gst_rate) if p.gst_rate is not None else '18.00',
        })

    return JsonResponse({'products': products, 'count': len(products)})


@login_required
def product_list(request):
    """Directory view for Product List.xlsx with fast flexible search and brand filtering."""
    from django.core.paginator import Paginator
    query = request.GET.get('q', '').strip()
    brand_filter = request.GET.get('brand', '').strip()

    qs = get_filtered_product_queryset(query=query, brand=brand_filter)

    total_count = qs.count()
    paginator = Paginator(qs, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    all_brands = Product.objects.filter(is_active=True).values_list('category', flat=True).distinct().order_by('category')
    brands_list = [b for b in all_brands if b]

    return render(request, 'quotations/product_list.html', {
        'page_obj': page_obj,
        'products': page_obj,
        'product_form': ProductForm(),
        'query': query,
        'brand_filter': brand_filter,
        'brands': brands_list,
        'total_count': total_count,
    })


@login_required
def product_create(request):
    """Add a new product, saving directly into database and Product List.xlsx."""
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save()
            excel_saved, excel_msg = append_or_update_product_in_excel(product)

            global LAST_PRODUCT_EXCEL_SYNC_MTIME
            excel_path = os.path.join(settings.BASE_DIR, 'Product List.xlsx')
            if os.path.exists(excel_path):
                LAST_PRODUCT_EXCEL_SYNC_MTIME = os.path.getmtime(excel_path)

            is_ajax = (
                request.headers.get('x-requested-with') == 'XMLHttpRequest' or
                'application/json' in request.headers.get('accept', '')
            )

            if is_ajax:
                return JsonResponse({
                    'success': True,
                    'product': {
                        'id': product.id,
                        'model_code': product.model_code,
                        'category': product.category,
                        'description': product.description or '',
                        'unit_rate': str(product.unit_rate),
                        'hsn_code': product.hsn_code or '84136090',
                        'unit': product.unit or 'NOS',
                        'gst_rate': str(product.gst_rate) if product.gst_rate is not None else '18.00',
                    },
                    'excel_saved': excel_saved,
                    'message': f"Product '{product.model_code}' added! {excel_msg}"
                })

            if excel_saved:
                messages.success(request, f"Product '{product.model_code}' added successfully and saved into 'Product List.xlsx'!")
            else:
                messages.warning(request, f"Product '{product.model_code}' saved to database! ({excel_msg})")

            return redirect('product_list')
        else:
            is_ajax = (
                request.headers.get('x-requested-with') == 'XMLHttpRequest' or
                'application/json' in request.headers.get('accept', '')
            )
            if is_ajax:
                return JsonResponse({'success': False, 'errors': form.errors.get_json_data()}, status=400)
            messages.error(request, "Failed to add product. Please review the errors in the form.")
    return redirect('product_list')


@login_required
def product_edit(request, pk):
    """
    Edit an existing product item in the catalog.
    Directly reflects into database master and 'Product List.xlsx'.
    Supports both AJAX modal editing and direct page editing.
    """
    product = get_object_or_404(Product, pk=pk)
    original_code = product.model_code

    is_ajax = (
        request.headers.get('x-requested-with') == 'XMLHttpRequest' or
        'application/json' in request.headers.get('accept', '') or
        request.GET.get('format') == 'json'
    )

    if request.method == 'GET' and is_ajax:
        return JsonResponse({
            'success': True,
            'product': {
                'id': product.id,
                'model_code': product.model_code,
                'category': product.category,
                'description': product.description or '',
                'unit_rate': str(product.unit_rate),
                'hsn_code': product.hsn_code or '84136090',
                'unit': product.unit or 'NOS',
                'gst_rate': str(product.gst_rate) if product.gst_rate is not None else '18.00',
            }
        })

    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            product = form.save()
            excel_saved, excel_msg = append_or_update_product_in_excel(product, original_code=original_code)

            global LAST_PRODUCT_EXCEL_SYNC_MTIME
            excel_path = os.path.join(settings.BASE_DIR, 'Product List.xlsx')
            if os.path.exists(excel_path):
                LAST_PRODUCT_EXCEL_SYNC_MTIME = os.path.getmtime(excel_path)

            if is_ajax:
                return JsonResponse({
                    'success': True,
                    'product': {
                        'id': product.id,
                        'model_code': product.model_code,
                        'category': product.category,
                        'description': product.description or '',
                        'unit_rate': str(product.unit_rate),
                        'hsn_code': product.hsn_code or '84136090',
                        'unit': product.unit or 'NOS',
                        'gst_rate': str(product.gst_rate) if product.gst_rate is not None else '18.00',
                    },
                    'excel_saved': excel_saved,
                    'message': f"Product '{product.model_code}' updated! {excel_msg}"
                })

            if excel_saved:
                messages.success(request, f"Product '{product.model_code}' updated successfully and saved directly into 'Product List.xlsx'!")
            else:
                messages.warning(request, f"Product '{product.model_code}' updated in database! ({excel_msg})")

            return redirect('product_list')
        else:
            if is_ajax:
                return JsonResponse({'success': False, 'errors': form.errors.get_json_data()}, status=400)
            messages.error(request, "Failed to update product. Please review the errors in the form.")
    else:
        form = ProductForm(instance=product)

    return render(request, 'quotations/product_edit.html', {
        'product': product,
        'form': form,
    })


@login_required
def product_delete(request, pk):
    """
    Delete a product from the database master and remove from 'Product List.xlsx'.
    Supports both AJAX modal delete and POST submission.
    """
    product = get_object_or_404(Product, pk=pk)
    code = product.model_code
    category = product.category

    if request.method == 'POST':
        product.delete()
        excel_deleted, excel_msg = delete_product_from_excel(code, category=category)

        global LAST_PRODUCT_EXCEL_SYNC_MTIME
        excel_path = os.path.join(settings.BASE_DIR, 'Product List.xlsx')
        if os.path.exists(excel_path):
            LAST_PRODUCT_EXCEL_SYNC_MTIME = os.path.getmtime(excel_path)

        is_ajax = (
            request.headers.get('x-requested-with') == 'XMLHttpRequest' or
            'application/json' in request.headers.get('accept', '')
        )

        if is_ajax:
            return JsonResponse({
                'success': True,
                'deleted_id': pk,
                'model_code': code,
                'excel_deleted': excel_deleted,
                'message': f"Product '{code}' deleted! {excel_msg}"
            })

        if excel_deleted:
            messages.success(request, f"Product '{code}' deleted successfully and removed from 'Product List.xlsx'!")
        else:
            messages.warning(request, f"Product '{code}' deleted from database! ({excel_msg})")

        return redirect('product_list')

    return render(request, 'quotations/product_confirm_delete.html', {'product': product})


@login_required
def product_export_excel(request):
    """Sync/Write all products from database into Product List.xlsx."""
    success, msg = sync_all_products_to_excel()
    if success:
        messages.success(request, msg)
    else:
        messages.warning(request, msg)
    return redirect('product_list')


@login_required
def product_sync_excel(request):
    """Manually triggers re-import of products from 'Product List.xlsx'."""
    try:
        from django.core.management import call_command
        call_command('import_products')
        messages.success(request, "Products have been successfully synchronized from 'Product List.xlsx'!")
    except Exception as e:
        messages.error(request, f"Failed to sync products from Excel: {str(e)}")
    return redirect('product_list')


@login_required
def quotation_detail(request, pk):
    """Preview the quotation layout in clean web format."""
    quotation = get_object_or_404(Quotation, pk=pk)
    logo_path = os.path.join(settings.BASE_DIR, 'quotations', 'static', 'images', 'logo.png')
    stamp_path = os.path.join(settings.BASE_DIR, 'quotations', 'static', 'images', 'stamp.png')
    return render(request, 'quotations/quotation_detail.html', {
        'quotation': quotation,
        'items': quotation.items.all(),
        'logo_path': logo_path if os.path.exists(logo_path) else None,
        'stamp_path': stamp_path if os.path.exists(stamp_path) else None,
    })

@login_required
def quotation_download_pdf(request, pk):
    """Generate and trigger download of the PDF file."""
    quotation = get_object_or_404(Quotation, pk=pk)
    quotation.recalculate_totals()
    items = quotation.items.all()
    logo_path = os.path.join(settings.BASE_DIR, 'quotations', 'static', 'images', 'logo.png')
    stamp_path = os.path.join(settings.BASE_DIR, 'quotations', 'static', 'images', 'stamp.png')
    
    context = {
        'quotation': quotation,
        'items': items,
        'logo_path': logo_path if os.path.exists(logo_path) else None,
        'stamp_path': stamp_path if os.path.exists(stamp_path) else None,
    }
    
    pdf_content = render_to_pdf('quotations/pdf_template.html', context)
    
    if pdf_content:
        # Sanitize quotation number for clean filename
        safe_num = re.sub(r'[^A-Za-z0-9_\-\.]', '_', str(quotation.quotation_number or quotation.pk))
        filename = f"Quotation_{safe_num}.pdf"
        response = HttpResponse(pdf_content, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response
    
    return HttpResponse("Error generating PDF. Please check server logs.", status=500)

@login_required
def quotation_view_pdf(request, pk):
    """Stream PDF directly in the browser viewer."""
    quotation = get_object_or_404(Quotation, pk=pk)
    quotation.recalculate_totals()
    items = quotation.items.all()
    logo_path = os.path.join(settings.BASE_DIR, 'quotations', 'static', 'images', 'logo.png')
    stamp_path = os.path.join(settings.BASE_DIR, 'quotations', 'static', 'images', 'stamp.png')
    
    context = {
        'quotation': quotation,
        'items': items,
        'logo_path': logo_path if os.path.exists(logo_path) else None,
        'stamp_path': stamp_path if os.path.exists(stamp_path) else None,
    }
    
    pdf_content = render_to_pdf('quotations/pdf_template.html', context)
    
    if pdf_content:
        safe_num = re.sub(r'[^A-Za-z0-9_\-\.]', '_', str(quotation.quotation_number or quotation.pk))
        filename = f"Quotation_{safe_num}.pdf"
        response = HttpResponse(pdf_content, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response
    
    return HttpResponse("Error rendering PDF", status=500)

@login_required
def quotation_delete(request, pk):
    """Delete a quotation."""
    quotation = get_object_or_404(Quotation, pk=pk)
    if request.method == 'POST':
        q_num = quotation.quotation_number
        quotation.delete()
        messages.success(request, f"Quotation '{q_num}' deleted successfully.")
        return redirect('quotation_list')
    return render(request, 'quotations/quotation_confirm_delete.html', {'quotation': quotation})


# ==============================================================================
# PROFORMA INVOICE VIEWS
# ==============================================================================

@login_required
def proforma_generate_from_quotation(request, pk):
    """
    Creates a new Proforma Invoice from an existing Quotation.
    Pre-fills matching customer, item, and financial data without modifying the source quotation.
    """
    from decimal import Decimal
    from django.utils import timezone

    quotation = get_object_or_404(Quotation, pk=pk)
    next_p_num = get_next_proforma_number(quotation.customer_name)

    proforma = Proforma.objects.create(
        quotation=quotation,
        quotation_number_ref=quotation.quotation_number,
        proforma_number=next_p_num,
        proforma_date=timezone.now().date(),
        status='Draft',
        customer_name=quotation.customer_name,
        customer_address=quotation.customer_address,
        customer_contact=quotation.customer_phone or '',
        customer_email=quotation.customer_email,
        customer_gstin=quotation.customer_gstin or '',
        salutation='DEAR SIR,',
        po_reference=f"VERBAL P.O. THROUGH EMAIL REF {quotation.quotation_number}" if quotation.quotation_number else "VERBAL P.O. THROUGH EMAIL",
        po_date=quotation.quotation_date or timezone.now().date(),
        subject_note="WE ACKNOWLEDGE WITH THANKS RECEIPT OF YOUR {po_reference} DT. {po_date}, PLEASE FIND BELOW OUR PROFORMA INVOICE FOR YOUR KIND REFERENCE.",
        freight_label='',
        freight_amount=Decimal('0.00'),
        tax_type='GST',
        tax_rate=Decimal('18.00'),
        discount_percentage=quotation.discount_percentage or Decimal('0.00'),
        discount_amount=quotation.discount_amount or Decimal('0.00'),
        round_off_enabled=True,
        created_by=request.user if request.user.is_authenticated else None,
    )

    # Copy items from quotation into separate proforma items
    for idx, item in enumerate(quotation.items.all()):
        u = item.unit
        if u == 'NOS':
            u = 'No'
        sr = item.sr_no if (item.sr_no and str(item.sr_no).strip()) else f"{idx + 1:02d}."
        ProformaItem.objects.create(
            proforma=proforma,
            sr_no=sr,
            description=item.description,
            quantity=item.quantity if item.quantity is not None else Decimal('1.00'),
            unit=u or 'No',
            unit_rate=item.unit_rate if item.unit_rate is not None else Decimal('0.00'),
        )

    proforma.recalculate_totals()
    messages.success(
        request,
        f"Proforma Invoice {proforma.proforma_number} created from Quotation {quotation.quotation_number}. You can now make any necessary edits below."
    )
    return redirect('proforma_edit', pk=proforma.pk)


@login_required
def proforma_create(request):
    """Create a new blank Proforma Invoice directly."""
    next_p_num = get_next_proforma_number()
    proforma = Proforma.objects.create(
        proforma_number=next_p_num,
        created_by=request.user if request.user.is_authenticated else None
    )
    ProformaItem.objects.create(
        proforma=proforma,
        sr_no='01.',
        description='',
        quantity=1,
        unit='No',
        unit_rate=0
    )
    proforma.recalculate_totals()
    return redirect('proforma_edit', pk=proforma.pk)


@login_required
def proforma_edit(request, pk):
    """
    Proforma Edit View.
    Allows modifying all header fields, customer details, PO references, item rows, freight, and taxes.
    """
    proforma = get_object_or_404(Proforma, pk=pk)

    if request.method == 'POST':
        form = ProformaForm(request.POST, instance=proforma)
        formset = ProformaItemFormSet(request.POST, instance=proforma)

        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                saved_proforma = form.save()
                formset.save()
                saved_proforma.refresh_from_db()
                saved_proforma.recalculate_totals()

            messages.success(request, f"Proforma {saved_proforma.proforma_number} saved successfully!")
            if 'save_and_preview' in request.POST or 'save_and_pdf' in request.POST:
                return redirect('proforma_pdf_preview', pk=saved_proforma.pk)
            return redirect('proforma_edit', pk=saved_proforma.pk)
        else:
            err_list = []
            for field, errs in form.errors.items():
                err_list.append(f"{field}: {', '.join(errs)}")
            for form_err in formset.errors:
                if form_err:
                    for field, errs in form_err.items():
                        err_list.append(f"Item {field}: {', '.join(errs)}")
            err_msg = "Please correct the errors in the form: " + " | ".join(err_list) if err_list else "Please correct the errors in the form."
            messages.error(request, err_msg)
    else:
        form = ProformaForm(instance=proforma)
        formset = ProformaItemFormSet(instance=proforma)

    initial_customers = list(Customer.objects.filter(is_active=True).order_by('name')[:30])
    if proforma.customer_name:
        existing_cust = Customer.objects.filter(name__iexact=proforma.customer_name.strip(), is_active=True).first()
        if existing_cust and not any(c.id == existing_cust.id for c in initial_customers):
            initial_customers.insert(0, existing_cust)

    return render(request, 'quotations/proforma_form.html', {
        'form': form,
        'formset': formset,
        'proforma': proforma,
        'customers': initial_customers,
        'title': f'Edit Proforma: {proforma.proforma_number}',
    })


@login_required
def proforma_detail(request, pk):
    """
    Proforma Detail / Preview Page.
    Visual presentation faithfully mirroring the reference Proforma Invoice.
    """
    proforma = get_object_or_404(Proforma, pk=pk)
    proforma.recalculate_totals()
    items = proforma.items.all()
    logo_path = os.path.join(settings.BASE_DIR, 'quotations', 'static', 'images', 'logo.png')
    stamp_path = os.path.join(settings.BASE_DIR, 'quotations', 'static', 'images', 'stamp.png')

    return render(request, 'quotations/proforma_detail.html', {
        'proforma': proforma,
        'items': items,
        'logo_path': logo_path if os.path.exists(logo_path) else None,
        'stamp_path': stamp_path if os.path.exists(stamp_path) else None,
    })


@login_required
def proforma_list(request):
    """
    Proforma History / Tracking view.
    Includes search, filtering by date, status, customer, and action buttons.
    """
    from django.core.paginator import Paginator
    from django.db.models import Count

    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()

    proformas_qs = Proforma.objects.select_related('quotation')

    if query:
        proformas_qs = proformas_qs.filter(
            Q(proforma_number__icontains=query) |
            Q(customer_name__icontains=query) |
            Q(quotation_number_ref__icontains=query) |
            Q(attention_to__icontains=query)
        )

    if status_filter:
        proformas_qs = proformas_qs.filter(status=status_filter)

    if date_from:
        proformas_qs = proformas_qs.filter(proforma_date__gte=date_from)

    if date_to:
        proformas_qs = proformas_qs.filter(proforma_date__lte=date_to)

    proformas_qs = proformas_qs.annotate(item_count=Count('items')).order_by('-created_at')

    total_count = proformas_qs.count()
    paginator = Paginator(proformas_qs, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'quotations/proforma_list.html', {
        'page_obj': page_obj,
        'proformas': page_obj,
        'query': query,
        'status_filter': status_filter,
        'date_from': date_from,
        'date_to': date_to,
        'total_count': total_count,
    })


@login_required
def proforma_download_pdf(request, pk):
    """Generate and trigger download of the branded Proforma PDF."""
    proforma = get_object_or_404(Proforma, pk=pk)
    proforma.recalculate_totals()
    items = proforma.items.all()
    logo_path = os.path.join(settings.BASE_DIR, 'quotations', 'static', 'images', 'logo.png')
    stamp_path = os.path.join(settings.BASE_DIR, 'quotations', 'static', 'images', 'stamp.png')

    context = {
        'proforma': proforma,
        'items': items,
        'logo_path': logo_path if os.path.exists(logo_path) else None,
        'stamp_path': stamp_path if os.path.exists(stamp_path) else None,
    }

    pdf_content = render_to_pdf('quotations/proforma_pdf_template.html', context)

    if pdf_content:
        safe_num = re.sub(r'[^A-Za-z0-9_\-\.]', '_', str(proforma.proforma_number or proforma.pk))
        filename = f"Proforma_{safe_num}.pdf"
        response = HttpResponse(pdf_content, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response

    return HttpResponse("Error generating Proforma PDF. Please check server logs.", status=500)


@login_required
def proforma_view_pdf(request, pk):
    """Stream Proforma PDF directly in browser tab viewer."""
    proforma = get_object_or_404(Proforma, pk=pk)
    proforma.recalculate_totals()
    items = proforma.items.all()
    logo_path = os.path.join(settings.BASE_DIR, 'quotations', 'static', 'images', 'logo.png')
    stamp_path = os.path.join(settings.BASE_DIR, 'quotations', 'static', 'images', 'stamp.png')

    context = {
        'proforma': proforma,
        'items': items,
        'logo_path': logo_path if os.path.exists(logo_path) else None,
        'stamp_path': stamp_path if os.path.exists(stamp_path) else None,
    }

    pdf_content = render_to_pdf('quotations/proforma_pdf_template.html', context)

    if pdf_content:
        safe_num = re.sub(r'[^A-Za-z0-9_\-\.]', '_', str(proforma.proforma_number or proforma.pk))
        filename = f"Proforma_{safe_num}.pdf"
        response = HttpResponse(pdf_content, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response

    return HttpResponse("Error rendering Proforma PDF", status=500)


@login_required
def proforma_delete(request, pk):
    """Delete a Proforma Invoice with confirmation."""
    proforma = get_object_or_404(Proforma, pk=pk)
    if request.method == 'POST':
        p_num = proforma.proforma_number
        proforma.delete()
        messages.success(request, f"Proforma '{p_num}' deleted successfully.")
        return redirect('proforma_list')
    return render(request, 'quotations/proforma_confirm_delete.html', {'proforma': proforma})

