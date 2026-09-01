"""
URL configuration for config project.
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('bible.urls')),
    path('api/', include('notes.urls')),
    path('api/auth/', include('accounts.urls')),
    path('api/', include('search.urls')),
    path('api/', include('sermon.urls')),
]

