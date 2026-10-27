"""privacy.redact on synthetic SIP/SDP/log text (all addresses are made up / doc ranges)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import io as _io
from privacy import redact, MASK, _RedactingStream

LEAKS = ["203.0.113.45", "198.51.100.7", "2001:db8:85a3::8a2e:370:7334", "fe80::1%eth0",
         "phone.example.net", "abcDEF123secretkey", "deadbeefnonce", "ufragX1", "pwdY2"]

SAMPLE = """INVITE sip:alice@phone.example.net:5060;transport=udp SIP/2.0
Via: SIP/2.0/UDP 198.51.100.7:5060;rport;branch=z9hG4bK776
v: SIP/2.0/UDP [2001:db8:85a3::8a2e:370:7334]:5060
Contact: <sip:alice@203.0.113.45:40112;ob>
Record-Route: <sip:proxy.example.net;lr>
From: "Alice" <sip:alice@phone.example.net>;tag=abc
To: <sip:bob@phone.example.net>
Authorization: Digest username="u", nonce="deadbeefnonce", response="xx"
Via: SIP/2.0/UDP 10.0.0.2;received=203.0.113.45;rport=40112
o=- 1 1 IN IP4 203.0.113.45
c=IN IP6 2001:db8:85a3::8a2e:370:7334
a=candidate:1 1 UDP 2130706431 203.0.113.45 40112 typ host
a=rtcp:40113 IN IP4 203.0.113.45
a=crypto:1 AES_CM_128_HMAC_SHA1_80 inline:abcDEF123secretkey
a=ice-ufrag:ufragX1
a=ice-pwd:pwdY2
12:34:56.789 pjsua_core.c  Sending Request msg to fe80::1%eth0:5060
ConnectionError: could not reach 203.0.113.45:5060
"""

def test_no_leaks():
    out = redact(SAMPLE)
    for leak in LEAKS:
        assert leak not in out, (leak, out)
    assert MASK in out

def test_keeps_ordinary_text():
    for keep in ["12:34:56.789 call connected", 'User replied: "你好 3.5 分钟后打给我"',
                 "listen: exit=silence dur=2.0s rms_max=812 thresh=300"]:
        assert redact(keep) == keep, (keep, redact(keep))

FOLDED = """Authorization: Digest username="alice",
    realm="phone.example.net", nonce="deadbeefnonce",
\tresponse="cafebabe0011", uri="sip:bob@203.0.113.45"
Max-Forwards: 70
"""

def test_folded_header():
    out = redact(FOLDED)
    for leak in ["alice", "phone.example.net", "deadbeefnonce", "cafebabe0011", "203.0.113.45"]:
        assert leak not in out, (leak, out)
    assert "Max-Forwards: 70" in out

def test_prefixed_fields():
    lines = [
        'call failed: Authorization: Digest username="alice", response="cafebabe0011"',
        "pjsua_media.c  remote sdp: a=ice-pwd:pwdY2 a=ice-ufrag:ufragX1",
        "RuntimeError: bad answer (c=IN IP4 203.0.113.45)",
        "error in SDP o=- 99 2 IN IP6 2001:db8::7 attr",
        "Exception: WWW-Authenticate: Digest realm=\"phone.example.net\", nonce=\"deadbeefnonce\"",
        "candidate a=candidate:2 1 udp 1 198.51.100.7 5000 typ srflx raddr 10.0.0.9",
    ]
    out = redact("\n".join(lines))
    for leak in ["alice", "cafebabe0011", "pwdY2", "ufragX1", "203.0.113.45", "2001:db8::7",
                 "phone.example.net", "deadbeefnonce", "198.51.100.7", "10.0.0.9"]:
        assert leak not in out, (leak, out)

def test_stderr_stream():
    sink = _io.StringIO()
    st = _RedactingStream(sink)
    st.write("Traceback ...\nConnectionError: Contact: <sip:x@203.0.113.45>")
    st.write(" and more\n    folded 198.51.100.7\n")
    st.flush()
    out = sink.getvalue()
    assert "203.0.113.45" not in out and "198.51.100.7" not in out, out
    assert "Traceback ..." in out

def test_flush_midline():
    sink = _io.StringIO()
    st = _RedactingStream(sink)
    st.write("connect to 203.0."); st.flush()
    assert sink.getvalue() == "", sink.getvalue()
    st.write("113.45 failed\n"); st.flush()
    st.write("tail 198.51."); st.flush(); st.write("100.7"); st.close()
    out = sink.getvalue()
    assert "203.0.113.45" not in out and "198.51.100.7" not in out, out
    assert "failed" in out

def test_redactor_state_across_feeds():
    from privacy import Redactor
    r = Redactor()
    out = r.feed("Authorization: Digest username=\"alice\",\n")
    out += r.feed("    realm=\"phone.example.net\"\n")
    out += r.feed("User replied: 你好\n")
    assert "alice" not in out and "phone.example.net" not in out, out
    assert "User replied: 你好" in out

if __name__ == "__main__":
    test_flush_midline(); test_redactor_state_across_feeds()
    test_no_leaks(); test_keeps_ordinary_text(); test_folded_header()
    test_prefixed_fields(); test_stderr_stream(); print("privacy ok")
