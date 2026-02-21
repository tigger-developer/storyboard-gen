# storyboard-gen

Turn a YAML storyboard into AI-generated video. Define your scenes, characters, and visual style in a `project.yaml`, then let storyboard-gen handle the API calls, Ken Burns effects, and final assembly.

The idea is simple: separate the creative decisions (what your video looks like) from the plumbing (API clients, polling, file handling, FFmpeg commands). You focus on the storyboard; the tool does the rest.

## What it does

1. **Generate stills** — AI-rendered images from your scene prompts (Google Imagen, FAL Flux/Kontext, Replicate Flux)
2. **Generate clips** — AI-rendered video from your scene prompts (Google Veo, FAL Kling)
3. **Apply Ken Burns effects** — zoom, pan, and static effects on stills via FFmpeg
4. **Assemble** — concatenate everything in scene order with optional audio
5. **Export to Kdenlive** — full editing project (see below)

Multiple AI providers are supported — use one or mix and match per scene. See [docs/models.md](docs/models.md) for the full model reference.

### Kdenlive export

Where AI generation meets real video editing. The `kdenlive` command generates a complete Kdenlive project file — every scene on the timeline at the correct duration, Ken Burns effects as native Kdenlive transforms, audio included, and dissolve transitions between scenes. Open the `.kdenlive` file and you have a working first cut ready for editing: adjust timing, tweak keyframes, add titles, swap scenes, or re-render at any resolution.

```bash
storyboard-gen kdenlive                 # Export with default 15-frame dissolves
storyboard-gen kdenlive --dissolve 30   # 30-frame dissolves (1s at 30fps)
storyboard-gen kdenlive --no-dissolve   # Hard cuts, no transitions
```

## Quickstart

### Install via Homebrew (recommended)

```bash
brew install tigger04/tap/storyboard-gen
```

### Install from source

```bash
git clone https://github.com/tigger04/storyboard-gen.git
cd storyboard-gen
make install
source .venv/bin/activate
```

### Set up a project

```bash
storyboard-gen init ~/Movies/social/my-project
cd ~/Movies/social/my-project

# Edit .env with your provider credentials
# Edit project.yaml with your storyboard
# Add reference images to references/
```

See [docs/project-yaml-spec.md](docs/project-yaml-spec.md) for the full `project.yaml` schema.

### Generate and assemble

```bash
storyboard-gen validate                # Check project.yaml
storyboard-gen list                    # List all scenes
storyboard-gen generate --scene 1      # Generate one scene
storyboard-gen generate --all          # Generate everything
storyboard-gen assemble                # Assemble final video
storyboard-gen kdenlive                # Export Kdenlive project for editing
```

### GUI (optional)

An optional graphical interface provides visual scene management, image preview, and generation controls. Install with:

```bash
pip install storyboard-gen[gui]        # Or: make install-gui
storyboard-gen-gui                     # Launch the GUI
storyboard-gen-gui ~/Movies/my-proj    # Launch with a project
```

## Dependencies

- Python 3.12+
- FFmpeg (system install, must be on PATH)
- At least one provider SDK:
  - **Google:** `pip install storyboard-gen[google]` — requires GCP project or Gemini API key
  - **FAL.ai:** `pip install storyboard-gen[fal]` — requires FAL_KEY
  - **Replicate:** `pip install storyboard-gen[replicate]` — requires REPLICATE_API_TOKEN
  - **All providers:** `pip install storyboard-gen[all]`
  - **GUI:** `pip install storyboard-gen[gui]` — PySide6 (Qt6) graphical interface

## Documentation

| Document | Description |
|----------|-------------|
| [docs/VISION.md](docs/VISION.md) | Project vision, goals, and non-goals |
| [docs/architecture.md](docs/architecture.md) | Technical architecture and data flow |
| [docs/models.md](docs/models.md) | AI model reference — capabilities, options, safety defaults, choosing guide |
| [docs/project-yaml-spec.md](docs/project-yaml-spec.md) | Complete `project.yaml` schema with examples |

## Project structure

| File/Dir | Purpose |
|----------|---------|
| `src/storyboard_gen/` | Tool source code (CLI + optional GUI) |
| `src/storyboard_gen/gui/` | Optional PySide6 graphical interface |
| `tests/` | Test suite (421 tests) |
| `scripts/release.sh` | Release automation |
| `Makefile` | Build, test, lint, release targets |
| `CLAUDE.md` | Claude Code configuration |

## Makefile targets

| Target | Description |
|--------|-------------|
| `make install` | Create venv, install deps |
| `make install-gui` | Install with GUI dependencies (PySide6) |
| `make test` | Run all tests |
| `make lint` | Ruff check + format check |
| `make lint-fix` | Auto-fix lint issues |
| `make gui` | Launch the GUI |
| `make clean` | Remove build artefacts |
| `make release [VERSION=x.y.z]` | Full release: test, tag, GitHub release, Homebrew update |
| `make formula` | Update Homebrew formula SHA256 for current version |
| `make brew-upgrade` | Upgrade local Homebrew install |
| `make sync` | Git add/commit/pull/push |

## Per-project layout

Each video project is a directory containing:

```
my-project/
├── project.yaml      # Storyboard definition
├── .env              # API credentials (not committed)
├── audio.m4a         # Optional audio track for assembly
├── references/       # Character/style reference images
└── output/           # Generated assets (created by tool)
    ├── stills/       # Generated still images (PNG)
    ├── clips/        # Generated video clips (MP4)
    ├── intermediate/ # Ken Burns output (MP4)
    └── final/        # Assembled video
```

## Licence

MIT. Copyright Taḋg Paul O'Brien.
