try:
    from pydantic import BaseModel
except ImportError as e:
    import logging
    import sys

    logger = logging.getLogger(__name__)
    if not logger.hasHandlers():
        handler = logging.StreamHandler(sys.stderr)
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.CRITICAL)
    logger.critical("CRITICAL ERROR: Pydantic is required for production use: %s", e)
    logger.critical("Install required dependencies: pip install pydantic")
    raise ImportError("Missing required dependency: pydantic") from e


class StoryResponse(BaseModel):
    """
    Response model for generated story.

    Attributes:
        story_text: The full text of the generated story.
        audio_url: Optional URL to a pre-recorded or synthesized narration.
    """
    story_text: str
    audio_url: str | None = None
