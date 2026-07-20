# ── NEW FILE: careers/services/emails.py ─────────────────────────────────
"""
Pipeline stage 10 (Email Generation) from the architecture doc.

Uses Django's built-in EmailMultiAlternatives — no extra email-sending
library needed for CID embedding, it's supported natively via
MIMEImage + Content-ID headers. `premailer` is used only to inline the
template's CSS, since most email clients (Outlook especially) ignore
<style> blocks in the <head>.

The logo is attached once per email as an inline (not regular)
attachment, referenced in the HTML template as:
    <img src="cid:company_logo" ... >
"""
from __future__ import annotations

import logging
from email.mime.image import MIMEImage
from pathlib import Path

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from premailer import transform

from careers.models import CareerRecommendation, RecommendationExplanation, ExplanationType

logger = logging.getLogger(__name__)

LOGO_PATH = Path(settings.BASE_DIR) / "core" / "static" / "core" / "img" / "edpal-logo.jpg"
LOGO_CONTENT_ID = "company_logo"


def _build_email_context(recommendation: CareerRecommendation) -> dict:
    details = recommendation.recommendation_details or {}
    ranked_careers = details.get("ranked_careers", [])[:3]  # top 3 in the email body

    career_ids = [rc["career_id"] for rc in ranked_careers]
    narratives = dict(
        RecommendationExplanation.objects
        .filter(recommendation=recommendation, explanation_type=ExplanationType.NARRATIVE)
        .values_list("explanation_data__career_id", "explanation_data__text")
    )

    from careers.models import Career
    career_titles = dict(Career.objects.filter(id__in=career_ids).values_list("id", "title"))

    top_careers = [
        {
            "title": career_titles.get(rc["career_id"], "Career"),
            "fit_score_pct": round(rc["fit_score"] * 100),
            "confidence_pct": round(rc["confidence_score"] * 100),
            "narrative": narratives.get(rc["career_id"], ""),
        }
        for rc in ranked_careers
    ]

    return {
        "profile": recommendation.user,
        "top_careers": top_careers,
        "recommendation_id": recommendation.id,
        "logo_cid": LOGO_CONTENT_ID,
    }


def build_recommendation_email(recommendation: CareerRecommendation) -> EmailMultiAlternatives:
    context = _build_email_context(recommendation)

    text_body = render_to_string("careers/emails/recommendation_email.txt", context)
    html_body_raw = render_to_string("careers/emails/recommendation_email.html", context)
    html_body = transform(html_body_raw)  # inline all CSS for email-client compatibility

    to_email = getattr(recommendation.user.user, "email", None)
    if not to_email:
        raise ValueError(f"Profile {recommendation.user_id} has no email address on file.")

    message = EmailMultiAlternatives(
        subject="Your career recommendations are ready",
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to_email],
    )
    message.attach_alternative(html_body, "text/html")
    message.mixed_subtype = "related"  # required for inline (CID) images to render correctly

    if LOGO_PATH.exists():
        with open(LOGO_PATH, "rb") as f:
            logo = MIMEImage(f.read())
        logo.add_header("Content-ID", f"<{LOGO_CONTENT_ID}>")
        logo.add_header("Content-Disposition", "inline", filename="logo.png")
        message.attach(logo)
    else:
        logger.warning("Recommendation email logo not found at %s — sending without it.", LOGO_PATH)

    return message


def send_recommendation_email(recommendation: CareerRecommendation) -> bool:
    """
    Sends the email and updates recommendation.email_status accordingly.
    Returns True on success. Does NOT raise on send failure — callers
    (the Celery task) decide whether/how to retry; this function just
    reports outcome via return value + the persisted status field so a
    failure is always visible in the admin, not just in logs.

    ADJUST: assumes CareerRecommendation has an `email_status` CharField
    (e.g. PENDING/SENT/FAILED) and an `email_sent_at` DateTimeField.
    """
    from django.utils import timezone

    try:
        message = build_recommendation_email(recommendation)
        message.send(fail_silently=False)
    except Exception:
        logger.exception("Failed to send recommendation email for recommendation_id=%s", recommendation.id)
        CareerRecommendation.objects.filter(pk=recommendation.pk).update(email_sent=False)
        return False

    CareerRecommendation.objects.filter(pk=recommendation.pk).update(
        email_sent=True, email_sent_at=timezone.now()
    )
    return True
