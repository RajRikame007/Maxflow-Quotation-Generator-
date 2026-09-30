from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('', views.home, name='home'),
    path('quotations/', views.quotation_list, name='quotation_list'),
    path('quotations/new/', views.quotation_create, name='quotation_create'),
    path('quotations/<int:pk>/', views.quotation_detail, name='quotation_detail'),
    path('quotations/<int:pk>/edit/', views.quotation_edit, name='quotation_edit'),
    path('quotations/<int:pk>/delete/', views.quotation_delete, name='quotation_delete'),
    path('quotations/<int:pk>/pdf/', views.quotation_download_pdf, name='quotation_pdf_download'),
    path('quotations/<int:pk>/pdf/preview/', views.quotation_view_pdf, name='quotation_pdf_preview'),
    path('customers/', views.customer_list, name='customer_list'),
    path('customers/add/', views.customer_create, name='customer_create'),
    path('customers/<int:pk>/edit/', views.customer_edit, name='customer_edit'),
    path('customers/<int:pk>/delete/', views.customer_delete, name='customer_delete'),
    path('customers/sync-excel/', views.customer_sync_excel, name='customer_sync_excel'),
    path('customers/export-excel/', views.customer_export_excel, name='customer_export_excel'),
    path('api/customers/search/', views.customer_search_api, name='customer_search_api'),
    path('products/', views.product_list, name='product_list'),
    path('products/add/', views.product_create, name='product_create'),
    path('products/<int:pk>/edit/', views.product_edit, name='product_edit'),
    path('products/<int:pk>/delete/', views.product_delete, name='product_delete'),
    path('products/sync-excel/', views.product_sync_excel, name='product_sync_excel'),
    path('products/export-excel/', views.product_export_excel, name='product_export_excel'),
    path('api/products/search/', views.product_search_api, name='product_search_api'),
]


