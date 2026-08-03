#!/usr/bin/env python3
"""
Voice Reader — reads any document in a British or African voice using edge-tts.

Usage:
    python3 read.py document.pdf                -> document_spoken.mp3
    python3 read.py document.txt                -> document_spoken.mp3
    python3 read.py document.pdf out.mp3        -> custom output name
    python3 read.py document.pdf --voice Ryan   -> pick a voice
    python3 read.py --list-voices               -> show every voice
    python3 read.py --samples                   -> sample clips of the African voices
    python3 read.py --samples all               -> sample clips of every voice
    python3 read.py --verify-voices             -> check IDs against the service

Available British voices:
    --- Male ---
    Ryan     (British male, deep)        <- default
    Thomas   (British male, warm)
    George   (British male, clear)
    Lewis    (British male, smooth)

    --- Female ---
    Libby    (British female, bright)
    Sonia    (British female, mature)
    Maisie   (British female, young)
    Emma     (British female, gentle)
    Isabella (British female, expressive)

Available African voices (English, native to the region):
    --- Male ---
    Chilemba (Kenyan male)
    Abeo     (Nigerian male)
    Elimu    (Tanzanian male)
    Luke     (South African male)

    --- Female ---
    Asilia   (Kenyan female)
    Ezinne   (Nigerian female)
    Imani    (Tanzanian female)
    Leah     (South African female)

Speed: a full 60,000-word book finishes in ~10-15 minutes.
"""

import sys
import os
import re
import asyncio
import warnings
warnings.filterwarnings("ignore")

DEFAULT_VOICE = "Ryan"

# edge-tts British voices (online, Microsoft)
EDGE_BRITISH_VOICES = {
    "ryan":   "en-GB-RyanNeural",
    "thomas": "en-GB-ThomasNeural",
    "libby":  "en-GB-LibbyNeural",
    "sonia":  "en-GB-SoniaNeural",
    "maisie": "en-GB-MaisieNeural",
}

# edge-tts African English voices (online, Microsoft)
EDGE_AFRICAN_VOICES = {
    "chilemba": "en-KE-ChilembaNeural",
    "asilia":   "en-KE-AsiliaNeural",
    "abeo":     "en-NG-AbeoNeural",
    "ezinne":   "en-NG-EzinneNeural",
    "elimu":    "en-TZ-ElimuNeural",
    "imani":    "en-TZ-ImaniNeural",
    "luke":     "en-ZA-LukeNeural",
    "leah":     "en-ZA-LeahNeural",
}

EDGE_VOICES = {**EDGE_BRITISH_VOICES, **EDGE_AFRICAN_VOICES}

# Kokoro voices (offline). Kokoro ships no African English voices — the
# African options above all require a network connection.
KOKORO_VOICES = {
    "george":   "bm_george",
    "lewis":    "bm_lewis",
    "emma":     "bf_emma",
    "isabella": "bf_isabella",
}

ALL_VOICES = {**EDGE_VOICES, **KOKORO_VOICES}

# Human-readable description per voice, used by --list-voices
VOICE_LABELS = {
    "ryan":     "British male, deep",
    "thomas":   "British male, warm",
    "george":   "British male, clear (offline)",
    "lewis":    "British male, smooth (offline)",
    "libby":    "British female, bright",
    "sonia":    "British female, mature",
    "maisie":   "British female, young",
    "emma":     "British female, gentle (offline)",
    "isabella": "British female, expressive (offline)",
    "chilemba": "Kenyan male",
    "asilia":   "Kenyan female",
    "abeo":     "Nigerian male",
    "ezinne":   "Nigerian female",
    "elimu":    "Tanzanian male",
    "imani":    "Tanzanian female",
    "luke":     "South African male",
    "leah":     "South African female",
}


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


def list_voices():
    groups = [
        ("British", EDGE_BRITISH_VOICES.keys() | KOKORO_VOICES.keys()),
        ("African", EDGE_AFRICAN_VOICES.keys()),
    ]
    for title, keys in groups:
        print(f"\n{title}")
        for key in sorted(keys):
            default = "  <- default" if key == DEFAULT_VOICE.lower() else ""
            print(f"  {key:<10} {ALL_VOICES[key]:<22} {VOICE_LABELS[key]}{default}")
    print()


async def verify_voices():
    """Confirm every voice ID we advertise still exists in the service."""
    import edge_tts
    available = {v["ShortName"] for v in await edge_tts.list_voices()}
    missing = {k: v for k, v in EDGE_VOICES.items() if v not in available}
    for key, voice_id in sorted(EDGE_VOICES.items()):
        mark = "MISSING" if key in missing else "ok"
        print(f"  {mark:<8} {key:<10} {voice_id}")
    if missing:
        print(f"\n{len(missing)} voice(s) not found in the service.")
        sys.exit(1)
    print(f"\nAll {len(EDGE_VOICES)} online voices verified.")


SAMPLE_TEXT = (
    "Chapter one. The morning sun rose over the hills, and the whole village "
    "gathered to hear the story that had been passed down for generations."
)


def sample_voices(group: str, text: str, out_dir: str = "samples"):
    """Render the same passage in each voice so they can be compared."""
    if group == "african":
        chosen = dict(EDGE_AFRICAN_VOICES)
    elif group == "british":
        chosen = {**EDGE_BRITISH_VOICES, **KOKORO_VOICES}
    else:
        chosen = dict(ALL_VOICES)

    os.makedirs(out_dir, exist_ok=True)
    print(f"Rendering {len(chosen)} samples into {out_dir}/\n")

    failed = []
    for key in sorted(chosen):
        out = os.path.join(out_dir, f"{key}.mp3")
        print(f"  {key:<10} {VOICE_LABELS[key]:<28} ", end="", flush=True)
        try:
            if key in EDGE_VOICES:
                asyncio.run(synthesize_edge(text, ALL_VOICES[key], out))
            else:
                synthesize_kokoro(text, ALL_VOICES[key], out)
            print("ok")
        except Exception as exc:
            failed.append(key)
            print(f"failed ({type(exc).__name__})")

    print(f"\nDone. {len(chosen) - len(failed)}/{len(chosen)} rendered.")
    if failed:
        print(f"Failed: {', '.join(failed)}")
    print(f"Listen, then re-run with --voice <name> on your document.")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    args = sys.argv[1:]

    if "--list-voices" in args:
        list_voices()
        sys.exit(0)

    if "--samples" in args:
        idx = args.index("--samples")
        rest = args[idx + 1:]
        group = rest[0].lower() if rest and not rest[0].startswith("-") else "african"
        if group not in ("african", "british", "all"):
            print(f"Unknown group '{group}'. Use: african, british, all")
            sys.exit(1)
        sample_voices(group, SAMPLE_TEXT)
        sys.exit(0)

    if "--verify-voices" in args:
        asyncio.run(verify_voices())
        sys.exit(0)

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
    print(f"Voice    : {voice_name} ({VOICE_LABELS[voice_key]})")
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
