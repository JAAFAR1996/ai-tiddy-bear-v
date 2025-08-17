"""ESP32 Audio Processing Use Case - Domain-Driven
=================================================
Use case orchestrating domain services for business logic.
No business rules here - pure coordination.
"""

from datetime import datetime
from fastapi import HTTPException

from src.shared.dto.ai_response import AIResponse
from src.shared.dto.esp32_request import ESP32Request
from src.shared.audio_types import AudioFormat, VoiceEmotion

# Domain imports - business logic
from src.domain.audio import (
    AudioFile,
    Voice,
    TranscriptionRequest,
    AudioValidationService,
    VoiceSelectionService,
    ContentSafetyService,
    AudioProcessingRulesService,
)

# Infrastructure interfaces
from src.interfaces.providers.esp32_protocol import ESP32Protocol
from src.interfaces.services import IAIService, IConversationService, IAudioService
from src.interfaces.repositories import IChildRepository
from src.interfaces.providers.stt_provider import ISTTProvider
from src.interfaces.providers.tts_provider import (
    ITTSService,
    TTSRequest,
    TTSConfiguration,
    VoiceProfile,
    ChildSafetyContext,
)
from src.shared.audio_types import VoiceGender


class ProcessESP32AudioUseCase:
    """
    Use case coordinating domain services for ESP32 audio processing.
    Pure orchestration - all business logic delegated to domain.
    """

    def __init__(
        self,
        # Domain services - business logic
        audio_validation_service: AudioValidationService,
        voice_selection_service: VoiceSelectionService,
        content_safety_service: ContentSafetyService,
        processing_rules_service: AudioProcessingRulesService,
        # Infrastructure services
        stt_provider: ISTTProvider,
        tts_service: ITTSService,
        audio_service: IAudioService,
        esp32_protocol: ESP32Protocol,
        ai_service: IAIService,
        conversation_service: IConversationService,
        child_repository: IChildRepository,
    ) -> None:
        # Domain services
        self.audio_validation = audio_validation_service
        self.voice_selection = voice_selection_service
        self.content_safety = content_safety_service
        self.processing_rules = processing_rules_service

        # Infrastructure
        self.stt_processor = stt_provider
        self.tts_service = tts_service
        self.audio_service = audio_service
        self.esp32_protocol = esp32_protocol
        self.ai_service = ai_service
        self.conversation_service = conversation_service
        self.child_repository = child_repository

    async def execute(self, request: ESP32Request) -> AIResponse:
        """
        Execute ESP32 audio processing using domain services.
        Pure coordination - all business logic in domain.
        """
        from src.shared.audit_logger import ProductionAuditLogger

        audit_logger = ProductionAuditLogger("ESP32AudioUseCase")

        start_time = datetime.now()

        try:
            # Step 1: Get child profile (business context)
            child_profile = await self.child_repository.get_by_id(request.child_id)
            if not child_profile:
                audit_logger.log_error(
                    "get_child_profile",
                    ValueError(f"Child not found: {request.child_id}"),
                )
                raise HTTPException(status_code=404, detail="Child profile not found")

            child_age = child_profile.age

            # Step 2: Create domain audio entity
            audio_file = AudioFile(
                data=request.audio_data,
                format=AudioFormat.WAV,
                duration_ms=len(request.audio_data) / 16,
                sample_rate=16000,
                is_child_safe=False,
            )

            # Step 3: Domain validation (business rules)
            transcription_request = TranscriptionRequest(
                audio=audio_file,
                target_language="en-US",
                child_age=child_age,
                require_safety_check=True,
            )

            is_valid, validation_issues = (
                self.audio_validation.validate_transcription_request(
                    transcription_request
                )
            )
            if not is_valid:
                raise HTTPException(
                    status_code=400,
                    detail=f"Audio validation failed: {validation_issues}",
                )

            # Step 4: Speech-to-text processing
            transcribed_text = await self.stt_processor.transcribe(
                request.audio_data, language="en-US", child_age=child_age
            )

            # Step 5: Content safety validation (domain rules)
            is_text_safe, safety_issues = (
                self.content_safety.is_text_appropriate_for_child(
                    transcribed_text, child_age
                )
            )
            if not is_text_safe:
                transcribed_text = self.content_safety.filter_inappropriate_content(
                    transcribed_text
                )

            # Step 6: Get AI response
            conversation_history = (
                await self.conversation_service.get_conversation_history(
                    request.child_id
                )
            )
            history_texts = [conv.summary for conv in conversation_history]

            ai_response = await self.ai_service.get_ai_response(
                request.child_id,
                history_texts,
                transcribed_text,
                child_preferences=child_profile.preferences,
            )

            # Step 7: Voice selection (domain rules)
            available_voices = await self.audio_service.get_available_voices(
                language="en-US", child_age=child_age
            )

            # Convert to domain entities
            domain_voices = [
                Voice(
                    voice_id=v.voice_id,
                    name=v.name,
                    language=v.language,
                    gender=v.gender,
                    age_group=v.age_group,
                    is_child_appropriate=v.is_child_appropriate,
                    supported_emotions=v.supported_emotions,
                )
                for v in available_voices
            ]

            selected_voice = self.voice_selection.select_appropriate_voice(
                domain_voices, child_age, VoiceEmotion.NEUTRAL
            )

            if not selected_voice:
                raise HTTPException(
                    status_code=500, detail="No appropriate voice found"
                )

            # Step 8: Text-to-speech processing using unified interface
            tts_request = TTSRequest(
                text=ai_response.response_text,
                config=TTSConfiguration(
                    voice_profile=VoiceProfile(
                        voice_id=selected_voice.voice_id,
                        name=selected_voice.name,
                        language="en-US",
                        gender=VoiceGender.NEUTRAL,
                        age_range="adult",
                        description="Selected voice for child interaction",
                    ),
                    emotion=VoiceEmotion.NEUTRAL,
                    quality=self.processing_rules.get_recommended_quality_for_age(
                        child_age
                    ),
                ),
                safety_context=ChildSafetyContext(
                    child_age=child_age,
                    parental_controls=True,
                    content_filter_level="strict",
                ),
            )

            tts_result = await self.tts_service.synthesize_speech(tts_request)
            tts_audio = tts_result.audio_data

            # Step 9: Update conversation history
            await self.conversation_service.start_new_conversation(
                request.child_id, transcribed_text
            )

            # Step 10: Log success and return result
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            audit_logger.log_audio_processing(
                request.child_id,
                "esp32_audio_processing",
                True,
                processing_time,
                {"text_length": len(transcribed_text), "safe": is_text_safe},
            )

            return AIResponse(
                text=transcribed_text,
                audio=tts_audio,
                emotion=ai_response.emotion,
                sentiment=ai_response.sentiment,
                safe=is_text_safe,
                audio_response=tts_audio,
            )

        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            audit_logger.log_audio_processing(
                request.child_id,
                "esp32_audio_processing",
                False,
                processing_time,
                {"error": str(e)},
            )

            if "transcribed_text" in locals() and not is_text_safe:
                audit_logger.log_safety_violation(
                    request.child_id, "inappropriate_content", transcribed_text[:100]
                )

            raise
