"""Synergy data you collect yourself, read from text files in the repo's decks/ folder.

Two kinds of file, any number of each, one file per commander (name it after the commander, e.g.
decks/arabella-abandoned-doll.txt):

  1. An EDHREC commander page, copied by hand (Ctrl+A, Ctrl+C on edhrec.com/commanders/<name>, paste, commit).
     For every card EDHREC shows its inclusion (% of this commander's decks that run it) and its LIFT (how many
     times more often it's played with this commander than expected; 1.0x = a generic staple). Lift is the synergy.
  2. Decklists you exported yourself (e.g. Moxfield's most-liked decks: Export -> copy as plain text), each one
     under a header line:   # Deck title | 241 likes
     Inclusion is weighted by likes; lift is estimated against how common the card is everywhere (Scryfall's
     EDHREC popularity rank), so universal staples don't count as synergy.

The builder never contacts these sites: it only reads what you pasted. Keep the repo private if you store them.
score() returns 0..1 per card plus a reason, used by reference.Reference like the other reference sources."""
import math
import os
import re

_PCT = re.compile(r"^(\d+(?:\.\d+)?)%$")
_DECKS = re.compile(r"^([\d.]+)(K?) decks$")
_LIFT = re.compile(r"^(\d+(?:\.\d+)?)x$")
_PRICE = re.compile(r"^\$\d")
_CARD_LINE = re.compile(r"^\s*(\d+)x?\s+(.+?)\s*$")
_HEADER = re.compile(r"^#\s*(.*?)(?:\|\s*([\d,]+)\s*likes?)?\s*$", re.I)


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower().split(" // ")[0]).strip("-")


def _count(num, k):
    return float(num) * (1000 if k else 1)


def parse_edhrec(text):
    """{'commander', 'decks', 'cards': {name: dict(inclusion, decks, potential, lift)}} or None if it isn't one."""
    lines = [ln.strip() for ln in text.splitlines()]
    cmd = next((m.group(1) for ln in lines for m in [re.match(r"^(.+) \(Commander\)$", ln)] if m), None)
    if not cmd or "inclusion" not in lines:
        return None
    total = None
    for i, ln in enumerate(lines):
        if ln == "decks" and i and re.match(r"^[\d,]+$", lines[i - 1]):
            total = int(lines[i - 1].replace(",", ""))
            break
    cards = {}
    for i, ln in enumerate(lines):
        if ln != "inclusion" or i < 2:
            continue
        m_pct = _PCT.match(lines[i - 1])
        m_d = _DECKS.match(lines[i + 1]) if i + 1 < len(lines) else None
        m_p = _DECKS.match(lines[i + 2]) if i + 2 < len(lines) else None
        m_l = _LIFT.match(lines[i + 3]) if i + 3 < len(lines) else None
        if not (m_pct and m_l):
            continue
        # the card name: the nearest line above that isn't a price or a "HOT/NEW" duplicate
        name = None
        for j in range(i - 2, max(i - 9, -1), -1):
            cand = lines[j]
            if not cand or _PRICE.match(cand):
                continue
            name = re.sub(r"(HOT|NEW)$", "", cand).strip()
            if j > 0 and lines[j - 1] == name:
                name = lines[j - 1]
            break
        if not name or name in cards:
            continue
        cards[name] = dict(inclusion=float(m_pct.group(1)) / 100,
                           decks=_count(*m_d.groups()) if m_d else None,
                           potential=_count(*m_p.groups()) if m_p else None,
                           lift=float(m_l.group(1)))
    return dict(commander=cmd, decks=total, cards=cards) if cards else None


def parse_decklists(text):
    """[{'title', 'likes', 'cards': set(names)}] from exported decklists under '# title | N likes' headers."""
    decks, cur = [], None
    for ln in text.splitlines():
        s = ln.strip()
        if not s:
            continue
        h = _HEADER.match(s)
        if h and s.startswith("#"):
            cur = dict(title=h.group(1).strip(), likes=int((h.group(2) or "0").replace(",", "")), cards=set())
            decks.append(cur)
            continue
        m = _CARD_LINE.match(s)
        if m and cur is not None:
            name = re.sub(r"\s+\([A-Z0-9]{2,6}\)\s*[\w-]*\s*(?:\*[A-Z]\*)?$", "", m.group(2))   # "(MH3) 123 *F*"
            name = name.replace(" / ", " // ").strip()
            cur["cards"].add(name)
    return [d for d in decks if len(d["cards"]) >= 40]


def expected_rate(rank):
    """Rough share of all Commander decks (in its colors) that run a card with this EDHREC rank (from Scryfall)."""
    if not rank:
        return 0.02
    return min(0.6, 2.2 / (rank ** 0.45))


class DeckLists:
    """Everything in decks/ for one commander."""

    def __init__(self, commander, folder="decks", log=print):
        self.cmd = commander
        self.edhrec, self.lists, self.files = None, [], []
        if not os.path.isdir(folder):
            return
        want = {slug(commander), slug(commander.split(" // ")[0])}
        for f in sorted(os.listdir(folder)):
            if not f.endswith(".txt"):
                continue
            try:
                text = open(os.path.join(folder, f), encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            e = parse_edhrec(text)
            mine = slug(os.path.splitext(f)[0]) in want or (e and slug(e["commander"]) in want)
            if not mine:
                continue
            self.files.append(f)
            if e:
                if not self.edhrec or (e.get("decks") or 0) > (self.edhrec.get("decks") or 0):
                    self.edhrec = e
            else:
                self.lists += parse_decklists(text)
        self._edh = {k.lower(): v for k, v in (self.edhrec or {}).get("cards", {}).items()}
        if self._edh:
            for k in list(self._edh):
                self._edh.setdefault(k.split(" // ")[0], self._edh[k])
        self._rates = {}
        if self.lists:
            wsum = 0.0
            for d in self.lists:
                w = 1 + math.log1p(d["likes"])               # most-liked decks count more
                wsum += w
                for n in d["cards"]:
                    for key in {n.lower(), n.lower().split(" // ")[0]}:
                        self._rates[key] = self._rates.get(key, 0) + w
            self._wsum = wsum
        if self.files:
            log(f"Your decks/ folder: {', '.join(self.files)} "
                f"({'EDHREC page, ' + str(self.edhrec.get('decks') or '?') + ' decks' if self.edhrec else ''}"
                f"{'; ' if self.edhrec and self.lists else ''}{str(len(self.lists)) + ' decklists' if self.lists else ''})")

    def score(self, c):
        """(0..1, reason)."""
        n = c["name"].lower()
        best = (0.0, "")
        e = self._edh.get(n) or self._edh.get(n.split(" // ")[0])
        if e:
            syn = max(0.0, min(1.0, (e["lift"] - 1.0) / 5.0))          # lift 6x or more = full synergy
            conf = min(1.0, e["inclusion"] / 0.40) ** 0.5             # in 40%+ of decks = fully trusted
            s = syn * conf
            if e["lift"] >= 0.9 and e["inclusion"] >= 0.5:
                s = max(s, 0.2)                                       # a near-universal pick for this commander
            if s > 0:
                pct = f"{e['inclusion'] * 100:.0f}%" if e["inclusion"] >= 0.1 else f"{e['inclusion'] * 100:.1f}%"
                pool = "EDHREC decks with this commander" if not e.get("potential") or not self.edhrec.get("decks") or \
                    e["potential"] >= 0.9 * self.edhrec["decks"] else "of the EDHREC decks that could run it"
                pool = ("of " + pool) if pool.startswith("EDHREC") else pool
                best = (round(s, 3), f"in {pct} {pool}, " + (f"{e['lift']:g}x more than usual (EDHREC lift)" if e["lift"] >= 1.5
                                                             else "a common pick for this commander"))
        if self.lists:
            w = self._rates.get(n) or self._rates.get(n.split(" // ")[0]) or 0
            if w:
                k = len(self.lists)
                rate = w / self._wsum
                exp = expected_rate(c.get("rank"))
                shrunk = (rate * k + 2 * exp) / (k + 2)               # few decks: don't trust one-offs
                lift = shrunk / exp
                syn = max(0.0, min(1.0, (lift - 1.0) / 5.0))
                s = syn * min(1.0, shrunk / 0.40) ** 0.5
                if s > best[0]:
                    hits = sum(1 for d in self.lists if n in {x.lower() for x in d["cards"]} or
                               n.split(" // ")[0] in {x.lower().split(" // ")[0] for x in d["cards"]})
                    best = (round(s, 3), f"in {hits} of your {k} top decks with this commander (~{lift:.1f}x more than usual)")
        return best

    def summary(self):
        return dict(files=self.files, edhrec_decks=(self.edhrec or {}).get("decks") if self.edhrec else None,
                    edhrec_cards=len((self.edhrec or {}).get("cards", {})), decklists=len(self.lists))
