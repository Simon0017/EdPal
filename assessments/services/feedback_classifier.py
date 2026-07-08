from enum import Enum
from numbers import Real
from decimal import Decimal
from typing import Union

Number = Union[int, float, Decimal]


class Feedback(Enum):
    """
    Enum representing feedback categories based on percentage intervals of 10.
    Each member stores a tuple (lower_bound, upper_bound, feedback_message).
    The intervals are: [0,10), [10,20), ..., [90,100], where 100 is included in the top interval.
    """

    VERY_POOR = (
        0, 10,
        "Needs immediate and substantial intervention. "
        "Performance is far below expectations with critical gaps."
    )
    POOR = (
        10, 20,
        "Significant improvement required. "
        "Foundational concepts are missing; consider restarting from basics."
    )
    BELOW_AVERAGE = (
        20, 30,
        "Below average. Some understanding exists, but large gaps remain. "
        "Focus on key areas to build a stronger base."
    )
    AVERAGE = (
        30, 40,
        "Average. Meets minimum expectations but lacks depth. "
        "Regular practice and review of mistakes will help climb higher."
    )
    FAIR = (
        40, 50,
        "Fair. Approaching satisfactory level. "
    )
    GOOD = (
        50, 60,
        "Good! Solid grasp of the material. "
        "A few refinements and tackling advanced topics will push you further."
    )
    VERY_GOOD = (
        60, 70,
        "Very good! Above average performance. "
        "You demonstrate strong understanding. Keep challenging yourself."
    )
    EXCELLENT = (
        70, 80,
        "Excellent! Well above expectations. "
        "Your work shows clarity, correctness, and good problem-solving skills."
    )
    OUTSTANDING = (
        80, 90,
        "Outstanding! Near‑perfect mastery. "
        "Only minor nuances separate you from perfection. Celebrate this!"
    )
    PERFECT = (
        90, 101,
        "Perfect! Exceptional achievement. "
        "You have demonstrated flawless understanding and execution. "
        "Keep up this remarkable standard."
    )

    @classmethod
    def from_percentage(cls, percentage: Number) -> "Feedback":
        """
        Returns the Feedback enum member corresponding to the given percentage.

        Args:
            percentage: numeric value, 0 <= percentage <= 100. int, float, and
                Decimal are all accepted; bool is explicitly rejected even
                though Python treats it as an int subclass.

        Returns:
            Feedback: The matching enum member.

        Raises:
            TypeError: If percentage is not a real number (or is a bool).
            ValueError: If percentage is outside the valid range [0, 100].
        """
        if isinstance(percentage, bool):
            raise TypeError(
                f"percentage must be a number, got bool: {percentage!r}"
            )

        if isinstance(percentage, Decimal):
            # Decimal deliberately isn't registered under numbers.Real, so it
            # would otherwise fail the isinstance check below even though
            # it's a perfectly valid input (e.g. straight from a
            # DecimalField). Normalize it to float up front.
            percentage = float(percentage)
        elif not isinstance(percentage, Real):
            raise TypeError(
                "percentage must be an int, float, or Decimal, got "
                f"{type(percentage).__name__}: {percentage!r}"
            )

        if not (0 <= percentage <= 100):
            raise ValueError(f"Percentage must be between 0 and 100, got {percentage}")

        for member in cls._ordered_members():
            lower, upper, _ = member.value
            if lower <= percentage < upper:
                return member

        # Fallback (should never happen due to the range check above and
        # the import-time contiguity check below).
        return cls.PERFECT

    @classmethod
    def _ordered_members(cls):
        """
        Members sorted by lower bound. Doesn't rely on declaration order
        staying sorted if someone reorders members during a future edit.
        """
        return sorted(cls, key=lambda m: m.value[0])

    @property
    def message(self) -> str:
        """Returns the feedback message for this enum member."""
        return self.value[2]

    @property
    def sentences(self) -> list:
        """
        Message split into clean, non-empty sentences. Prefer this over a
        raw `message.split(".")` at call sites — every message here ends in
        a period, so a naive split leaves a trailing empty string in the
        result.
        """
        return [s.strip() for s in self.message.split(".") if s.strip()]

    @property
    def range_str(self) -> str:
        """Returns a string representation of the percentage interval."""
        lower, upper, _ = self.value
        if upper == 101:
            return f"{lower}% – 100%"
        return f"{lower}% – {upper - 1}%"


def _validate_ranges() -> None:
    """
    Fail fast at import time if the enum's percentage ranges are ever edited
    into an inconsistent state — a gap, an overlap, or a total range that
    doesn't span exactly [0, 100]. Better to blow up loudly on deploy than
    to silently misclassify scores at runtime.

    Deliberately uses explicit if/raise rather than `assert`, since asserts
    are stripped when Python runs with -O.
    """
    members = Feedback._ordered_members()

    if members[0].value[0] != 0:
        raise RuntimeError(
            f"Feedback ranges must start at 0, got {members[0].value[0]} "
            f"({members[0].name})."
        )

    if members[-1].value[1] != 101:
        raise RuntimeError(
            "Feedback ranges must end with an inclusive upper bound of 101 "
            f"(covering 100), got {members[-1].value[1]} ({members[-1].name})."
        )

    for prev, curr in zip(members, members[1:]):
        if prev.value[1] != curr.value[0]:
            raise RuntimeError(
                f"Gap or overlap between {prev.name} (upper={prev.value[1]}) "
                f"and {curr.name} (lower={curr.value[0]}); ranges must be "
                "contiguous with no gaps or overlaps."
            )


_validate_ranges()


# Example usage
if __name__ == "__main__":
    test_scores = [0, 5, 15, 25, 35, 45, 55, 65, 75, 85, 95, 100]

    for score in test_scores:
        fb = Feedback.from_percentage(score)
        print(f"Score: {score:3}% -> {fb.message} ({fb.range_str})")

    # Defensive-path smoke tests
    for bad_value in [-1, 101, "50", None, True]:
        try:
            Feedback.from_percentage(bad_value)
            print(f"UNEXPECTED: {bad_value!r} did not raise")
        except (TypeError, ValueError) as e:
            print(f"OK - rejected {bad_value!r}: {e}")

    from decimal import Decimal as _D
    print(Feedback.from_percentage(_D("62.5")))