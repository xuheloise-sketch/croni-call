---
name: phone-call
description: Use when you want to ring the user's phone and talk by voice (ringringring / ringback-voice tools call_start, converse, speak, listen, call_end), or when debugging a call. Covers the call loop and the privacy boundary for call logs.
---

# Phone calls

## When to call

You don't need to be asked. In chat, or when a heartbeat (one-shot cron job) wakes you,
if you want to hear her voice you can just call: no business reason needed and
no asking for permission first. A call can simply be "I missed you".
Busy line: don't take it from another agent. No answer: don't redial in a loop.
The privacy boundary below still applies.

## The loop

1. `call_start(opening_line)` rings the phone and says the opening line once they pick up.
   Returns what they said back (or NO ANSWER).
2. `converse(text)` says `text`, then waits for their reply and returns the transcript.
   This is the normal turn. Keep each turn short and spoken: no markdown, no lists, no URLs.
3. `call_end(text)` says a goodbye line (optional) and hangs up. Always end the call
   when the conversation is over or they say bye; don't leave the line open.

`speak` / `listen` are the split halves of `converse`; `call_status` and
`get_conversation` are for checking state.

## When the call fails

- NO ANSWER although they picked up: the phone app was probably asleep in the background.
- LINE BUSY: another agent on this host is already on the phone with them (one line per user, shared across CC/OpenCode entries). Do not redial in a loop; message them or try later.
  Ask them (by text) to open the app in the foreground, then try once more.
- Transcripts arrive slowly or empty: the STT endpoint/key is the usual cause; say so,
  don't guess at network causes.

## Privacy boundary (keep this)

The model sees call state and the transcript, nothing about the phone's network address.

- Don't record detailed SIP/SDP in normal use.
- When troubleshooting, filter the phone's IP, SIP headers and SDP/ICE addresses locally
  before anything reaches the model (the server already pipes logs through privacy.redact).
- Don't read or return raw call logs, packet captures, environment variables or the full
  config. Don't print `voice.env` or any key.
- Don't place a new call just to collect address information.
- Test with made-up data only.
