"""Strategic game plan: think about what the commander's deck DOES, what makes it stronger, and what beats it.

analyze.py reads the commander's text (plans, abilities, role, conditions). This module turns that into a game plan
the way a player would reason about it:

  1. FACETS: what kind of deck this is.
       go-wide        it wants many creatures (it counts them, or its plan is tokens)
       small bodies   only small creatures count ("power 2 or less"), so permanent anthems hurt
       big bodies     only big creatures count ("power 4 or greater"), so anthems help
       trigger        the ability that wins/drives the deck waits for an event (it attacks, a creature enters...)
       damage out     it wins by dealing damage / life loss to opponents
       voltron        it wins by hitting with the commander
       graveyard      it uses the graveyard
  2. NEEDS (cards it wants, each with a target count), derived from the facets:
       board protection     a go-wide deck loses to one board wipe: Teferi's Protection, Boros Charm, Flawless Maneuver
       value per creature   a go-wide deck turns each body into value: Mentor of the Meek, Impact Tremors
       retrigger            make the winning ability happen again: extra combats, "triggers an additional time"
       amplifier            more damage/life loss per trigger: Torbran, Fiery Emancipation
       haste                an attack-trigger commander should attack the turn it lands (and after a wipe)
       anthems              only for "big bodies" or plain go-wide decks without a small-body condition
  3. THREATS and what NOT to play:
       symmetric board wipes in a go-wide deck are cut (one-sided ones, or ones that miss your creatures, are fine:
       "destroy each creature with power 4 or greater" is GREAT next to Arabella's 1/1s)
       "exile all graveyards" in a graveyard deck
  4. A plain-English game plan for the run summary.

Everything is generic: no commander is special-cased. The facets come from the commander's own text."""
import re

import abilities as AB

BOARD_PROTECT = (r"(?:creatures|permanents) you control (?:gain|have|get [^.]{0,20}and gain) [^.]{0,30}"
                 r"(?:indestructible|hexproof|shroud|protection from)|(?:creatures|permanents) you control phase out|"
                 r"regenerate each creature you control")
ENTER_ENGINE = (r"whenever (?:a|another|one or more|a nontoken|another nontoken) (?:other )?(?:\w+ )?creatures?"
                r"(?: tokens?)?[^.\n]{0,50}\benters?\b[^\n]{0,140}?"
                r"(?:draw|loses? \d+ life|deals? \d+ damage|treasure|scry|gain \d+ life)")
CAST_ENGINE = r"whenever you cast a creature spell[^\n]{0,60}(?:draw|treasure|damage|loses)"
DIES_ENGINE = r"whenever (?:a|another|one or more) (?:nontoken )?creatures? you control dies[^\n]{0,80}(?:draw|treasure|loses? \d+ life|deals? \d+ damage)|equipped creature dies, draw"
TOKEN_ENGINE = r"whenever you create (?:a|one or more) (?:creature )?tokens?[^.]{0,80}(?:draw|loses?|damage|treasure|scry)"
HASTE = r"(?:creatures you control|equipped creature|target creature|your commanders?|each creature you control)[^.]{0,30}(?:have|has|gains?) haste"
AMP_DAMAGE = (r"would deal (?:noncombat )?damage to (?:an opponent|a player|any target|a permanent an opponent controls)[^.]{0,80}"
              r"(?:plus|double|twice|triple)|deals? (?:double|triple) that damage|that much damage plus \d|"
              r"if an opponent would lose life[^.]{0,40}(?:twice|double)|(?:double|triple) the damage")
ANTHEM = r"(?:other )?creatures you control get \+[1-9]/\+[1-9](?![^.]*until end of turn)"
RETRIGGER_ATTACK = [r"additional combat phase", r"untap all (?:attacking )?creatures[^.]{0,80}additional combat",
                    r"(?:attacking|attacks)[^.]{0,60}triggers? an additional time"]
GY_HATE_ALL = r"exile (?:all|each player's) graveyards?|exile all cards from all graveyards"
_WIPE = re.compile(r"(?:destroy|exile) (?:all|each) [^.]{0,60}|all creatures get -\d+/-\d+[^.]{0,30}|"
                   r"deals? (?:\d+|x) damage to each (?:creature|other creature|non\w+ creature)[^.]{0,40}|"
                   r"return (?:all|each) (?:nonland )?(?:creatures|permanents|nonland permanents)[^.]{0,40}|"
                   r"each (?:player|opponent) sacrifices (?:all|x|two|three) (?:creatures|permanents)[^.]{0,20}", re.I)

LABELS = {}
_RX_CACHE = {}


def _rx(p):
    if p not in _RX_CACHE:
        _RX_CACHE[p] = re.compile(p, re.I)
    return _RX_CACHE[p]


def _need(nid, label, why, patterns, weight, quota, concepts=None):
    LABELS[nid] = label
    import knowledge as K
    return dict(id=nid, label=label, why=why, patterns=patterns, weight=weight, quota=quota,
                concepts=concepts if concepts is not None else K.NEED_FROM.get(nid, []))


def plan(cmd, role, conds, parsed, routes):
    """The commander's strategic game plan. JSON-safe (patterns are strings)."""
    names = [r["name"] for r in routes]
    top2 = names[:2]
    text = (cmd.get("text") or "").lower()
    facets, needs, avoid, story = [], [], [], []
    creature_rules = [r for r in conds if r["type"] in ("creature", "token")]
    counts_bodies = any(r["counts"] or r["strong"] for r in creature_rules)
    cap = next((r["n"] for r in creature_rules if r.get("stat") == "power" and r["op"] == "le"), None)
    floor = next((r["n"] for r in creature_rules if r.get("stat") == "power" and r["op"] == "ge"), None)
    go_wide = counts_bodies or "Tokens / go wide" in top2 or bool(re.search(r"number of creatures you control|for each creature you control", text))
    if go_wide:
        facets.append("go-wide")
    if cap is not None:
        facets.append(f"small bodies (power {cap} or less)")
    if floor is not None:
        facets.append(f"big bodies (power {floor} or greater)")
    if "Voltron / equipment & auras" in top2:
        facets.append("voltron")
    if "Graveyard / self-mill / reanimation" in top2:
        facets.append("graveyard")

    # the ability that drives the deck: the winning one if it's a finisher, else its first triggered ability
    fin_lines = [ln.lower() for ln in role.get("lines") or []]
    driver = None
    for ab in parsed:
        if ab["kind"] == "triggered" and ab["event"]:
            if not driver or any(ab["text"].lower()[:40] in ln for ln in fin_lines):
                driver = ab
    damage_out = any(h in ("drains the table", "damages every opponent") for h in role.get("how") or [])
    if damage_out:
        facets.append("damage out")
    is_fin = role.get("role") == "finisher"

    # --- how it wins
    if is_fin:
        story.append(f"**How it wins:** its own ability ends the game ({', '.join(role.get('how') or [])}).")
    elif role.get("role") == "enabler":
        story.append(f"**How it wins:** it makes your {role['beneficiary']['label']} better, so the deck is full of them and "
                     "wins with that buffed board, backed by a few dedicated win conditions.")
    elif role.get("role") == "engine":
        story.append("**How it wins:** it builds an advantage, and dedicated win conditions turn that advantage into a win.")
    else:
        story.append("**How it wins:** through its themes and dedicated win conditions.")
    if creature_rules and counts_bodies:
        story.append(f"**What it scales with:** how many {', '.join(_cond_text(r) for r in creature_rules)} you have. "
                     "Every card that adds such bodies (itself, or tokens) makes each trigger bigger.")

    # --- multiply the driver
    if driver:
        ev = driver["event"][0]
        pats = list(AB.DOUBLERS.get(ev, [])) + list(AB.GENERIC_DOUBLER) + (RETRIGGER_ATTACK if ev == "attacks" else [])
        needs.append(_need("retrigger", "makes its key ability happen again",
                           f"its key ability waits for '{driver['event'][1]}': cards that repeat that event or copy the trigger multiply it",
                           sorted(set(pats)), 15 if is_fin else 8, 3 if is_fin else 2,
                           concepts=["trigger_doubler"] + (["extra_combat"] if ev == "attacks" else [])))
        story.append(f"**Multiply it:** its key ability triggers when {driver['event'][1]}. Extra copies of that event "
                     "(extra combats, trigger doublers, copying the trigger) are worth more than almost anything else.")
        if ev == "attacks" and re.search(r"whenever ~ attacks|whenever (?:this creature|it) attacks", _self(cmd)) \
                and not role.get("haste"):              # Forge: it doesn't already have (or give itself) haste
            needs.append(_need("haste", "lets it attack right away", "an attack-trigger commander loses a whole turn without haste",
                               [HASTE], 6, 1))
    if damage_out:
        needs.append(_need("amplify", "multiplies its damage / life loss", "each trigger hits every opponent, so +2 or x2 per hit adds up fast",
                           [AMP_DAMAGE], 12, 2))
        story.append("**Amplify it:** damage boosters (+2 per hit, double or triple damage) turn each trigger into a much bigger one.")

    # --- go-wide: value per body, protect the board, never wipe yourself
    if go_wide:
        needs.append(_need("enter_engine", "turns your creatures into value",
                           "a deck that makes lots of creatures should get cards, damage or mana from each one",
                           [ENTER_ENGINE, TOKEN_ENGINE, CAST_ENGINE, DIES_ENGINE], 12, 4))
        needs[-1]["cap"] = cap          # an engine for BIG creatures does nothing next to small ones
        needs[-1]["aligned"] = [r["text"].lower().split(" with ", 1)[-1] for r in creature_rules]   # "power 2 or less"
        needs.append(_need("board_protect", "protects your whole board",
                           "one board wipe undoes a go-wide deck's work: indestructible / phasing / hexproof for the whole team",
                           [BOARD_PROTECT], 14, 4))
        avoid.append(dict(id="own_wipe", label="board wipes that would kill your own creatures", cap=cap,
                          why="a go-wide deck shouldn't wipe its own board; one-sided wipes (or ones that miss your creatures) are fine"))
        story.append("**Biggest threat:** board wipes. The deck carries extra board protection, gets value from every "
                     "creature that enters (so a rebuild refills your hand), and leaves out wipes that kill its own creatures. "
                     + (f"Wipes that only hit big creatures (power {cap + 1}+) are kept: they're one-sided here." if cap is not None else ""))
        if cap is None:
            needs.append(_need("anthem", "makes the whole team bigger", "a wide board plus a team pump is a win condition", [ANTHEM], 7, 2))
        else:
            story.append(f"**Avoid:** permanent anthems and +1/+1 counters on your team: they push creatures above power {cap} "
                         "and out of the count. Pumps until end of turn (after the trigger) are fine.")
    elif floor is not None:
        needs.append(_need("anthem", "pushes your creatures into the count", f"anthems help creatures reach power {floor}", [ANTHEM], 9, 3))
    if any(r["kind"] == "compare" and r["stat"] == "toughness" for r in creature_rules):
        facets.append("big toughness")
        needs.append(_need("toughness_payoff", "turns big toughness into damage",
                           "high-toughness creatures hit like their toughness, or attack despite defender",
                           [r"(?:assigns?|deals?) combat damage equal to (?:its|their) toughness",
                            r"toughness rather than (?:its|their) power", r"damage equal to (?:its|the) toughness",
                            r"attack as though (?:it|they) didn't have defender", r"\bgets? \+0/\+\d"], 14, 4))
        story.append("**Make toughness matter:** high-toughness creatures are only threats if they deal damage, so the "
                     "deck runs cards that make creatures deal combat damage equal to their toughness (and lets defenders attack).")
    if role.get("gifts"):
        facets.append("gifts to opponents")
        needs.append(_need("gift_payoff", "profits when opponents take your gifts",
                           "every card you hand an opponent should also pay you back",
                           [r"whenever an opponent (?:draws|creates|gains|casts|searches)",
                            r"whenever (?:a|another) player (?:draws|creates|gains)", r"unless that player pays",
                            r"\bmonarch\b", r"\bgoad", r"\bvote\b|will of the council|council's dilemma",
                            r"each (?:player|opponent) (?:draws|creates|gains)[^.]{0,60}\byou\b"], 13, 6))
        story.append("**How it wins:** it keeps the table friendly with gifts while cards that profit from those gifts "
                     "(Smothering Tithe style) and political tools put you ahead; then its finishers close.")
    # --- what its Forge script says it does with other cards (analyze._read_deck_facts)
    if role.get("copies"):
        nonleg = any("nonLegendary" in c["filter"] for c in role["copies"])
        needs.append(_need("copy_target", "is worth copying",
                           "the commander copies your creatures, so each copy of an enter-the-battlefield effect is a free spell",
                           [r"\bwhen(?:ever)? [^.]{0,40}\benters\b", r"\benters[^.]{0,30}(?:draw|create|deal|destroy|exile|search|return)"],
                           12, 8, concepts=[]))
        story.append("**Copy targets:** it copies your creatures, so creatures with strong enter-the-battlefield effects"
                     + (" (nonlegendary ones)" if nonleg else "") + " are worth the most.")
    _DBL = {"tokens": [r"\bcreates? [^.]{0,60}\btokens?\b"],
            "counters": [r"\+1/\+1 counters?", r"\bproliferate\b", r"\bput (?:a|an|one|two|\w+) [^.]{0,20}counters? on"],
            "damage": [r"deals? (?:\d+|x) damage to (?:each|any|target)"],
            "life gain": [r"\byou gain (?:\d+|x) life\b", r"\bgain (?:\d+|x) life\b", r"\blifelink\b"],
            "card draw": [r"\bdraws? (?:a|two|three|\w+) cards?\b"], "mana": [r"\badd \{", r"\bcreate[^.]{0,20}treasure"]}
    pats = sorted({p for d in role.get("doubles") or [] for p in _DBL.get(d, [])})
    if pats:
        needs.append(_need("doubled", "makes what the commander doubles",
                           f"the commander doubles your {', '.join(role['doubles'])}, so every card that makes them counts twice",
                           pats, 12, 10))
        story.append(f"**Doubled:** it doubles your {', '.join(role['doubles'])}; the deck is full of cards that make them.")
    if role.get("steals"):
        needs.append(_need("sac_outlet", "sacrifices what you borrow",
                           "it takes opponents' creatures until end of turn; a free sacrifice outlet makes that permanent",
                           [r"\bsacrifice (?:a|another) (?:creature|artifact|permanent)[^.]{0,40}:"], 10, 3,
                           concepts=["sac_outlet"]))
    if role.get("extra_lands"):
        needs.append(_need("land_payoff", "uses the extra land drops",
                           "it lets you play extra lands, so cards that reward lands entering (or put more lands in) pay off",
                           [r"\blandfall\b", r"whenever a land (?:you control )?enters", r"put (?:a|up to \w+) land cards? from your hand onto",
                            r"return (?:a|target) land card"], 9, 6, concepts=["landfall"]))
    if role.get("own_sac") or role.get("revolt"):
        needs.append(_need("fodder", "gives it something to sacrifice",
                           "it sacrifices your own permanents, so spare bodies and tokens keep it running",
                           [r"\bcreates? [^.]{0,40}creature tokens?", r"\bwhen(?:ever)? [^.]{0,30}dies\b"], 9, 6,
                           concepts=["token_maker"]))
    if role.get("alone") and "voltron" not in facets:
        facets.append("voltron")
    if role.get("mill") and "graveyard" not in facets:
        facets.append("graveyard")
    if role.get("taxes"):
        story.append("**Taxes:** opponents must pay or suffer; cards that punish or slow them fit the plan.")
    if any(r["zone"] == "Graveyard" for r in role.get("requirements") or []):
        facets.append("fills its graveyard")
        if "graveyard" not in facets:
            facets.append("graveyard")             # so the deck also avoids exiling its own graveyard
        rq = next(r for r in role["requirements"] if r["zone"] == "Graveyard")
        needs.append(_need("fills_graveyard", "fills your graveyard", f"its ability needs {rq['text']}",
                           [r"\bmills?\b", r"\bsurveil\b", r"put the top \w+ cards? of your library into your graveyard",
                            r"discard (?:a|two|three|\w+) cards?", r"\bdredge\b"], 11, 6, concepts=["self_mill"]))
    if "voltron" in facets:
        story.append("**Biggest threat:** spot removal on the commander. The deck carries extra protection for it.")
    if "graveyard" in facets:
        avoid.append(dict(id="gy_hate", label="effects that exile every graveyard (yours too)", cap=None,
                          why="a graveyard deck shouldn't hate on its own graveyard"))
        story.append("**Biggest threat:** graveyard hate. The deck leaves out cards that exile every graveyard.")
    if is_fin and "voltron" not in facets:
        story.append("**Protect the engine:** it IS the win condition, so it gets extra protection.")
    return dict(facets=facets, needs=needs, avoid=avoid, story=story)


def _cond_text(r):
    if r["kind"] == "keyword":
        return f"creatures with {r['keyword']}"
    return f"creatures with {r['stat']} {r['n']} or {'less' if r['op'] == 'le' else 'greater'}"


def _self(cmd):
    x = (cmd.get("text") or "").lower()
    for n in sorted({cmd["name"], cmd["name"].split(",")[0], cmd["name"].split(" // ")[0]}, key=len, reverse=True):
        x = x.replace(n.lower(), "~")
    return x


_BIG_ONLY = re.compile(r"(?:with )?power (\d+)(?: or greater| or more|, \d+,? or \d+)", re.I)


def meets(card, need):
    x = card.get("text") or ""
    tagged = set(need.get("concepts") or []) & set(card.get("otags") or [])
    if tagged and not (need.get("cap") is not None and _BIG_ONLY.search(x) and int(_BIG_ONLY.search(x).group(1)) > need["cap"]):
        return True                            # Scryfall Tagger says it does this job
    for p in need["patterns"]:
        m = _rx(p).search(x)
        if m:
            big = _BIG_ONLY.search(m.group(0))
            if need.get("cap") is not None and big and int(big.group(1)) > need["cap"]:
                continue                       # "whenever you cast a creature with power 4 or greater": not for small bodies
            return True
    return False


def hurts(card, av):
    """Reason this card works against the plan ('' = fine)."""
    x = (card.get("text") or "")
    if av["id"] == "gy_hate":
        return av["label"] if _rx(GY_HATE_ALL).search(x) else ""
    if av["id"] == "own_wipe":
        if "one_sided_wipe" in (card.get("otags") or ()):
            return ""                          # tagged one-sided: only hurts opponents
        m = _WIPE.search(x)
        if not m or "sweeper" not in card.get("tags", ()):
            return ""
        cl = m.group(0).lower()
        if re.search(r"you don't control|your opponents control|an opponent controls|opponents control|target player controls", cl):
            return ""
        if not re.search(r"creature|permanent", cl):
            return ""                          # artifact / enchantment wipes don't touch your creatures
        p = re.search(r"with power (\d+) or greater", cl)
        if p and av.get("cap") is not None and int(p.group(1)) > av["cap"]:
            return ""                          # only hits creatures bigger than yours
        return "a board wipe that would kill your own creatures"
    return ""


_RESTRICT = re.compile(r"whenever (?:a|another|one or more) (?:other )?(colorless|artifact|legendary|nontoken|[A-Z][a-z]+)"
                       r"(?: \w+)? creatures?")


def fit_factor(card, need):
    """How well an engine's trigger matches THIS deck's bodies: x1.5 if it names the commander's own condition
    (Mentor of the Meek's 'power 2 or less' next to Arabella), x0.5 if it only sees bodies this deck rarely makes
    ('colorless', 'nontoken', one creature type)."""
    x = card.get("text") or ""
    if any(a and a in x.lower() for a in need.get("aligned") or []):
        return 1.5
    m = _RESTRICT.search(x)
    if m and m.group(1).lower() not in ("another", "creature", "one"):
        return 0.5
    return 1.0


def judge(card, strat):
    """(synergy delta, [need ids met], avoid reason) for one card."""
    if not strat:
        return 0.0, [], ""
    d, met = 0.0, []
    for n in strat["needs"]:
        if meets(card, n):
            d += n["weight"] * (fit_factor(card, n) if n["id"] == "enter_engine" else 1.0)
            met.append(n["id"])
    bad = ""
    for av in strat["avoid"]:
        bad = hurts(card, av)
        if bad:
            d -= 30
            break
    return d, met, bad
