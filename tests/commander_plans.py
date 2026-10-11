"""Commander test suite: the expected game plan for commanders the builder has gotten wrong before (and other tricky
ones). Run after any change:  python tests/commander_plans.py   (needs data/cards.json; uses Forge scripts if present)"""
import sys
sys.path.insert(0, "src")
import analyze as A, options as O, build_deck as B
from common import load_cards

EXPECT = {   # name: (role, text that must appear in the beneficiary label or a condition, or None)
    "Arabella, Abandoned Doll": ("finisher", "power 2 or less"),
    "Doran, Besieged by Time": ("enabler", "toughness"),
    "Edgar Markov": ("enabler", "vampire"),
    "Krenko, Mob Boss": ("enabler", "goblin"),
    "Talrand, Sky Summoner": ("engine", None),
    "Lathril, Blade of the Elves": ("finisher", None),
    "Purphoros, God of the Forge": ("finisher", None),
    "Jodah, the Unifier": ("enabler", "legendary"),
    "Atraxa, Praetors' Voice": ("engine", None),
    "Korvold, Fae-Cursed King": ("engine", None),
    "Meren of Clan Nel Toth": ("engine", None),
}
idx = load_cards("data/cards.json")
B.all_types(idx)
bad = 0
for name, (role, must) in EXPECT.items():
    c = idx.get(name.lower())
    if not c:
        print(f"SKIP {name} (not in card data)")
        continue
    p = A.analyze(c, A.ALL_TYPES, O.VIBES[O.DEFAULT_VIBE])
    th = p["thesis"]
    text = " ".join([(th.get("beneficiary") or {}).get("label", "")] + [r["text"] for r in p["conditions"]]).lower()
    ok = th["role"] == role and (must is None or must in text)
    bad += not ok
    print(("ok   " if ok else "FAIL ") + f"{name}: {th['role']} | {text or '-'} | {th.get('read_from')}")
GIFTS = ["Gluntch, the Bestower", "Phelddagrif", "Kynaios and Tiro of Meletis"]   # give their gifts to OTHER players
for name in GIFTS:
    c = idx.get(name.lower())
    if not c:
        continue
    p = A.analyze(c, A.ALL_TYPES, O.VIBES[O.DEFAULT_VIBE])
    ok = p["role"].get("gifts") and p["thesis"]["lead"] == "Politics / goad / monarch"
    bad += not ok
    print(("ok   " if ok else "FAIL ") + f"{name}: gift commander -> {p['thesis']['lead']}")
REQUIRES = {   # abilities that only work once a condition is met: the deck has to set it up
    "Jor Kadeen, the Prevailer": "3+ artifacts",
    "Tatyova, Steward of Tides": "7+ lands",
    "Titania, Voice of Gaea": "4+ cards in your graveyard",
    "Jetmir, Nexus of Revels": "9+ creatures",
}
for name, must in REQUIRES.items():
    c = idx.get(name.lower())
    if not c:
        continue
    p = A.analyze(c, A.ALL_TYPES, O.VIBES[O.DEFAULT_VIBE])
    got = [r["text"] for r in p["role"].get("requirements") or []]
    ok = any(must in t for t in got)
    bad += not ok
    print(("ok   " if ok else "FAIL ") + f"{name}: needs {got}")
FACTS = {   # what the commander does with other cards, read from its Forge script: (role key, check, a card it should favor)
    "Zur the Enchanter": ("targets", lambda v: any(t["kind"] == "tutor" and "Enchantment" in t["filter"] for t in v), "Rancor"),
    "Aang, at the Crossroads": ("targets", lambda v: any(t["kind"] == "dig" for t in v), None),
    "Karador, Ghost Chieftain": ("targets", lambda v: any(t["kind"] == "cast" and "Creature" in t["filter"] for t in v), None),
    "Captain Sisay": ("targets", lambda v: any(t["kind"] == "tutor" and "Legendary" in t["filter"] for t in v), None),
    "Adrix and Nev, Twincasters": ("doubles", lambda v: "tokens" in v, None),
    "Kiki-Jiki, Mirror Breaker": ("copies", lambda v: bool(v), None),
    "Yuriko, the Tiger's Shadow": ("scales_mv", lambda v: v, None),
}
for name, (key, check, fav) in FACTS.items():
    c = idx.get(name.lower())
    if not c:
        continue
    p = A.analyze(c, A.ALL_TYPES, O.VIBES[O.DEFAULT_VIBE])
    v = p["role"].get(key)
    ok = bool(check(v or ([] if key != "scales_mv" else False)))
    if ok and fav and idx.get(fav.lower()):
        fc = dict(idx[fav.lower()])
        sc, why = A.synergy(fc, p)
        ok = "target" in fc.get("_needs", [])
    bad += not ok
    print(("ok   " if ok else "FAIL ") + f"{name}: {key} = {str(v)[:90]}")
import conditions as CN
ara = A.analyze(idx["arabella, abandoned doll"], A.ALL_TYPES, O.VIBES[O.DEFAULT_VIBE])
PUMPS = {"Glorious Anthem": "breaks", "Inspired Charge": "", "Overrun": ""}   # permanent pump breaks "power 2 or less"
for name, want in PUMPS.items():
    c = idx.get(name.lower())
    if not c:
        continue
    got = CN.judge(c, ara["conditions"][0])[0] if ara["conditions"] else "?"
    ok = got == want
    bad += not ok
    print(("ok   " if ok else "FAIL ") + f"Arabella vs {name}: {got or 'neutral'}")
total = len(EXPECT) + len(GIFTS) + len(REQUIRES) + len(PUMPS) + len(FACTS)
print(f"{total - bad}/{total} commanders read as expected")
sys.exit(1 if bad else 0)
