import logging

from django.contrib.auth import logout, update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.contrib.sessions.backends.db import SessionStore
from django.db import transaction

logger = logging.getLogger(__name__)


def user_set_remember_me(user: User, remember_me: bool) -> bool:
    """
    Update the user's remember me preference.
    """
    try:
        profile = getattr(user, "profile", None)

        if profile is None:
            logger.warning(
                "Remember me update failed. Profile not found for user %s",
                user.pk,
            )
            return False

        profile.remember_me = remember_me
        profile.save(update_fields=["remember_me"])

        logger.info(
            "Remember me updated for user %s -> %s",
            user.pk,
            remember_me,
        )

        return True

    except Exception:
        logger.exception(
            "Failed to update remember me for user %s",
            user.pk,
        )
        return False


def change_user_password(
    user: User,
    current_password: str,
    new_password: str,
) -> bool:
    """
    Change a user's password.
    """
    try:

        if not user.check_password(current_password):
            logger.warning(
                "Password change failed. Invalid current password for user %s",
                user.pk,
            )
            return False

        user.set_password(new_password)
        user.save(update_fields=["password"])

        # Prevent logging the user out.
        update_session_auth_hash(None, user)

        logger.info(
            "Password changed successfully for user %s",
            user.pk,
        )

        return True

    except Exception:
        logger.exception(
            "Failed changing password for user %s",
            user.pk,
        )
        return False


def logout_user(request) -> bool:
    """
    Logout current user.
    """
    try:
        user_id = request.user.pk

        logout(request)

        logger.info(
            "User %s logged out successfully",
            user_id,
        )

        return True

    except Exception:
        logger.exception(
            "Failed logging out user %s",
            getattr(request.user, "pk", None),
        )
        return False


def update_notification_preferences(
    user: User,
    notifications: dict,
) -> bool:
    """
    Update notification settings.
    """
    try:

        profile = getattr(user, "profile", None)

        if profile is None:
            logger.warning(
                "Notification update failed. Profile not found for user %s",
                user.pk,
            )
            return False

        profile.notification_settings = notifications
        profile.save(update_fields=["notification_settings"])

        logger.info(
            "Notification settings updated for user %s",
            user.pk,
        )

        return True

    except Exception:
        logger.exception(
            "Failed updating notification settings for user %s",
            user.pk,
        )
        return False


def delete_user_session(
    user: User,
    session_id: str,
) -> bool:
    """
    Delete one of the user's sessions.
    """
    try:

        try:
            session = Session.objects.get(session_key=session_id)
        except Session.DoesNotExist:
            logger.warning(
                "Session %s not found.",
                session_id,
            )
            return False

        data = session.get_decoded()

        if data.get("_auth_user_id") != str(user.pk):
            logger.warning(
                "User %s attempted deleting another user's session.",
                user.pk,
            )
            return False

        session.delete()

        logger.info(
            "Deleted session %s for user %s",
            session_id,
            user.pk,
        )

        return True

    except Exception:
        logger.exception(
            "Failed deleting session %s for user %s",
            session_id,
            user.pk,
        )
        return False


@transaction.atomic
def delete_user_account(
    user: User,
    confirm_username: str,
) -> bool:
    """
    Permanently delete a user's account.
    """
    try:

        if user.username != confirm_username:
            logger.warning(
                "Account deletion failed for user %s. Username confirmation mismatch.",
                user.pk,
            )
            return False

        logger.info(
            "Deleting account for user %s",
            user.pk,
        )

        user.delete()

        logger.info(
            "Account deleted successfully."
        )

        return True

    except Exception:
        logger.exception(
            "Failed deleting account for user %s",
            user.pk,
        )
        return False