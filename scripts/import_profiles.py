"""Import pinned upstream TV metadata; never execute its scripts or lists."""
import argparse
import json
from pathlib import Path
import re

COMMIT = "204143007f0bebfb14d6ef001a32e5836b1c90b5"
PKG = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)+\Z")
POSITIVE = re.compile(r"telemetry|analytics|tracking|tracker|\bACR\b|advertis|\bads\b|promo|recommendation", re.I)
NEGATIVE = re.compile(r"assistant|voice|cast|mirror|firmware|updat|preload|stream|unused apps|by choice|optional|demo|retail|shop mode|hotel|IoT|ambient|screensaver", re.I)


def compile_profiles(source):
    profiles = []
    for folder in sorted((source / "examples").iterdir()):
        meta, listing = folder / "tv.json", folder / "debloat.txt"
        if not meta.is_file() or not listing.is_file():
            continue
        data = json.loads(meta.read_text(encoding="utf-8-sig"))
        if "fire" in (data.get("os", "") + data.get("tv", "")).lower():
            continue
        text = listing.read_text(encoding="utf-8-sig")
        # Header is evidence for identity matching; prose is never treated as a command.
        header = "\n".join(text.splitlines()[:8])
        group = ""
        entries = []
        for line in text.splitlines():
            value = line.strip()
            if value.startswith("#"):
                comment = value.lstrip("# -").strip()
                if not comment:
                    group = ""
                elif POSITIVE.search(comment) or NEGATIVE.search(comment):
                    group = comment
                continue
            raw, _, comment = value.partition("#")
            pkg = raw.strip()
            if not PKG.fullmatch(pkg):
                continue
            purpose = comment.strip() or group
            # Metadata only. app.py requires its separate curated catalog before offering a package.
            entries.append({"package": pkg, "purpose": purpose[:400]})
        profiles.append({"id": folder.name, "tv": data["tv"], "brand": data["brand"],
            "os": data["os"], "notes": data.get("notes", ""), "header": header,
            "source": f"examples/{folder.name}/debloat.txt", "packages": entries})
    return {"commit": COMMIT, "profiles": profiles}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "profiles.json")
    args = parser.parse_args()
    result = compile_profiles(args.source)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    profiles = result["profiles"]
    print(f"{len(profiles)} profiles; {len({p['brand'] for p in profiles})} brands")
