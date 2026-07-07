from django.urls import path
from .views import *


CBVS = [

]

FBVS = [
    path("search-careers",search_careers_re,name="search_careers")
]


urlpatterns = [
    *CBVS,*FBVS
]