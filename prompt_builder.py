"""Create a consistent Korean strategy prompt for Run-teller."""

from models import ChallengeAnalysisResult


class PromptBuilder:
    """Build the strategy prompt delivered to the downstream coach."""

    def build(self, result: ChallengeAnalysisResult) -> str:
        """Render challenge metrics and coaching guidance as plain text."""
        target_label = "1위" if result.my_rank == 1 else "바로 앞 순위"
        target_daily = result.daily_req_for_leader if result.my_rank != 1 else 0.0
        return (
            "[역할]\n당신은 가민 커스텀 챌린지 전략 AI 코치 Run-teller입니다. "
            "사용자는 가민 워치 없이 앱/계정을 사용하므로 심박수, 바디 배터리 등 생체 데이터를 추정하지 마세요.\n\n"
            "[챌린지 전황 데이터]\n"
            f"- 챌린지명: {result.challenge_name}\n- 남은 기간: {result.remaining_days}일\n"
            f"- 현재 위치: {result.total_participants}명 중 {result.my_rank}위 ({result.my_distance_km:.2f} km)\n"
            f"- 1위와 격차: {result.gap_to_leader_km:.2f} km (역전용 하루 평균 +{result.daily_req_for_leader:.2f} km/일)\n"
            f"- 목표 순위({target_label})와 격차: {result.gap_to_target_km:.2f} km (하루 평균 +{target_daily:.2f} km/일)\n\n"
            "[조언 가이드라인]\n"
            "1. 현재 순위와 거리 격차를 진단하세요.\n"
            "2. 오늘의 목표 누적 거리를 km 단위로 제시하세요.\n"
            "3. 생활 걷기와 러닝을 현실적인 분할 루틴으로 제안하세요.\n"
            "4. 남은 기간에 맞춰 무리하지 않는 페이싱과 마감 전략을 제시하세요.\n"
            "수치만으로 판단하고, 확인되지 않은 컨디션이나 생체 데이터를 가정하지 마세요."
        )
