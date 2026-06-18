
def is_staff(user) -> bool:
    """tests if the user is a staff for role bases access

    Args:
        user (Any): User object

    Returns:
        bool: True /  False
    """

    return user.is_staff


def is_superuser(user) -> bool:
    """tests if the user is a super user for role bases access

    Args:
        user (Any): User object

    Returns:
        bool: True /  False
    """

    return user.is_superuser