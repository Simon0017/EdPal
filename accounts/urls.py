from django.urls import path
from .views import *

urlpatterns = [
    path("user-registration",RegistrationView.as_view(),name="user_registration"),
    path("user-login",UserLogin.as_view(),name="user_login"),
    path("forgot-password", ForgotPassword.as_view(), name="forgot_password"),
    path("reset-password/<int:uid>/<str:token>/", ResetPassword.as_view(), name="reset_password"),
    path("search-subject",search_subjects_re,name="search_subjects"),
    path("user-dashboard",UserDashboard.as_view(),name="user_dashboard"),
    path('user-profile',UserProfile.as_view(),name='user_profile'),
    path('user-settings',UserSettings.as_view(),name='user_settings'),
]