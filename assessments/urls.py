from django.urls import path
from .views import *


CBVS = [
    path("administer-questionnare",AdminQuestinnare.as_view(),name="administer_questionnare"),
    path("questionnares",ListQuestionnares.as_view(),name="questionnare_list"),
    path("questionnares/<int:pk>",ManageQuestionnares.as_view(),name="questionnare_detail"),
    path("attempt-questionnare/<int:pk>",AttemptQuestionnaire.as_view(),name="attempt_questionnare"),
    path("user-questionnares",UserQuestionnaires.as_view(),name="user_questionnares"),
    path("user-results",UserResults.as_view(),name="user_results"),
    path('fetch-questionnaires',FetchQuestionnaires.as_view(),name='fetch_questionnaires'),
]

FBVS = [
    path('list_questionnares',get_questionnnaire_list,name="list-questionnares"),
]


urlpatterns = [
    *CBVS,*FBVS
]