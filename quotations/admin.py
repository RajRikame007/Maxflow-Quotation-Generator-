from django.contrib import admin
from .models import Quotation, QuotationItem, Product, Customer, UserProfile, Proforma, ProformaItem


class QuotationItemInline(admin.TabularInline):
    model = QuotationItem
    extra = 1

@admin.register(Quotation)
class QuotationAdmin(admin.ModelAdmin):
    list_display = ('quotation_number', 'customer_name', 'quotation_date', 'grand_total', 'created_at')
    search_fields = ('quotation_number', 'customer_name', 'signatory_name')
    list_filter = ('quotation_date', 'created_at')
    inlines = [QuotationItemInline]

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('model_code', 'category', 'unit_rate', 'hsn_code', 'unit', 'gst_rate', 'is_active')
    search_fields = ('model_code', 'description', 'category')
    list_filter = ('category', 'is_active')
    list_editable = ('unit_rate', 'hsn_code', 'is_active')

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'mobile', 'email', 'gstin', 'is_active')
    search_fields = ('name', 'gstin', 'mobile', 'email', 'address')
    list_filter = ('is_active', 'created_at')

from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Signatory Profile Details'

class CustomUserAdmin(BaseUserAdmin):
    inlines = [UserProfileInline]
    list_display = ('username', 'first_name', 'last_name', 'email', 'get_designation', 'get_phone', 'is_staff')

    def get_designation(self, obj):
        profile = getattr(obj, 'profile', None)
        return profile.designation if profile else '-'
    get_designation.short_description = 'Designation'

    def get_phone(self, obj):
        profile = getattr(obj, 'profile', None)
        return profile.phone if profile else '-'
    get_phone.short_description = 'Cell Number'

admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'designation', 'phone')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'designation', 'phone')


class ProformaItemInline(admin.TabularInline):
    model = ProformaItem
    extra = 1


@admin.register(Proforma)
class ProformaAdmin(admin.ModelAdmin):
    list_display = ('proforma_number', 'customer_name', 'quotation_number_ref', 'proforma_date', 'status', 'grand_total', 'created_at')
    search_fields = ('proforma_number', 'customer_name', 'quotation_number_ref', 'signatory_name')
    list_filter = ('status', 'tax_type', 'proforma_date', 'created_at')
    inlines = [ProformaItemInline]


