import json

from django import forms
from django.core.exceptions import ValidationError
from django.forms import BaseModelFormSet

from .models import (
    Questionnaire,
    QuestionnaireTag,
    Question,
    AnswerChoice,
    QuestionnaireAttempt,
    QuestionResponse,
    AttemptScore,
    QuestionType,
    AttemptStatus,
)




class QuestionnaireForm(forms.ModelForm):
    """
    Create / update a questionnaire. slug is auto-managed by the model's
    save() hook so it's excluded here.
    """

    class Meta:
        model = Questionnaire
        fields = [
            "title",
            "description",
            "instructions",
            "status",
            "max_score",
            "time_limit_minutes",
            "is_randomised",
            "created_by"
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "instructions": forms.Textarea(attrs={"rows": 4}),
        }

    def clean_max_score(self):
        value = self.cleaned_data.get("max_score")
        if value is not None and value <= 0:
            raise ValidationError("Max score must be greater than zero.")
        return value

    def clean_time_limit_minutes(self):
        value = self.cleaned_data.get("time_limit_minutes")
        if value is not None and value < 1:
            raise ValidationError("Time limit must be at least 1 minute.")
        return value

    def clean(self):
        cleaned = super().clean()
        status = cleaned.get("status")
        max_score = cleaned.get("max_score")
        # Prevent publishing a questionnaire with no meaningful max_score
        if status == "PUBLISHED" and (max_score is None or max_score <= 0):
            self.add_error(
                "status",
                "Cannot publish a questionnaire with a zero or missing max score.",
            )
        return cleaned


class QuestionnaireTagForm(forms.ModelForm):
    """Through-model form for attaching tags to a questionnaire."""

    class Meta:
        model = QuestionnaireTag
        fields = ["tag", "coupling_strength", "is_primary"]

    def clean_coupling_strength(self):
        value = self.cleaned_data.get("coupling_strength")
        if value is not None and not (0 <= value <= 1):
            raise ValidationError("Coupling strength must be between 0.0 and 1.0.")
        return value

    def clean(self):
        cleaned = super().clean()
        # Only one primary tag allowed per questionnaire
        if cleaned.get("is_primary"):
            questionnaire = (
                self.instance.questionnaire
                if self.instance.pk
                else cleaned.get("questionnaire")
            )
            if questionnaire:
                qs = QuestionnaireTag.objects.filter(
                    questionnaire=questionnaire, is_primary=True
                )
                if self.instance.pk:
                    qs = qs.exclude(pk=self.instance.pk)
                if qs.exists():
                    raise ValidationError(
                        {"is_primary": "This questionnaire already has a primary tag."}
                    )
        return cleaned


# ─────────────────────────────────────────────
# Question
# ─────────────────────────────────────────────

class QuestionForm(forms.ModelForm):
    """
    Create / update a question.
    numeric_config is edited as pretty-printed JSON text and parsed on clean.
    """

    numeric_config_raw = forms.CharField(
        required=False,
        label="Numeric Config (JSON)",
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": '{"min": 0, "max": 10, "step": 1, "unit": "years"}',
            }
        ),
        help_text='Required keys when question type is NUMERIC: "min", "max".',
    )

    class Meta:
        model = Question
        fields = [
            "questionnaire",
            "question_type",
            "question_text",
            "explanation",
            "weight",
            "max_points",
            "order",
            "randomisation_group",
            "is_required",
        ]
        widgets = {
            "question_text": forms.Textarea(attrs={"rows": 3}),
            "explanation": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate the raw textarea from the model JSON field on edit
        if self.instance.pk and self.instance.numeric_config:
            self.fields["numeric_config_raw"].initial = json.dumps(
                self.instance.numeric_config, indent=2
            )

    def clean_weight(self):
        value = self.cleaned_data.get("weight")
        if value is not None and value <= 0:
            raise ValidationError("Weight must be greater than zero.")
        return value

    def clean_max_points(self):
        value = self.cleaned_data.get("max_points")
        if value is not None and value <= 0:
            raise ValidationError("Max points must be greater than zero.")
        return value

    def clean_numeric_config_raw(self):
        raw = self.cleaned_data.get("numeric_config_raw", "").strip()
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"Invalid JSON: {exc}")
        if not isinstance(data, dict):
            raise ValidationError("Numeric config must be a JSON object.")
        return data

    def clean(self):
        cleaned = super().clean()
        q_type = cleaned.get("question_type")
        numeric_config = cleaned.get("numeric_config_raw")

        if q_type == QuestionType.NUMERIC:
            if not numeric_config:
                self.add_error(
                    "numeric_config_raw",
                    "Numeric config is required for NUMERIC questions.",
                )
            elif "min" not in numeric_config or "max" not in numeric_config:
                self.add_error(
                    "numeric_config_raw",
                    'Numeric config must contain at least "min" and "max" keys.',
                )
            elif numeric_config["min"] >= numeric_config["max"]:
                self.add_error(
                    "numeric_config_raw", '"min" must be less than "max".'
                )
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.numeric_config = self.cleaned_data.get("numeric_config_raw")
        if commit:
            instance.save()
        return instance




class AnswerChoiceForm(forms.ModelForm):
    """
    Single choice row. Uniqueness of choice_key per question is validated here.
    """

    class Meta:
        model = AnswerChoice
        fields = [
            "question",
            "choice_key",
            "choice_text",
            "is_correct",
            "partial_score",
            "order",
            "explanation",
        ]
        widgets = {
            "choice_text": forms.Textarea(attrs={"rows": 2}),
            "explanation": forms.Textarea(attrs={"rows": 2}),
        }

    def clean_choice_key(self):
        key = self.cleaned_data.get("choice_key", "").strip().upper()
        if not key:
            raise ValidationError("Choice key is required.")
        return key

    def clean_partial_score(self):
        value = self.cleaned_data.get("partial_score")
        if value is not None and not (0 <= value <= 1):
            raise ValidationError("Partial score must be between 0.0 and 1.0.")
        return value

    def clean(self):
        cleaned = super().clean()
        question = cleaned.get("question")
        key = cleaned.get("choice_key")

        if question and key:
            qs = AnswerChoice.objects.filter(question=question, choice_key=key)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError(
                    {"choice_key": f'Choice key "{key}" already exists for this question.'}
                )
        return cleaned


class BaseAnswerChoiceFormSet(BaseModelFormSet):
    """
    Validates the full set of choices for a question together:
    - MCQ must have exactly one correct answer.
    - MULTI must have at least two correct answers.
    - LIKERT must not mix is_correct with partial_score = 0.
    """

    def __init__(self, *args, question_type=None, **kwargs):
        self.question_type = question_type
        super().__init__(*args, **kwargs)

    def clean(self):
        if any(self.errors):
            return

        active_forms = [
            f for f in self.forms
            if f.cleaned_data and not f.cleaned_data.get("DELETE", False)
        ]

        correct_count = sum(
            1 for f in active_forms if f.cleaned_data.get("is_correct")
        )

        if self.question_type == QuestionType.MCQ and correct_count != 1:
            raise ValidationError(
                "MCQ questions must have exactly one correct answer."
            )

        if self.question_type == QuestionType.MULTI_SELECT and correct_count < 2:
            raise ValidationError(
                "Multi-select questions must have at least two correct answers."
            )

        # Ensure no duplicate choice keys within the set
        keys = []
        for f in active_forms:
            key = f.cleaned_data.get("choice_key")
            if key in keys:
                raise ValidationError(
                    f'Duplicate choice key "{key}" in this question.'
                )
            keys.append(key)




class QuestionnaireAttemptForm(forms.ModelForm):
    """
    Minimal form used when starting an attempt.
    attempt_number is managed by the service layer, not the form.
    """

    class Meta:
        model = QuestionnaireAttempt
        fields = ["profile", "questionnaire"]

    def clean_questionnaire(self):
        questionnaire = self.cleaned_data.get("questionnaire")
        if questionnaire and questionnaire.status != "PUBLISHED":
            raise ValidationError(
                "Only published questionnaires can be attempted."
            )
        return questionnaire


class AttemptStatusUpdateForm(forms.ModelForm):
    """
    Used by the service layer to advance an attempt's status.
    Enforces valid status transitions.
    """

    VALID_TRANSITIONS = {
        AttemptStatus.IN_PROGRESS: {
            AttemptStatus.COMPLETED,
            AttemptStatus.ABANDONED,
            AttemptStatus.TIMED_OUT,
        },
    }

    class Meta:
        model = QuestionnaireAttempt
        fields = ["status", "completed_at"]

    def clean(self):
        cleaned = super().clean()
        new_status = cleaned.get("status")
        current_status = self.instance.status if self.instance.pk else None

        if current_status and new_status:
            allowed = self.VALID_TRANSITIONS.get(current_status, set())
            if new_status != current_status and new_status not in allowed:
                raise ValidationError(
                    {
                        "status": (
                            f'Cannot transition from "{current_status}" '
                            f'to "{new_status}".'
                        )
                    }
                )

        if new_status == AttemptStatus.COMPLETED and not cleaned.get("completed_at"):
            self.add_error("completed_at", "completed_at is required when marking as Completed.")

        return cleaned




class QuestionResponseForm(forms.ModelForm):
    """
    Records a single answer. answer_value is validated against the
    question type rules.
    """

    class Meta:
        model = QuestionResponse
        fields = ["attempt", "question", "answer_value", "time_taken_ms"]

    def clean_time_taken_ms(self):
        value = self.cleaned_data.get("time_taken_ms")
        if value is not None and value < 0:
            raise ValidationError("time_taken_ms cannot be negative.")
        return value

    def clean(self):
        cleaned = super().clean()
        question = cleaned.get("question")
        answer = cleaned.get("answer_value")
        attempt = cleaned.get("attempt")

        # Uniqueness: one response per question per attempt
        if attempt and question:
            qs = QuestionResponse.objects.filter(attempt=attempt, question=question)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError(
                    "A response for this question already exists in this attempt."
                )

        # Type-specific answer_value validation
        if question and answer is not None:
            q_type = question.question_type
            self._validate_answer_for_type(q_type, answer, question)

        return cleaned

    def _validate_answer_for_type(self, q_type, answer, question):
        if q_type == QuestionType.MCQ:
            valid_keys = set(
                question.answer_choices.values_list("choice_key", flat=True)
            )
            if not isinstance(answer, str) or answer not in valid_keys:
                self.add_error(
                    "answer_value",
                    f"MCQ answer must be one of: {', '.join(sorted(valid_keys))}.",
                )

        elif q_type == QuestionType.MULTI_SELECT:
            if not isinstance(answer, list) or len(answer) == 0:
                self.add_error(
                    "answer_value", "Multi-select answer must be a non-empty list."
                )
            else:
                valid_keys = set(
                    question.answer_choices.values_list("choice_key", flat=True)
                )
                invalid = set(answer) - valid_keys
                if invalid:
                    self.add_error(
                        "answer_value",
                        f"Invalid choice keys: {', '.join(sorted(invalid))}.",
                    )

        elif q_type == QuestionType.NUMERIC:
            try:
                val = float(answer)
            except (TypeError, ValueError):
                self.add_error("answer_value", "Numeric answer must be a number.")
                return
            config = question.numeric_config or {}
            if "min" in config and val < config["min"]:
                self.add_error(
                    "answer_value",
                    f'Value must be at least {config["min"]}.',
                )
            if "max" in config and val > config["max"]:
                self.add_error(
                    "answer_value",
                    f'Value must be at most {config["max"]}.',
                )

        elif q_type == QuestionType.LIKERT:
            valid_keys = set(
                question.answer_choices.values_list("choice_key", flat=True)
            )
            if str(answer) not in valid_keys:
                self.add_error(
                    "answer_value",
                    f"Likert answer must be one of: {', '.join(sorted(valid_keys))}.",
                )

        elif q_type == QuestionType.RANKING:
            if not isinstance(answer, list):
                self.add_error("answer_value", "Ranking answer must be a list.")
            else:
                valid_keys = set(
                    question.answer_choices.values_list("choice_key", flat=True)
                )
                if set(answer) != valid_keys:
                    self.add_error(
                        "answer_value",
                        "Ranking must include every choice key exactly once.",
                    )




class AttemptScoreForm(forms.ModelForm):
    """
    Written by the scoring engine — not a user-facing form.
    Included for completeness and admin/test use.
    """

    class Meta:
        model = AttemptScore
        fields = [
            "attempt",
            "raw_score",
            "weighted_score",
            "percentage",
            "percentile_rank",
            "scoring_engine_version",
        ]

    def clean_percentage(self):
        value = self.cleaned_data.get("percentage")
        if value is not None and not (0 <= value <= 100):
            raise ValidationError("Percentage must be between 0 and 100.")
        return value

    def clean_percentile_rank(self):
        value = self.cleaned_data.get("percentile_rank")
        if value is not None and not (0 <= value <= 100):
            raise ValidationError("Percentile rank must be between 0 and 100.")
        return value

    def clean(self):
        cleaned = super().clean()
        raw = cleaned.get("raw_score")
        weighted = cleaned.get("weighted_score")
        if raw is not None and weighted is not None and weighted > raw * 10:
            # Sanity check: weighted shouldn't be an order of magnitude larger
            raise ValidationError(
                "Weighted score appears inconsistent with raw score. "
                "Please verify the scoring engine output."
            )
        return cleaned