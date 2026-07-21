# ── NEW FILE: careers/tasks.py ────────────────────────────────────────────
"""
Celery tasks. Each task is intentionally thin — it fetches what it
needs, calls into services/selectors, and handles retry/error state.
No scoring or aggregation logic lives here.

Task design principles followed:
  - One profile per generation task (not batched) — a single user's
    failure/retry never blocks or re-triggers work for anyone else.
  - Idempotent where it matters: persist_recommendation() always CREATEs
    a new CareerRecommendation row rather than mutating one, so a retried
    task after a partial failure just produces one more (harmless) row,
    never a corrupted one.
  - tenacity handles in-process retry/backoff for transient failures
    (DB connection blips, SMTP timeouts); Celery's own retry handles
    task-level retry (worker crash, broker redelivery).
"""
from __future__ import annotations

import logging

from celery import shared_task
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from django.db import OperationalError

from careers.selectors.tags import get_cached_user_tag_vector
from careers.selectors.recommendations import get_pending_recommendations
from careers.services.engine.registry import get_active_engine, get_shadow_engines
from careers.services.persistence import persist_recommendation
from careers.services.emails import send_recommendation_email
from careers.services.aggregation import AggregatedTagScore

logger = logging.getLogger(__name__)

_DB_RETRY = retry(
    retry=retry_if_exception_type(OperationalError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,       # redeliver to another worker if this one dies mid-task
    reject_on_worker_lost=True,
)
def generate_recommendations_task(self, profile_id: int):
    """
    The main user-facing job: run the ACTIVE engine for one profile,
    persist the result, then enqueue the email send as a separate task
    (so a slow/failing SMTP provider never blocks recommendation
    generation, and so email can be retried independently).
    """
    from accounts.models import UserProfile  # local import, avoids app-loading order issues

    try:
        profile = UserProfile.objects.get(pk=profile_id)
        engine = get_active_engine()
        result = engine.generate(profile, is_shadow=False)
        # rank_careers() operates on the freshly-aggregated in-memory
        # vector inside the engine; for persistence's explanation step we
        # re-read the just-written cache rather than threading the raw
        # aggregated dict through the return value, keeping EngineResult
        # (Part 5/7's stable contract) free of engine-internal detail.
        user_vector_raw = get_cached_user_tag_vector(profile)
        user_vector = {
            tag_id: AggregatedTagScore(tag_id=tag_id, affinity_score=affinity, confidence=conf, evidence_count=n)
            for tag_id, (affinity, conf, n) in user_vector_raw.items()
        }
        recommendation = persist_recommendation(profile, result, user_vector)
        logger.info("Generated recommendation %s for profile %s (engine %s)",
                    recommendation.id, profile_id, engine.version)

        send_recommendation_email_task.delay(recommendation.id)
        return recommendation.id

    except UserProfile.DoesNotExist:
        logger.warning("generate_recommendations_task: profile %s no longer exists — skipping.", profile_id)
        return None
    except OperationalError as exc:
        # Transient DB issue — let Celery retry with backoff.
        raise self.retry(exc=exc, countdown=min(60 * (2 ** self.request.retries), 600))
    except Exception:
        logger.exception("generate_recommendations_task failed for profile %s", profile_id)
        raise


@shared_task(bind=True, max_retries=2)
def run_shadow_engines_task(self, profile_id: int):
    """
    Runs every shadow-flagged engine version for a profile and persists
    results under their own algorithm_version, WITHOUT sending email or
    being surfaced anywhere user-facing. This is how a candidate V2/V3
    engine gets evaluated against real traffic before promotion
    (Part 7's shadow-mode evaluation).
    """
    from accounts.models import UserProfile

    try:
        profile = UserProfile.objects.get(pk=profile_id)
        for engine in get_shadow_engines():
            result = engine.generate(profile, is_shadow=True)
            user_vector_raw = get_cached_user_tag_vector(profile)
            user_vector = {
                tag_id: AggregatedTagScore(tag_id=tag_id, affinity_score=a, confidence=c, evidence_count=n)
                for tag_id, (a, c, n) in user_vector_raw.items()
            }
            persist_recommendation(profile, result, user_vector)
    except UserProfile.DoesNotExist:
        logger.warning("run_shadow_engines_task: profile %s no longer exists — skipping.", profile_id)
    except Exception:
        logger.exception("run_shadow_engines_task failed for profile %s", profile_id)
        raise


@shared_task(bind=True, max_retries=5, default_retry_delay=120)
def send_recommendation_email_task(self, recommendation_id: int):
    from careers.models import CareerRecommendation

    try:
        recommendation = CareerRecommendation.objects.select_related("user__user").get(pk=recommendation_id)
    except CareerRecommendation.DoesNotExist:
        logger.warning("send_recommendation_email_task: recommendation %s no longer exists.", recommendation_id)
        return

    success = send_recommendation_email(recommendation)
    if not success:
        raise self.retry(countdown=120 * (2 ** self.request.retries))


@shared_task
def regenerate_all_recommendations_task(batch_size: int = 500):
    """
    Cron safety net (see celery beat schedule) — periodically re-enqueues
    generation for every profile, in case an event-triggered job was
    missed (dropped message, worker outage during a deploy, etc.) or the
    active engine version changed and historical users should be
    refreshed under it.

    Fans out to individual generate_recommendations_task calls rather
    than doing the work inline, so one slow/failing profile can't stall
    the whole batch, and normal per-task retry/monitoring applies.
    """
    from accounts.models import UserProfile

    profile_ids = UserProfile.objects.filter(is_active=True).values_list("id", flat=True).iterator(chunk_size=batch_size)
    count = 0
    for profile_id in profile_ids:
        generate_recommendations_task.delay(profile_id)
        count += 1
    logger.info("regenerate_all_recommendations_task enqueued %s profile jobs.", count)
    return count


@shared_task
def compute_percentile_ranks_task():
    """
    Population-level job: AttemptScore.percentile_rank is documented on
    the model itself as "Async-computed. NULL until population data
    available." — this is that computation. Requires the whole
    population's scores per questionnaire, so it can only run as a
    batch job, not per-attempt.

    Kept simple (single ORDER BY + enumerate) rather than a DB-side
    percentile function, since it needs to run against whichever DB
    backend the project uses — swap for a window function
    (PERCENT_RANK() OVER (...)) if you're on Postgres and this becomes
    a bottleneck at scale.
    """
    from assessments.models import AttemptScore, Questionnaire

    updated = 0
    for questionnaire_id in Questionnaire.objects.values_list("id", flat=True):
        scores = list(
            AttemptScore.objects
            .filter(attempt__questionnaire_id=questionnaire_id)
            .order_by("percentage")
            .values_list("id", flat=True)
        )
        n = len(scores)
        if n < 2:
            continue  # percentile rank is meaningless with <2 data points
        for index, score_id in enumerate(scores):
            percentile = round((index / (n - 1)) * 100, 4)
            AttemptScore.objects.filter(pk=score_id).update(percentile_rank=percentile)
            updated += 1
    logger.info("compute_percentile_ranks_task updated %s AttemptScore rows.", updated)
    return updated


@shared_task
def retry_stuck_recommendation_jobs_task():
    """
    Monitoring/self-healing task: finds CareerRecommendation rows stuck
    in PENDING/PROCESSING beyond a reasonable window and re-triggers
    generation. Guards against a task being lost between enqueue and
    execution (e.g. broker restart without message persistence).
    """
    stuck = get_pending_recommendations(limit=200)
    count = 0
    for rec in stuck:
        generate_recommendations_task.delay(rec.profile_id)
        count += 1
    if count:
        logger.warning("retry_stuck_recommendation_jobs_task re-enqueued %s stuck jobs.", count)
    return count
