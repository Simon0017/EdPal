# Integrating the V1 Recommendation Engine

This walks through wiring everything from Part 1 and Part 2 into your
existing project, in the order it needs to happen. Nothing here should
break existing functionality — every step is additive.

---

## 0. Prerequisites

```bash
pip install -r requirements-recommendation-engine.txt
```

(Append that file's contents to your project's existing `requirements.txt`
first if you maintain one file.)

You'll also need a running Redis instance — used as both the Celery
broker/result backend and the Django cache backend (see
`settings_snippet.py`). One Redis instance is fine; the snippet uses
separate DB indices (`/0`, `/1`, `/2`) to keep broker, results, and cache
from colliding.

---

## 1. Drop in the Part 1 files (models + admin)

1. Merge `core/models_additions.py` into `core/models.py`.
2. Merge `core/admin_additions.py` into `core/admin.py`.
3. Add `core/signals.py` as a new file, and wire it into `core/apps.py`'s
   `ready()` method (shown in that file's header comment).
4. Merge `careers/models_additions.py` into `careers/models.py`.
5. Merge `careers/admin_additions.py` into `careers/admin.py`.
6. Apply the index snippets and the `AttemptScore.profile` migration
   from `MIGRATION_NOTES.md` to your actual `careers`, `accounts`, and
   `assessments` model files.

```bash
python manage.py makemigrations core careers assessments accounts
python manage.py migrate
```

Review the generated migrations before applying — confirm there's no
unexpected `AlterField`/`RemoveField` on anything you didn't intend to
touch. Everything from Part 1 should generate as `CreateModel`,
`AddField`, or `AddIndex` operations only.

---

## 2. Drop in the Part 2 files (engine)

Copy the following into your `careers` app, preserving the directory
structure:

```
careers/
  services/            ← entire directory
  selectors/            ← entire directory
  tasks.py
  signals.py
  templates/careers/emails/
  static/careers/emails/   ← then add your actual logo.png here
```

Merge `careers/apps_snippet.py` into your existing `careers/apps.py`
(the `ready()` method needs to import `careers.signals`).

**Field-name check before running anything:** several files are marked
`ADJUST:` in their docstrings — they were written against the
architecture brief's description of `Career`, `CareerRecommendation`,
`UserProfile`, `ProfileSubject`, and the psychometric models, none of
which were part of the uploaded files. Grep for `ADJUST:` across the
`careers/` directory and reconcile field names with your actual models
before deploying:

```bash
grep -rn "ADJUST" careers/
```

The two most consequential ones:
- `careers/selectors/evidence.py` → `get_psychometric_evidence()` — the
  import path and field names for your psychometric models.
- `careers/services/persistence.py` / `careers/selectors/recommendations.py`
  → exact field names on `CareerRecommendation` (`profile` vs `user`,
  `generated_at` vs `created_at`).

---

## 3. Celery setup

1. Add `celery_app_snippet.py`'s contents to `<project>/celery.py`
   (create it if it doesn't exist), adjusting the settings module path
   and app name at the top.
2. In `<project>/__init__.py`, ensure the Celery app loads on Django
   startup:

```python
from .celery import app as celery_app
__all__ = ("celery_app",)
```

3. Merge `settings_snippet.py` into your settings file: `INSTALLED_APPS`
   addition (`django_celery_beat`), the `CELERY_*` settings, the
   `CELERY_BEAT_SCHEDULE` crontab dict, and the `CACHES` config.
4. Run migrations for `django_celery_beat` (it ships its own):

```bash
python manage.py migrate django_celery_beat
```

---

## 4. Register the V1 engine

The engine code auto-registers `RuleBasedEngineV1` in
`careers/services/engine/registry.py`'s `_ENGINE_CLASSES` dict — no
action needed there. What you DO need to do is create the matching
`EngineVersion` row so the registry has something to activate:

```python
# one-time, e.g. in a data migration or via the admin
from careers.models import EngineVersion, EngineType

EngineVersion.objects.create(
    version_number="v1.0.0",       # must exactly match RuleBasedEngineV1.version
    engine_type=EngineType.RULE_BASED,
    is_active=True,
    description="Initial deterministic weighted-graph engine.",
)
```

Until this row exists with `is_active=True`, `get_active_engine()` will
raise `EngineVersion.DoesNotExist` — this is intentional (see that
selector's docstring): a misconfigured registry should fail loudly, not
silently pick something.

---

## 5. Logo for the email

Drop your actual logo file at:

```
careers/static/careers/emails/logo.png
```

(see `careers/static/careers/emails/README_LOGO.txt` for size
guidance). `services/emails.py` reads this exact path and embeds it via
`Content-ID`, referenced in the templates as `cid:company_logo`. If the
file is missing, the email still sends — just without the logo, and a
warning is logged.

---

## 6. Running it

**Start a worker and beat scheduler** (separate processes, typically
separate systemd services / Docker containers in production):

```bash
celery -A <project> worker -l info
celery -A <project> beat -l info
```

**Trigger a recommendation manually** (e.g. from the Django shell, to
verify end-to-end before relying on signals):

```python
from careers.tasks import generate_recommendations_task
generate_recommendations_task.delay(profile_id=123)
```

**Event-driven triggering** happens automatically once
`careers/signals.py` is wired up — completing an assessment
(`AttemptScore` creation) will enqueue a debounced regeneration job
30 seconds later. Uncomment and adjust the psychometric/subject/profile
receivers in that file once you've confirmed the field names.

---

## 7. Verifying the pipeline end-to-end

Checklist, in order, for a test profile with at least one completed
assessment:

1. `UserTagVector` rows exist for that profile after the task runs
   (`UserTagVector.objects.filter(profile=profile)`).
2. A `CareerRecommendation` row exists with `processing_status=COMPLETED`
   and a populated `recommendation_details` JSON field.
3. `RecommendationExplanation` rows exist for the top 5 careers
   (`TAG_CONTRIBUTION` and `NARRATIVE` types).
4. `email_status` on the `CareerRecommendation` row moves to `SENT`
   (check your email backend's console/log output if using the console
   backend in development).
5. In Django admin, `EngineVersion` shows exactly one `is_active=True`
   row.

---

## 8. Adding a future engine version (V2/V3/...) later

This is the part the whole architecture was designed to make easy:

1. Implement a new class in `careers/services/engine/` subclassing
   `BaseRecommendationEngine`, implementing `.generate()`.
2. Add one line to `_ENGINE_CLASSES` in `registry.py`.
3. Create its `EngineVersion` row with `is_shadow=True` — it now runs in
   parallel on real traffic (via `run_shadow_engines_task`, which you'd
   add to the beat schedule or trigger alongside
   `generate_recommendations_task` in `signals.py`) without being
   user-facing.
4. Once you're satisfied comparing shadow results against production
   ones (via the `RecommendationFeedback` / `UserInteraction` tables),
   flip `is_active=True` on the new version in the admin — the model's
   `save()` override automatically deactivates the old one. No code
   deploy required for the cutover itself.

Nothing in `tasks.py`, `persistence.py`, or `emails.py` needs to change
for this — that's the whole point of the `EngineResult` contract.
