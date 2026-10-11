"""Audit: which parts of commanders' Forge scripts does the builder NOT read yet?

For every card that can be a commander, list each parameter on its triggers / static abilities / activated
abilities / effects, and count the ones the builder ignores (forge_db.READ_KEYS), ranked by how many commanders
use them. Cosmetic keys (descriptions, AI hints, prompts) are skipped. The top of the list = the next gaps to close,
found before a user hits a misbuilt deck.   Usage: python tests/audit_commanders.py [data/cards.json]"""
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, "src")
import forge_db as F
from common import load_cards

COSMETIC = {"TriggerDescription", "SpellDescription", "Description", "StackDescription", "AILogic", "AIPreference",
            "ChoiceTitle", "PrecostDesc", "CostDesc", "Secondary", "AITgts", "AiAttackController", "IsCurse",
            "SpellDescription", "ActivationLimit", "PlayerTurn", "AnyPlayer", "TgtPrompt", "AILifeThreshold",
            "SorcerySpeed", "Planeswalker", "Ultimate", "AIManaPref", "IsPresent", "PresentZone", "TriggerZones",
            "AffectedZone", "EffectZone", "CharacteristicDefining", "Hidden", "Static", "OptionalDecider",
            "RememberObjects", "RememberChosen", "RememberTokens", "RememberCostCards", "ClearRemembered",
            "SubAbility", "Execute", "DB", "AB", "SP", "Mode", "Cost",
            # bookkeeping: how Forge tracks objects / targets, not what the card does for a deck
            "RememberChanged", "ForgetOnMoved", "ExileOnMoved", "ValidTgtsDesc", "TargetMin", "TargetMax",
            "LibraryPosition", "MayChooseTarget", "TokenTapped", "Choices", "Optional", "TgtZone", "Imprint",
            "RememberDiscarded", "RememberLKI", "ImprintCards", "Chooser", "NoReveal", "Shuffle", "StackDescription$"}


def main(path="data/cards.json"):
    idx = load_cards(path)
    cmds = [c for c in {id(v): v for v in idx.values()}.values() if c.get("can_be_commander")]
    by, read, reviewed = defaultdict(set), defaultdict(set), defaultdict(set)
    scripted = 0
    for c in cmds:
        rec = F.get(c)
        if not rec:
            continue
        scripted += 1
        for prm in F.expand(rec)["params"]:         # every part of the script, nested effects included
            for k in prm:
                if k.startswith("_") or k in COSMETIC or F.cosmetic(k):
                    continue
                if k in F.READ_KEYS:
                    read[k].add(c["name"])
                elif k in F.REVIEWED:
                    reviewed[k].add(c["name"])
                else:
                    by[k].add(c["name"])
    print(f"{scripted}/{len(cmds)} commanders have a Forge script")
    print(f"{len(read)} parameters read by the builder; {len(reviewed)} checked and marked as bookkeeping "
          f"(no effect on which cards belong in the deck)")
    print(f"Parameters the builder doesn't read yet ({len(by)}), by number of commanders that use them:\n")
    for k, names in sorted(by.items(), key=lambda kv: -len(kv[1]))[:500]:
        ex = ", ".join(sorted(names)[:3])
        print(f"{len(names):5}  {k:28} e.g. {ex}")


if __name__ == "__main__":
    main(*(sys.argv[1:2]))
