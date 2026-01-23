"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.http import FileResponse, Http404
from django.views.static import serve
from core import admin_views, views
import os
import mimetypes


def serve_media(request, path):
    """
    Custom media file serving view that works in production.
    This serves files from MEDIA_ROOT.
    """
    # Security: prevent directory traversal attacks
    path = path.replace('..', '').lstrip('/')
    
    # Build the full file path
    file_path = os.path.join(settings.MEDIA_ROOT, path)
    
    # Check if file exists
    if not os.path.exists(file_path) or not os.path.isfile(file_path):
        raise Http404(f"Media file not found: {path}")
    
    # Get the content type
    content_type, encoding = mimetypes.guess_type(file_path)
    if content_type is None:
        content_type = 'application/octet-stream'
    
    # Serve the file
    try:
        response = FileResponse(open(file_path, 'rb'), content_type=content_type)
        # Add cache headers for performance
        response['Cache-Control'] = 'public, max-age=86400'  # Cache for 1 day
        return response
    except IOError:
        raise Http404(f"Cannot read media file: {path}")


urlpatterns = [
    # Favicon handler (browsers automatically request /favicon.ico)
    path('favicon.ico', views.favicon_ico, name='favicon_ico'),
    
    # Custom admin routes (must come BEFORE Django admin)
    path('admin/login/', admin_views.admin_login, name='admin_login'),
    path('admin/logout/', admin_views.admin_logout, name='admin_logout'),
    path('admin/dashboard/', admin_views.admin_dashboard, name='admin_dashboard'),
    path('admin/orders/', admin_views.admin_order_records, name='admin_order_records'),
    path('admin/orders/add/', admin_views.admin_add_order, name='admin_add_order'),
    path('admin/orders/<int:order_id>/edit/', admin_views.admin_edit_order, name='admin_edit_order'),
    path('admin/inventory/', admin_views.admin_inventory, name='admin_inventory'),
    path('admin/inventory/add/', admin_views.admin_add_item, name='admin_add_item'),
    path('admin/inventory/<int:item_id>/edit/', admin_views.admin_edit_item, name='admin_edit_item'),
    path('admin/accounting/', admin_views.admin_accounting, name='admin_accounting'),
    path('admin/users/', admin_views.admin_users, name='admin_users'),
    path('admin/users/create/', admin_views.admin_create_user, name='admin_create_user'),
    path('admin/users/<int:user_id>/delete/', admin_views.admin_delete_user, name='admin_delete_user'),
    
    # Customer order management
    path('admin/customer-orders/', admin_views.admin_customer_orders, name='admin_customer_orders'),
    path('admin/customer-orders/<int:order_id>/', admin_views.admin_customer_order_detail, name='admin_customer_order_detail'),
    path('admin/banking/', admin_views.admin_banking_info, name='admin_banking_info'),
    path('admin/suggestions/', admin_views.admin_suggestions, name='admin_suggestions'),
    
    # Django default admin (must come AFTER custom routes)
    path('admin/', admin.site.urls),
    
    # Core app routes
    path('', include('core.urls')),
    
    # PWA routes
    path('', include('pwa.urls')),
]

# Serve media files - use custom view that works in production
# This MUST be added regardless of DEBUG setting
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve_media, name='serve_media'),
]

# Serve static files in development
if settings.DEBUG:
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns
    urlpatterns += staticfiles_urlpatterns()
