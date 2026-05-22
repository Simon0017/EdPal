from functools import wraps
from django.http import JsonResponse
from rest_framework import status
import logging

logger = logging.getLogger(__name__)

def json_exception_handler(logger=logger):
    """
    Outer exception handler decorator
    """

    def decorator(view_func):

        @wraps(view_func)
        def wrapper(request, *args, **kwargs):

            try:
                return view_func(request, *args, **kwargs)

            except Exception as e:

                logger.error(str(e))

                return JsonResponse(
                    {
                        "success": False,
                        "error": str(e),
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        return wrapper

    return decorator