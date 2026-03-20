"""Configuration settings for the speech-to-speech translation backend."""

import logging
import os
from dataclasses import dataclass
from typing import Dict


@dataclass
class AudioConfig:
    """Audio configuration matching the existing realtime_s2s.py."""
    sample_rate: int = 16000
    chunk_size: int = 4800  # ~300ms at 16kHz
    channels: int = 1
    bytes_per_sample: int = 2  # int16


@dataclass
class RivaConfig:
    """Riva service configuration."""
    uri: str = "localhost:50051"
    model: str = "megatronnmt_any_any_1b"
    source_language: str = "en-US"


@dataclass
class WatchdogConfig:
    """TTS zombie watchdog configuration."""
    zombie_timeout: int = 60      # seconds with no response → restart TTS
    check_interval: int = 30      # seconds between watchdog checks
    tts_container: str = "magpie-tts-multilingual"
    tts_grpc_addr: str = "localhost:50053"
    recovery_timeout: int = 120   # seconds to wait for TTS to become healthy


# Supported target languages with their TTS voice names
# Note: Only languages with voices installed on the Riva server will work
SUPPORTED_LANGUAGES: Dict[str, dict] = {
    "es-US": {
        "name": "Spanish (US)",
        "voice": "Magpie-Multilingual.ES-US.Isabela",
        "available": True,
    },
    # Add more languages here when voices are installed on the Riva server
    # Example format:
    # "fr-FR": {
    #     "name": "French",
    #     "voice": "Voice-Name-Here",
    #     "available": True,
    # },
}

# Default configuration instances
audio_config = AudioConfig()
riva_config = RivaConfig()
watchdog_config = WatchdogConfig()


def setup_logging() -> None:
    """Configure logging level from LOG_LEVEL env var (default: INFO)."""
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
