from django.dispatch import receiver
from django.http import HttpRequest

from allauth.account.signals import (
    user_signed_up,
)

import logging
from .models import UserProfile

logger = logging.getLogger(__name__)

@receiver(user_signed_up)
def on_user_signed_up(request:HttpRequest, user, **kwargs):
    try:
        logger.info(f"New user of email: {user.email}.Setting up...")
        profile_instance = UserProfile(
            user=user
        )
        profile_instance.save()

    except Exception as e:
        logger.error(str(e))

