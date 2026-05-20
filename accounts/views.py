from django.shortcuts import render
from .models import *
import logging
from django.views import View
from django.http import HttpRequest,JsonResponse
from django.contrib.auth import authenticate,login
from .forms import *
from rest_framework import status

logger = logging.getLogger(__name__)

'''
FBV(s)
'''




'''
CBV(s)
'''

class RegistrationView(View):
    template_name = "accounts/registration.html"

    def get(self,request:HttpRequest,*args,**kwargs):
        try:
            return render(request,"accounts/registration.html")
        except Exception as e:
            logger.error(str(e))
            return JsonResponse({
                "success": False,
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def post(self,request:HttpRequest,*args,**kwargs):
        try:
            user_form = UserRegistrationForm(request.POST)
            user_profile_form = UserProfileForm(request.POST)
            careers_form = CareerPreferenceForm(request.POST)
            profile_subject_form = ProfileSubjectForm(request.POST)

            if (
                user_form.is_valid() and
                user_profile_form.is_valid() and
                careers_form.is_valid() and
                profile_subject_form.is_valid()
            ):
                user,password = user_form.save()

                user_profile = user_profile_form.save(commit=False)
                user_profile.user = user
                user_profile.save()

                careers = careers_form.save(commit=False)
                careers.profile = user_profile
                careers.save()

                subject = profile_subject_form.save(commit=False)
                subject.profile = user_profile
                subject.save()

                # send welcome email

                # login the user
                auth  = authenticate(request,username=user.username,password=password)
                if auth is not None:
                    login(request,auth)
                
                return JsonResponse({
                    "success":True,
                    "messsage":"Successfull registered"
                },status=status.HTTP_201_CREATED)
            
            else:
                logger.error(
                    str(user_form.errors) + 
                    str(careers_form.errors) +
                    str(user_profile_form.errors) +
                    str(profile_subject_form.errors)
                )

                return JsonResponse({
                    "success": False,
                    "errors": str(user_form.errors) + 
                            str(careers_form.errors) +
                            str(user_profile_form.errors) +
                            str(profile_subject_form.errors)
                }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(str(e))
            return JsonResponse({
                "success": False,
                "errors": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
