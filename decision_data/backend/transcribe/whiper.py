""" Using OpenAI services to do speech transcription """

import openai
from openai import OpenAI
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv
import os


def transcribe_from_local(audio_path: Path) -> str:
    """Transcribe audio file using Whiper service

    :param audio_path: local audio path file
    :type audio_path: Path
    :return: transcription
    :rtype: str
    """
    openai.api_key = os.getenv("OPENAI_API_KEY")
    client = OpenAI()
    with audio_path.open("rb") as audio_file:
        transcription = client.audio.transcriptions.create(
            model="whisper-1", file=audio_file
        )
    return transcription.text


def main():
    audio_path = Path("data/20241120_130749.wav")
    response = transcribe_from_local(audio_path=audio_path)
    logger.info(f"Transcription: {response}")


if __name__ == "__main__":
    load_dotenv()
    main()
