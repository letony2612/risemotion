"""Stand-in voice-over (local Kokoro TTS) so the edit can be built before the real take exists.

Writes one continuous take of timeline.LINES, to be imported like a real one:
python3 tools/standin_voice.py /tmp/standin.wav && python3 tools/import_voice.py /tmp/standin.wav
"""
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).parent))
import timeline as T  # noqa: E402

CACHE = Path.home() / ".cache" / "hyperframes" / "tts"
SAY = {"RISE": "Raïze"}  # Kokoro spells capitals out


def say(word):
    core = word.strip(".,!?")
    return word.replace(core, SAY[core]) if core in SAY else word


def main(out):
    import kokoro_onnx
    model = kokoro_onnx.Kokoro(str(CACHE / "models" / "kokoro-v1.0.onnx"), str(CACHE / "voices" / "voices-v1.0.bin"))
    parts, sr = [], 24000
    for spoken, _ in T.LINES.values():
        text = " ".join(say(w) for w in spoken.split())
        samples, sr = model.create(text, voice="ff_siwis", speed=1.12, lang="fr-fr")
        parts += [np.asarray(samples, dtype=np.float32), np.zeros(int(0.28 * sr), dtype=np.float32)]
    sf.write(out, np.concatenate(parts), sr)
    print("stand-in take written to", out)


if __name__ == "__main__":
    main(sys.argv[1])
