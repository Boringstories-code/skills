# skills

Twenty skills from my own setup, free, for Claude Code, Codex, Grok and anything else that reads a `SKILL.md`.

## Install

```sh
npx skills add Boringstories-code/skills
```

Have a Little Brain? Open it and say: **install the skills**. The agent does the rest.

Or copy them by hand, from the folder you open your agent in:

```sh
t=$(mktemp -d) && git clone --depth 1 https://github.com/Boringstories-code/skills "$t" && for d in .claude .agents .grok; do mkdir -p $d/skills && cp -R "$t"/skills/* $d/skills/; done
```

That puts them where Claude Code (`.claude/skills`), Codex (`.agents/skills`) and Grok (`.grok/skills`) look. Start a new session and they're there.

## Fun things to try first

| Say this | What happens | Why it's good |
|---|---|---|
| `brainstorm three ways to <something you're stuck on>` | **explore-options** lays out real alternatives, pokes holes in each, picks one and says why not the others | You stop marrying your first idea |
| `learn how I write` | **write-as-you** reads a few things you've written and builds a voice card | Every draft after this sounds like you, not like a chatbot |
| `humanize this: <paste text>` | **humanizer** strips the AI tells (the "delve", the tidy triplets, the em dashes) | Your emails stop sounding generated |
| `chart this song: ~/Desktop/idea.m4a` | **song-loop** turns a voice memo into lyrics, chords and a verse/chorus map | Hum it once, get a chart back |
| `process this meeting: <recording>` | **meeting-loop** gives you a transcript with who said what, plus action items. Runs locally | Recordings never leave your machine |
| `organize my Downloads folder` | **organize-folder** sorts it into folders, writes an undo script, and refuses to move anything an app still points at | Tidy without breaking a project file |
| `what did I learn from this? <article, notes or transcript>` | **distill-understanding** turns it into concept cards that link to what you already know | Reading becomes something you keep |
| `is this skill safe? <folder>` | **audit-tool** scans a skill or plugin someone shared before you install it, without running it | Skills can do anything your agent can. Check first |
| `/q what did I decide about <thing>` | **second-brain-query** answers from your own notes and tells you which page it came from | No more digging through old docs |
| `remember this: <thought>` | **capture** files it somewhere you'll find it again | You don't have to decide where it goes |
| `make this easier to read: <file>` | **easy-read** puts the decision on the first screen and the detail behind it | People actually read it |
| `wrap up` | **session-close** saves what you learned and where you stopped | Tomorrow starts where today ended |

## All twenty

| Skill | Say this to try it |
|---|---|
| `audit-tool` | `is this skill safe? <folder>` |
| `build` | `/build <an idea>`: grill, spec and tickets in one sitting. Needs Matt Pocock's skills |
| `capture` | `remember this: <thought>` |
| `checkpoint` | `/checkpoint` when the session's getting long, then `/clear` |
| `distill-understanding` | `what did I learn from this? <article>` |
| `easy-read` | `make this easier to read: <file>` |
| `explore-options` | `brainstorm three ways to <problem>` |
| `humanizer` | `humanize this: <text>` |
| `meeting-loop` | `process this meeting: <recording>` |
| `new-skill` | `make that a skill` |
| `next` | `/next`: works the next ticket from `/build`. Needs Matt Pocock's skills |
| `organize-folder` | `organize my Desktop` |
| `person-enrich` | just talk about someone. Notes go to a private `People/` folder |
| `second-brain-ingest` | `/ingest <file or folder>` |
| `second-brain-query` | `/q <question>` |
| `session-close` | `wrap up` |
| `song-loop` | `chart this song: <voice memo>` |
| `what-can-i-do` | `what can I do?` |
| `wiki-lint` | `check the wiki` |
| `write-as-you` | `learn how I write`, then `write this as me` |

## Good to know

- They're written for a brain laid out a certain way: wiki pages in `00-OS/wiki/`, sources in `00-OS/raw/`, people in `People/`, loose stuff in `Inbox/`. Most of them make what they need the first time. Little Brain sets the whole thing up for you.
- `meeting-loop` and `song-loop` want a Mac with Apple Silicon and `ffmpeg` (`brew install ffmpeg`). They transcribe locally and set up their own Python environment on first run.
- `build` and `next` drive Matt Pocock's build skills. Install those too (link below).
- Updating: run the install again. In a Little Brain, say **update the skills**.

## Recommended from elsewhere

Other people's work. I use all of it.

- **Matt Pocock's skills**: `grill me`, `/teach`, `/wait-what`, `prototype`, TDD, and the ticket pipeline `build` and `next` run on. https://github.com/mattpocock/skills
- **ponytail**: makes the agent pick the laziest solution that works. https://github.com/DietrichGebert/ponytail
- **caveman**: short, blunt answers, a lot fewer tokens. https://github.com/JuliusBrussee/caveman
- **i-have-adhd**: shapes every answer for ADHD reading. Claude Code plugin. https://github.com/ayghri/i-have-adhd
- **Nano Banana**: Gemini image generation and editing. Bring your own Google AI key. https://github.com/gemini-cli-extensions/nanobanana
- **humanizer, the original**: the one mine is adapted from. https://github.com/blader/humanizer
- **skills CLI**: the `npx skills` installer above. https://github.com/vercel-labs/skills

## License

MIT, see `LICENSE`. Made by Jason Portillo.

`skills/humanizer/` is adapted from Siqi Chen's humanizer and keeps its own MIT license, in `skills/humanizer/LICENSE`. Details in `THIRD-PARTY-NOTICES.md`.
