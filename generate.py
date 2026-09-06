#!/usr/bin/env python3
"""Builds the DATUM fix matrix from the live state of the gateway repositories.

Every cell is computed, never typed: a fix is detected by a PR's merge state, a
code marker in the tree at a ref, a file that exists, or a commit being an
ancestor of the build. Writes docs/index.html, README.md and docs/state.json.
Needs GITHUB_TOKEN (or `gh auth token` locally). Standard library only.
"""
import datetime
import html
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import urllib.request

API = "https://api.github.com"
TOKEN = os.environ.get("GITHUB_TOKEN") or subprocess.run(["gh", "auth", "token"], capture_output=True, text=True).stdout.strip()

# ---- what is checked -----------------------------------------------------------------------
# Columns: a repository and the refs that count. "main" is what the build is; "sides" are branches
# where a fix may live unmerged. Lazarus has no gateway, only branches behind his PRs.
COLUMNS = [
    {"key": "ocean",    "label": "OCEAN",          "repo": "OCEAN-xyz/datum_gateway",       "main": "master", "sides": []},
    {"key": "innerhat", "label": "innerhat",       "repo": "innerhat-dev/datum_gateway",    "main": "master", "sides": []},
    {"key": "convoy",   "label": "CONVOY",         "repo": "CONVOYMining/datum_gateway",    "main": "master", "sides": []},
    {"key": "fly",      "label": "FlyTheElephant", "repo": "FlyTheElephant1/datum_gateway", "main": "master", "sides": ["test/insulince"]},
    {"key": "maveth",   "label": "MaVeTh",         "repo": "Maveth/datum_gateway",          "main": "master", "sides": ["fix/mainnet-coinbaser-ui-addr", "bip110-pow-v2-innerhat", "fix/blake-payout-coinbase-v2"]},
    {"key": "lazarus",  "label": "Lazarus",        "repo": "AwokenLazarus/datum_gateway",   "main": None,     "sides": ["fix/blake2b-unsplit-coinbase", "fix/late-coinbaser-convoy"]},
]

# Fixes: how to recognise each one. `marker` is a regex over src/*.c, src/*.h and doc/*.md at a ref;
# `exists` is a path; `contains` is a commit that must be an ancestor; `prs` are PR numbers per column
# key that override the code check with the PR's own state.
FIXES = [
    {"group": "Payouts: a wrong answer here pays miners short"},
    {"title": "Full payout coinbase on BLAKE2b jobs (class 4, not the 755-byte class 2)", "note": "Blocks 968456 and 968159 show the truncated shape.",
     "marker": r"blake2b_coinbase_index|return COINBASE_TYPE_YUGE|coinbase_selection = COINBASE_TYPE_YUGE", "prs": {"innerhat": 17, "convoy": [10, 8]}},
    {"title": "Never pair the pool-only class 0 with a full template when the coinbaser is late",
     "marker": r"is_active\(\) \? DATUM_COINBASE_ID_EMPTY", "prs": {"convoy": 13}},
    {"title": "Sigop budget on payout outputs (a big P2PKH split can exceed the block limit)",
     "marker": r"sigops_budget", "prs": {"convoy": 10}},
    {"title": "Block weight accounted with the 164-byte header and the coinbase's real static size",
     "marker": r"DATUM_BLAKE2B_BLOCK_HEADER_SIZE\+5\)<<2", "prs": {"convoy": 10}},
    {"title": "Coinbaser wait race / lost wakeup",
     "marker": None, "prs": {"ocean": 229, "innerhat": 19, "convoy": 9}},
    {"group": "Safety: malformed input from the pool or a miner"},
    {"title": "Job-validation parser bounds and clz(0) guard",
     "marker": r"job_validation_stxlist\(int len", "prs": {"ocean": 236, "innerhat": 20, "convoy": 11}},
    {"title": "Bound the 0x50 0x11 transaction reply to the buffer",
     "marker": r"DATUM_STXLIST_REPLY_MAX", "prs": {"ocean": 235, "innerhat": 18, "convoy": 2}},
    {"title": "Header XOR through memcpy (undefined behavior)",
     "marker": r"T_DATUM_PROTOCOL_HEADER must be four bytes", "prs": {"convoy": 5}},
    {"group": "Operations: blocks and logs"},
    {"title": "submitblock \"duplicate\" treated as the block being accepted",
     "marker": r"datum_submitblock_reply_status", "prs": {"ocean": 233, "innerhat": 14, "convoy": 3}},
    {"title": "Log the node's JSON-RPC error instead of dropping it",
     "marker": r"No CURLOPT_FAILONERROR", "prs": {"convoy": 4}},
    {"title": "Logger waits for its writer thread at init",
     "marker": r"Logger thread not ready after", "prs": {"ocean": 231, "convoy": 6}},
    {"title": "Name the client that found a block",
     "marker": r"found by %s", "prs": {"convoy": 7}},
    {"title": "Warn about BLAKE2b misconfiguration before it costs a block",
     "marker": r"datum_blocktemplates_check_tag_space", "prs": {"innerhat": 12}},
    {"title": "Template PoW on the status page",
     "marker": r"datum_api_var_STRATUM_JOB_POW", "prs": {"innerhat": 11}},
    {"title": "BLAKE2b setup guide",
     "exists": "doc/blake2b.md", "prs": {"innerhat": 10}},
    {"title": "Share prevalidation, share hash on node-check lines, log rotation",
     "exists": "doc/SHARE_VALIDATION.md", "prs": {"innerhat": 9}},
    {"title": "Smart logging by state (NoFlames)",
     "marker": r"last_logged_job_valid", "prs": {"innerhat": 13}},
    {"title": "Drop the forced BIP9 bit 4 (high-hash), headline warning, mainnet address display",
     "contains": "e82d7e5", "prs": {}},
    {"group": "Platform"},
    {"title": "Luke's 64-bit Prime ID, submitblock failure handling, oversized tag, jsonrpc free",
     "contains": "b9ea7dc", "prs": {}},
    {"title": "Wire-time fixes and macOS build (August 26 batch)",
     "contains": "2fea7e5", "prs": {}},
]

# Packages: where the build ref comes from, then the payout-coinbase marker is checked at that ref.
PAYOUT_MARKER = r"blake2b_coinbase_index|return COINBASE_TYPE_YUGE"
PACKAGES = [
    {"label": "Léo Haf's StartOS package, mempool.guide registry (Retropex/datum-gateway-startos, branch pow)",
     "kind": "submodule", "repo": "Retropex/datum-gateway-startos", "ref": "pow", "path": "datum_gateway", "network": "CONVOYMining/datum_gateway"},
    {"label": "paulscode's StartOS package (paulscode/datum-blake2b-startos)",
     "kind": "dockerfile", "repo": "paulscode/datum-blake2b-startos", "ref": "main", "path": "Dockerfile",
     "repo_re": r"ARG DATUM_REPO=https://github.com/([\w.-]+/[\w.-]+)\.git", "ref_re": r"ARG DATUM_REF=([0-9a-f]{7,40})"},
    {"label": "gridlabs gridpool appliance (gridlabs-science/datum-gateway-blake2b-gridpool, branch develop)",
     "kind": "branch", "repo": "gridlabs-science/datum-gateway-blake2b-gridpool", "ref": "develop"},
    {"label": "FlyTheElephant's build (master)",
     "kind": "branch", "repo": "FlyTheElephant1/datum_gateway", "ref": "master"},
]

# ---- GitHub access --------------------------------------------------------------------------
_cache = {}

def api(path, raw=False):
    if path in _cache:
        return _cache[path]
    req = urllib.request.Request(API + "/" + path.lstrip("/"), headers={"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json", "User-Agent": "datum-fix-matrix"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read() if raw else json.loads(r.read())
            break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                data = None
                break
            if attempt == 3 or e.code < 500:
                raise
        except (urllib.error.URLError, ConnectionError, TimeoutError, OSError):
            if attempt == 3:
                raise
        import time
        time.sleep(2 * (attempt + 1))
    _cache[path] = data
    return data

def tree_text(repo, ref):
    """Text of src/*.c, src/*.h and doc/*.md at ref, plus the set of paths. One tarball request per ref."""
    key = ("tree", repo, ref)
    if key in _cache:
        return _cache[key]
    blob = api(f"repos/{repo}/tarball/{ref}", raw=True)
    text, paths = "", set()
    if blob:
        with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as t:
            for m in t.getmembers():
                p = m.name.split("/", 1)[1] if "/" in m.name else m.name
                paths.add(p)
                if m.isfile() and (re.match(r"src/[^/]+\.[ch]$", p) or re.match(r"doc/[^/]+\.md$", p)):
                    text += t.extractfile(m).read().decode("utf-8", "replace") + "\n"
    _cache[key] = (text, paths)
    return _cache[key]

def contains(repo, ref, sha):
    c = api(f"repos/{repo}/compare/{sha}...{ref}")
    return bool(c) and c.get("status") in ("ahead", "identical")

def pr_state(repo, n):
    p = api(f"repos/{repo}/pulls/{n}")
    if not p:
        return None
    return "merged" if p.get("merged_at") else p["state"]

def ref_of(col, ref):
    return f"{col['repo'].split('/')[0]}:{ref}" if ref else None

# ---- cells ----------------------------------------------------------------------------------
def check_ref(fix, repo, ref):
    if ref is None:
        return False
    if fix.get("marker"):
        text, _ = tree_text(repo, ref)
        return re.search(fix["marker"], text) is not None
    if fix.get("exists"):
        _, paths = tree_text(repo, ref)
        return fix["exists"] in paths
    if fix.get("contains"):
        return contains(repo, ref, fix["contains"])
    return False

def cell(fix, col):
    """Returns (state, label): state in ok / warn / bad / na."""
    prs = fix.get("prs", {}).get(col["key"])
    if prs:
        # One fix can ride in more than one PR; the best state wins.
        states = [(n, pr_state(col["repo"], n)) for n in (prs if isinstance(prs, list) else [prs])]
        merged = [n for n, st in states if st == "merged"]
        opened = [n for n, st in states if st == "open"]
        closed = [n for n, st in states if st == "closed"]
        if merged:
            return "ok", "merged " + ", ".join(f"#{n}" for n in merged)
        if opened:
            return "warn", ", ".join(f"#{n}" for n in opened) + " open"
        if closed:
            return "bad", ", ".join(f"#{n}" for n in closed) + " closed"
    if col["main"] and check_ref(fix, col["repo"], col["main"]):
        return "ok", "on master"
    for s in col["sides"]:
        if check_ref(fix, col["repo"], s):
            return "warn", f"branch {s.split('/')[-1]}"
    if col["main"] is None:
        return "na", "n/a"
    return "bad", "missing"

def package_row(p):
    if p["kind"] == "submodule":
        c = api(f"repos/{p['repo']}/contents/{p['path']}?ref={p['ref']}")
        sha = c["sha"] if c else None
        built = f"{p['network']} at {sha[:7]}" if sha else "?"
        ok = sha and re.search(PAYOUT_MARKER, tree_text(p["network"], sha)[0]) is not None
    elif p["kind"] == "dockerfile":
        c = api(f"repos/{p['repo']}/contents/{p['path']}?ref={p['ref']}")
        import base64
        text = base64.b64decode(c["content"]).decode() if c else ""
        rm, fm = re.search(p["repo_re"], text), re.search(p["ref_re"], text)
        src, sha = (rm.group(1) if rm else "?"), (fm.group(1) if fm else None)
        built = f"{src} at {sha[:7]}" if sha else "?"
        ok = sha and re.search(PAYOUT_MARKER, tree_text(src, sha)[0]) is not None
    else:
        built = f"{p['repo']} at {p['ref']}"
        ok = re.search(PAYOUT_MARKER, tree_text(p["repo"], p["ref"])[0]) is not None
    return {"label": p["label"], "built": built, "state": "ok" if ok else "bad", "text": "present" if ok else "missing"}

# ---- output ---------------------------------------------------------------------------------
def build():
    rows = []
    for f in FIXES:
        if "group" in f:
            rows.append({"group": f["group"]})
            continue
        rows.append({"title": f["title"], "note": f.get("note", ""), "cells": [dict(zip(("state", "text"), cell(f, c))) for c in COLUMNS]})
    pkgs = [package_row(p) for p in PACKAGES]
    return {"generated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "columns": [c["label"] for c in COLUMNS], "rows": rows, "packages": pkgs}

def render_html(state):
    e = html.escape
    out = [HTML_HEAD.replace("__GENERATED__", state["generated"])]
    out.append('<section><h2>Fixes by repository</h2><div class="wrap"><table><thead><tr><th>Fix</th>' + "".join(f"<th>{e(c)}</th>" for c in state["columns"]) + "</tr></thead><tbody>")
    for r in state["rows"]:
        if "group" in r:
            out.append(f'<tr class="group"><td colspan="{len(state["columns"]) + 1}">{e(r["group"])}</td></tr>')
        else:
            note = f' <span class="note">{e(r["note"])}</span>' if r["note"] else ""
            out.append(f"<tr><td>{e(r['title'])}{note}</td>" + "".join(f'<td class="c"><span class="{c["state"]}">{e(c["text"])}</span></td>' for c in r["cells"]) + "</tr>")
    out.append("</tbody></table></div>")
    out.append('<p class="foot" style="margin-top:8px">Lazarus has no gateway of his own; his column is the working branches behind his PRs. His pool, Prime, points users at CONVOY, FlyTheElephant\'s build or iohzrd\'s RATUM, a separate Rust gateway outside this lineage.</p></section>')
    out.append('<section><h2>What people install</h2><div class="wrap"><table><thead><tr><th>Package or build</th><th>Built from</th><th>Payout coinbase fix</th></tr></thead><tbody>')
    for p in state["packages"]:
        out.append(f'<tr><td>{e(p["label"])}</td><td class="mono">{e(p["built"])}</td><td class="c"><span class="{p["state"]}">{e(p["text"])}</span></td></tr>')
    out.append("</tbody></table></div></section>")
    out.append(HTML_FOOT)
    return "\n".join(out)

def render_md(state):
    o = [f"# DATUM fix matrix\n\nGenerated {state['generated']} from the live repositories by `generate.py`; the page with color is at `docs/index.html` (GitHub Pages). Bold = merged where that build comes from; plain = a PR or branch exists; missing = no fix; n/a = no gateway.\n",
         "| Fix | " + " | ".join(state["columns"]) + " |", "|---|" + "---|" * len(state["columns"])]
    for r in state["rows"]:
        if "group" in r:
            o.append(f"| **{r['group']}** |" + " |" * len(state["columns"]))
        else:
            o.append(f"| {r['title']} | " + " | ".join(f"**{c['text']}**" if c["state"] == "ok" else c["text"] for c in r["cells"]) + " |")
    o += ["", "## What people install", "", "| Package or build | Built from | Payout coinbase fix |", "|---|---|---|"]
    for p in state["packages"]:
        o.append(f"| {p['label']} | `{p['built']}` | {'**present**' if p['state'] == 'ok' else 'missing'} |")
    o.append("\nTo add a fix, append an entry to `FIXES` in `generate.py`: a marker regex, a file path or a commit, plus PR numbers per repository.")
    return "\n".join(o) + "\n"

HTML_HEAD = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "template-head.html"), encoding="utf8").read()
HTML_FOOT = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "template-foot.html"), encoding="utf8").read()

if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    state = build()
    os.makedirs(os.path.join(here, "docs"), exist_ok=True)
    with open(os.path.join(here, "docs", "index.html"), "w", encoding="utf8") as f:
        f.write(render_html(state))
    with open(os.path.join(here, "docs", "state.json"), "w", encoding="utf8") as f:
        json.dump(state, f, indent=1)
    with open(os.path.join(here, "README.md"), "w", encoding="utf8") as f:
        f.write(render_md(state))
    bad = sum(1 for r in state["rows"] if "cells" in r for c in r["cells"] if c["state"] == "bad")
    print(f"generated {state['generated']}: {sum(1 for r in state['rows'] if 'cells' in r)} fixes, {len(state['columns'])} columns, {bad} missing cells, {len(state['packages'])} packages")
