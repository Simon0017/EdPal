from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
import logging
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from core.decorators import outer_exception_handler
from email.mime.image import MIMEImage
from django.contrib.staticfiles import finders

logger = logging.getLogger(__name__)

@shared_task
def send_welcome_email(username,email,login_url):
    try:
        context = {
            "username":username,
            "company_url":login_url
        }

        html_content = render_to_string("emails/welcome.html", context)
        text_content = f"""
                        Hi {username}, welcome to Edpal!,\n
                        We are happy to welcome you to our community as we help you test yourself and find your career path.\n
                        Don't be a stranger.\n

                        From:\n
                            Edpal. 

                        """
        message = EmailMultiAlternatives(
            subject="Welcome to Edpal!",
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
        )

        message.attach_alternative(html_content,"text/html")
        attach_logo(message)

        message.send()

    except Exception as e:
        logger.error(str(e))

@shared_task
def send_reset_password_email(username,email,reset_url):
    try:
        context = {
            "username":username,
            "reset_url":reset_url
        }

        html_content = render_to_string("emails/reset_password.html", context)
        text_content = f"""
                        Hi {username},\nReset your password here: {reset_url}\n

                        From:\n
                            Edpal. 

                        """
        message = EmailMultiAlternatives(
            subject="Password Reset Request",
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
        )

        message.attach_alternative(html_content,"text/html")
        attach_logo(message)

        message.send()

    except Exception as e:
        logger.error(str(e))


def attach_logo(message:EmailMultiAlternatives):
    '''Reusable func to attach the site\n' logo in the message'''
    try:
        logo_path = finders.find('core/img/edpal-logo.jpg')

        if not logo_path:
            raise FileNotFoundError("Logo not found in static files")

        with open(logo_path, 'rb') as f:
            msg_img = MIMEImage(f.read())
            msg_img.add_header('Content-ID', '<edpal-logo>')
            msg_img.add_header('Content-Disposition', 'inline; filename="edpal-logo.jpg"')
            message.attach(msg_img)

    except Exception as e:
        logger.error(str(e))