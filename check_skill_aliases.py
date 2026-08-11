# file: check_skill_aliases.py
"""
Prints the current, actual content of MANUAL_ALIASES and AUTO_ALIASES as
loaded from app/normalize_sections/normalize_skills.py -- ground truth
check, rather than relying on what we think was pasted in.

Usage:
    python check_skill_aliases.py
"""

from app.normalize_sections.normalize_skills import MANUAL_ALIASES, AUTO_ALIASES, CANONICAL_CASING


def main():
    print(f"CANONICAL_CASING ({len(CANONICAL_CASING)} entries):")
    for k, v in sorted(CANONICAL_CASING.items()):
        print(f"  {k!r} -> {v!r}")

    print(f"\nMANUAL_ALIASES ({len(MANUAL_ALIASES)} entries):")
    for k, v in sorted(MANUAL_ALIASES.items()):
        print(f"  {k!r} -> {v!r}")

    print(f"\nAUTO_ALIASES ({len(AUTO_ALIASES)} entries):")
    for k, v in sorted(AUTO_ALIASES.items()):
        print(f"  {k!r} -> {v!r}")

    # Specific spot-checks for the values we expected to be merged
    expected = [
        "Microsoft Office", "Microsoft Suite",
        "Business Continuity Plan", "IT Master Plan",
        "IT master plan development",
    ]
    print("\nSpot-check on expected merges:")
    for raw in expected:
        in_manual = raw in MANUAL_ALIASES
        in_auto = raw in AUTO_ALIASES
        target = MANUAL_ALIASES.get(raw) or AUTO_ALIASES.get(raw)
        print(f"  {raw!r}: in MANUAL_ALIASES={in_manual}, in AUTO_ALIASES={in_auto}, resolves to={target!r}")


if __name__ == "__main__":
    main()