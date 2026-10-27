"""Cloud-STT config: new VOICE_STT_* names win, old GROQ names still work. Fake keys only."""
import importlib, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

NAMES = ["VOICE_STT_KEY", "GROQ_API_KEY", "VOICE_STT_ENV_FILE", "VOICE_GROQ_ENV_FILE",
         "VOICE_STT_URL", "VOICE_GROQ_URL", "VOICE_STT_MODEL", "VOICE_GROQ_MODEL"]


def load(**env):
    for n in NAMES:
        os.environ.pop(n, None)
    os.environ.update(env)
    import voice_agent
    return importlib.reload(voice_agent)


def main():
    va = load()
    assert not va.USE_GROQ and va.GROQ_STT_URL.startswith("https://api.groq.com/")
    va = load(GROQ_API_KEY="fake-old", VOICE_GROQ_MODEL="m-old")
    assert va.USE_GROQ and va._GROQ_KEY == "fake-old" and va.GROQ_STT_MODEL == "m-old"
    va = load(GROQ_API_KEY="fake-old", VOICE_STT_KEY="fake-new",
              VOICE_GROQ_URL="https://old.invalid/x", VOICE_STT_URL="https://new.invalid/x")
    assert va._GROQ_KEY == "fake-new" and va.GROQ_STT_URL == "https://new.invalid/x"
    with tempfile.NamedTemporaryFile("w", suffix=".env", delete=False) as f:
        f.write('export VOICE_STT_KEY="fake-file"\n')
    try:
        va = load(VOICE_STT_ENV_FILE=f.name)
        assert va._GROQ_KEY == "fake-file"
        va = load(VOICE_GROQ_ENV_FILE=f.name)
        assert va._GROQ_KEY == "fake-file"
    finally:
        os.unlink(f.name)
    print("test_stt_env: ok")


if __name__ == "__main__":
    main()
