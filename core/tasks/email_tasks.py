from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
import logging
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from core.decorators import outer_exception_handler
from email.mime.image import MIMEImage
import os

logger = logging.getLogger(__name__)

@shared_task
@outer_exception_handler(logger=logger)
def send_welcome_email(user,login_url):

    context = {
        "user":user,
        "company_url":login_url
    }

    html_content = render_to_string("emails/welcome.html", context)
    text_content = f"""
                    Hi {user.first_name}, welcome to Edpal!,\n
                    We are happy to welcome you to our community as we help you test yourself and find your career path.\n
                    Don't be a stranger.\n

                    From:\n
                        Edpal. 

                    """
    message = EmailMultiAlternatives(
        subject="Welcome to Edpal!",
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=user.email,
    )

    message.attach_alternative(html_content,"text/html")
    attach_logo(message)

    message.send()


@shared_task
@outer_exception_handler(logger=logger)
def send_reset_password_email(user,reset_url):
    context = {
        "user":user,
        "reset_url":reset_url
    }

    html_content = render_to_string("emails/reset_password.html", context)
    text_content = f"""
                    Hi {user.first_name},\nReset your password here: {reset_url}\n

                    From:\n
                        Edpal. 

                    """
    message = EmailMultiAlternatives(
        subject="Password Reset Request",
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=user.email,
    )

    message.attach_alternative(html_content,"text/html")
    attach_logo(message)

    message.send()


@outer_exception_handler(logger=logger)
def attach_logo(message:EmailMultiAlternatives):
    '''Reusable func to attach the site\n' logo in the message'''
    logo_path = os.path.join('static','core', 'img', 'edpal-logo.jpg')
    with open(logo_path, 'rb') as f:
        msg_img = MIMEImage(f.read())
        msg_img.add_header('Content-ID', '<edpal-logo>')
        msg_img.add_header('Content-Disposition', 'inline', filename='logo.png')
        message.attach(msg_img)