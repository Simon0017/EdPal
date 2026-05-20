from django.urls import path
from .views import *

urlpatterns = [
    path("user-registration",RegistrationView.as_view(),name="user_regisration"),
]