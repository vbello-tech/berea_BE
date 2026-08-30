from django.urls import path
from . import views

urlpatterns = [
    path('passage/', views.passage_view, name='passage'),
    path('concordance/', views.concordance_search_view, name='concordance-search'),
    path('strongs/', views.strongs_lookup_view, name='strongs-lookup'),
]
