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

| Game | Score | Range | Better | Ranked on |
|---|---|---|---|---|
| [Krillion](https://www.krillion.org/) | seven rounds, rarity-tiered 10–100 each | 0–700 | higher | **percentile** |
| [Wordle](https://www.nytimes.com/games/wordle/index.html) | guesses used (a miss counts as 7) | 1–7 | **lower** | score |
| [dialed.gg color](https://dialed.gg/color) | five colors, CIELAB distance, 10 each | 0–50 | higher | score |
| [dialed.gg sound](https://dialed.gg/sound) | five tones, ERB scale, 10 each | 0–50 | higher | score |

Each game's score input is tailored to it: Wordle gives you a 1–6–X tap row, Krillion a 0–700 box
that live-converts your score into dive depth plus a **required percentile** box, the dialed games a
0–50 box that shows your percentage of perfect.

---

## How the ranking works

**Within a game**, players are ranked by their **average** across every day they logged. Average
rather than total, so somebody who plays twenty days isn't automatically ahead of somebody who plays
two; average rather than personal best, so one lucky day doesn't define you. Ties share a rank and the
next rank skips — 1, 2, 2, 4.

**Krillion is ranked on average percentile, not average score.** Krillion's difficulty swings a lot
day to day, so a raw score isn't comparable across days — averaging it partly measures *which days you
showed up for* rather than how well you played. The percentile Krillion reports is already normalised
against that day's field, which is exactly the correction needed, so it ranks and the score rides
along as a displayed stat and the tiebreak.

The two are deliberately **not** combined. Percentile is derived from where your score landed in that
day's field, so within a day it's a monotone transform of the score — they aren't independent signals.
Adding them would double-weight the same thing and drag the day-difficulty bias back into a measure
chosen to remove it.

Because the global board sums *ranks* rather than scores, each game is free to rank on whatever metric
suits it without disturbing the global math. That's what makes this a one-line config change rather
than an architectural one.

Percentile is **required** when logging a Krillion score, since you can't be ranked on a figure you
didn't enter. A Krillion entry that somehow has no percentile still counts toward the score stats but
shows as unranked (`—`), and for the global sum that player is treated the same as never having played
the game.

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
date,game,player,score,percentile
2026-09-28,wordle,Viggy,4,
2026-09-28,krillion,Jai,500,88
```

`game` is one of `krillion`, `wordle`, `dialed_color`, `dialed_sound`. Rows naming a game the site no
longer tracks are ignored on load rather than erroring, so a game can be retired without rewriting
history.

`percentile` is blank for every game except Krillion. A CSV still using the original four-column
header is read fine and gains the column the next time anything is written. Re-submitting a score with
the percentile box left blank updates the score and leaves the stored percentile alone, so fixing a
typo in one field doesn't wipe the other.

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

### Every score triggers a deploy — on purpose

Submitting a score commits to `main`, and that commit triggers a Vercel build. **This is not
incidental; it is the publish step.** Vercel serves `scores.csv` from the last *built* deployment, not
from GitHub, so the new row is not readable by anybody else until that build finishes (~30 seconds).

Two consequences worth knowing:

- **Do not add an Ignored Build Step** to skip builds for score commits. It looks like an easy way to
  cut deploy churn, and it would silently freeze the leaderboard at whatever the last real build
  contained — the commits would keep landing in git and never reach the site.
- **The person submitting sees their score immediately anyway.** The client mirrors its own write into
  local state rather than refetching a CSV it knows is stale for the next half-minute; otherwise your
  score would appear, then vanish on the re-render. Everyone else sees it after the build.

Vercel's Hobby plan allows [100 deployments per day](https://vercel.com/docs/limits). Four games times
a handful of friends is comfortably inside that, but it is the limit to watch if the group or the game
list grows a lot.

## Adding a game

Everything game-specific lives in one place — the `GAMES` array at the top of the `<script>` in
`index.html`. Add an entry with its `id`, `route`, scoring `dir` (`high`/`low`), `min`/`max`, and an
accent color, then add the same `id` and range to `GAME_RANGES` in `api/add-score.py` so the server
validates it too. The nav, the global leaderboard column, the game page, and the history chart all
derive from that entry; nothing else needs touching.

To give a game a percentile, set `percentile: true` on it and add its `id` to `PERCENTILE_GAMES` in
`api/add-score.py`. Adding `rankBy: 'percentile'` makes it rank on that instead of score (which also
switches the history chart to plot percentile), and `percentileRequired: true` enforces it at the form.
Omit `rankBy` to record a percentile for display only.

## Local development

```bash
python3 -m http.server 8731     # then open http://localhost:8731
```

Reading works offline against the local CSV. Submitting needs the serverless functions, so use
`vercel dev` with the two env vars set in `.env` if you want to exercise writes.
