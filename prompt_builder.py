"""Create a concise, actionable Korean strategy prompt for Run-teller."""

from models import ChallengeAnalysisResult


class PromptBuilder:
    """Build the strategy prompt delivered to the downstream coach."""

    def build(self, result: ChallengeAnalysisResult) -> str:
        """Render challenge metrics and strict coaching guidelines for KakaoTalk delivery."""
        return (
            "[역할 및 절대 원칙]\n"
            "- 당신은 러너의 챌린지 성공을 돕는 전략 AI 코치입니다.\n"
            "- ★인사말(안녕하세요, 반갑습니다 등), 자기소개(AI 코치입니다 등), 서론은 '절대로' 쓰지 마세요.\n"
            "- 카카오톡 200자 제한이 있으므로 첫 문장부터 즉각 실행 가능한 '구체적인 러닝 거리 분배 및 전략'을 제시하세요.\n"
            "- 총 2~3문장, 공백 포함 110자 이내로 핵심만 압축하세요.\n\n"
            "[현재 챌린지 현황]\n"
            f"- 챌린지: {result.challenge_name}\n"
            f"- 목표/누적: {result.my_distance_km:.1f}km / {result.target_distance_km:.1f}km (남은 거리: {result.remaining_distance_km:.1f}km)\n"
            f"- 남은 기간: {result.remaining_days}일\n"
            f"- 하루 필요 권장 거리: {result.daily_req_for_goal:.1f}km/일\n"
            f"- 순위 현황: {result.total_participants}명 중 {result.my_rank}위 (앞 순위와 격차: {result.gap_to_target_km:.1f}km)\n\n"
            "[필수 조언 내용]\n"
            f"1. 오늘 또는 이번 주에 반드시 채워야 할 권장 러닝 거리({result.daily_req_for_goal:.1f}km 기준) 제시\n"
            "2. 주중/주말 마일리지 분배 방법이나 앞 순위 추월/순위 방어 팁 제시\n"
            "3. 동기부여와 함께 바로 뛸 수 있는 현실적인 조언만 작성"
        )
