from django.urls import path
from .views import *

CBVS = [
    path("tags",TagsView.as_view(),name="tags"),
    path("",HomePageView.as_view(),name="homepage")
]

FBVS = [
    
]


urlpatterns = [
    *CBVS,*FBVS
]