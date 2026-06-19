from guardian.shortcuts import assign_perm
import logging

logger = logging.getLogger(__name__)


def assign_full_access(user_or_group,app:str, obj) -> None:
    try:
        perms = [
            f"{app}.view_{obj._meta.model_name}",
            f"{app}.change_{obj._meta.model_name}",
            f"{app}.delete_{obj._meta.model_name}",
        ]

        for perm in perms:
            assign_perm(perm, user_or_group, obj)
            logger.debug(f"Assigned permission {perm} to {user_or_group} for object {obj}")
    except Exception as e:
        logger.error(str(e))
    