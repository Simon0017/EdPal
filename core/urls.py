from django.urls import path
from .views import *

urlpatterns = [
    path("tags",TagsView.as_view(),name="tags"),
]