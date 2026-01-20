from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # Customer-facing routes
    path('', views.home, name='home'),
    path('new-order/', views.bundle_builder, name='bundle_builder'),
    path('new-order/snacks/', views.bundle_builder_snacks, name='bundle_builder_snacks'),
    path('new-order/juices/', views.bundle_builder_juices, name='bundle_builder_juices'),
    path('new-order/review/', views.bundle_builder_review, name='bundle_builder_review'),
    path('clear-session/', views.clear_bundle_session, name='clear_bundle_session'),
    
    # Legacy admin routes (redirect to new admin)
    path('dashboard/', views.dashboard, name='dashboard'),
    path('inventory/', views.inventory, name='inventory'),
]
