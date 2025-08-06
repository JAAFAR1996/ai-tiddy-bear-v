from typing import Any
from uuid import UUID

import logging

logger = logging.getLogger(__name__)


from src.application.content import ContentManager


class GenerateDynamicStoryUseCase:
    """Use case for generating dynamic stories based on child interaction."""

    def __init__(
        self, ai_service=None, profile_service=None, content_manager=None
    ) -> None:
        self.logger = get_logger(__name__, component="use_cases")
        self.ai_service = ai_service
        self.profile_service = profile_service
        self.content_manager = content_manager or ContentManager()

    async def execute(
        self,
        child_id: UUID,
        story_theme: str | None = None,
        story_length: str = "medium",
    ) -> dict[str, Any]:
        """Generate a dynamic story based on child's preferences
        Args:
            child_id: The child's UUID identifier
            story_theme: Optional theme for the story
            story_length: short, medium, or long
        Returns:
            Dict containing the generated story and metadata.
        """
        try:
            # Get child preferences from profile service
            child_preferences = await self._get_child_preferences(child_id)
            if not child_preferences:
                self.logger.warning(
                    f"No profile found for child {child_id}, using defaults",
                )
                child_preferences = self._get_default_preferences()

            # Try to fetch a story template from the CMS based on preferences
            template_id = None
            if story_theme:
                # Try to find a template matching the theme
                for group in self.content_manager.stories.templates.values():
                    for tpl in group:
                        if (
                            story_theme.lower() in tpl.get("title", "").lower()
                            or story_theme.lower() in tpl.get("text", "").lower()
                        ):
                            template_id = tpl.get("id")
                            break
                    if template_id:
                        break
            # Fallback: pick any template matching age
            if not template_id:
                for group in self.content_manager.stories.templates.values():
                    for tpl in group:
                        if self.content_manager.age_filter.is_allowed(
                            tpl, child_preferences.get("age", 5)
                        ):
                            template_id = tpl.get("id")
                            break
                    if template_id:
                        break

            story_template = (
                self.content_manager.get_story(
                    template_id, child_preferences.get("age", 5)
                )
                if template_id
                else None
            )

            if story_template:
                # Use the template as the base for the story
                prompt = f"Rewrite or expand the following story for a {child_preferences.get('age', 5)}-year-old, making it interactive and educational: {story_template.get('text', '')}"
            else:
                # Fallback to dynamic prompt
                prompt = self._create_story_prompt(
                    theme=story_theme,
                    preferences=child_preferences,
                    length=story_length,
                )

            # Generate story using AI service
            story_response = await self.ai_service.generate_story(
                prompt=prompt,
                child_preferences=child_preferences,
            )

            return {
                "success": True,
                "story": story_response,
                "metadata": {
                    "theme": story_theme,
                    "length": story_length,
                    "child_id": child_id,
                    "template_id": template_id,
                },
            }
        except Exception as e:
            self.logger.error(f"Error generating story for child {child_id}: {e!s}")
            return {"success": False, "error": str(e), "story": None}

    def _create_story_prompt(
        self,
        theme: str | None,
        preferences: dict[str, Any],
        length: str,
    ) -> str:
        """Create a story prompt based on parameters."""
        age = preferences.get("age", 5)
        interests = preferences.get("interests", [])
        base_prompt = f"Create a {length} story suitable for a {age}-year-old child"

        if theme:
            base_prompt += f" about {theme}"
        elif interests:
            base_prompt += f" involving {', '.join(interests)}"

        base_prompt += ". Make it educational, fun, and age-appropriate."
        return base_prompt

    async def _get_child_preferences(self, child_id: UUID) -> dict[str, Any] | None:
        """Get child preferences from profile service."""
        try:
            child_profile = await self.profile_service.get_child_profile(child_id)
            if child_profile:
                preferences = child_profile.preferences.copy()
                preferences["age"] = child_profile.age
                preferences["name"] = child_profile.name

                # Ensure required fields exist
                if "interests" not in preferences:
                    preferences["interests"] = self._get_age_appropriate_interests(
                        child_profile.age,
                    )
                if "language" not in preferences:
                    preferences["language"] = "en"

                self.logger.info(f"Retrieved preferences for child {child_id}")
                return preferences
            return None
        except Exception as e:
            self.logger.error(f"Error retrieving child preferences: {e!s}")
            return None

    def _get_default_preferences(self) -> dict[str, Any]:
        """Get default preferences when no profile found."""
        return {
            "age": 5,
            "interests": ["animals", "adventures", "friendship"],
            "language": "en",
            "name": "Friend",
        }

    def _get_age_appropriate_interests(self, age: int) -> list[str]:
        """Get age-appropriate interests based on child's age."""
        if age <= 3:
            return ["animals", "colors", "shapes", "family"]
        if age <= 5:
            return ["animals", "adventures", "friendship", "toys"]
        if age <= 8:
            return ["adventures", "friendship", "school", "sports", "nature"]
        if age <= 12:
            return [
                "adventures",
                "friendship",
                "school",
                "sports",
                "science",
                "art",
            ]
        return [
            "adventures",
            "friendship",
            "challenges",
            "discovery",
            "creativity",
        ]
