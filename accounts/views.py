from django.shortcuts import render
from .models import *
import logging
from django.views import View
from django.http import HttpRequest,JsonResponse
from django.contrib.auth import authenticate,login
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.views.decorators.http import require_GET,require_POST
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.contrib.auth.models import User
from .forms import *
from rest_framework import status
import json
from datetime import date
from core.decorators import outer_exception_handler
from core.tasks.email_tasks import send_welcome_email,send_reset_password_email
from .selectors.dashboard_pop import DashboardService
from .services.user_sessions import get_active_sessions_for_user
from .services.user_settings import (
    delete_user_account,
    delete_user_session,
    user_set_remember_me,
    update_notification_preferences,
    change_user_password,
    logout_user
)


logger = logging.getLogger(__name__)
token_generator = PasswordResetTokenGenerator()

'''
FBV(s)
'''

@require_GET
@outer_exception_handler(logger)
def search_subjects_re(request:HttpRequest):
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

@require_POST
@outer_exception_handler(logger)
def upload_profile_avatar(request:HttpRequest):
    avatar_file = request.FILES.get("avatar")

    if not avatar_file:
        return JsonResponse({
            "success":False,
            "message":"Avatar file missing in the request"
        },status=status.HTTP_400_BAD_REQUEST)
    
    profile = request.user.profile
    profile.avatar = avatar_file
    profile.save()

    new_avatar_url = profile.avatar.url if profile.avatar else None

    return JsonResponse({
        "success":True,
        "message":"Avatar uploaded successfully",
        "avatar_url":new_avatar_url
    })

'''
CBV(s)
'''

class RegistrationView(View):
    '''Handles user registration ie both rendering the template and also hte post requesr
    '''
    template_name = "accounts/registration.html"

    @method_decorator(outer_exception_handler(logger))
    def get(self,request:HttpRequest,*args,**kwargs):
        return render(request,self.template_name)
    
    @method_decorator(outer_exception_handler(logger))
    def post(self,request:HttpRequest,*args,**kwargs):
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
            login_path = reverse("user_login")
            url = request.build_absolute_uri(login_path)

            send_welcome_email.delay(user.username,user.email,url)

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


class UserLogin(View):
    '''Handles user Login ie both rendering the template and also hte post requesr
    '''

    template_name = "accounts/login.html"

    @method_decorator(outer_exception_handler(logger))
    def get(self,request:HttpRequest,*args,**kwargs):
        return render(request,self.template_name)

    @method_decorator(outer_exception_handler(logger))
    def post(self,request:HttpRequest,*args,**kwargs):
        username = request.POST.get("username")
        password = request.POST.get("password")

        auth  = authenticate(request,username=username,password=password)
        if auth is not None:
            login(request,auth)
        
            return JsonResponse({
                "success":True,
                "messsage":"Login successful",
                "role":"staff" if auth.is_staff else "user"
            },status=status.HTTP_201_CREATED)
        
        else:
            return JsonResponse({
                "success":False,
                "messsage":"Login Failed"
            },status=status.HTTP_400_BAD_REQUEST)



class ForgotPassword(View):
    '''
    Handles serving the forgot passsword template and the handling of the  token serving and email sending to the
    '''
    template_name = "accounts/forgot_password.html"

    @method_decorator(outer_exception_handler(logger))
    def get(self,request:HttpRequest,*args,**kwargs):
        return render(request,self.template_name)
        
    @method_decorator(outer_exception_handler(logger))
    def post(self,request:HttpRequest,*args,**kwargs):
        email = request.POST.get("email")
        if not email:
            return JsonResponse({
                "success":False,
                "messsage":"Email field missing"
            },status=status.HTTP_400_BAD_REQUEST) 

        user = get_object_or_404(User,email=email)
        token = token_generator.make_token(user)

        reset_path = reverse('reset_password', kwargs={'uid': user.pk, 'token': token})
        reset_url = request.build_absolute_uri(reset_path)

        # send the reset url in email via tasks
        send_reset_password_email.delay(user.username,user.email,reset_url)

        return JsonResponse({
            "success":True,
            "messsage":"Check your email to reset the password"
        },status=status.HTTP_202_ACCEPTED)
        

        
class ResetPassword(View):
    '''
    Handles serving the reset passsword template and the handling of the reset
    '''
    template_name = "accounts/reset_password.html"

    @method_decorator(outer_exception_handler(logger))
    def get(self,request:HttpRequest,*args,**kwargs):
        return render(request,self.template_name)
        
    @method_decorator(outer_exception_handler(logger))
    def post(self,request:HttpRequest,*args,**kwargs):
        uid = kwargs.get("uid")
        token = kwargs.get("token")
        new_password = request.POST.get("new_password")

        if new_password is None:
            return JsonResponse({
                "success":False,
                "message":"New password missing in the request"
            },status=status.HTTP_400_BAD_REQUEST)

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
            "messsage":"Password reset completed successfully"
        },status=status.HTTP_202_ACCEPTED)
    
    
class UserDashboard(View):
    '''Handles rendering the user dashboard'''
    template_name = "accounts/user_dashboard.html"

    @method_decorator(login_required)
    @method_decorator(outer_exception_handler(logger))
    def get(self,request:HttpRequest,*args,**kwargs):
        dashboard = DashboardService(request)
        metrics = dashboard.stats
        score_trends = dashboard.score_trend
        latest_q = dashboard.latest_questionnaires
        trending_tags = dashboard.trending_tags
        category = dashboard.category
        quote = dashboard.quote_of_the_day

        context = {
            "data":{
                **metrics,
                "score_trend":score_trends,
                "latest_questionnaires":latest_q,
                "trending_tags":trending_tags,
                "categories":category
            },
            "quote":quote
        }

        return render(request,self.template_name,context)
    
    @method_decorator(login_required)
    @method_decorator(outer_exception_handler(logger))
    def post(self,request:HttpRequest,*args,**kwargs):
        pass



class UserProfile(View):
    '''Handles rendering the user profile'''
    template_name = "accounts/user_profile.html"

    @method_decorator(login_required)
    @method_decorator(outer_exception_handler(logger))
    def get(self,request:HttpRequest,*args,**kwargs):
        data = {
            "user": {
                "id": request.user.id,
                "username": request.user.username,
                "first_name": request.user.first_name,
                "last_name":request.user.last_name,
                "email":request.user.email
            },
            "profile": {
                "date_of_birth": request.user.profile.date_of_birth.strftime("%Y-%m-%d") if request.user.profile.date_of_birth else None,
                "about_me": request.user.profile.about_me,
                "avatar_url": request.user.profile.avatar.url if request.user.profile.avatar else None,
                "subjects": list(request.user.profile.subjects.values("id", "name"))
            }
        }

        context = {
            "data":data
        }

        return render(request,self.template_name,context)
    
    @method_decorator(login_required)
    @method_decorator(outer_exception_handler(logger))
    def put(self,request:HttpRequest,*args,**kwargs):
        data:dict = json.loads(request.body.decode())

        first_name = data.get("first_name")
        last_name = data.get("last_name")
        email = data.get("email")
        date_of_birth = data.get("date_of_birth")
        about_me = data.get("about_me")
        subject_ids = [sid for sid in data.get("subject_ids", []) if sid is not None]

        user = request.user
        profile = request.user.profile
        
        user.first_name = first_name if first_name else user.first_name
        user.last_name = last_name if last_name else user.last_name
        user.email = email if email else user.email

        if date_of_birth:
            profile.date_of_birth = date.fromisoformat(date_of_birth)

        profile.about_me = about_me if about_me else profile.about_me
        
        new_ids = set(subject_ids)
        current_ids = set(
            ProfileSubject.objects.filter(profile=profile)
            .values_list("subject_id", flat=True)
        )

        # Remove subjects that were unselected
        ProfileSubject.objects.filter(
            profile=profile,
            subject_id__in=current_ids - new_ids
        ).delete()

        # Add newly selected subjects
        ProfileSubject.objects.bulk_create([
            ProfileSubject(profile=profile, subject_id=sid)
            for sid in new_ids - current_ids
        ])

        user.save()
        profile.save()

        return JsonResponse({
            "success":True,
            "message":"Profile updated successfully"
        },status=status.HTTP_200_OK)


class UserSettings(View):
    '''Handles rendering the user settings'''
    template_name = "accounts/user_settings.html"

    @method_decorator(login_required)
    @method_decorator(outer_exception_handler(logger))
    def get(self,request:HttpRequest,*args,**kwargs):
        current_user = request.user
        current_key = request.session.session_key

        active_sessions = get_active_sessions_for_user(current_user, current_key)

        data = {
            "user": {
                "username": request.user.username
            },
            "settings": {
                "theme": "light",
                "remember_me": True,
                "sessions": active_sessions,
                "notifications": {
                    "email": True,
                    "sms": True,
                    "push": True
                }
            }
        }

        context = {
            "data":data
        }

        return render(request,self.template_name,context)
    
    @method_decorator(login_required)
    @method_decorator(outer_exception_handler(logger))
    def post(self,request:HttpRequest,*args,**kwargs):
        data:dict = json.loads(request.body)

        COMMANDS = {
            "remember-me": lambda request, data: user_set_remember_me(
                request.user,
                data.get("remember_me", False),
            ),
            "change-password": lambda request, data: change_user_password(
                request.user,
                data.get("current_password"),
                data.get("new_password"),
            ),
            "logout": lambda request, data: logout_user(request),
            "notifications": lambda request, data: update_notification_preferences(
                request.user,
                data.get("notifications", {}),
            ),
            "delete-account": lambda request, data: delete_user_account(
                request.user,
                data.get("confirm_username"),
            ),
        }

        command = data.get("command")

        handler = COMMANDS.get(command)

        if handler is None:
            return JsonResponse(
                {
                    "success": False,
                    "message": "Unknown command.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        success = handler(request, data)

        return JsonResponse(
            {
                "success": success,
            },
            status=status.HTTP_200_OK if success else status.HTTP_400_BAD_REQUEST,
        )

    @method_decorator(login_required)
    @method_decorator(outer_exception_handler(logger))
    def delete(self,request:HttpRequest,*args,**kwargs):
        data:dict = json.loads(request.body)
        
        DELETE_COMMANDS = {
            "delete-session": lambda request, data: delete_user_session(
                request.user,
                data.get("sessionId"),
            ),
        }

        command = data.get("command")

        handler = DELETE_COMMANDS.get(command)

        if handler is None:
            return JsonResponse(
                {
                    "success": False,
                    "message": "Unknown command.",
                },
                status=400,
            )

        success = handler(request, data)

        return JsonResponse(
            {
                "success": success,
            },
            status=200 if success else 400,
        )