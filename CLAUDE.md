# Project Instructions for AI Agents

This file provides instructions and context for AI coding agents working on this project.

<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:6cd5cc61 -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

**Architecture in one line:** issues live in a local Dolt DB; sync uses `refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md for details and anti-patterns.

## Agent Context Profiles

The managed Beads block is task-tracking guidance, not permission to override repository, user, or orchestrator instructions.

- **Conservative (default)**: Use `bd` for task tracking. Do not run git commits, git pushes, or Dolt remote sync unless explicitly asked. At handoff, report changed files, validation, and suggested next commands.
- **Minimal**: Keep tool instruction files as pointers to `bd prime`; use the same conservative git policy unless active instructions say otherwise.
- **Team-maintainer**: Only when the repository explicitly opts in, agents may close beads, run quality gates, commit, and push as part of session close. A current "do not commit" or "do not push" instruction still wins.

## Session Completion

This protocol applies when ending a Beads implementation workflow. It is subordinate to explicit user, repository, and orchestrator instructions.

1. **File issues for remaining work** - Create beads for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **Handle git/sync by active profile**:
   ```bash
   # Conservative/minimal/default: report status and proposed commands; wait for approval.
   git status

   # Team-maintainer opt-in only, unless current instructions forbid it:
   git pull --rebase
   git push
   git status
   ```
5. **Hand off** - Summarize changes, validation, issue status, and any blocked sync/commit/push step

**Critical rules:**
- Explicit user or orchestrator instructions override this Beads block.
- Do not commit or push without clear authority from the active profile or the current user request.
- If a required sync or push is blocked, stop and report the exact command and error.
<!-- END BEADS INTEGRATION -->


## Decision Records (Beads)

> Bu bölüm yönetilen Beads bloğunun DIŞINDADIR; `bd setup claude` yeniden
> çalıştırıldığında silinmez.

Before changing an existing workaround, architecture, pin mapping,
dependency version, timing value, or bug fix, run `bd prime` and inspect
the relevant Beads records.

After every meaningful bug fix or behavioral change, save:
- problem,
- decision,
- reason,
- affected files and symbols,
- failed approaches,
- validation/test result,
- related commit SHA,
- conditions under which the decision may be reverted.

Never revert a recorded decision silently. Explain the conflict and obtain
user approval before replacing it.

## Build & Test

Tüm komutlar `pcbqa/` dizininden, **sanal ortam yorumlayıcısıyla** çalışır.
Sistem `python`'ı kullanmayın: `pyyaml` ve `kicad-python` yalnızca `.venv`
içindedir.

```bash
# Test (cerceve unittest'tir, pytest DEGIL - pytest kurulu degil)
.venv\Scripts\python.exe -m unittest discover -s tests    # 277 test, ~2-3 dk

# Tek modul
.venv\Scripts\python.exe -m unittest tests.test_copper_rules

# Calistirma
run.cmd <proje> [secenekler]

# Bagimliliklar
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Derleme adımı yoktur (saf Python; setup.py/pyproject.toml da yok).

## Architecture Overview

KiCad üzerinde **otomatik bileşen yerleştirme + kalite denetimi** yapan bir
Python aracı. Gömülü firmware değildir: C/C++ kaynağı ve `compile_commands.json`
yoktur.

Katmanlar (her katman yalnızca altındakini bilir):

1. **Ayrıştırma** — `sexpr.py` (bağımlılıksız s-expression), `pcb.py`
   (`.kicad_pcb`: bileşen, pad, iz, via), `schematic.py`, `netlist.py`
2. **Model** — `model.py` (`Design`, `PinRef`), `geom.py`. **KiCad'i bilmez.**
3. **Kurallar** — `rules.py` (11 kural tipi, YAML), `ipc2221.py` (IPC-2221B
   hesapları), `presets/` (kaynaklı eşik kütüphanesi)
4. **Yerleştirme** — `placement/` (`auto` üretim yerleştiricisi)
5. **Yazma** — `ipc_apply.py` (IPC), `sch_*.py`, `pcb_sync.py`
6. **ML** — `ml/` (model karar vermez, hamle sırası önerir)

Ayrıntı: `pcbqa/HANDOFF.md` (tam bağlam), `pcbqa/README.md`,
`pcbqa/docs/tasarim-kurallari/` (kural eşiklerinin kaynakları).

## Conventions & Patterns

- **Kod ve YAML ASCII'dir**; dokümanlar (`.md`) tam Türkçe. Kod içi yorumlar da
  Türkçe ama ASCII harflerle (`aciklik`, `genislik`).
- Yorumlar **nedeni** anlatır, ne yaptığını değil. Ölçülmüş bir sayı varsa
  yorumda geçer (ör. "0.03 mm cakisma TO-92'de yanlis alarm uretiyordu").
- Kural eşiklerinin **kaynağı yazılır**; kaynağı olmayanlar "mühendislik
  seçimi" diye etiketlenir. Uydurma sayı yazılmaz.
- Testler davranıştan çok **sessizliği** korur: sağlam bir gerçek kartta
  (`samples/pic_programmer`) bakır kuralları sıfır bulgu üretmelidir.
- Netlist değişmezliği kutsaldır: yerleştirme bağlantıyı asla değiştirmez.
- KiCad açıkken dosyaya yazılmaz (açık-proje koruması).
