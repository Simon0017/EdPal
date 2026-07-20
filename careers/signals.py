# ── NEW FILE: careers/signals.py ─────────────────────────────────────────
"""
Event -> Celery job wiring (Part 3's "Input sources" trigger points:
assessment completion, psychometric completion, subject updates,
profile updates).

These are receivers living in the CAREERS app that listen to signals
from OTHER apps' models (assessments.AttemptScore, etc.) — this is the
standard, non-invasive way to react to events without editing those
apps' files directly.

Debouncing: a user completing several actions in quick succession
(e.g. retaking 2 questionnaires back to back) would otherwise enqueue
several redundant generation jobs. A short cache-based lock collapses
those into one job per profile per DEBOUNCE_SECONDS window, using
cache.add() as an atomic "set if not already set" — safe under
concurrent requests without needing a DB-level lock.
"""
from __future__ import annotations

import logging

from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from careers.tasks import generate_recommendations_task
from careers.models import CareerTag
from careers.selectors.tags import invalidate_career_tag_vector_cache

# NOTE: post_save's `sender` must be an actual model class — unlike
# ForeignKey, signals don't support lazy "app_label.ModelName" strings.
# Importing here is safe because this module is only ever imported from
# CoreConfig/CareersConfig.ready(), which Django guarantees runs after
# every app's models are loaded — so this can't hit app-registry timing
# issues or circular imports at Django startup.
from assessments.models import AttemptScore

logger = logging.getLogger(__name__)

DEBOUNCE_SECONDS = 30
DEBOUNCE_DELAY_SECONDS = 30  # matches the task countdown so the lock outlives the delay


def _enqueue_debounced(profile_id: int, reason: str) -> None:
    lock_key = f"recsys:pending_regen:{profile_id}"
    if not cache.add(lock_key, "1", timeout=DEBOUNCE_SECONDS):
        logger.debug("Recommendation regen for profile %s already queued (%s) — skipping duplicate.", profile_id, reason)
        return
    logger.info("Enqueuing recommendation regen for profile %s (trigger: %s)", profile_id, reason)
    generate_recommendations_task.apply_async(args=[profile_id], countdown=DEBOUNCE_DELAY_SECONDS)


# ── CareerTag changes invalidate the cached career-vector lookup ──────
@receiver(post_save, sender=CareerTag)
@receiver(post_delete, sender=CareerTag)
def on_career_tag_changed(sender, instance, **kwargs):
    invalidate_career_tag_vector_cache()


# ── Assessment completion ──────────────────────────────────────────────
@receiver(post_save, sender=AttemptScore)
def on_assessment_scored(sender, instance, created, **kwargs):
    if not created:
        return  # AttemptScore is immutable/append-only per its own docstring — only react to creation
    profile_id = instance.attempt.profile_id
    _enqueue_debounced(profile_id, reason="assessment_completed")


# ── Psychometric completion ────────────────────────────────────────────
# ADJUST: import your actual CareerPsychometricResponse model at the top
# of this file (same pattern as AttemptScore above — sender must be a
# real class, not a string), then wire it up:
#
# from careers.models_psychometric import CareerPsychometricResponse
#
# @receiver(post_save, sender=CareerPsychometricResponse)
# def on_psychometric_completed(sender, instance, created, **kwargs):
#     if instance.status != "COMPLETED":
#         return
#     _enqueue_debounced(instance.profile_id, reason="psychometric_completed")


# ── Subject / grade updates ────────────────────────────────────────────
# ADJUST: import your actual ProfileSubject model, same pattern.
#
# from accounts.models import ProfileSubject
#
# @receiver(post_save, sender=ProfileSubject)
# def on_subject_updated(sender, instance, **kwargs):
#     _enqueue_debounced(instance.profile_id, reason="subject_updated")


# ── Profile updates ─────────────────────────────────────────────────────
# ADJUST: import your actual UserProfile model, same pattern. Guard
# against firing on every trivial field change (e.g. last_login-style
# bookkeeping fields) if UserProfile has any — only fields that could
# plausibly shift tag evidence should trigger regeneration.
#
# from accounts.models import UserProfile
#
# @receiver(post_save, sender=UserProfile)
# def on_profile_updated(sender, instance, created, **kwargs):
#     if created:
#         return  # nothing to score yet on first creation
#     _enqueue_debounced(instance.id, reason="profile_updated")
