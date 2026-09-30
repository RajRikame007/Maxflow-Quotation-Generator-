import os
from django.conf import settings
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, Http404, JsonResponse
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
import re
from django.db import transaction
from django.db.models import Q, Case, When, Value, IntegerField
from .models import Quotation, QuotationItem, Product, Customer, UserProfile, get_next_quotation_number
from .forms import QuotationForm, QuotationItemFormSet, UserRegistrationForm, CustomerForm, ProductForm, UserProfileForm
from .utils import render_to_pdf
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

def home(request):
    """Dashboard / Homepage with recent quotations and summary."""
    recent_quotations = Quotation.objects.all()[:5]
    total_count = Quotation.objects.count()
    return render(request, 'quotations/home.html', {
        'recent_quotations': recent_quotations,
        'total_count': total_count,
    })

def quotation_list(request):
    """List all quotations with search and action options."""
    query = request.GET.get('q', '').strip()
    if query:
        quotations = Quotation.objects.filter(
            quotation_number__icontains=query
        ) | Quotation.objects.filter(
            customer_name__icontains=query
        )
    else:
        quotations = Quotation.objects.all()

    return render(request, 'quotations/quotation_list.html', {
        'quotations': quotations,
        'query': query,
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

def quotation_create(request):
    """Create a new quotation with dynamic item rows and auto-populated signatory name."""
    auto_sync_excel_if_modified()
    auto_sync_product_excel_if_modified()
    customers = Customer.objects.filter(is_active=True).order_by('name')
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
                    # Recalculate totals automatically on the backend
                    quotation.recalculate_totals()
                
                messages.success(request, f"Quotation '{quotation.quotation_number}' created successfully!")
                return redirect('quotation_detail', pk=quotation.pk)
            except Exception as e:
                messages.error(request, f"An error occurred while saving: {str(e)}")
        else:
            messages.error(request, "Please correct the errors in the form below.")
    else:
        initial_data = {
            'quotation_number': get_next_quotation_number(),
        }
        # Pre-populate customer details if customer_id passed in URL
        customer_id = request.GET.get('customer_id')
        if customer_id:
            try:
                cust = Customer.objects.get(pk=customer_id)
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
        'customers': customers,
        'customer_form': CustomerForm(),
        'title': 'Create New Quotation'
    })

def quotation_edit(request, pk):
    """Edit an existing quotation."""
    auto_sync_excel_if_modified()
    auto_sync_product_excel_if_modified()
    quotation = get_object_or_404(Quotation, pk=pk)
    customers = Customer.objects.filter(is_active=True).order_by('name')
    brands = [b for b in Product.objects.filter(is_active=True).values_list('category', flat=True).distinct().order_by('category') if b]
    initial_products = Product.objects.filter(is_active=True)[:30]

    if request.method == 'POST':
        form = QuotationForm(request.POST, instance=quotation)
        formset = QuotationItemFormSet(request.POST, instance=quotation)
        
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                quotation = form.save()
                formset.save()
                quotation.recalculate_totals()
            messages.success(request, f"Quotation '{quotation.quotation_number}' updated successfully!")
            return redirect('quotation_detail', pk=quotation.pk)
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = QuotationForm(instance=quotation)
        formset = QuotationItemFormSet(instance=quotation)

    return render(request, 'quotations/quotation_form.html', {
        'form': form,
        'formset': formset,
        'quotation': quotation,
        'products': initial_products,
        'brands': brands,
        'customers': customers,
        'customer_form': CustomerForm(),
        'title': f'Edit Quotation: {quotation.quotation_number}'
    })

def customer_list(request):
    """Customer Directory view to search and manage customers."""
    auto_sync_excel_if_modified()
    query = request.GET.get('q', '').strip()
    if query:
        customers = Customer.objects.filter(
            Q(name__icontains=query) |
            Q(gstin__icontains=query) |
            Q(address__icontains=query) |
            Q(mobile__icontains=query) |
            Q(email__icontains=query)
        )
    else:
        customers = Customer.objects.all().order_by('name')

    return render(request, 'quotations/customer_list.html', {
        'customers': customers,
        'customer_form': CustomerForm(),
        'query': query,
        'total_count': Customer.objects.count()
    })

def customer_create(request):
    """Add a new customer, saving directly into database and customer address raj.xlsx."""
    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            customer = form.save()
            excel_saved, excel_msg = append_or_update_customer_in_excel(customer)

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
            excel_saved, excel_msg = append_or_update_customer_in_excel(customer, original_name=original_name)

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


def customer_export_excel(request):
    """Sync/Write all customers from database into customer address raj.xlsx."""
    success, msg = sync_all_customers_to_excel()
    if success:
        messages.success(request, msg)
    else:
        messages.warning(request, msg)
    return redirect('customer_list')

def customer_sync_excel(request):
    """Re-sync customer master database directly from 'customer address raj.xlsx'."""
    from django.core.management import call_command
    try:
        call_command('import_customers')
        messages.success(request, "Customers have been successfully synchronized from 'customer address raj.xlsx'!")
    except Exception as e:
        messages.error(request, f"Failed to sync customers from Excel: {str(e)}")
    return redirect('customer_list')

def customer_search_api(request):
    """JSON API to search customers dynamically."""
    auto_sync_excel_if_modified()
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


def product_search_api(request):
    """
    JSON API for real-time live product searching across Item Name, Brand, and Description.
    Supports flexible matching ignoring hyphens, spaces, and letter case.
    Supports filtering by query (?q=...) and brand (?brand=...).
    Returns top 50 ranked matches.
    """
    auto_sync_product_excel_if_modified()
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


def product_list(request):
    """Directory view for Product List.xlsx with fast flexible search and brand filtering."""
    from django.core.paginator import Paginator
    auto_sync_product_excel_if_modified()
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


def product_export_excel(request):
    """Sync/Write all products from database into Product List.xlsx."""
    success, msg = sync_all_products_to_excel()
    if success:
        messages.success(request, msg)
    else:
        messages.warning(request, msg)
    return redirect('product_list')


def product_sync_excel(request):
    """Manually triggers re-import of products from 'Product List.xlsx'."""
    try:
        from django.core.management import call_command
        call_command('import_products')
        messages.success(request, "Products have been successfully synchronized from 'Product List.xlsx'!")
    except Exception as e:
        messages.error(request, f"Failed to sync products from Excel: {str(e)}")
    return redirect('product_list')


def quotation_detail(request, pk):
    """Preview the quotation layout in clean web format."""
    quotation = get_object_or_404(Quotation, pk=pk)
    logo_path = os.path.join(settings.BASE_DIR, 'quotations', 'static', 'images', 'logo.png')
    return render(request, 'quotations/quotation_detail.html', {
        'quotation': quotation,
        'items': quotation.items.all(),
        'logo_path': logo_path if os.path.exists(logo_path) else None,
    })

def quotation_download_pdf(request, pk):
    """Generate and trigger download of the PDF file."""
    quotation = get_object_or_404(Quotation, pk=pk)
    items = quotation.items.all()
    logo_path = os.path.join(settings.BASE_DIR, 'quotations', 'static', 'images', 'logo.png')
    
    context = {
        'quotation': quotation,
        'items': items,
        'logo_path': logo_path if os.path.exists(logo_path) else None,
    }
    
    pdf_content = render_to_pdf('quotations/pdf_template.html', context)
    
    if pdf_content:
        # Sanitize quotation number for clean filename
        safe_num = quotation.quotation_number.replace('/', '_').replace('\\', '_').replace(' ', '_')
        filename = f"Quotation_{safe_num}.pdf"
        response = HttpResponse(pdf_content, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    
    return HttpResponse("Error generating PDF. Please check server logs.", status=500)

def quotation_view_pdf(request, pk):
    """Stream PDF directly in the browser viewer."""
    quotation = get_object_or_404(Quotation, pk=pk)
    items = quotation.items.all()
    logo_path = os.path.join(settings.BASE_DIR, 'quotations', 'static', 'images', 'logo.png')
    
    context = {
        'quotation': quotation,
        'items': items,
        'logo_path': logo_path if os.path.exists(logo_path) else None,
    }
    
    pdf_content = render_to_pdf('quotations/pdf_template.html', context)
    
    if pdf_content:
        response = HttpResponse(pdf_content, content_type='application/pdf')
        response['Content-Disposition'] = 'inline; filename="preview.pdf"'
        return response
    
    return HttpResponse("Error rendering PDF", status=500)

def quotation_delete(request, pk):
    """Delete a quotation."""
    quotation = get_object_or_404(Quotation, pk=pk)
    if request.method == 'POST':
        q_num = quotation.quotation_number
        quotation.delete()
        messages.success(request, f"Quotation '{q_num}' deleted successfully.")
        return redirect('quotation_list')
    return render(request, 'quotations/quotation_confirm_delete.html', {'quotation': quotation})
