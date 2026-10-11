"""Card logic from Forge (github.com/Card-Forge/forge, GPL-3.0): every card already translated by Forge's community
into structured game logic that follows Magic's Comprehensive Rules.

Why: English rules text has endless wordings for the same thing ("toughness greater than its power",
"power less than toughness"...). Forge collapses every wording into one vocabulary:
  triggers   T:Mode$ Attacks | ValidCard$ Creature.YouCtrl            ("whenever a creature you control attacks")
  filters    Creature.YouCtrl+powerLE2, Creature.powerLTtoughness, Card.Vampire+Other, Instant,Sorcery
  effects    DB$ DamageAll | ValidPlayers$ Player.Opponent              ("deals X damage to each opponent")
  counts     SVar:X:Count$Valid Creature.YouCtrl+powerLE2               (what an X counts)
  statics    S:Mode$ Continuous | Affected$ Elf.Other+YouCtrl | AddPower$ 1
  hints      DeckHints:Type$Vampire, DeckHas:Ability$Token, SVar:BuffedBy:Vampire (Forge's own deck-building hints)
This module reads those scripts (downloaded weekly by the workflow, never stored in the repo), evaluates Forge
filters against any card, and extracts the FACTS the builder needs: what a card counts, what it rewards, what it
wins with, what it needs. Unknown filter words are ignored (logged), so a filter can only be too lenient, never crash.
Credit: card logic from the Forge project (github.com/Card-Forge/forge)."""
import json
import os
import re

DATA_DIR = "data"
_DB = {"by_name": None, "dir": None}
FORMAT = 2              # bump when parse() changes, so old data/forge_db.json caches are rebuilt


def configure(data_dir):
    """Point at the data folder (common.load_cards calls this with the folder of cards.json)."""
    global DATA_DIR
    if data_dir != DATA_DIR:
        DATA_DIR = data_dir
        _DB["by_name"] = None


def _dirs():
    return [os.path.join(DATA_DIR, d) for d in ("forge/forge-gui/res/cardsfolder", "forge/cardsfolder", "forge")]
UNKNOWN_PROPS = {}
# script parameters the builder reads (tests/audit_commanders.py lists the ones it doesn't, ranked by use)
READ_KEYS = {"Mode", "ValidCard", "ValidSource", "ValidTarget", "CombatDamage", "Execute", "Destination", "Origin",
             "Affected", "AddPower", "AddToughness", "AddKeyword", "AddAbility", "Activator", "Amount", "Type",
             "Cost", "SubAbility", "Defined", "TokenOwner", "Placer", "DefinedPlayer", "ValidTgts", "ValidPlayers",
             "ValidCards", "CounterType", "CounterNum", "NumAtt", "NumDef", "TokenScript", "TokenAmount",
             "ExtraPhase", "NumDmg", "LifeAmount", "NumCards", "Phase", "ValidPlayer", "ValidActivatingPlayer",
             "IsPresent", "PresentCompare", "PresentZone", "ConditionPresent", "ConditionCompare", "CheckSVar",
             "SVarCompare", "ConditionCheckSVar", "ConditionSVarCompare", "Condition", "Duration", "ConditionDefined",
             "ConditionZone",
             # deck_facts(): what it fetches, digs for, casts, copies, doubles, steals, sacrifices, grants...
             "ChangeType", "ChangeNum", "DestinationZone", "DigNum", "ChangeValid", "Valid", "ValidSA", "KW",
             "StaticAbilities", "AddStaticAbilities", "Triggers", "AddTrigger", "AddTriggers", "ReplacementEffects",
             "AddReplacementEffects", "AffectedDefined", "Produced", "MayPlay", "WithoutManaCost", "MayPlayWithoutManaCost",
             "AttackingPlayer", "ValidAttackers", "ValidAttacker", "ValidCreature", "DamageSource", "ValidCause", "SacValid",
             "LoseControl", "SetPower", "SetToughness", "AddType", "AddTypes", "Types", "AddAllCreatureTypes",
             "AddKeywords", "Keywords", "PumpKeywords", "TokenPower", "TokenToughness", "TokenAttacking", "TokenTapped",
             "WithCountersType", "UnlessCost", "UnlessPayer", "RepeatSubAbility", "TrueSubAbility", "FalseSubAbility",
             "ChooseSubAbility", "FallbackAbility", "Choices", "Alone", "AtEOT", "FoundDestination", "ReplaceWith",
             "Event", "ValidToken", "ActivatorThisTurnCast", "SetMaxHandSize", "ValidZone", "AffectedZone",
             "WinSubAbility", "LoseSubAbility", "TailsSubAbility", "ReturnAbility", "VoteTiedAbility",
             "ExtraPhaseDelayedTriggerExcute", "ExtraTurnDelayedTriggerExecute", "UnlessResolveSubs", "staticAbilities",
             "AddStaticAbility", "AddReplacementEffect", "Replacements", "Trigger", "Abilities", "AddAbilities",
             "ResultSubAbilities", "Threshold", "Delirium", "Revolt", "ConditionPresent2", "ConditionCompare2",
             "IsPresent2", "PresentCompare2", "ValidAttackersAmount", "Populate", "DiscardValid", "Goad", "AddKWs",
             "KWChoice", "GainsAbilitiesOf", "GainsAbilitiesOfDefined", "GainsAbilitiesOfZones", "GainsTriggerAbsOf",
             "AdjustLandPlays", "RaiseCost", "ValidSpell", "ValidLKI", "ValidObject", "MayPlayIgnoreColor",
             "MayPlayAltManaCost", "MayPlayWithFlash", "MayPlayPlayer", "PlayReduceCost", "MayPlayDontGrantZonePermissions"}

_COSMETIC = re.compile(r"(?:Desc|Description|Prompt|Title|Message|Text)$|^(?:AI|Remember|Forget|Clear|Imprint|Stack|"
                       r"Spell(?:Description)?$|Choice(?:Title|Prompt))")


def cosmetic(k):
    """Text shown to the player, AI hints, and Forge's memory of objects: never about deck building."""
    return bool(_COSMETIC.search(k))


# parameters checked by hand and found to change nothing about which cards belong in the deck: how Forge tracks
# objects, chooses, reveals, orders, names or targets things, or the stats of a card that animates ITSELF.
# The audit lists them separately so real gaps stay visible.
REVIEWED = {
    "Tapped", "RestRandomOrder", "Mandatory", "ETB", "Power", "Toughness", "ClearImprinted", "ActivationZone",
    "Controller", "RestrictValid", "DestinationZone2", "RevealedDestination", "Reveal", "Transformed",
    "ValidDescription", "VarName", "Number", "Caster", "PowerUp", "VarValue", "ChoiceZone", "Attacking", "RemoveType",
    "ValidBlocker", "MayLookAt", "RememberRevealed", "MayPlayLimit", "NewController", "AttackedTarget",
    "ShuffleNonMandatory", "TargetType", "Object", "SelectPrompt", "ForgetOtherRemembered", "NoResolvingCheck",
    "ClearChosenCard", "RepeatPlayers", "BranchConditionSVar", "BranchConditionSVarCompare", "RememberMilled",
    "ForceRevealToController", "NonLegendary", "PumpZone", "ResolvedLimit", "ExileFaceDown", "MinCharmNum", "CharmNum",
    "RememberFound", "AttachedTo", "ValidMode", "RandomOrder", "AfterPhase", "NewName", "PeekAmount", "UnlessSwitched",
    "DividedAsYouChoose", "ActivationPhases", "StaticEffect", "ReplaceGraveyard", "ReplaceGraveyardValid", "CopyCard",
    "Attacked", "Attributes", "LibraryPosition2", "WithCountersAmount", "ChoiceRestriction", "WithMayLook",
    "RememberSacrificed", "EffectOwner", "TargetUnique", "Num", "ScryNum", "TargetsValid", "GainControl", "Num",
    "PumpDuration", "Colors", "OverwriteColors", "RemoveCreatureTypes", "ReplacementResult", "ActiveZones",
    "MayPlayIgnoreType", "ManaConversion", "Destroy", "Description", "IsPresent", "PresentDefined",
    # the rare tail (used by 1-37 commanders each): targeting details, ordering, voting, coin flips, naming, colors,
    # one-off mechanics. Each was looked at; none changes which cards the deck wants.
    "Activation", "ActivationFirstCombat", "ActivatorThisTurnCastEach", "Adapt", "AddColors", "AddHiddenKeyword",
    "AddSVar", "AddSVars", "AdditionalActivationZone", "AdditionalOptionalVote", "AdditionalVillainousChoice",
    "AfterReplacement", "AllValid", "AlreadyRevealed", "AlternateCost", "AlternativeDecider", "AlwaysRemember",
    "AlwaysReplace", "AmountFromVotes", "Announce", "AnnounceMax", "AnyNumber", "AtEOTCondition",
    "AtLeastOneInstance", "AtRandom", "AttachedToPlayer", "Attacker", "Boast", "Bolster", "CalcKeywordN",
    "CantCopy", "ChangeController", "ChangeZoneTable", "CheckDefinedPlayer", "CheckOnTriggeredCard", "ChoiceNum",
    "ChoiceOptional", "ChooseCounter", "ChooseFromDefined", "ChooseFromList", "ChosenPile", "CloneTarget", "Color",
    "ColorOrType", "ConditionFirstCombat", "ConditionNotPresent", "ConditionPhases", "ConditionPlayerContains",
    "ConditionPlayerDefined", "ConditionPlayerTurn", "ConniveNum", "CopyForEachCanTarget", "CopyFromChosenName",
    "CounterAmount", "CounterMapValues", "CounterNum2", "CounterNumPerDefined", "CounterNumShared", "CounterType2",
    "CounterTypes", "DamageAmount", "DamageMap", "DamageTarget", "DayTime", "DeclaresBlockers",
    "DefenderNotNearestToYouInChosenDirection", "DefinedAttacker", "DefinedBlocker", "DefinedCards",
    "DefinedDamagers", "DefinedExiler", "DefinedKW", "DefinedName", "DefinedPiles", "DefinedTarget",
    "DelayedTriggerDefinedPlayer", "DescriptionFromChosenName", "DestZone2Optional", "DestinationAlternative",
    "DifferentNames", "DividedUpTo", "EachFromSource", "EachVote", "EnduringStory", "ExcessSVar",
    "ExcessSVarCondition", "ExcludeChosen", "ExcludeDestination", "ExcludedDestinations", "ExecuteMode", "Exhaust",
    "ExileWithCounters", "Expression", "ExtraPhaseDelayedTrigger", "ExtraTurnDelayedTrigger", "FaceDown",
    "FaceDownPower", "FaceDownSetType", "FaceDownToughness", "FirstAttack", "FirstCardInDrawStep", "FirstCombat",
    "FirstExtraCardDrawnThisTurn", "FirstForetell", "FirstTime", "Fizzle", "FlipUntilYouLose", "ForCost",
    "ForEachColorPair", "ForReveal", "ForceReveal", "GainThisAbility", "Gains", "GainsAbilitiesLimitPerTurn",
    "GainsValidAbilities", "GameActivationLimit", "HasXManaCost", "Highest", "IgnoreFreeze", "IgnoreGeneric",
    "Image", "InvertValidSource", "IsCombat", "IsSingleTarget", "KeywordDefined", "Layer", "LeaveBattlefield",
    "LethalDamageByPower", "LibraryPositionAlternative", "LifeTotal", "List", "LockTokenScript", "Look",
    "ManaType", "Max", "MaxAttackers", "MaxBlockers", "MaxNum", "MaxRepeat", "MaxTotalTargetCMC",
    "MaxTotalTargetPower", "Min", "MinAmount", "MinLimit", "MinMana", "Monstrosity", "MustAttack", "Name",
    "NewCounterAmount", "NextTurnForEachPlayer", "NoCall", "NoMoveRevealed", "NoPeek", "NoRegen", "NoShuffle",
    "NonZero", "NotFirstCardInDrawStep", "NotThisAbility", "NoteCards", "NoteCardsFor", "NumCopies", "NumPhases",
    "NumTurns", "OneOff", "OnlyFirst", "OnlyFirstSpell", "OnlySorcerySpeed", "OpponentTurn", "OriginAlternative",
    "PersistentMana", "PhaseCount", "Phases", "PlayCost", "Player", "PlayerChoices", "PresentPlayer", "Prevent",
    "PreventionEffect", "Primary", "RaiseMaxHandSize", "Random", "RandomCompare", "RandomCompareSVar",
    "ReduceCost", "ReflectProperty", "Relative", "RemoveAllAbilities", "RemoveCardTypes", "RemoveKeyword",
    "RemoveKeywords", "RemoveLandTypes", "RemoveSubTypes", "Reorder", "RepeatCards", "RepeatCheckSVar",
    "RepeatCompare", "RepeatDefined", "RepeatOptional", "RepeatOptionalForEachPlayer", "RepeatPresent",
    "RepeatSVarCompare", "RepeatTypesFrom", "ReplaceDyingDefined", "ReplaceType", "Result", "ReturnValid",
    "RevealDefined", "RevealNumber", "RevealOptional", "RevealRandomOrder", "RevealValid",
    "RevealedLibraryPosition", "ST", "SVar", "SearchOwnLibrary", "SecondaryType", "Secretly", "Separator",
    "SetChosenNumber", "SetColor", "SetCreatureTypes", "SharedKeywords", "SharedKeywordsDefined",
    "SharedKeywordsZone", "SharedRestrictions", "ShowChoice", "Sides", "Skip", "SkipReorder", "Source",
    "SourceZone", "Step", "StoreVoteNum", "Target", "TargetRelativeToCause", "TargetRelativeToSource",
    "TargetingPlayer", "TargetsAtRandom", "TargetsForEachPlayer", "TargetsWithDefinedController",
    "TargetsWithDifferentControllers", "Teamwork", "TempRemember", "ThisDefinedAndTgts", "ThisTurn", "Times",
    "TokenBlocking", "TokenRemembered", "TriggerAmount", "TriggerController", "TriggeredCounterMap",
    "TriggersWhenSpent", "UnchosenPile", "Unique", "UnlessDefender", "UnlessType", "UnlessValidTarget", "Untap",
    "UntapExactly", "UntapType", "UpTo", "UseAllOriginZones", "UseImprinted", "ValidActivator", "ValidAfterStack",
    "ValidAmountEach", "ValidBlocked", "ValidBlockerAmount", "ValidChoices", "ValidCounterType", "ValidDefender",
    "ValidEntity", "ValidExplored", "ValidKeyword", "ValidOriginalController", "ValidResult", "ValidSAonCard",
    "ValidSpellAbility", "ValidStepTurnToController", "ValidTypes", "Value", "VarType", "VotePlayer",
    "WerewolfTransformCondition", "WithDifferentPowers", "WithTotalCMC", "WithTotalCardTypes", "Won",
    "XAlternative", "XColor", "XMax", "XMin", "Zone", "cmcGT",
}

# ------------------------------------------------------------------------------------------------ parsing
def _params(s):
    out = {}
    for part in s.split("|"):
        part = part.strip()
        if "$" in part:
            k, v = part.split("$", 1)
            out[k.strip()] = v.strip()
    return out


def parse(text):
    rec = dict(name=None, types="", pt=None, keywords=[], triggers=[], statics=[], abilities=[], replacements=[],
               svars={}, hints={}, oracle="", faces=[])
    cur = rec
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("ALTERNATE") or line == "ALTERNATE":
            face = dict(name=None, types="", pt=None, keywords=[], triggers=[], statics=[], abilities=[],
                        replacements=[], svars={}, hints={}, oracle="")
            rec["faces"].append(face)
            cur = face
            continue
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        if key == "Name":
            cur["name"] = val
        elif key == "Types":
            cur["types"] = val
        elif key == "PT":
            cur["pt"] = val
        elif key == "K":
            cur["keywords"].append(val)
        elif key == "T":
            cur["triggers"].append(_params(val))
        elif key == "S":
            cur["statics"].append(_params(val))
        elif key == "A":
            cur["abilities"].append(_params(val))
        elif key == "R":
            cur["replacements"].append(_params(val))
        elif key == "SVar":
            if ":" in val:
                n, v = val.split(":", 1)
                cur["svars"][n] = v
        elif key in ("DeckHints", "DeckHas", "DeckNeeds"):
            cur["hints"][key] = val
        elif key == "Oracle":
            cur["oracle"] = val
    for n in ("BuffedBy", "BuffedByStr"):
        if n in rec["svars"]:
            rec["hints"]["BuffedBy"] = rec["svars"][n]
    return rec


def load(dirs=None, cache=None):
    """{lowercase card name: record}. Uses a JSON cache next to the scripts when it's newer than the folder."""
    if _DB["by_name"] is not None:
        return _DB["by_name"]
    dirs = dirs or _dirs()
    cache = cache or os.path.join(DATA_DIR, "forge_db.json")
    root = next((d for d in dirs if os.path.isdir(d)), None)
    by = {}
    if root:
        try:
            if os.path.exists(cache) and os.path.getmtime(cache) >= os.path.getmtime(root):
                by = json.load(open(cache))
                if by.get("__format__") != FORMAT:
                    by = {}
        except (OSError, ValueError):
            by = {}
        if not by:
            for dp, _, files in os.walk(root):
                for f in files:
                    if not f.endswith(".txt"):
                        continue
                    try:
                        rec = parse(open(os.path.join(dp, f), encoding="utf-8", errors="replace").read())
                    except OSError:
                        continue
                    if rec["name"]:
                        by[rec["name"].lower()] = rec
                        for face in rec["faces"]:
                            if face.get("name"):
                                by.setdefault(face["name"].lower(), rec)
            by["__format__"] = FORMAT
            try:
                json.dump(by, open(cache, "w"))
            except OSError:
                pass
    _DB["by_name"], _DB["dir"] = by, root
    return by


def get(card):
    by = load()
    n = card["name"].lower()
    r = by.get(n) or by.get(n.split(" // ")[0])
    return r if isinstance(r, dict) else None


def status():
    by = load()
    return dict(cards=len(by), dir=_DB["dir"])


# ------------------------------------------------------------------------------------------------ filters
_KW = {"withFlying": "flying", "withTrample": "trample", "withDeathtouch": "deathtouch", "withLifelink": "lifelink",
       "withDefender": "defender", "withMenace": "menace", "withHaste": "haste", "withReach": "reach",
       "withVigilance": "vigilance", "withFirst Strike": "first strike", "withDouble Strike": "double strike",
       "withHexproof": "hexproof", "withIndestructible": "indestructible", "withFlash": "flash", "withInfect": "infect"}
_COLORS = {"White": "W", "Blue": "U", "Black": "B", "Red": "R", "Green": "G"}
_STAT = re.compile(r"^(power|toughness|cmc|CMC)(LE|LT|GE|GT|EQ|NE)(\d+|power|toughness)$")
_IGNORE = {"YouCtrl", "YouOwn", "Other", "StrictlyOther", "inZoneBattlefield", "untapped", "IsCommander", "wasCastByYou",
           "wasCast", "Self", "Card", "nonToken"}          # true for "a card you'd put in your deck" (or not checkable)
_TYPE_WORDS = {"Card", "Permanent", "Creature", "Artifact", "Enchantment", "Land", "Planeswalker", "Instant", "Sorcery",
               "Battle", "Spell", "Legendary", "Equipment", "Aura", "Vehicle", "Token", "Historic"}


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _prop_ok(p, card):
    if p in _IGNORE or p.startswith("YouCtrl$"):
        return True
    tl = card.get("type_line") or ""
    text = (card.get("text") or "").lower()
    m = _STAT.match(p)
    if m:
        stat, op, rhs = m.groups()
        val = {"power": _num(card.get("power")), "toughness": _num(card.get("toughness")),
               "cmc": _num(card.get("cmc")), "CMC": _num(card.get("cmc"))}[stat]
        other = {"power": _num(card.get("power")), "toughness": _num(card.get("toughness"))}.get(rhs, _num(rhs))
        if val is None or other is None:
            return False
        return {"LE": val <= other, "LT": val < other, "GE": val >= other, "GT": val > other, "EQ": val == other,
                "NE": val != other}[op]
    if p in _KW:
        kws = {k.lower() for k in card.get("keywords") or []}
        return _KW[p] in kws or bool(re.search(r"(?:^|\n|, )%s\b" % _KW[p], text))
    if p.startswith("without") and ("with" + p[7:]) in _KW:
        return not _prop_ok("with" + p[7:], card)
    if p in _COLORS:
        return _COLORS[p] in (card.get("colors") or card.get("identity") or [])
    if p == "Colorless":
        return not (card.get("colors") or [])
    if p == "MultiColor":
        return len(card.get("colors") or card.get("identity") or []) >= 2
    if p.startswith("non") and len(p) > 3:
        return not _type_ok(p[3:], card)
    if p in ("token",):
        return False
    if p in ("Legendary", "Historic"):
        return "Legendary" in tl or (p == "Historic" and ("Artifact" in tl or "Saga" in tl))
    if p[:1].isupper() and p.isalpha():
        return _type_ok(p, card)
    UNKNOWN_PROPS[p] = UNKNOWN_PROPS.get(p, 0) + 1
    return True                                    # unknown: lenient


def _type_ok(word, card):
    tl = card.get("type_line") or ""
    if word in ("Card", "Spell"):
        return "Land" not in tl.split("//")[0] if word == "Spell" else True
    if word == "Permanent":
        return not re.search(r"\b(?:Instant|Sorcery)\b", tl)
    if word == "Historic":
        return bool(re.search(r"\b(?:Legendary|Artifact|Saga)\b", tl))
    if re.search(r"\b%s\b" % re.escape(word), tl):
        return True
    return word not in _TYPE_WORDS and "changeling" in (card.get("text") or "").lower() and "Creature" in tl


def matches(flt, card):
    """Does `card` satisfy a Forge filter like 'Creature.YouCtrl+powerLE2' or 'Instant,Sorcery'?"""
    for alt in (flt or "").split(","):
        alt = alt.strip()
        if not alt:
            continue
        base, _, props = alt.partition(".")
        base = base.lstrip("!")
        if base and not _type_ok(base, card):
            continue
        if all(_prop_ok(p.strip(), card) for p in props.split("+") if p.strip()):
            return True
    return False


def describe_filter(flt):
    """'Creature.YouCtrl+powerLE2' -> 'creatures with power 2 or less'."""
    words = []
    for alt in flt.split(","):
        base, _, props = alt.partition(".")
        bits = []
        for p in props.split("+"):
            m = _STAT.match(p)
            if m:
                stat, op, rhs = m.groups()
                stat = "mana value" if stat.lower() == "cmc" else stat
                opw = {"LE": "or less", "LT": "less than", "GE": "or greater", "GT": "greater than", "EQ": "exactly",
                       "NE": "not"}[op]
                if rhs.isdigit():
                    bits.append(f"{stat.lower()} {rhs} {opw}" if op in ("LE", "GE") else f"{stat.lower()} {opw} {rhs}")
                else:
                    bits.append(f"{stat.lower()} {opw} {rhs}")
            elif p in _KW:
                bits.append(_KW[p])
            elif p in _COLORS or p in ("Legendary", "Historic", "Colorless", "MultiColor"):
                bits.insert(0, p.lower())
            elif p[:1].isupper() and p.isalpha() and p not in _IGNORE and p not in _TYPE_WORDS:
                bits.insert(0, p)                  # a subtype inside the props: Creature.Elf -> Elf creatures
        plural = {"Sorcery": "sorceries", "Card": "cards", "Permanent": "permanents"}
        noun = plural.get(base, (base.lower() if base in _TYPE_WORDS else base) + "s")
        adj = " ".join(b for b in bits if " " not in b)
        withs = [b for b in bits if " " in b]
        words.append((adj + " " if adj else "") + noun + (" with " + " and ".join(withs) if withs else ""))
    return " or ".join(words)


def has_stat_props(flt):
    return any(_STAT.match(p) or p in _KW for alt in flt.split(",") for p in alt.partition(".")[2].split("+"))


# ------------------------------------------------------------------------------------------------ facts
_EVENT = {"Attacks": "attacks", "AttackersDeclared": "attacks", "SpellCast": "cast", "DamageDone": "damage",
          "DamageDoneOnce": "damage", "Phase": "phase", "Drawn": "draw", "LifeGained": "gain_life",
          "Sacrificed": "sacrifice", "Discarded": "discard", "LandPlayed": "land_enters", "CounterAddedOnce": "counters_put",
          "CounterAdded": "counters_put", "Taps": "becomes_tapped", "Blocks": "blocks", "Cycled": "cycle",
          "TokenCreated": "token_enters", "LifeLost": "opponent_loses_life"}


def _effects(rec, start):
    """Follow an Execute$/ability chain (SubAbility$) and return [(api, params)]."""
    out, seen, cur = [], set(), start
    while cur and cur not in seen:
        seen.add(cur)
        prm = _params(cur) if "$" in cur and ("DB$" in cur or "AB$" in cur or "SP$" in cur) else None
        if prm is None:
            v = rec["svars"].get(cur)
            if not v:
                break
            prm = _params(v)
        api = prm.get("DB") or prm.get("AB") or prm.get("SP")
        if api:
            out.append((api, prm))
        cur = prm.get("SubAbility")
    return out


def facts(card):
    """What a card DOES, in the builder's terms, read from its Forge script. None if Forge has no script."""
    rec = get(card)
    if not rec:
        return None
    events, wins, counts, buffs, needs, outputs = [], [], [], [], [], []
    for t in rec["triggers"]:
        if t.get("Secondary") == "True":
            continue
        mode = t.get("Mode", "")
        ev = _EVENT.get(mode)
        if mode == "ChangesZone":
            if t.get("Destination") == "Battlefield":
                ev = "enters"
            elif t.get("Origin") == "Battlefield" and t.get("Destination") == "Graveyard":
                ev = "dies"
        effs = _effects(rec, t.get("Execute"))
        if mode == "AttackersDeclared" and t.get("AttackingPlayer") == "You":
            ev = "attacks"
        events.append(dict(event=ev or mode, filter=t.get("ValidCard") or t.get("ValidSource") or t.get("ValidSA") or
                           t.get("ValidAttackers") or t.get("ValidAttacker") or t.get("ValidCreature") or
                           t.get("DamageSource") or t.get("ValidCause") or t.get("ValidSpell") or t.get("ValidLKI") or
                           t.get("ValidObject") or t.get("Valid") or "",
                           desc=t.get("TriggerDescription", ""), effects=[a for a, _ in effs]))
        outputs += effs
    for a in rec["abilities"]:
        effs = _effects(rec, None) or []
        api = a.get("AB") or a.get("SP")
        if api:
            effs = [(api, a)] + _effects(rec, a.get("SubAbility"))
        outputs += effs
        cost = a.get("Cost", "")
        m = re.search(r"tapXType<(\d+)/([A-Za-z.+]+)>", cost)
        if m:
            needs.append(dict(count=int(m.group(1)), filter=m.group(2), text=f"tap {m.group(1)} untapped {m.group(2)}"))
        m = re.search(r"Sac<(\d+)/([A-Za-z.+]+)>", cost)
        if m:
            needs.append(dict(count=int(m.group(1)), filter=m.group(2), text=f"sacrifice {m.group(2)}", sac=True))
    x = expand(rec)
    outputs = [(api, prm) for api, prm, _ in x["effects"]]     # every effect, nested ones included
    gifts, own = [], []
    for api, prm in outputs:
        if api in ("Draw", "Token", "PutCounter", "PutCounterAll", "GainLife", "Mana", "ChangeZone", "Pump"):
            who = prm.get("Defined") or prm.get("TokenOwner") or prm.get("Placer") or prm.get("DefinedPlayer") or ""
            if not who and re.search(r"Opponent|Player", prm.get("ValidTgts", "")):
                who = prm["ValidTgts"]              # "target opponent gains 2 life"
            who = who or "You"
            if re.search(r"Chosen|Targeted|Player|Opp|Each", who) and not re.search(r"\bYou\b|^Self", who):
                gifts.append(api)               # it goes to ANOTHER player (a gift), not to you
            else:
                own.append(api)
    for api, prm in outputs:
        if api in ("DamageAll", "DealDamage") and "Opponent" in (prm.get("ValidPlayers", "") + prm.get("Defined", "")):
            wins.append("damages every opponent")
        elif api == "LoseLife" and "Opponent" in prm.get("Defined", ""):
            wins.append("drains the table")
        elif api == "WinsGame":
            wins.append("wins the game outright")
        elif api == "AddPhase" and "Combat" in prm.get("ExtraPhase", "Combat"):
            wins.append("takes extra combats")
        elif api == "PumpAll" and "YouCtrl" in prm.get("ValidCards", "") and _num(re.sub(r"[^0-9]", "", prm.get("NumAtt", "")) or 0) and \
                (_num(re.sub(r"[^0-9]", "", prm.get("NumAtt", "0"))) or 0) >= 2:
            wins.append("pumps the whole team (overrun)")
        if api in ("PutCounterAll", "PumpAll") and prm.get("ValidCards") and "Self" not in prm.get("ValidCards"):
            # Pump effects last until end of turn unless Forge says otherwise; counters are permanent
            temp = api == "PumpAll" and prm.get("Duration", "EOT") not in ("Permanent", "Perpetual")
            buffs.append(dict(filter=prm["ValidCards"], how=api, temporary=temp))
    for s in x["statics"]:
        mode = s.get("Mode")
        if mode == "Continuous" and s.get("Affected") and "Self" not in s.get("Affected") and \
                "IsRemembered" not in s.get("Affected") and \
                (s.get("AddPower") or s.get("AddToughness") or s.get("AddKeyword") or s.get("AddAbility")):
            buffs.append(dict(filter=s["Affected"], how="static", temporary=s.get("_temp", False)))
        if mode == "ReduceCost" and s.get("ValidCard") and s.get("Activator", "You") == "You":
            buffs.append(dict(filter=s["ValidCard"], how="cost"))
    for n, v in rec["svars"].items():
        m = re.match(r"Count\$Valid (\S+)", v)
        if m and "YouCtrl" in m.group(1):
            counts.append(m.group(1))
    hints = rec.get("hints", {})
    if hints.get("BuffedBy"):
        for t in hints["BuffedBy"].split(","):
            buffs.append(dict(filter=t.strip() + ".YouCtrl", how="hint"))
    deck_types = []
    for part in (hints.get("DeckHints", "") + "&" + hints.get("DeckNeeds", "")).split("&"):
        m = re.match(r"\s*Type\$(.+)", part)
        if m:
            deck_types += [x.strip() for x in m.group(1).split("|") if x.strip()]
    reqs = requirements(rec)
    more = deck_facts(rec)
    return dict(more, events=events, wins=sorted(set(wins)), counts=counts, buffs=buffs, needs=needs, gifts=gifts, own=own,
                requirements=reqs,
                apis=sorted({a for a, _ in outputs}), deck_types=deck_types, hints=hints,
                keywords=rec["keywords"])


def to_conditions(flt, strong=True):
    """Convert a Forge filter into the builder's condition records (conditions.py), so everything downstream
    (scoring, caps, anthems, the simulator) works the same whichever source the condition came from."""
    out = []
    for alt in flt.split(","):
        base, _, props = alt.partition(".")
        typ = "creature" if base in ("Creature", "Card", "Permanent") or base not in _TYPE_WORDS else base.lower()
        for p in props.split("+"):
            m = _STAT.match(p)
            if m:
                stat, op, rhs = m.groups()
                stat = "mana value" if stat.lower() == "cmc" else stat.lower()
                text = describe_filter(alt)
                if rhs in ("power", "toughness"):
                    hi = rhs if op in ("LT", "LE") else stat          # powerLTtoughness -> toughness is bigger
                    out.append(dict(kind="compare", type="creature", stat=hi, op="gt", n=None, keyword=None, text=text,
                                    counts=strong, strong=strong, source="forge"))
                else:
                    n = int(rhs)
                    o, n = {"LE": ("le", n), "LT": ("le", n - 1), "GE": ("ge", n), "GT": ("ge", n + 1)}.get(op, (None, n))
                    if o:
                        out.append(dict(kind="stat", type=typ, stat=stat, op=o, n=n, keyword=None, text=text,
                                        counts=strong, strong=strong, source="forge"))
            elif p in _KW:
                out.append(dict(kind="keyword", type="creature", stat=None, op=None, n=None, keyword=_KW[p],
                                text=describe_filter(alt), counts=strong, strong=strong, source="forge"))
    return out


def subtype_of(flt):
    """'Goblin.YouCtrl' -> 'Goblin'; 'Creature.Legendary+YouCtrl' -> 'Legendary'; None for plain card types."""
    base, _, props = flt.split(",")[0].partition(".")
    if base and base not in _TYPE_WORDS:
        return base
    for p in props.split("+"):
        if p in ("Legendary", "Historic") or (p[:1].isupper() and p.isalpha() and p not in _TYPE_WORDS
                                                  and p not in _IGNORE and p not in _COLORS and p not in ("Colorless", "MultiColor")):
            return p
    return None


# ------------------------------------------------------------------------------------------------ conditions & duration
_ABILITY_WORDS = {   # Forge's named conditions -> what the deck has to set up
    "Threshold": dict(zone="Graveyard", filter="Card", count=7, text="threshold (7+ cards in your graveyard)"),
    "Delirium": dict(zone="Graveyard", filter="Card", count=4, text="delirium (4+ card types in your graveyard)"),
    "Metalcraft": dict(zone="Battlefield", filter="Artifact.YouCtrl", count=3, text="metalcraft (3+ artifacts)"),
    "Hellbent": dict(zone="Hand", filter="Card", count=0, text="hellbent (no cards in hand)"),
    "Ferocious": dict(zone="Battlefield", filter="Creature.YouCtrl+powerGE4", count=1, text="ferocious (a creature with power 4+)"),
}
_CMP = re.compile(r"^(GE|GT|EQ|LE|LT)(\d+)$")


def _req(flt, zone, cmp_, text=""):
    m = _CMP.match(cmp_ or "GE1")
    if not m:
        return None
    op, n = m.group(1), int(m.group(2))
    if op in ("LE", "LT") or (op == "EQ" and n == 0):
        return None                                   # "as long as you have no..." isn't something to build toward
    n = n + 1 if op == "GT" else n
    return dict(zone=zone or "Battlefield", filter=flt, count=n,
                text=text or f"{n}+ {describe_filter(flt).lower()} {'in your graveyard' if zone == 'Graveyard' else ''}".strip())


def requirements(rec):
    """Conditions the card's abilities need ("as long as you control three or more artifacts", threshold,
    "if there are four or more permanent cards in your graveyard"): [{zone, filter, count, text}]."""
    out = []
    parts = expand(rec)["params"]
    for prm in parts:
        if prm.get("IsPresent") and prm.get("PresentCompare") and "Self" not in prm["IsPresent"]:
            r = _req(prm["IsPresent"], prm.get("PresentZone"), prm["PresentCompare"])
            if r:
                out.append(r)
        if prm.get("ConditionPresent") and not prm.get("ConditionDefined") and prm.get("ConditionCompare"):
            r = _req(prm["ConditionPresent"], prm.get("ConditionZone"), prm["ConditionCompare"])
            if r:
                out.append(r)
        for key, cmpk in (("CheckSVar", "SVarCompare"), ("ConditionCheckSVar", "ConditionSVarCompare")):
            if prm.get(key) and prm.get(cmpk):
                v = rec["svars"].get(prm[key], "")
                m = re.match(r"Count\$Valid (\S+)", v)
                if m and "YouCtrl" in m.group(1):
                    r = _req(m.group(1), "Battlefield", prm[cmpk])
                    if r:
                        out.append(r)
                elif re.match(r"Count\$(?:ValidGraveyard|InYourYard|CardsInYourGraveyard)", v):
                    r = _req("Card", "Graveyard", prm[cmpk], "")
                    if r:
                        out.append(r)
        c = prm.get("Condition")
        if c in _ABILITY_WORDS:
            out.append(dict(_ABILITY_WORDS[c]))
        for word in ("Threshold", "Delirium", "Metalcraft", "Hellbent"):
            if prm.get(word) == "True":                 # Delirium$ True on a trigger
                out.append(dict(_ABILITY_WORDS[word]))
        if prm.get("ConditionPresent2") and prm.get("ConditionCompare2"):
            r = _req(prm["ConditionPresent2"], prm.get("ConditionZone2"), prm["ConditionCompare2"])
            if r:
                out.append(r)
        if prm.get("IsPresent2") and prm.get("PresentCompare2"):
            r = _req(prm["IsPresent2"], prm.get("PresentZone2"), prm["PresentCompare2"])
            if r:
                out.append(r)
        if prm.get("ValidAttackersAmount") and prm.get("Mode") == "AttackersDeclared":
            flt = (prm.get("ValidAttackers") or "Creature").split(".")[0] + ".YouCtrl" + \
                ("+" + prm["ValidAttackers"].split(".", 1)[1] if "." in prm.get("ValidAttackers", "") else "")
            r = _req(flt, "Battlefield", prm["ValidAttackersAmount"],
                     f"attacking with {_CMP.match(prm['ValidAttackersAmount']).group(2) if _CMP.match(prm['ValidAttackersAmount']) else 'several'}+ "
                     f"{describe_filter(prm.get('ValidAttackers') or 'Creature').lower()}")
            if r:
                out.append(r)
    seen, uniq = set(), []
    for r in out:
        k = (r["zone"], r["filter"], r["count"])
        if k not in seen and r["count"] >= 1:
            seen.add(k)
            uniq.append(r)
    return uniq


def team_pump(card):
    """'permanent' if the card permanently makes your whole team bigger (anthem, counters on each creature), 'temporary'
    for until-end-of-turn pumps, None otherwise. Read from Forge, so the wording doesn't matter."""
    rec = get(card)
    if not rec:
        return None
    kind = None
    x = expand(rec)
    for st in x["statics"]:
        if st.get("Mode") == "Continuous" and "YouCtrl" in st.get("Affected", "") and "Creature" in st.get("Affected", "") \
                and re.match(r"\+?[1-9X]", st.get("AddPower", "") or "0") and not st.get("Condition"):
            if not st.get("_temp"):
                return "permanent"
            kind = kind or "temporary"
    for api, prm, temp in x["effects"]:
        if api == "PutCounterAll" and "YouCtrl" in prm.get("ValidCards", "") and prm.get("CounterType") == "P1P1":
            return "permanent"
        if api == "PumpAll" and "YouCtrl" in prm.get("ValidCards", "") and re.match(r"\+?[1-9X]", prm.get("NumAtt", "") or "0"):
            kind = "permanent" if prm.get("Duration") in ("Permanent", "Perpetual") else (kind or "temporary")
    if kind:
        return kind
    for v in list(rec["svars"].values()) + [""]:
        prm = _params(v) if "$" in v else {}
        api = prm.get("DB") or prm.get("AB") or prm.get("SP")
        if api == "PutCounterAll" and "YouCtrl" in prm.get("ValidCards", "") and prm.get("CounterType") == "P1P1":
            return "permanent"
        if api == "PumpAll" and "YouCtrl" in prm.get("ValidCards", ""):
            kind = "permanent" if prm.get("Duration") in ("Permanent", "Perpetual") else (kind or "temporary")
    for a in rec["abilities"]:
        api = a.get("AB") or a.get("SP")
        if api == "PumpAll" and "YouCtrl" in a.get("ValidCards", ""):
            kind = "permanent" if a.get("Duration") in ("Permanent", "Perpetual") else (kind or "temporary")
        if api == "PutCounterAll" and "YouCtrl" in a.get("ValidCards", "") and a.get("CounterType") == "P1P1":
            return "permanent"
    return kind


# ------------------------------------------------------------------------------------------------ the whole script
# Effects hide inside other effects: an Effect that grants a static ability ("you may play that card"), a delayed
# trigger, a charm's modes, a repeat or a branch. expand() follows every one of those links so nothing is missed.
_FOLLOW = ("SubAbility", "RepeatSubAbility", "TrueSubAbility", "FalseSubAbility", "Execute", "ReplaceWith",
           "ChooseSubAbility", "FallbackAbility", "WinSubAbility", "LoseSubAbility", "TailsSubAbility", "ReturnAbility",
           "VoteTiedAbility", "ExtraPhaseDelayedTriggerExcute", "ExtraTurnDelayedTriggerExecute", "UnlessResolveSubs")
_NESTED = (("StaticAbilities", "statics"), ("AddStaticAbilities", "statics"), ("Triggers", "triggers"),
           ("AddTrigger", "triggers"), ("AddTriggers", "triggers"), ("ReplacementEffects", "replacements"),
           ("AddReplacementEffects", "replacements"), ("staticAbilities", "statics"), ("AddStaticAbility", "statics"),
           ("AddReplacementEffect", "replacements"), ("Replacements", "replacements"), ("Trigger", "triggers"),
           ("Abilities", "abilities"), ("AddAbilities", "abilities"), ("ResultSubAbilities", "abilities"))
_TEMP = ("Permanent", "Perpetual", "UntilHostLeavesPlay", "UntilLoseControlOfHost")
_X_CACHE = {}


def expand(rec):
    """{triggers, statics, replacements, effects: [(api, params, temporary)]} for a record, nested parts included.
    Statics and effects granted by a temporary Effect/Pump are marked temporary (they end this turn)."""
    key = id(rec)
    if key in _X_CACHE:
        return _X_CACHE[key]
    out = dict(triggers=list(rec["triggers"]), statics=[dict(st, _temp=False) for st in rec["statics"]],
               replacements=list(rec.get("replacements") or []), effects=[], params=[])
    seen = set()

    def handle(prm, temp):
        out["params"].append(prm)
        api = prm.get("DB") or prm.get("AB") or prm.get("SP")
        here = temp
        if api in ("Effect", "Animate", "Pump", "PumpAll", "AnimateAll"):
            here = prm.get("Duration", "EOT") not in _TEMP
        if api:
            out["effects"].append((api, prm, here))
        for k in _FOLLOW:
            if prm.get(k):
                walk(prm[k], temp)
        for nm in (prm.get("Choices") or "").split(","):
            if nm.strip():
                walk(nm.strip(), temp)
        for k, dest in _NESTED:
            for nm in (prm.get(k) or "").split(","):
                nm = nm.strip()
                v = rec["svars"].get(nm)
                if not v or nm in seen:
                    continue
                seen.add(nm)
                p = _params(v)
                out["params"].append(p)
                if dest == "statics":
                    out["statics"].append(dict(p, _temp=here))
                elif dest == "abilities":
                    handle(p, here)
                else:
                    out[dest].append(p)
                    walk(p.get("Execute") or p.get("ReplaceWith"), here)

    def walk(name, temp):
        if not name or not isinstance(name, str):
            return
        name = name.strip()
        if re.search(r"\b(?:DB|AB|SP)\$", name):
            handle(_params(name), temp)
            return
        if name in seen:
            return
        seen.add(name)
        v = rec["svars"].get(name)
        if v and "$" in v:
            handle(_params(v), temp)

    for t in rec["triggers"]:
        out["params"].append(t)
        walk(t.get("Execute"), False)
    for r in rec.get("replacements") or []:
        out["params"].append(r)
        walk(r.get("ReplaceWith"), False)
    for a in rec["abilities"]:
        handle(a, False)
    for st in rec["statics"]:
        out["params"].append(st)
    _X_CACHE[key] = out
    return out


def _who_other(prm):
    """True when the effect is about ANOTHER player's cards (target opponent's library, each player...)."""
    w = " ".join(prm.get(k, "") for k in ("Defined", "DefinedPlayer", "ValidTgts", "TargetType"))
    return bool(re.search(r"Opponent|Player\b|Player\.|TargetedPlayer|Targeted(?:Controller|Owner)", w)) and \
        not re.search(r"(?:^|\W)You(?:\W|$)", w)


def _clean(flt):
    """Drop bookkeeping props (IsRemembered, TopLibrary...) from a filter so it can be matched against deck cards."""
    out = []
    for alt in (flt or "").split(","):
        base, _, props = alt.strip().partition(".")
        keep = [p for p in props.split("+") if p and not re.match(
            r"^(IsRemembered|IsImprinted|TopLibrary|YouOwn|YouCtrl|OppOwn|OppCtrl|nonToken|wasCastFromExile|token|"
            r"!token|IsTriggerRemembered|ChosenType|sharesCreatureTypeWith|Other|StrictlyOther|attacking|Remembered)", p)]
        out.append(base + ("." + "+".join(keep) if keep else ""))
    return ",".join(x for x in out if x) or "Card"


def specific_filter(flt):
    """Does a filter name WHICH cards (a type other than 'card', a subtype, a stat)? 'Card' says nothing."""
    for alt in (flt or "Card").split(","):
        base, _, props = alt.partition(".")
        if base not in ("Card", "Permanent", "") or [p for p in props.split("+") if p and p not in _IGNORE]:
            return True
    return False


_TOKEN_PT = re.compile(r"_(\d+|x)_(\d+|x)_")
_DOUBLE_EVENTS = {"CreateToken": "tokens", "AddCounter": "counters", "DamageDone": "damage", "GainLife": "life gain",
                  "Draw": "card draw", "ProduceMana": "mana", "Moved": "moves", "LoseLife": "life loss"}


def deck_facts(rec):
    """Deck-building facts from every part of the script. All lists; empty when the card doesn't do that."""
    x = expand(rec)
    targets, grants, copies, doubles, steals, sac, taxes, types, mana, tokens, play_zones = ([] for _ in range(11))
    scales_mv, attacks_alone, set_pt, multi_cast, no_max_hand, extra_lands, revolt = False, False, [], 0, False, False, False
    for api, prm, temp in x["effects"]:
        if api in ("ChangeZone", "ChangeZoneAll"):
            org, dst = prm.get("Origin", ""), prm.get("Destination", "")
            flt = prm.get("ChangeType") or (prm.get("ValidTgts") if prm.get("ValidTgts") and "Opp" not in prm.get("ValidTgts") else "")
            if _who_other(prm) and org == "Library":
                continue
            kind = None
            if org.startswith("Library") and dst in ("Hand", "Battlefield") and (prm.get("ChangeType") or prm.get("Hidden")):
                kind = "tutor"
            elif org.startswith("Library") and dst == "Graveyard" and prm.get("ChangeType"):
                kind = "entomb"
            elif "Graveyard" in org and dst in ("Hand", "Battlefield", "Library") and flt:
                kind = "recur"
            elif org == "Hand" and dst == "Battlefield":
                kind = "cheat"
            if kind:
                targets.append(dict(kind=kind, filter=_clean(flt or "Card"), to=dst,
                                    num=prm.get("ChangeNum", "1"), counters=prm.get("WithCountersType")))
        elif api in ("Dig", "DigUntil", "PeekAndReveal", "RevealHand") and not _who_other(prm):
            if api == "RevealHand":
                continue
            flt = prm.get("ChangeValid") or prm.get("Valid") or "Card"
            dst = prm.get("DestinationZone") or prm.get("FoundDestination") or "Hand"
            targets.append(dict(kind="dig" if dst != "Graveyard" else "mill", filter=_clean(flt), to=dst,
                                num=prm.get("DigNum", "1")))
        elif api in ("Play", "Discover", "Cascade"):
            flt = prm.get("Valid") or prm.get("ValidSA") or "Card"
            free = prm.get("WithoutManaCost") == "True" or api in ("Discover", "Cascade")
            targets.append(dict(kind="free_cast" if free else "cast", filter=_clean(flt), to="Stack",
                                num=prm.get("Amount", "1"), zone=prm.get("ValidZone", "")))
        elif api in ("Pump", "PumpAll") and prm.get("KW"):
            who = prm.get("ValidCards") or prm.get("Defined") or prm.get("ValidTgts") or "Self"
            for kw in prm["KW"].split("&"):
                grants.append(dict(keyword=kw.strip().split(":")[0].lower(), filter=who, temporary=temp or
                                   prm.get("Duration", "EOT") not in _TEMP, team=api == "PumpAll"))
        elif api in ("CopyPermanent", "Clone"):
            who = prm.get("ValidTgts") or prm.get("Defined") or prm.get("Choices") or ""
            if "Opp" not in who:
                copies.append(dict(filter=_clean(who or "Creature"), temporary=prm.get("AtEOT") in ("Sacrifice", "Exile")
                                   or bool(prm.get("AtEOT"))))
        elif api == "MultiplyCounter":
            doubles.append("counters")
        elif api == "GainControl":
            steals.append(dict(temporary=bool(prm.get("LoseControl")), filter=prm.get("ValidTgts") or prm.get("Defined", "")))
        elif api in ("Sacrifice", "SacrificeAll"):
            who = prm.get("Defined", "You")
            flt = prm.get("SacValid") or prm.get("ValidCards") or "Creature"
            if re.search(r"Opp|Player|Targeted", who) and "You" not in who:
                sac.append(dict(own=False, filter=flt))
            elif "Self" not in flt:
                sac.append(dict(own=True, filter=_clean(flt)))
        elif api in ("Mana", "ManaReflected"):
            mana.append(prm.get("Produced") or "Any")
        elif api == "Token":
            m = _TOKEN_PT.search(prm.get("TokenScript", "") + "_")
            tokens.append(dict(script=prm.get("TokenScript", ""), power=prm.get("TokenPower") or (m and m.group(1)),
                               toughness=prm.get("TokenToughness") or (m and m.group(2)),
                               attacking=prm.get("TokenAttacking") == "True", tapped=prm.get("TokenTapped") == "True",
                               keywords=prm.get("PumpKeywords", "")))
        elif api in ("Animate", "AnimateAll") and (prm.get("Types") or prm.get("AddTypes")):
            if "Self" not in (prm.get("Defined") or "") and not (prm.get("ValidTgts") and not prm.get("ValidCards")):
                types.append(dict(types=prm.get("Types") or prm.get("AddTypes"), filter=prm.get("ValidCards") or prm.get("Defined", "")))
            for kw in (prm.get("Keywords") or "").split("&"):
                if kw.strip() and api == "AnimateAll" and "YouCtrl" in prm.get("ValidCards", ""):
                    grants.append(dict(keyword=kw.strip().lower(), filter=prm["ValidCards"], temporary=temp, team=True))
        if api == "CopyPermanent" and prm.get("Populate") == "True":
            doubles.append("tokens")                        # populate: copies a token, so token makers are better
        if api in ("Discard",) and not _who_other(prm) and prm.get("Defined", "You") == "You":
            targets.append(dict(kind="mill", filter="Card", to="Graveyard", num=prm.get("NumCards", "1")))
        if api == "Goad" or prm.get("Goad") == "True":
            taxes.append("goad")
        for kw in (prm.get("AddKWs") or prm.get("KWChoice") or "").split("&"):
            if kw.strip() and api not in ("GainControl",):
                grants.append(dict(keyword=kw.strip().lower(), filter=prm.get("Defined") or prm.get("ValidTgts", ""),
                                   temporary=True, team=False))
        if prm.get("UnlessCost") and re.search(r"Opp|Targeted|Player|Each", prm.get("UnlessPayer", "")):
            taxes.append(prm["UnlessCost"])
        if prm.get("AddKeywords") and api not in ("CopyPermanent", "Clone"):
            for kw in prm["AddKeywords"].split("&"):
                grants.append(dict(keyword=kw.strip().split(":")[0].lower(), filter=prm.get("Defined") or prm.get("ValidTgts", ""),
                                   temporary=True, team=False))
    for v in rec["svars"].values():
        if re.search(r"(?:Remembered|Revealed|Triggered\w*|Targeted)\$Card(?:ManaCost|CMC)|Count\$CardManaCost", v) \
                and "Self" not in v:
            scales_mv = True
    for st in x["statics"]:
        mode, aff = st.get("Mode"), st.get("Affected", "")
        if mode == "Continuous" and st.get("MayPlay") == "True":
            zone = st.get("AffectedZone", "")
            play_zones.append(zone)
            flt = _clean(aff)
            if zone == "Graveyard" or "TopLibrary" in aff or zone == "Library" or \
                    (zone == "Exile" and "IsRemembered" not in aff):
                targets.append(dict(kind="free_cast" if st.get("MayPlayWithoutManaCost") == "True" else "cast",
                                    filter=flt, to="Stack", zone=zone or "Library"))
            elif st.get("MayPlayWithoutManaCost") == "True":
                targets.append(dict(kind="free_cast", filter=flt, to="Stack", zone=zone))
        if mode == "Continuous" and st.get("Affected") == "You" and st.get("SetMaxHandSize") == "Unlimited":
            no_max_hand = True
        if mode == "Continuous" and st.get("Affected") == "You" and st.get("AdjustLandPlays"):
            extra_lands = True
        if mode == "Continuous" and st.get("Goad") == "True":
            taxes.append("goad")
        if mode == "RaiseCost" and "Opp" in st.get("Activator", "") + st.get("ValidCard", ""):
            taxes.append("raises costs")
        if mode == "Continuous" and ("YouCtrl" in aff or st.get("AffectedDefined")):
            for kw in (st.get("AddKeyword") or "").split("&"):
                if kw.strip() and "Self" not in aff:
                    grants.append(dict(keyword=kw.strip().split(":")[0].lower(), filter=aff or st.get("AffectedDefined"),
                                       temporary=st.get("_temp", False), team="Creature" in aff))
            if (st.get("AddType") or st.get("AddAllCreatureTypes")) and "Self" not in aff:
                types.append(dict(types=st.get("AddType") or "AllCreatureTypes", filter=aff))
            if st.get("GainsAbilitiesOf") and "Self" in (st.get("AffectedDefined") or aff):
                targets.append(dict(kind="borrow", filter=_clean(st["GainsAbilitiesOf"]), to="Self"))
            if st.get("SetMaxHandSize") == "Unlimited":
                no_max_hand = True
            if (st.get("SetPower") or st.get("SetToughness")) and "Self" not in aff:
                set_pt.append(dict(power=st.get("SetPower"), toughness=st.get("SetToughness"), filter=aff))
    for t in x["triggers"]:
        if t.get("Alone") == "True" and t.get("Mode") in ("Attacks", "AttackersDeclared"):
            attacks_alone = True
        if t.get("Revolt") == "True":
            revolt = True                                   # "if a permanent you controlled left the battlefield this turn"
        m = re.match(r"(?:EQ|GE)(\d+)", t.get("ActivatorThisTurnCast", ""))
        if m and t.get("Mode") == "SpellCast" and int(m.group(1)) >= 2:
            multi_cast = max(multi_cast, int(m.group(1)))      # "whenever you cast your second spell each turn"
    for r in x["replacements"]:
        ev = r.get("Event")
        valid = r.get("ValidToken") or r.get("ValidCard") or r.get("ValidSource") or r.get("ValidPlayer") or ""
        rw = rec["svars"].get(r.get("ReplaceWith", ""), "")
        if ev in _DOUBLE_EVENTS and re.search(r"YouCtrl|You\b|Card\.YouCtrl", valid + " " + r.get("ValidTarget", "")) and \
                re.search(r"Replace(?:Token|Counter|Damage|Mana)|Amount|Twice|Double|\+", rw + r.get("Description", "")):
            doubles.append(_DOUBLE_EVENTS[ev])
    return dict(targets=targets, grants=grants, copies=copies, doubles=sorted(set(doubles)), steals=steals,
                sacrifices=sac, taxes=taxes, adds_types=types, mana=mana, tokens=tokens, play_zones=play_zones,
                scales_with_mv=scales_mv, attacks_alone=attacks_alone, set_pt=set_pt, multi_cast=multi_cast,
                no_max_hand=no_max_hand, extra_lands=extra_lands, revolt=revolt)
