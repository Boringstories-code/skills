# Threat model — what each finding category means

A Claude skill/tool/plugin runs with Claude's access to the machine. The attack surface isn't
"will this crash" — it's "what can this quietly do to me, my files, my secrets, or Claude's
behavior." Categories below map 1:1 to the scanner's tags.

## Secret / credential theft (CRITICAL)
- `SECRET-ACCESS` — reads `~/.ssh`, `.aws/credentials`, `.npmrc`, `.netrc`, keychains, browser
  cookie/login stores, or Claude's own `~/.claude/.credentials.json`. Almost never legitimate
  in a skill. This is the crown-jewel attack: steal the keys, own everything.
- `ENV-HARVEST` — dumps the whole environment (`printenv`, `JSON.stringify(process.env)`).
  Env vars routinely hold tokens. Wholesale harvest is a tell.
- `KEYCHAIN` — pulls from the OS secret store.

## Network callouts / exfil (HIGH–CRITICAL)
- `NETWORK` — any outbound request primitive. Legit for tools that fetch things; suspicious in
  tools that shouldn't need the network. The question is always *where* and *with what data*.
- `EXFIL-DEST` — the destination is a known drop site (webhook.site, discord webhook, telegram
  bot API, pastebin, ngrok, transfer.sh, odd TLDs). Strong signal of data theft.
- `REVERSE-SHELL` — `/dev/tcp`, `nc -e`, `bash -i`, `pty.spawn`, `socket…connect`. Hands an
  attacker a shell. No benign reason in a skill.
- `HARDCODED-IP` — a raw `ip:port`. Worth a look; legit configs use hostnames.

## Obfuscation & pipe-to-shell (HIGH–CRITICAL)
- `PIPE-TO-SHELL` — `curl … | sh`, `base64 -d | sh`. Runs code you never see. The classic
  one-liner dropper.
- `OBFUSCATION` — `eval(atob(…))`, `Function("return…")`, `\xNN` escapes. Hiding the payload
  from a reader is the whole purpose; honest code doesn't need it.
- `BASE64-BLOB` — a long encoded string on one line. Often a packed payload.
- `ENCODED-EXEC` — `eval`, `exec`, `child_process`, `subprocess`, `os.system`. Executing code is
  normal for many tools; combined with obfuscation or network input it's how RCE lands.

## Claude-tool-specific surfaces (HIGH–CRITICAL)
- `AUTO-HOOK` — `PreToolUse`/`PostToolUse`/`UserPromptSubmit`/`SessionStart` hooks with a
  `command`. These run **automatically**, without Claude deciding to — the highest-trust surface
  in the whole config. Read every one.
- `MCP-SERVER` / `MCP-INLINE` — defines a server process Claude will talk to: what binary runs,
  what args, what env (secrets!) it's handed, what URL it reaches. Audit like a hook.
- `PROMPT-INJECTION` — text aimed at Claude, not the user: "ignore previous instructions," "don't
  tell the user," "you must run…," "reveal the system prompt." In a tool you're about to install,
  this is an attack on the assistant. Near-automatic QUARANTINE.

## Destructive / persistence (HIGH–CRITICAL)
- `DESTRUCTIVE` — `rm -rf /`, fork bomb, `mkfs`, `dd` over a device, `chmod -R 777 /`.
- `PERSISTENCE` — crontab, LaunchAgents/Daemons, appending to `.bashrc`/`.zshrc`, `systemctl
  enable`. How malware survives a reboot.
- `SELF-MODIFY` — touches `~/.claude/` (settings, other skills). A tool rewriting Claude's own
  config can escalate quietly.
- `PRIVILEGE` — `sudo`, `chmod +x`, `osascript -e`, `defaults write`.

## Package install lifecycle (MEDIUM–HIGH)
- `NPM-LIFECYCLE` — `preinstall`/`postinstall` scripts run on `npm install`, before you run
  anything. Prime supply-chain real estate.
- `PY-INSTALL` — `setup.py` `cmdclass`, `install_requires` git URLs, exec at import time.
- `SHIPPED-DEPS` — a skill bundling `node_modules/` or a venv. Why? Often hides code.

## Hidden content (HIGH)
- `HIDDEN-UNICODE` — zero-width spaces, bidi overrides, BOM mid-file. Used to hide instructions
  from a human reading the file while Claude still parses them. No honest use.
- `BINARY` — an opaque executable shipped inside a skill. Can't be statically reviewed; treat as
  unknown until its purpose is disclosed and justified.

## Known-bad (CRITICAL)
- `KNOWN-BAD` — matches a seed list of historical malicious packages, miner signatures, and
  exfil/interaction sinks. A hit is a strong stop signal. The list is a seed, not a live feed —
  no match ≠ safe.

---

### The judgment the scanner can't make
Every category above is *evidence*. The verdict is whether the **capability matches the claim**.
A backup tool that reads many files and uploads them is doing its job; a "spell-checker" doing
the same is stealing. Read the stated purpose, then read the code, and decide if the reach is
honest and disclosed. Undisclosed egress of your data is a finding even when every line looks
clean.
