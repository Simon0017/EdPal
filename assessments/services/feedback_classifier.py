from enum import Enum
from typing import Union

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
    def from_percentage(cls, percentage: Union[int, float]) -> 'Feedback':
        """
        Returns the Feedback enum member corresponding to the given percentage.

        Args:
            percentage (int, float): The percentage value (0 <= percentage <= 100).

        Returns:
            Feedback: The matching enum member.

        Raises:
            ValueError: If percentage is outside the valid range [0, 100].
        """
        if not 0 <= percentage <= 100:
            raise ValueError(f"Percentage must be between 0 and 100, got {percentage}")

        for member in cls:
            lower, upper, _ = member.value
            if lower <= percentage < upper:
                return member
        # Fallback (should never happen due to range check and inclusive upper bound)
        return cls.PERFECT

    @property
    def message(self) -> str:
        """Returns the feedback message for this enum member."""
        return self.value[2]

    @property
    def range_str(self) -> str:
        """Returns a string representation of the percentage interval."""
        lower, upper, _ = self.value
        if upper == 101:
            return f"{lower}% – 100%"
        return f"{lower}% – {upper-1}%"


# Example usage
if __name__ == "__main__":
    test_scores = [0, 5, 15, 25, 35, 45, 55, 65, 75, 85, 95, 100]

    for score in test_scores:
        fb = Feedback.from_percentage(score)
        print(f"Score: {score:3}% → {fb.message} ({fb.range_str})")