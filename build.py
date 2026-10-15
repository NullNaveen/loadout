#!/usr/bin/env python3
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
TITLE = "loadout"
SLUG = re.compile(r"[\w.-]+/[\w.-]+")


def parse(path):
    intro, sections, section, category = [], [], None, None
    with open(path, encoding="utf-8-sig") as f:
        for n, raw in enumerate(f, 1):
            line = raw.strip()
            if not line:
                continue
            if line.startswith("# "):
                section, category = {"name": line[2:], "categories": []}, None
                sections.append(section)
            elif line.startswith("## "):
                if section is None:
                    sys.exit(f"list.txt:{n}: category before any section")
                category = {"name": line[3:], "repos": []}
                section["categories"].append(category)
            elif section is None:
                intro.append(line)
            elif category is None:
                sys.exit(f"list.txt:{n}: repo outside a category")
            else:
                slug, *note = line.split(None, 1)
                if not SLUG.fullmatch(slug):
                    sys.exit(f"list.txt:{n}: bad repo {slug!r}")
                category["repos"].append({"slug": slug, "note": note[0] if note else ""})
    return intro, sections


def fetch(slug, token):
    req = urllib.request.Request(f"https://api.github.com/repos/{slug}")
    req.add_header("Accept", "application/vnd.github+json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.load(r)
            return data["full_name"], data["stargazers_count"]
        except urllib.error.HTTPError as e:
            if e.code in (404, 410, 451):
                print(f"skipping {slug}: HTTP {e.code}", file=sys.stderr)
                return None
            if e.headers.get("x-ratelimit-remaining") == "0":
                sys.exit("rate limited, set GITHUB_TOKEN")
            err = e
        except OSError as e:
            err = e
        if attempt < 2:
            time.sleep(5 * 3 ** attempt)
    sys.exit(f"{slug}: {err}")


def short(n):
    if n < 1000:
        return str(n)
    if n < 10000:
        return f"{n / 1000:.1f}k".replace(".0k", "k")
    return f"{round(n / 1000)}k"


def anchor(name):
    return re.sub(r"[^\w\- ]", "", name.lower()).replace(" ", "-")


def render(intro, sections):
    out = [f"# {TITLE}", "", *intro, ""]
    out.append(" · ".join(f"[{s['name']}](#{anchor(s['name'])})" for s in sections))
    for s in sections:
        out += ["", f"## {s['name']}"]
        cats = [c for c in s["categories"] if c["repos"]]
        cats.sort(key=lambda c: -max(r["stars"] for r in c["repos"]))
        for c in cats:
            out += ["", f"### {c['name']}", "", "| Repo | Stars | About |", "|---|--:|---|"]
            for r in sorted(c["repos"], key=lambda r: (-r["stars"], r["name"].lower())):
                note = r["note"].replace("|", r"\|")
                out.append(f"| [{r['name']}](https://github.com/{r['name']}) | {short(r['stars'])} | {note} |")
    return "\n".join(out) + "\n"


def main():
    token = os.environ.get("GITHUB_TOKEN")
    intro, sections = parse(os.path.join(HERE, "list.txt"))
    seen = set()
    for s in sections:
        for c in s["categories"]:
            kept = []
            for r in c["repos"]:
                got = fetch(r["slug"], token)
                if not got:
                    continue
                if got[0].lower() in seen:
                    sys.exit(f"{r['slug']} is listed twice (as {got[0]})")
                seen.add(got[0].lower())
                r["name"], r["stars"] = got
                kept.append(r)
            c["repos"] = kept
    with open(os.path.join(HERE, "README.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(render(intro, sections))


if __name__ == "__main__":
    main()
