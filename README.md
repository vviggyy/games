# games

*Leaderboards for the daily web games, settled among friends.*

A single-page site at [games.viggy.me](https://games.viggy.me) that tracks how a group of friends
does at four daily puzzle games, ranks each game, and rolls those ranks into one global standing.

There is no database, no build step, no framework, and no npm install. The site is `index.html` +
`style.css`. Every score anyone has ever logged lives in one CSV file, which the browser fetches and
derives everything else from on page load. Writes go through three dependency-free Python serverless
functions that commit straight back to this repo — so the git history *is* the audit log.

Same shape as [chiptrack](https://chiptrack.viggy.me), same visual language as
[coffeehour](https://coffeehour.viggy.me).

---

## The games

| Game | Score | Range | Better |
|---|---|---|---|
| [Krillion](https://www.krillion.org/) | seven rounds, rarity-tiered 10–100 each | 0–700 | higher |
| [Wordle](https://www.nytimes.com/games/wordle/index.html) | guesses used (a miss counts as 7) | 1–7 | **lower** |
| [dialed.gg color](https://dialed.gg/color) | five colors, CIELAB distance, 10 each | 0–50 | higher |
| [dialed.gg sound](https://dialed.gg/sound) | five tones, ERB scale, 10 each | 0–50 | higher |

Each game's score input is tailored to it: Wordle gives you a 1–6–X tap row, Krillion a 0–700 box
that live-converts your score into dive depth, the dialed games a 0–50 box that shows your percentage
of perfect.

---

## How the ranking works

**Within a game**, players are ranked by their **average score** across every day they logged. Average
rather than total, so somebody who plays twenty days isn't automatically ahead of somebody who plays
two; average rather than personal best, so one lucky day doesn't define you. Ties share a rank and the
next rank skips — 1, 2, 2, 4.

**Globally**, you get your rank in each of the four games and those ranks are **summed. Lowest total
wins.** Raw scores can't be added together — 385 at Krillion and 4 at Wordle aren't on the same scale,
and they don't even point the same direction — but ranks are comparable across anything.

**If you never played a game**, you're placed one below that game's last place for the purposes of
the sum. Skipping a game costs you, which is the point; everyone still gets a global rank. These
placeholder ranks are greyed out on the global table, so you can see which of someone's numbers are
real and which are penalties.

Worked example — four players, where Khang has only ever logged Wordle:

```
#   Player   Krillion  Wordle  Color  Sound   Total
1   Viggy       1        1       2      2       6
2   Bhiv        3*       2       1      1       7
3   Jai         2        2       3      3*     10
4   Khang       3*       4       4*     3*     14
                                              (* = never played, last place + 1)
```

---

## Logging a score

Hit **LOG A SCORE** on any game page. Pick yourself from the dropdown (or **+ New player…** to add
somebody), confirm the date, enter the score, submit. The row lands in `scores.csv` as a commit and
the page updates immediately.

**One score per person per game per day.** Submitting again for the same day overwrites the old value
rather than adding a second row, so a typo is fixed by just re-submitting. Names are matched
case-insensitively against existing players, so `viggy` won't create a second `Viggy`.

Adding a score is deliberately open — no password, anyone with the link can log a night. Deleting is
not: hover a row in **Player history** and hit the `×` to get an admin password prompt.

## Player history

On a game page, pick anyone from **Show history for** to see their full run at that game: average,
best, days played, a bar chart where taller always means better (Wordle is inverted, since fewer
guesses is the good outcome), and a table of every entry with how far it sat from their own average.

## Suggestion box

`/#/suggestions` — another game worth tracking, a rule you want changed, or a complaint. Optionally
signed. Posts commit to `suggestions.json`.

---

## Data

`scores.csv` — one row per person per game per day:

```csv
date,game,player,score
2026-09-28,wordle,Viggy,4
2026-09-28,krillion,Jai,500
```

`game` is one of `krillion`, `wordle`, `dialed_color`, `dialed_sound`. Rows naming a game the site no
longer tracks are ignored on load rather than erroring, so a game can be retired without rewriting
history.

`suggestions.json` — `[{id, name, text, ts}]`.

---

## Deploying

The site is static; only the three `api/*.py` functions need a runtime, declared in `vercel.json`.

1. Push this repo to GitHub as **`vviggyy/games`**. The `REPO` constant at the top of each function
   in `api/` points there — change it in all three if you name the repo something else.
2. Import the repo in Vercel. No build command, no output directory.
3. Set two environment variables in the Vercel project:
   - `GITHUB_TOKEN` — a fine-grained personal access token with **Contents: read and write** on this
     repo only. This is what lets submissions commit.
   - `ADMIN_PASSWORD` — gates deleting scores and suggestions.
4. Add `games.viggy.me` as a domain on the project, and point a CNAME at Vercel in your DNS, the same
   way `coffeehour` and `chiptrack` are set up.

Scores are read client-side straight from the CSV on the deployed site, so a fresh deploy is live the
moment DNS resolves.

## Adding a game

Everything game-specific lives in one place — the `GAMES` array at the top of the `<script>` in
`index.html`. Add an entry with its `id`, `route`, scoring `dir` (`high`/`low`), `min`/`max`, and an
accent color, then add the same `id` and range to `GAME_RANGES` in `api/add-score.py` so the server
validates it too. The nav, the global leaderboard column, the game page, and the history chart all
derive from that entry; nothing else needs touching.

## Local development

```bash
python3 -m http.server 8731     # then open http://localhost:8731
```

Reading works offline against the local CSV. Submitting needs the serverless functions, so use
`vercel dev` with the two env vars set in `.env` if you want to exercise writes.
