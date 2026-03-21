"""Riva S2S client wrapper adapted from realtime_s2s.py."""

import logging
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from queue import Queue, Empty
from typing import Optional, Callable

import riva.client
import riva.client.proto.riva_asr_pb2 as riva_asr_pb2
import riva.client.proto.riva_nmt_pb2 as riva_nmt_pb2

from config import audio_config, riva_config, watchdog_config, SUPPORTED_LANGUAGES

logger = logging.getLogger("riva")


class AudioChunkIterator:
    """Iterator that yields audio chunks from a queue."""

    def __init__(self):
        self._queue: Queue = Queue()
        self._stopped = False
        self._chunk_count = 0

    def add_chunk(self, chunk: bytes) -> None:
        """Add an audio chunk to be processed."""
        if not self._stopped:
            self._chunk_count += 1
            logger.debug(f"Audio chunk {self._chunk_count} added, {len(chunk)} bytes")
            self._queue.put(chunk)

    def stop(self) -> None:
        """Signal the iterator to stop."""
        logger.debug("Iterator stopped")
        self._stopped = True
        self._queue.put(None)  # Sentinel to unblock iteration

    def __iter__(self):
        return self

    def __next__(self) -> bytes:
        # Block until we get a chunk or are stopped
        while True:
            try:
                chunk = self._queue.get(timeout=0.5)
                if chunk is None:
                    logger.debug("Got stop sentinel")
                    raise StopIteration
                return chunk
            except Empty:
                if self._stopped:
                    logger.debug("Iterator stopped during wait")
                    raise StopIteration
                # Keep waiting for more chunks
                continue


class RivaS2SClient:
    """Wrapper for Riva Speech-to-Speech translation."""

    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._nmt_client: Optional[riva.client.NeuralMachineTranslationClient] = None
        self._auth: Optional[riva.client.Auth] = None
        self._connected = False

    def connect(self) -> bool:
        """Connect to Riva services."""
        try:
            logger.info(f"Connecting to {riva_config.uri}...")
            self._auth = riva.client.Auth(uri=riva_config.uri)
            self._nmt_client = riva.client.NeuralMachineTranslationClient(self._auth)
            self._connected = True
            logger.info("Connected successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            self._connected = False
            return False

    def disconnect(self) -> None:
        """Disconnect from Riva services."""
        self._connected = False
        self._nmt_client = None
        self._auth = None

    def is_connected(self) -> bool:
        """Check if connected to Riva."""
        return self._connected

    def create_s2s_config(self, target_language: str) -> riva.client.StreamingTranslateSpeechToSpeechConfig:
        """Create S2S configuration for the specified target language."""
        # Get voice for target language
        lang_config = SUPPORTED_LANGUAGES.get(target_language, SUPPORTED_LANGUAGES["es-US"])
        voice_name = lang_config["voice"]

        logger.info(f"Creating config: {riva_config.source_language} -> {target_language}, voice: {voice_name}")

        # Endpointing config — reduce stalls by detecting silence faster.
        # Default server config waits too long for sentence boundaries,
        # causing 15-35s stalls in continuous speech (e.g., sermons).
        # start_history/start_threshold raised from 100ms/0.3 to prevent ASR from
        # transcribing brief filler sounds ("uh") as standalone Chinese characters
        # (e.g., '呃'), which crash the TTS TRT-LLM encoder.
        endpointing_config = riva_asr_pb2.EndpointingConfig(
            start_history=500,       # 500ms — require sustained speech to start utterance (was 300ms)
            start_threshold=0.6,     # 60% non-blank frames triggers start (was 50%)
            stop_history=300,        # 300ms silence triggers final result
            stop_threshold=0.5,      # 50% blank frames triggers end
            stop_history_eou=200,    # 200ms early end-of-utterance
            stop_threshold_eou=0.6,  # 60% blank for early EOU
        )

        # ASR config for speech recognition
        asr_config = riva_asr_pb2.StreamingRecognitionConfig(
            config=riva_asr_pb2.RecognitionConfig(
                encoding=riva.client.AudioEncoding.LINEAR_PCM,
                sample_rate_hertz=audio_config.sample_rate,
                language_code=riva_config.source_language,
                max_alternatives=1,
                enable_automatic_punctuation=True,
                audio_channel_count=audio_config.channels,
                endpointing_config=endpointing_config,
            ),
            interim_results=True
        )

        # NMT config for translation
        translation_config = riva_nmt_pb2.TranslationConfig(
            source_language_code=riva_config.source_language,
            target_language_code=target_language,
            model_name=riva_config.model
        )

        # TTS config for speech synthesis
        tts_config = riva.client.SynthesizeSpeechConfig(
            language_code=target_language,
            encoding=riva.client.AudioEncoding.LINEAR_PCM,
            sample_rate_hz=audio_config.sample_rate,
            voice_name=voice_name,
        )

        return riva.client.StreamingTranslateSpeechToSpeechConfig(
            asr_config=asr_config,
            translation_config=translation_config,
            tts_config=tts_config,
        )

    async def translate_stream(
        self,
        target_language: str,
        on_audio: Callable[[bytes], None],
        on_error: Callable[[str], None],
    ) -> AudioChunkIterator:
        """
        Start a translation stream.

        Returns an AudioChunkIterator that accepts audio chunks.
        Translated audio is sent via the on_audio callback.
        """
        if not self._connected or not self._nmt_client:
            on_error("Not connected to Riva")
            raise RuntimeError("Not connected to Riva")

        chunk_iterator = AudioChunkIterator()
        last_response_time = [time.monotonic()]  # list so watchdog closure can mutate
        total_responses = [0]                    # list so watchdog closure can read

        def run_translation():
            """Run the blocking Riva translation in a thread with auto-restart."""
            logger.info("Starting translation thread")
            restart_count = 0

            while not chunk_iterator._stopped:
                try:
                    config = self.create_s2s_config(target_language)
                    responses = self._nmt_client.streaming_s2s_response_generator(
                        audio_chunks=chunk_iterator,
                        streaming_config=config,
                    )

                    for response in responses:
                        total_responses[0] += 1
                        if response.speech and response.speech.audio:
                            on_audio(response.speech.audio)
                            last_response_time[0] = time.monotonic()
                        else:
                            logger.debug(f"Response {total_responses[0]}: no audio")

                    if not chunk_iterator._stopped:
                        restart_count += 1
                        logger.info(f"ASR endpointing — restarting stream (#{restart_count})")
                        continue
                    else:
                        logger.info(f"Stream stopped normally, {total_responses[0]} total responses")
                        break

                except Exception as e:
                    if chunk_iterator._stopped:
                        logger.info(f"Stream ended: {e}")
                        break
                    restart_count += 1
                    logger.warning(f"Error (restarting #{restart_count}): {e}")
                    continue

            logger.info(f"Translation thread exiting. "
                        f"{total_responses[0]} responses, {restart_count} restarts")

        def watchdog():
            """Detect TTS zombie state and restart the container to recover."""
            logger.info("Watchdog started")
            while not chunk_iterator._stopped:
                time.sleep(watchdog_config.check_interval)
                if chunk_iterator._stopped:
                    break
                if total_responses[0] == 0:
                    continue  # still in warmup, no baseline yet
                silent_for = time.monotonic() - last_response_time[0]
                if silent_for < watchdog_config.zombie_timeout:
                    continue
                logger.warning(
                    f"TTS zombie detected (no response for {silent_for:.0f}s)"
                    f" — restarting {watchdog_config.tts_container}"
                )
                try:
                    subprocess.run(
                        ["docker", "restart", watchdog_config.tts_container],
                        timeout=30, check=True,
                    )
                except Exception as e:
                    logger.error(f"docker restart failed: {e}")
                    last_response_time[0] = time.monotonic()
                    continue

                # Wait for TTS gRPC healthcheck to pass
                deadline = time.monotonic() + watchdog_config.recovery_timeout
                while time.monotonic() < deadline and not chunk_iterator._stopped:
                    result = subprocess.run(
                        ["/bin/grpc_health_probe", "-addr", watchdog_config.tts_grpc_addr],
                        capture_output=True,
                    )
                    if result.returncode == 0:
                        logger.info("TTS healthy — resuming")
                        break
                    time.sleep(5)
                else:
                    logger.error("TTS did not recover in time")

                # Force-close the NMT gRPC channel so the blocked
                # `for response in responses:` loop receives a channel-closed
                # error and restarts the stream.
                logger.warning("Resetting NMT gRPC channel to unblock translation thread")
                self.disconnect()
                self.connect()

                last_response_time[0] = time.monotonic()

            logger.info("Watchdog stopped")

        # Run translation and watchdog in background threads
        self._executor.submit(run_translation)
        self._executor.submit(watchdog)

        return chunk_iterator


# Global client instance
riva_client = RivaS2SClient()
