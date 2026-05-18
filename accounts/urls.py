from django.urls import path
from .views import *

urlpatterns = [
    path("user-registration",user_registration,name="user_regisration"),
]