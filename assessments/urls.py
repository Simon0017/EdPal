from django.urls import path
from .views import *

urlpatterns = [
    path("administer-questionnare",AdminQuestinnare.as_view(),name="administer_questionnare"),
    
]