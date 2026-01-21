from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # Customer-facing routes
    path('', views.home, name='home'),
    
    # New ordering flow
    path('order/', views.bundle_builder, name='bundle_builder'),
    path('order/select/', views.bundle_builder_select, name='bundle_builder_select'),
    path('order/details/', views.bundle_builder_details, name='bundle_builder_details'),
    path('order/pending/<str:order_ref>/', views.order_pending, name='order_pending'),
    path('order/payment/<str:order_ref>/', views.order_payment, name='order_payment'),
    path('order/status/<str:order_ref>/', views.order_status, name='order_status'),
    path('check-order/', views.check_order, name='check_order'),
    path('clear-session/', views.clear_bundle_session, name='clear_bundle_session'),
    path('offline/', views.offline, name='offline'),
    
    # Legacy routes (redirects)
    path('new-order/', views.bundle_builder, name='bundle_builder_legacy'),
    path('new-order/snacks/', views.bundle_builder_snacks, name='bundle_builder_snacks'),
    path('new-order/juices/', views.bundle_builder_juices, name='bundle_builder_juices'),
    path('new-order/review/', views.bundle_builder_review, name='bundle_builder_review'),
    
    # Legacy admin routes (redirect to new admin)
    path('dashboard/', views.dashboard, name='dashboard'),
    path('inventory/', views.inventory, name='inventory'),
]
