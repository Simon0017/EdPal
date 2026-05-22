from django.urls import path
from .views import *

urlpatterns = [
    path("search-careers",search_careers_re,name="search_careers")
]