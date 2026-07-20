# ── NEW FILE: careers/selectors/evidence.py ──────────────────────────────
"""
Read-only queries that gather raw evidence for a profile from every
upstream source (Subjects, Questionnaire attempts, Psychometric
responses). Selectors NEVER write, NEVER call other services, and
NEVER contain business/scoring logic — that's what services/ is for.
This split follows the standard Django "services vs selectors" pattern
(business logic vs. query logic), which keeps the ORM query surface
testable in isolation from scoring math.

ASSUMPTIONS — the Subject/ProfileSubject/SubjectRequirement models and
the CareerPsychometric* models were not part of the uploaded files, so
field names below are best-guesses based on the architecture brief.
Anywhere marked "ADJUST:" needs to match your actual field names before
this will run.
"""
from __future__ import annotations

from decimal import Decimal,InvalidOperation

from core.models import TagSourceType,Tag
from careers.services.types import TagEvidence
from careers.constants import GRADE_MAP


def get_subject_evidence(profile) -> list[TagEvidence]:
    """
    Subject -> Tag evidence. Each Subject auto-creates a Tag (per the
    architecture brief); ProfileSubject stores the grade.

    ADJUST: assumes `ProfileSubject.profile`, `.subject`, `.grade`
    (0-100 scale) and `Subject.tag` (the auto-created Tag FK).
    """
    from accounts.models import ProfileSubject  # local import avoids app-loading order issues

    evidence = []
    qs = (
        ProfileSubject.objects
        .filter(profile=profile)
        .select_related("subject")
    )

    # 2. Get all subject names from the queryset
    subject_names = [ps.subject.name for ps in qs]

    # 3. Fetch tags matching those names and build a quick lookup dictionary
    tag_map = {
        tag.title: tag.id 
        for tag in Tag.objects.filter(title__in=subject_names)
    }

    for profile_subject in qs:
        tag_id = tag_map.get(profile_subject.subject.name)
        if not tag_id:
            continue  # Skip if no matching Tag was found
        
        raw_grade = str(profile_subject.grade).strip().upper()
        
        # 1. Try direct numeric conversion (in case someone entered "85" instead of "A")
        try:
            numeric_score = Decimal(raw_grade)
        except InvalidOperation:
            # 2. Look up letter grade in map; default to 0 if unknown/blank
            numeric_score = Decimal(GRADE_MAP.get(raw_grade, 0))

        # Avoid processing unmapped/empty grades
        if numeric_score == Decimal("0"):
            continue

        evidence.append(
            TagEvidence(
                tag_id=tag_id,
                raw_signal=numeric_score / Decimal("100"),
                source_type=TagSourceType.SUBJECT,
                source_id=profile_subject.id,
                source_confidence=Decimal("1.0"),
                source_weight=Decimal("1.0"),
            )
        )
    return evidence


def get_assessment_evidence(profile) -> list[TagEvidence]:
    """
    QuestionnaireAttempt -> QuestionResponse -> Tag evidence, weighted
    by QuestionnaireTag.coupling_strength and scaled by the attempt's
    AttemptScore.weighted_score.

    Only COMPLETED attempts with a computed AttemptScore contribute.
    Uses the most recent completed attempt per questionnaire — retakes
    supersede earlier attempts rather than both counting (avoids
    double-weighting a user who retried a few times).
    """
    from assessments.models import (
        QuestionnaireAttempt, QuestionnaireTag, AttemptStatus,
    )

    evidence = []

    attempts = (
        QuestionnaireAttempt.objects
        .filter(profile=profile, status=AttemptStatus.COMPLETED, score__isnull=False)
        .select_related("score", "questionnaire")
        .order_by("questionnaire_id", "-completed_at")
        .distinct("questionnaire_id")
    )
    
    for attempt in attempts:
        weighted_score_ratio = attempt.score.percentage / Decimal("100")
        q_tags = (
            QuestionnaireTag.objects
            .filter(questionnaire=attempt.questionnaire)
            .select_related("tag")
        )
        
        for qtag in q_tags:
            coupling = qtag.coupling_strength or Decimal("1.0")
            evidence.append(
                TagEvidence(
                    tag_id=qtag.tag_id,
                    raw_signal=weighted_score_ratio,
                    source_type=TagSourceType.QUESTIONNAIRE,
                    source_id=attempt.id,
                    source_confidence=Decimal("0.9") if qtag.is_primary else Decimal("0.7"),
                    source_weight=coupling,
                )
            )
    return evidence


def get_psychometric_evidence(profile) -> list[TagEvidence]:
    """
    CareerPsychometricResponse -> Tag evidence via chosen answer options.

    Psychometric questions have no "correct" answer — the signal is
    which trait the CHOSEN option maps to, not whether the choice was
    right. Confidence is intentionally lower than assessment evidence
    (0.6 vs 0.7-0.9) since psychometric self-report is a noisier signal
    than a graded assessment or an academic grade.

    ADJUST: assumes CareerPsychometricChoice has a `tag` FK and a
    `weight` field, and CareerPsychometricResponseAnswer links a
    response to the chosen choice(s).
    """
    from careers.models import ( 
        CareerPsychometricResponse, CareerPsychometricResponseAnswer,
    )

    evidence = []
    responses = (
        CareerPsychometricResponse.objects
        .filter(user=profile, status="COMPLETED")
        .order_by("questionnaire_id", "-completed_at")
    )
    seen_tests = set()
    for response in responses:
        if response.questionnaire_id in seen_tests:
            continue  # keep only the most recent completed attempt per test
        seen_tests.add(response.questionnaire_id)

        answers = (
            CareerPsychometricResponseAnswer.objects
            .filter(response=response)
            .select_related("choice", "choice__tag")
        )
        for answer in answers:
            choice = answer.choice
            if not getattr(choice, "tag_id", None):
                continue
            evidence.append(
                TagEvidence(
                    tag_id=choice.tag_id,
                    raw_signal=Decimal(str(choice.weight)),
                    source_type=TagSourceType.CAREER_PSYCHOMETRIC,
                    source_id=response.id,
                    source_confidence=Decimal("0.6"),
                    source_weight=Decimal("1.0"),
                )
            )
    return evidence


def collect_all_evidence(profile) -> list[TagEvidence]:
    """Single entry point the engine calls — gathers every source."""
    return [
        *get_subject_evidence(profile),
        *get_assessment_evidence(profile),
        *get_psychometric_evidence(profile),
    ]
