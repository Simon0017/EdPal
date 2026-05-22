from django.shortcuts import render
from .models import *
import logging
from django.views import View
from django.http import HttpRequest,JsonResponse
from django.contrib.auth import authenticate,login
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.views.decorators.http import require_GET
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.contrib.auth.models import User
from .forms import *
from rest_framework import status
import json

logger = logging.getLogger(__name__)
token_generator = PasswordResetTokenGenerator()

'''
FBV(s)
'''

@require_GET
def search_subjects_re(request:HttpRequest):
    try:
        query = request.GET.get("query")
        subject_q = Subject.objects.filter(name__iregex=query).values("id","name")
        
        if not subject_q.exists():
            return JsonResponse({
            "success": False,
            "error": f"Career \'{query}\' does not exist."
        }, status=status.HTTP_404_NOT_FOUND)

        return JsonResponse({
            "success":True,
            "message":list(subject_q)
        })
    
    except Exception as e:
        logger.error(str(e))
        return JsonResponse({
            "success": False,
            "error": str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



'''
CBV(s)
'''

class RegistrationView(View):
    '''Handles user registration ie both rendering the template and also hte post requesr
    '''
    template_name = "accounts/registration.html"

    def get(self,request:HttpRequest,*args,**kwargs):
        try:
            return render(request,self.template_name)
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


class UserLogin(View):
    '''Handles user Login ie both rendering the template and also hte post requesr
    '''

    template_name = "accounts/login.html"

    def get(self,request:HttpRequest,*args,**kwargs):
        try:
            return render(request,self.template_name)
        except Exception as e:
            logger.error(str(e))
            return JsonResponse({
                "success": False,
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self,request:HttpRequest,*args,**kwargs):
        try:
            username = request.POST.get("username")
            password = request.POST.get("password")

            auth  = authenticate(request,username=username,password=password)
            if auth is not None:
                login(request,auth)
            
                return JsonResponse({
                    "success":True,
                    "messsage":"Login successful"
                },status=status.HTTP_201_CREATED)
            
            else:
                return JsonResponse({
                    "success":False,
                    "messsage":"Login Failed"
                },status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(str(e))
            return JsonResponse({
                "success": False,
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ForgotPassword(View):
    '''
    Handles serving the forgot passsword template and the handling of the  token serving and email sending to the
    '''
    template_name = "accounts/forgot_password.html"

    def get(self,request:HttpRequest,*args,**kwargs):
        try:
            return render(request,self.template_name)
        except Exception as e:
            logger.error(str(e))
            return JsonResponse({
                "success": False,
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    
    def post(self,request:HttpRequest,*args,**kwargs):
        try:
            email = request.POST.get("email")

            if not email:
                return JsonResponse({
                    "success":False,
                    "messsage":"Email field missing"
                },status=status.HTTP_400_BAD_REQUEST) 

            user = get_object_or_404(User,email=email)
            token = token_generator.make_token(user)

            reset_path = reverse('reset-password', kwargs={'uid': user.pk, 'token': token})
            reset_url = request.build_absolute_uri(reset_path)

            # send the reset url in email via tasks

            return JsonResponse({
                "success":True,
                "messsage":"Check your email to reset the password"
            },status=status.HTTP_202_ACCEPTED)
        except Exception as e:
            logger.error(str(e))
            return JsonResponse({
                "success": False,
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

        
class ResetPassword(View):
    '''
    Handles serving the reset passsword template and the handling of the reset
    '''
    template_name = "accounts/reset_password.html"

    def get(self,request:HttpRequest,*args,**kwargs):
        try:
            return render(request,self.template_name)
        except Exception as e:
            logger.error(str(e))
            return JsonResponse({
                "success": False,
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    
    def post(self,request:HttpRequest,*args,**kwargs):
        try:
            uid = kwargs.get("uid")
            token = kwargs.get("token")
            new_password = request.POST.get("new_password")

            if not uid or not token:
                return JsonResponse({
                    "success":False,
                    "message":"User id or token missing in the request"
                },status=status.HTTP_400_BAD_REQUEST)
            
            user = get_object_or_404(User,pk=uid)

            is_valid = token_generator.check_token(user,token)

            if not is_valid:
                return JsonResponse({
                    "success":False,
                    "message":"The reset token has exipired. Try again"
                },status=status.HTTP_401_UNAUTHORIZED)

            user.set_password(new_password)
            user.save()

            user_auth = authenticate(request, username=user.username, password=new_password)

            if user_auth is not None:
                login(request, user_auth)
            else:
                return JsonResponse({
                    "success":False,
                    "message":"Authentication failed"
                },status=status.HTTP_401_UNAUTHORIZED)
            
            return JsonResponse({
                "success":True,
                "messsage":"Check your email to reset the password"
            },status=status.HTTP_202_ACCEPTED)
        except Exception as e:
            logger.error(str(e))
            return JsonResponse({
                "success": False,
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)