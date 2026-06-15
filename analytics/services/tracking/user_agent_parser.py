"""
User-agent parsing service for analytics.

Wraps the ``user-agents`` library (``pip install user-agents``) and
normalises the results into the field values stored on :class:`SiteActivity`.
"""

from __future__ import annotations

import logging
from typing import Dict

from analytics.constants import (
    DEVICE_BOT,
    DEVICE_DESKTOP,
    DEVICE_MOBILE,
    DEVICE_TABLET,
    DEVICE_UNKNOWN,
    UNKNOWN_VALUE,
)
from analytics.typing import UserAgentString

logger = logging.getLogger(__name__)


class UserAgentParser:
    """
    Parses raw User-Agent header strings into structured device/browser/OS data.

    The ``user-agents`` library is imported lazily so that applications not
    using user-agent parsing can avoid the dependency.

    Instances are stateless and safe to reuse across threads.
    """

    def parse(self, raw_ua: UserAgentString) -> Dict[str, str]:
        """
        Parse *raw_ua* and return a dict of normalised field values.

        Parameters
        ----------
        raw_ua:
            The raw ``User-Agent`` header string.

        Returns
        -------
        dict
            Keys: ``browser_family``, ``browser_version``, ``os_family``,
            ``os_version``, ``device_type``.  All values are strings; empty
            string when parsing fails.
        """
        if not raw_ua:
            return self._empty_result()

        try:
            from user_agents import parse as ua_parse  # type: ignore[import-untyped]

            ua = ua_parse(raw_ua)

            device_type = self._classify_device(ua)

            return {
                "browser_family": ua.browser.family or "",
                "browser_version": ua.browser.version_string or "",
                "os_family": ua.os.family or "",
                "os_version": ua.os.version_string or "",
                "device_type": device_type,
            }
        except ImportError:
            logger.warning(
                "The 'user-agents' package is not installed. "
                "User-agent parsing is disabled.  "
                "Install it with: pip install user-agents"
            )
            return self._empty_result()
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "User-agent parsing failed for ua=%r: %s",
                raw_ua[:200],
                exc,
                exc_info=False,
            )
            return self._empty_result()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _classify_device(ua) -> str:
        """
        Classify a parsed user-agent object into a device type constant.

        Parameters
        ----------
        ua:
            A ``user_agents.parsers.UserAgent`` instance.

        Returns
        -------
        str
            One of the ``DEVICE_*`` constants.
        """
        if ua.is_bot:
            return DEVICE_BOT
        if ua.is_mobile:
            return DEVICE_MOBILE
        if ua.is_tablet:
            return DEVICE_TABLET
        if ua.is_pc:
            return DEVICE_DESKTOP
        return DEVICE_UNKNOWN

    @staticmethod
    def _empty_result() -> Dict[str, str]:
        """Return a result dict with all fields set to empty string."""
        return {
            "browser_family": "",
            "browser_version": "",
            "os_family": "",
            "os_version": "",
            "device_type": "",
        }
