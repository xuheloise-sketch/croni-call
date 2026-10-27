# ringringring

Your AI agent calls your phone for a two-way voice conversation.

**Zero cost.** No Mac, no $99 developer account, no native iOS app, no database. Install the free Linphone app on your iPhone and your AI can call you.

- No phone number to buy, no per-minute billing. Speech-to-text and text-to-speech run on free tiers.
- Needs only the Linux server your AI already runs on.
- Rings even when the iPhone screen is off or Linphone is in the background.
- Swappable STT (any OpenAI-compatible `/audio/transcriptions` endpoint) and TTS (Edge TTS by default, or any command).

The full guide is in Chinese: **[README.zh-CN.md](README.zh-CN.md)**.

Quick start (Linux x86_64, Python 3.11):

```bash
git clone https://github.com/yanyan1115/ringringring.git && cd ringringring
plugin-native/bin/install.sh --check
plugin-native/bin/install.sh --pjsua2 https://github.com/yanyan1115/ringringring/releases/download/v0.1.0/pjsua2-2.17-linux-x86_64-cp311.tar.gz --src .
# then fill in ~/.config/ringringring/voice.env and open UDP 4000-4100
```

In Claude Code:

```
/plugin marketplace add yanyan1115/ringringring
/plugin install ringringring@ringringring
```

## Credits

Research and design: Cora and South. Implementation: Claude.

Built on [Ringback](https://github.com/mohitbadwal/ringback) by Mohit Badwal (Apache 2.0); its original README is kept at [docs/README.upstream.md](docs/README.upstream.md). Thanks to [Linphone](https://www.linphone.org/) for free SIP accounts.

## License

[GPL-3.0-or-later](LICENSE). Upstream Ringback code is Apache 2.0, see [LICENSE-APACHE-2.0](LICENSE-APACHE-2.0) and [NOTICE](NOTICE).
