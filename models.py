"""Typed data models used by the challenge strategy engine."""

from pydantic import BaseModel


class ParticipantProgress(BaseModel):
    """A participant's ranked challenge progress."""

    display_name: str
    rank: int
    distance_km: float
    is_self: bool


class ChallengeAnalysisResult(BaseModel):
    """Calculated standings and actionable distance targets."""

    challenge_name: str
    remaining_days: int
    target_distance_km: float
    remaining_distance_km: float
    daily_req_for_goal: float
    total_participants: int
    my_rank: int
    my_distance_km: float
    leader_distance_km: float
    target_rank_distance_km: float
    gap_to_leader_km: float
    gap_to_target_km: float
    daily_req_for_leader: float
    daily_req_for_target: float
