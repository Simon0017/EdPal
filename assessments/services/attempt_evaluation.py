from __future__ import annotations

from django.http import HttpRequest
from django.db import transaction, IntegrityError
from django.db.models import Prefetch, Max
import json
import logging
from typing import Any, Optional

from .feedback_classifier import Feedback

logger = logging.getLogger(__name__)

from ..models import *
from ..forms import QuestionResponseForm, AttemptScoreForm


# Defensive caps
MAX_ANSWERS_PER_ATTEMPT = 500
MAX_ATTEMPT_NUMBER_RETRIES = 3


class EvaluationError(Exception):
    """
    Raised for anything that should stop evaluation, with a machine-readable
    `code` so the calling view can map it to the right HTTP status instead
    of parsing message strings.

    codes: invalid_payload | unauthenticated | not_found | conflict | server_error
    """
    def __init__(self, message: str, code: str = "server_error"):
        super().__init__(message)
        self.message = message
        self.code = code


class AttemptEvaluationService:
    """
    Evaluates a submitted questionnaire attempt and persists the resulting
    QuestionnaireAttempt / QuestionResponse / AttemptScore rows.

    Usage:
        service = AttemptEvaluationService(request)
        try:
            result = service.evaluate()
        except EvaluationError as e:
            return JsonResponse({"error": e.message}, status=map_code(e.code))
    """

    def __init__(self, request: HttpRequest):
        self.request = request
        self.body_data: dict[str, Any] = {}
        self.parse_error: Optional[str] = None

        try:
            raw = request.body.decode()
            parsed = json.loads(raw) if raw else {}
            if not isinstance(parsed, dict):
                self.parse_error = "Request body must be a JSON object."
            else:
                self.body_data = parsed
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.warning("Failed to parse request body as JSON: %s", e)
            self.parse_error = "Request body is not valid JSON."

        self.questinnare_id = self.body_data.get('questionnaire_id')
        self.answers = self.body_data.get('answers')
        self.send_email: bool = bool(self.body_data.get('send_email', False))
        self.started_at = self.body_data.get('started_at')
        self.completed_at = self.body_data.get('completed_at')

        self.questionnaire: Optional["Questionnaire"] = None
        self.attempt_id: Optional[int] = None
        self.attempt_instance: Optional["QuestionnaireAttempt"] = None
        self._question_lookup: dict[int, "Question"] = {}

        # Guards against evaluate()/build_response accidentally being called
        # twice and creating a second attempt as a side effect.
        self._evaluated = False
        self._cached_response: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def validate(self) -> None:
        """Cheap, pre-DB sanity checks. Raises EvaluationError on failure."""
        if self.parse_error:
            raise EvaluationError(self.parse_error, code="invalid_payload")

        user = getattr(self.request, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            raise EvaluationError("Authentication is required.", code="unauthenticated")

        try:
            profile = user.profile
        except Exception:
            profile = None
        if profile is None:
            raise EvaluationError("No profile associated with this user.", code="unauthenticated")

        if self.questinnare_id is None:
            raise EvaluationError("questionnaire_id is required.", code="invalid_payload")
        try:
            self.questinnare_id = int(self.questinnare_id)
        except (TypeError, ValueError):
            raise EvaluationError("questionnaire_id must be an integer.", code="invalid_payload")

        if self.answers is None:
            raise EvaluationError("answers is required.", code="invalid_payload")
        if not isinstance(self.answers, list):
            raise EvaluationError("answers must be a list.", code="invalid_payload")
        if len(self.answers) == 0:
            raise EvaluationError("answers cannot be empty.", code="invalid_payload")
        if len(self.answers) > MAX_ANSWERS_PER_ATTEMPT:
            raise EvaluationError(
                f"Too many answers submitted (max {MAX_ANSWERS_PER_ATTEMPT}).",
                code="invalid_payload",
            )
        for i, answer in enumerate(self.answers):
            if not isinstance(answer, dict):
                raise EvaluationError(f"answers[{i}] must be an object.", code="invalid_payload")
            if "question_id" not in answer:
                raise EvaluationError(f"answers[{i}] is missing question_id.", code="invalid_payload")

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------
    def setup(self) -> None:
        prefetch_questions = Prefetch(
            "questions",
            queryset=Question.objects.prefetch_related("answer_choices")
        )

        self.questionnaire = (
            Questionnaire.objects
            .filter(id=self.questinnare_id)
            .prefetch_related(prefetch_questions)
            .first()
        )

        if self.questionnaire is None:
            raise EvaluationError("Questionnaire not found.", code="not_found")

        if self.questionnaire.max_score is None or float(self.questionnaire.max_score) <= 0:
            raise EvaluationError(
                "Questionnaire is misconfigured (max_score must be greater than zero).",
                code="server_error",
            )

        # In-memory lookup so per-answer scoring never re-queries the DB for
        # something already prefetched (previously: a query per answer, plus
        # a broken existence check via `question.exists` — a bound method
        # reference, always truthy — instead of `question.exists()`).
        self._question_lookup = {q.id: q for q in self.questionnaire.questions.all()}

    def save_response(self):
        pass

    # ------------------------------------------------------------------
    # Core scoring
    # ------------------------------------------------------------------
    def handle_answers(self) -> float:
        """
        Creates the attempt and scores every answer. The attempt_number
        allocation is retried on IntegrityError (optimistic concurrency) in
        case two requests race for the same profile+questionnaire. A single
        malformed answer is skipped and logged rather than aborting the
        whole submission and losing an already-created attempt.
        """
        profile = self.request.user.profile

        for retry in range(MAX_ATTEMPT_NUMBER_RETRIES):
            try:
                with transaction.atomic():
                    latest_attempt_number = QuestionnaireAttempt.objects.filter(
                        profile=profile,
                        questionnaire_id=self.questinnare_id
                    ).aggregate(max_attempt=Max("attempt_number"))["max_attempt"]

                    new_attempt_number = (latest_attempt_number or 0) + 1

                    attempt_instance = QuestionnaireAttempt(
                        profile=profile,
                        questionnaire_id=self.questinnare_id,
                        status="COMPLETED",
                        attempt_number=new_attempt_number,
                        started_at = self.started_at,
                        completed_at = self.completed_at
                    )
                    attempt_instance.save()

                    self.attempt_id = new_attempt_number
                    self.attempt_instance = attempt_instance

                    return self._score_all_answers(attempt_instance)

            except IntegrityError as e:
                logger.warning(
                    "Attempt-number collision for profile=%s questionnaire=%s (retry %s): %s",
                    getattr(profile, "id", None), self.questinnare_id, retry, e
                )
                if retry == MAX_ATTEMPT_NUMBER_RETRIES - 1:
                    logger.exception("Exhausted retries creating attempt")
                    raise EvaluationError(
                        "Could not record this attempt due to a conflicting request. Please try again.",
                        code="conflict",
                    )
                continue

        # Unreachable, but keeps type-checkers happy.
        return 0.0

    def _score_all_answers(self, attempt_instance: "QuestionnaireAttempt") -> float:
        total_points = 0.0

        for answer in self.answers:
            try:
                question_id = answer.get("question_id")
                answer_value = answer.get("answer_value")

                try:
                    question_id = int(question_id)
                except (TypeError, ValueError):
                    logger.warning("Non-integer question_id %r, skipping.", question_id)
                    continue

                question = self._question_lookup.get(question_id)
                if question is None:
                    logger.warning(
                        "Question id %s does not belong to questionnaire %s, skipping.",
                        question_id, self.questinnare_id
                    )
                    continue

                data = {
                    "question": question,
                    "answer_value": json.dumps(answer_value),
                    "attempt": attempt_instance,
                }

                question_response_form = QuestionResponseForm(data=data)
                if not question_response_form.is_valid():
                    logger.warning(
                        "Invalid answer for question id %s, errors: %s, skipping.",
                        question_id, question_response_form.errors
                    )
                    continue

                response: QuestionResponse = question_response_form.save(commit=False)

                try:
                    answer_points = self.evaluate_question_answer(question, answer_value, response)
                    answer_points = float(answer_points) if answer_points is not None else 0.0
                except (TypeError, ValueError) as e:
                    logger.warning(
                        "Could not coerce score for question id %s: %s, awarding 0 points.",
                        question_id, e
                    )
                    answer_points = 0.0

                total_points += answer_points

            except Exception as e:
                # Defense in depth: one bad answer must never take down the
                # whole submission (previously, any exception here — e.g. a
                # None returned from a scoring handler — bubbled up and
                # caused the *entire* attempt to silently score as 0,
                # despite an attempt row already having been created).
                logger.exception("Unexpected error scoring one answer, skipping it: %s", e)
                continue

        return total_points

    # ------------------------------------------------------------------
    # Per-question-type scoring
    # ------------------------------------------------------------------
    def evaluate_question_answer(self, question: "Question", answer_value: Any, response: "QuestionResponse") -> float:
        handlers = {
            "MCQ": self.handle_mcq,
            "MULTI": self.handle_multi,
            "TEXT": self.handle_text,
            "NUMERIC": self.handle_numeric,
            "LIKERT": self.handle_likert,
            "RANKING": self.handle_ranking,
        }
        handler = handlers.get(question.question_type)
        if handler is None:
            logger.warning("Unknown question_type %s for question %s", question.question_type, question.id)
            return 0.0
        return handler(question, answer_value, response)

    def handle_mcq(self, question: "Question", answer_value: Any, response: "QuestionResponse") -> float:
        """Multiple Choice (single answer)."""
        try:
            # Read from the already-prefetched manager and filter in Python
            # rather than re-querying, and rather than relying on `.first()`
            # silently picking an arbitrary row if the data is misconfigured.
            choices = list(question.answer_choices.all())
            correct_choices = [c for c in choices if c.is_correct]

            if not correct_choices:
                logger.error("No correct choice configured for question %s", question.id)
                response.is_correct = False
                response.points_awarded = 0.0
                response.save()
                return 0.0

            if len(correct_choices) > 1:
                logger.warning(
                    "Question %s has %d correct choices configured for an MCQ; using the first.",
                    question.id, len(correct_choices)
                )

            correct = correct_choices[0]
            max_points = float(question.max_points or 0)

            is_correct = str(answer_value).strip().lower() == str(correct.choice_key).strip().lower()
            response.is_correct = is_correct
            response.points_awarded = max_points if is_correct else 0.0
            response.save()

            return response.points_awarded

        except Exception as e:
            # Bug fix: this branch previously used a bare `return` (i.e.
            # returns None), which crashed the caller's `float(answer_points)`
            # and aborted the entire attempt via the outer try/except.
            logger.exception("Error scoring MCQ question %s: %s", question.id, e)
            return 0.0

    def handle_multi(self, question: "Question", answer_value: Any, response: "QuestionResponse") -> float:
        """Multiple Select (partial credit, penalized for both missed and extra/incorrect selections)."""
        try:
            if not isinstance(answer_value, list) or len(answer_value) == 0:
                response.is_correct = False
                response.points_awarded = 0.0
                response.save()
                return 0.0

            choices = list(question.answer_choices.all())
            correct_choices = [c.choice_key for c in choices if c.is_correct]
            max_points = float(question.max_points or 0)

            if not correct_choices:
                logger.error("No correct choices configured for MULTI question %s", question.id)
                response.is_correct = False
                response.points_awarded = 0.0
                response.save()
                return 0.0

            correct_lower = {str(c).strip().lower() for c in correct_choices}
            answer_lower = {str(a).strip().lower() for a in answer_value}

            intersection = correct_lower & answer_lower

            recall = len(intersection) / len(correct_lower)
            precision = len(intersection) / len(answer_lower)  # answer_lower is non-empty, checked above
            ratio = recall * precision

            points_awarded = max_points * ratio

            response.points_awarded = points_awarded
            response.is_correct = ratio == 1
            response.save()

            return points_awarded

        except Exception as e:
            logger.exception("Error scoring MULTI question %s: %s", question.id, e)
            return 0.0

    def handle_numeric(self, question: "Question", answer_value: Any, response: "QuestionResponse") -> float:
        """
        Numeric / Range. Correct target + tolerance are read from
        `question.numeric_config` (e.g. {"correct": 7.5, "tolerance": 0.5}).
        Falls back to an `is_correct` AnswerChoice whose choice_key holds the
        target value, for consistency with how MCQ stores its answer.
        """
        try:
            try:
                submitted = float(answer_value)
            except (TypeError, ValueError):
                logger.warning(
                    "Non-numeric answer_value %r for NUMERIC question %s, awarding 0.",
                    answer_value, question.id
                )
                response.is_correct = False
                response.points_awarded = 0.0
                response.save()
                return 0.0

            config = question.numeric_config or {}
            target = config.get("correct")
            tolerance = config.get("tolerance", config.get("step", 0)) or 0

            if target is None:
                choices = list(question.answer_choices.all())
                correct_choices = [c for c in choices if c.is_correct]
                if not correct_choices:
                    logger.error(
                        "No correct value configured for NUMERIC question %s "
                        "(neither numeric_config['correct'] nor an is_correct choice).",
                        question.id
                    )
                    response.is_correct = False
                    response.points_awarded = 0.0
                    response.save()
                    return 0.0
                try:
                    target = float(correct_choices[0].choice_key)
                except (TypeError, ValueError):
                    logger.error(
                        "Correct choice_key for NUMERIC question %s is not numeric.",
                        question.id
                    )
                    response.is_correct = False
                    response.points_awarded = 0.0
                    response.save()
                    return 0.0

            max_points = float(question.max_points or 0)
            is_correct = abs(submitted - float(target)) <= float(tolerance)

            response.is_correct = is_correct
            response.points_awarded = max_points if is_correct else 0.0
            response.save()

            return response.points_awarded

        except Exception as e:
            logger.exception("Error scoring NUMERIC question %s: %s", question.id, e)
            return 0.0

    def handle_text(self, question: "Question", answer_value: Any, response: "QuestionResponse") -> float:
        """
        Free text. Matches (case-insensitive, whitespace-trimmed) against
        any `is_correct` AnswerChoice.choice_text, so multiple acceptable
        phrasings can be configured as separate correct choices.
        """
        try:
            submitted = str(answer_value or "").strip().lower()

            if not submitted:
                response.is_correct = False
                response.points_awarded = 0.0
                response.save()
                return 0.0

            choices = list(question.answer_choices.all())
            acceptable = [str(c.choice_text or "").strip().lower() for c in choices if c.is_correct]

            if not acceptable:
                logger.error("No correct answer(s) configured for TEXT question %s", question.id)
                response.is_correct = False
                response.points_awarded = 0.0
                response.save()
                return 0.0

            max_points = float(question.max_points or 0)
            is_correct = submitted in acceptable

            response.is_correct = is_correct
            response.points_awarded = max_points if is_correct else 0.0
            response.save()

            return response.points_awarded

        except Exception as e:
            logger.exception("Error scoring TEXT question %s: %s", question.id, e)
            return 0.0

    def handle_likert(self, question: "Question", answer_value: Any, response: "QuestionResponse") -> float:
        """
        Likert scale. answer_value is the selected choice_key (e.g. "1".."5").
        Credit is `AnswerChoice.partial_score` (0..1) * max_points, per the
        model's own docstring for that field.
        """
        try:
            submitted = str(answer_value).strip().lower()

            choices = list(question.answer_choices.all())
            match = next((c for c in choices if str(c.choice_key).strip().lower() == submitted), None)

            if match is None:
                logger.warning(
                    "Answer %r for LIKERT question %s does not match any choice_key, awarding 0.",
                    answer_value, question.id
                )
                response.is_correct = False
                response.points_awarded = 0.0
                response.save()
                return 0.0

            max_points = float(question.max_points or 0)
            fraction = float(match.partial_score or 0)
            points_awarded = max_points * fraction

            response.points_awarded = points_awarded
            response.is_correct = fraction >= 1
            response.save()

            return points_awarded

        except Exception as e:
            logger.exception("Error scoring LIKERT question %s: %s", question.id, e)
            return 0.0

    def handle_ranking(self, question: "Question", answer_value: Any, response: "QuestionResponse") -> float:
        """
        Drag-to-rank. answer_value is a list of choice_keys in the order the
        user placed them. The correct order is the choices' own `order`
        field. Credit is the fraction of positions that match exactly.
        """
        try:
            if not isinstance(answer_value, list) or len(answer_value) == 0:
                response.is_correct = False
                response.points_awarded = 0.0
                response.save()
                return 0.0

            choices = sorted(question.answer_choices.all(), key=lambda c: c.order)
            correct_order = [str(c.choice_key).strip().lower() for c in choices]

            if not correct_order:
                logger.error("No choices configured for RANKING question %s", question.id)
                response.is_correct = False
                response.points_awarded = 0.0
                response.save()
                return 0.0

            submitted_order = [str(a).strip().lower() for a in answer_value]

            max_points = float(question.max_points or 0)
            positions = min(len(correct_order), len(submitted_order))
            matches = sum(
                1 for i in range(positions) if submitted_order[i] == correct_order[i]
            )
            ratio = matches / len(correct_order)

            points_awarded = max_points * ratio

            response.points_awarded = points_awarded
            response.is_correct = ratio == 1
            response.save()

            return points_awarded

        except Exception as e:
            logger.exception("Error scoring RANKING question %s: %s", question.id, e)
            return 0.0

    # ------------------------------------------------------------------
    # Response building
    # ------------------------------------------------------------------
    def evaluate(self) -> dict[str, Any]:
        """
        Runs validation, scoring, and persistence, and returns the report
        dict. The whole persistence step (attempt + responses + score) is
        one transaction: either it all lands, or none of it does — no more
        orphaned attempts with zero responses when scoring blows up
        partway through.

        Safe to call more than once: the first call's result is cached and
        replayed on subsequent calls instead of re-running (which would
        otherwise silently create a second attempt).
        """
        if self._evaluated:
            return self._cached_response

        self.validate()
        self.setup()

        with transaction.atomic():
            total_points = self.handle_answers()

            max_score = float(self.questionnaire.max_score)
            percentage = (total_points / max_score) * 100 if max_score > 0 else 0.0
            # Clamp defensively: weight/config mistakes elsewhere could in
            # theory push totals above max_score or below zero, and
            # Feedback.from_percentage raises ValueError outside [0, 100].
            percentage = min(max(percentage, 0.0), 100.0)

            passed = percentage >= 50
            score = total_points
            feedback = Feedback.from_percentage(percentage)
            message = feedback.message.split(".")

            response = {
                "percentage": round(percentage, 2),
                "passed": passed,
                "score": round(score, 2),
                "max_score": max_score,
                "feedback": message,
                "details": str(self.questionnaire.description),
                "email_sent": False,  # sending is not implemented yet
                "attempt_id": self.attempt_id,
            }

            attempt_score_data = {
                "attempt": self.attempt_instance,
                "raw_score": round(score, 2),
                "weighted_score": round(score, 2),
                "percentage": round(percentage, 2),
            }

            attempt_score_form = AttemptScoreForm(attempt_score_data)
            if not attempt_score_form.is_valid():
                logger.error("AttemptScore validation failed: %s", attempt_score_form.errors)
                # Raising here rolls back the whole transaction, including
                # the attempt and responses just written above.
                raise EvaluationError("Failed to persist the computed score.", code="server_error")

            attempt_score_form.save()

        self._cached_response = response
        self._evaluated = True
        return response

    @property
    def build_response(self) -> dict[str, Any]:
        """
        Backwards-compatible alias for `evaluate()`.

        Kept as a property because it used to do heavy DB writes on every
        attribute access (a footgun: accessing it twice created two
        attempts). It now delegates to `evaluate()`, which caches its
        result, so repeated access is idempotent. Failures still resolve to
        `{}` here to preserve the old calling contract — but real errors are
        logged with their category instead of silently vanishing. Callers
        that want to distinguish "bad request" from "server broke" should
        call `evaluate()` directly and catch `EvaluationError`.
        """
        try:
            return self.evaluate()
        except EvaluationError as e:
            logger.error("Evaluation failed [%s]: %s", e.code, e.message)
            return {}
        except Exception as e:
            logger.exception("Unexpected error during evaluation: %s", e)
            return {}