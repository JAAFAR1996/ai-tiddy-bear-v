from uuid import UUID

from src.interfaces.exceptions import ServiceError as ConsentError
from src.interfaces.read_model_interfaces import IConsentManager
from src.interfaces.services import IAIService, IAudioService
from src.shared.dto.ai_response import AIResponse


class GenerateAIResponseUseCase:
    """Use case for generating AI responses to child interactions.
    This use case orchestrates the generation of safe, age-appropriate AI responses
    for children, ensuring COPPA compliance and child safety throughout the process.
    FIXED: Removed Service Locator anti-pattern by using proper dependency injection.
    """

    def __init__(
        self,
        ai_orchestration_service: IAIService,
        audio_processing_service: AudioProcessingService,
        consent_manager: IConsentManager | None = None,
    ):
        self.ai_orchestration_service = ai_orchestration_service
        self.audio_processing_service = audio_processing_service
        self._consent_manager = consent_manager

    async def execute(
        self,
        child_id: UUID,
        conversation_history: list[str],
        current_input: str,
        voice_id: str,
        parent_id: str | None = None,  # ✅ Added parent_id for consent verification
    ) -> AIResponse:
        if parent_id and self._consent_manager:
            # Check required consents for AI interaction
            required_consents = [
                "data_collection",
                "voice_recording",
                "usage_analytics",
            ]

            for consent_type in required_consents:
                try:
                    has_consent = await self._consent_manager.verify_consent(
                        child_id=str(child_id),
                        operation=consent_type,
                    )
                    if not has_consent:
                        raise ConsentError(
                            f"Parental consent required for {consent_type}",
                        )
                except Exception as e:
                    raise ConsentError(
                        f"Error during consent verification for {consent_type}: {e}",
                    ) from e
        elif parent_id and not self._consent_manager:
            raise ConsentError(
                "Consent manager required for parental consent verification",
            )

        ai_response_dto = await self.ai_orchestration_service.get_ai_response(
            child_id,
            conversation_history,
            current_input,
            voice_id,
        )

        audio_output = await self.audio_processing_service.generate_audio_response(
            ai_response_dto.response_text,
            voice_id,
        )

        ai_response_dto.audio_response = audio_output
        return ai_response_dto
