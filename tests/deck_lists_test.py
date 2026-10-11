"""Parser checks for decks/ files (deck_lists.py), on small made-up samples."""
import sys
sys.path.insert(0, "src")
import deck_lists as D

EDH = """EDHREC
Test Commander (Commander)
Test Commander
Rank #57
21,884
decks
Top Cards
Great Synergy
Great SynergyHOT
$4.49
$2.57
66%
inclusion
14.3K decks
21.9K decks
4.4x
lift
Sol Ring
81%
inclusion
17.8K decks
21.9K decks
1.0x
lift
Split // Card
59%
inclusion
13K decks
21.9K decks
12x
lift
Bad Fit
13%
inclusion
2.92K decks
21.9K decks
0.4x
lift
"""
e = D.parse_edhrec(EDH)
bad = 0
checks = [
    (e["commander"] == "Test Commander" and e["decks"] == 21884, "header"),
    (set(e["cards"]) == {"Great Synergy", "Sol Ring", "Split // Card", "Bad Fit"}, "card names (HOT tag, split card)"),
    (e["cards"]["Great Synergy"]["lift"] == 4.4 and e["cards"]["Great Synergy"]["decks"] == 14300, "numbers"),
]
lists = D.parse_decklists("# Deck one | 241 likes\n" + "\n".join(f"1 C{i}" for i in range(60)) +
                          "\n1 Skullclamp (2XM) 248 *F*\n1 Dusk / Dawn\n# Deck two\n" + "\n".join(f"1 C{i}" for i in range(45)))
checks += [(len(lists) == 2 and lists[0]["likes"] == 241 and "Skullclamp" in lists[0]["cards"]
            and "Dusk // Dawn" in lists[0]["cards"], "decklists")]
for ok, what in checks:
    bad += not ok
    print(("ok   " if ok else "FAIL ") + what)
sys.exit(1 if bad else 0)
