# decks/ — synergy data you collect yourself

The builder reads every `.txt` file here whose **file name is the commander's name**
(e.g. `arabella-abandoned-doll.txt`). It never contacts these sites itself.

## Option A — an EDHREC commander page (best: thousands of decks in one paste)
1. Open `edhrec.com/commanders/<commander>` in your browser.
2. Ctrl+A, Ctrl+C.
3. Here on GitHub: **Add file → Create new file**, name it `<commander-name>.txt`, paste, **Commit changes**.

The builder reads each card's inclusion and **lift** (how much more often it's played with this commander than
expected; 1.0x = a generic staple) and favors high-lift cards. Bracket 3, budget and color rules still apply.

## Option B — top decklists you exported (e.g. Moxfield's most-liked decks)
Put each deck under a header line with its title and likes, all in one file:

```
# [Primer] All she needs is love | 241 likes
1 Arabella, Abandoned Doll
1 Sol Ring
...
# Arabella - the Hare Apparent | 189 likes
1 ...
```
Aim for 10–15 decks. Cards shared by many top decks (and not just universal staples) are favored, weighted by likes.

You can use both for the same commander. Keep this repo **private** if you store these files: they're for your
own use, not for republishing.
