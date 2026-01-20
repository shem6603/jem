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
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core import admin_views, views

urlpatterns = [
    # Favicon handler (browsers automatically request /favicon.ico)
    path('favicon.ico', views.favicon_ico, name='favicon_ico'),
    
    # Custom admin routes (must come BEFORE Django admin)
    path('admin/login/', admin_views.admin_login, name='admin_login'),
    path('admin/logout/', admin_views.admin_logout, name='admin_logout'),
    path('admin/dashboard/', admin_views.admin_dashboard, name='admin_dashboard'),
    path('admin/orders/', admin_views.admin_order_records, name='admin_order_records'),
    path('admin/inventory/', admin_views.admin_inventory, name='admin_inventory'),
    path('admin/inventory/add/', admin_views.admin_add_item, name='admin_add_item'),
    path('admin/inventory/<int:item_id>/edit/', admin_views.admin_edit_item, name='admin_edit_item'),
    path('admin/accounting/', admin_views.admin_accounting, name='admin_accounting'),
    path('admin/users/', admin_views.admin_users, name='admin_users'),
    path('admin/users/create/', admin_views.admin_create_user, name='admin_create_user'),
    path('admin/users/<int:user_id>/delete/', admin_views.admin_delete_user, name='admin_delete_user'),
    
    # Django default admin (must come AFTER custom routes)
    path('admin/', admin.site.urls),
    
    # Core app routes
    path('', include('core.urls')),
]

# Serve media files
# In production, configure your web server (Apache/Nginx) to serve /media/ directory
# For development, Django will serve them automatically
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    # Serve static files from STATICFILES_DIRS in development
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns
    urlpatterns += staticfiles_urlpatterns()
else:
    # In production, serve media files via Django (not recommended for high traffic)
    # Better to configure web server to serve /media/ directory directly
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
