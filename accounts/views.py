from django.shortcuts import render
from .models import *
import logging

logger = logging.getLogger(__name__)

'''
Templates rendering ---- FBV(s)
'''


def user_registration(request):
    '''Renders the template for the user registration'''
    try:
        return render(request,"accounts/registration.html")
    except Exception as e:
        logger.error(str(e))



'''
APIs views --------------CBV(s)
'''