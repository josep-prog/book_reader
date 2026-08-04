#!/usr/bin/env python3
"""
Voice Reader — reads any document in a British voice using edge-tts.

Usage:
    python3 read.py document.pdf              -> document_spoken.mp3
    python3 read.py document.txt              -> document_spoken.mp3
    python3 read.py document.pdf out.mp3      -> custom output name
    python3 read.py document.pdf --voice Ryan -> pick a voice
    python3 read.py document.pdf --voice Lina -> African (South African) female

Available voices:
    --- African English (female) ---
    Lina     (South African female)      <- African default
    Asilia   (Kenyan female)
    Ezinne   (Nigerian female)
    Imani    (Tanzanian female)

    --- African English (male) ---
    Luke     (South African male)
    Chilemba (Kenyan male)
    Abeo     (Nigerian male)

    --- British male ---
    Ryan     (British male, deep)        <- default
    Thomas   (British male, warm)
    George   (British male, clear)
    Lewis    (British male, smooth)

    --- British female ---
    Libby    (British female, bright)
    Sonia    (British female, mature)
    Maisie   (British female, young)
    Emma     (British female, gentle)
    Isabella (British female, expressive)

Speed: a full 60,000-word book finishes in ~10-15 minutes.
"""

import sys
import os
import re
import asyncio
import warnings
warnings.filterwarnings("ignore")

DEFAULT_VOICE = "Ryan"

# edge-tts voices (online, Microsoft)
EDGE_VOICES = {
    # African English
    "lina":     "en-ZA-LeahNeural",      # South African female
    "asilia":   "en-KE-AsiliaNeural",    # Kenyan female
    "ezinne":   "en-NG-EzinneNeural",    # Nigerian female
    "imani":    "en-TZ-ImaniNeural",     # Tanzanian female
    "luke":     "en-ZA-LukeNeural",      # South African male
    "chilemba": "en-KE-ChilembaNeural",  # Kenyan male
    "abeo":     "en-NG-AbeoNeural",      # Nigerian male
    # British English
    "ryan":   "en-GB-RyanNeural",
    "thomas": "en-GB-ThomasNeural",
    "libby":  "en-GB-LibbyNeural",
    "sonia":  "en-GB-SoniaNeural",
    "maisie": "en-GB-MaisieNeural",
}

# Kokoro voices (offline)
KOKORO_VOICES = {
    "george":   "bm_george",
    "lewis":    "bm_lewis",
    "emma":     "bf_emma",
    "isabella": "bf_isabella",
}

ALL_VOICES = {**EDGE_VOICES, **KOKORO_VOICES}


def extract_text(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        from pypdf import PdfReader
        return "\n".join(p.extract_text() or "" for p in PdfReader(path).pages)
    if ext in (".txt", ".md"):
        with open(path, encoding="utf-8") as f:
            return f.read()
    print(f"Unsupported file type '{ext}'. Supported: .pdf  .txt  .md")
    sys.exit(1)


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"[^\x20-\x7E]", " ", text)
    return text


async def synthesize_edge(text: str, voice_id: str, output_path: str):
    import edge_tts
    communicator = edge_tts.Communicate(text, voice_id)
    await communicator.save(output_path)


def synthesize_kokoro(text: str, voice_id: str, output_path: str):
    from kokoro import KPipeline
    import soundfile as sf
    import numpy as np
    pipeline = KPipeline(lang_code="b")  # 'b' = British English
    chunks = []
    for _, _, audio in pipeline(text, voice=voice_id, speed=1.0):
        chunks.append(audio)
    combined = np.concatenate(chunks) if len(chunks) > 1 else chunks[0]
    sf.write(output_path, combined, 24000)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    args = sys.argv[1:]

    # Parse --voice flag
    voice_name = DEFAULT_VOICE
    if "--voice" in args:
        idx = args.index("--voice")
        voice_name = args[idx + 1]
        args = [a for i, a in enumerate(args) if i != idx and i != idx + 1]

    voice_key = voice_name.lower()
    if voice_key not in ALL_VOICES:
        print(f"Unknown voice '{voice_name}'. Available: {', '.join(ALL_VOICES)}")
        sys.exit(1)

    src = args[0]
    if not os.path.exists(src):
        print(f"File not found: {src}")
        sys.exit(1)

    out = args[1] if len(args) > 1 else os.path.splitext(src)[0] + "_spoken.mp3"

    print(f"Document : {src}")
    text = clean_text(extract_text(src))
    print(f"Words    : {len(text.split())}")
    print(f"Voice    : {voice_name}")
    print(f"Output   : {out}\n")
    print("Generating audio... (fast)\n")

    voice_id = ALL_VOICES[voice_key]

    if voice_key in EDGE_VOICES:
        asyncio.run(synthesize_edge(text, voice_id, out))
    else:
        synthesize_kokoro(text, voice_id, out)

    size_mb = os.path.getsize(out) / 1_000_000
    print(f"Done! {out}  ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
