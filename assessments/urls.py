from django.urls import path
from .views import *

urlpatterns = [
    path("administer-questionnare",AdminQuestinnare.as_view(),name="administer_questionnare"),
    path("questionnares",ListQuestionnares.as_view(),name="questionnare_list"),
    path("questionnares<int:pk>",ManageQuestionnares.as_view(),name="questionnare_detail")
]