"""
SM-2 spaced repetition algorithm.

ratings are 0-5:
  0 = complete blackout
  1 = wrong, but remembered after seeing answer
  2 = wrong, but easy to recall after seeing answer
  3 = correct, but hard
  4 = correct, with some hesitation
  5 = perfect recall

anything < 3 resets the card (back to learning phase).
"""
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass


@dataclass
class SM2State:
    ease_factor: float = 2.5
    interval_days: int = 0
    repetitions: int = 0


@dataclass
class SM2Result:
    ease_factor: float
    interval_days: int
    repetitions: int
    next_review_at: datetime


def apply_sm2(state: SM2State, rating: int) -> SM2Result:
    """compute next review state given current state and a 0-5 rating"""
    if not 0 <= rating <= 5:
        raise ValueError(f"rating must be 0-5, got {rating}")

    ef = state.ease_factor
    reps = state.repetitions
    interval = state.interval_days

    if rating >= 3:
        # successful recall
        if reps == 0:
            interval = 1
        elif reps == 1:
            interval = 6
        else:
            interval = round(interval * ef)
        reps += 1
    else:
        # failed recall — reset to beginning
        reps = 0
        interval = 1

    # update ease factor (never drops below 1.3)
    ef = ef + (0.1 - (5 - rating) * (0.08 + (5 - rating) * 0.02))
    ef = max(1.3, ef)

    next_review = datetime.now(timezone.utc) + timedelta(days=interval)

    return SM2Result(
        ease_factor=round(ef, 4),
        interval_days=interval,
        repetitions=reps,
        next_review_at=next_review,
    )
