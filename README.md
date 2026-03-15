# storyboard-gen

Turn a YAML storyboard into AI-generated video. Define your scenes, characters, and visual style in a `project.yaml`, then let storyboard-gen handle the API calls, Ken Burns effects, and final assembly.

The idea is simple: separate the creative decisions (what your video looks like) from the plumbing (API clients, polling, file handling, FFmpeg commands). You focus on the storyboard; the tool does the rest.

## What it does

1. **Generate stills** — AI-rendered images from your scene prompts (Google Imagen, FAL Flux/Kontext/Ideogram, Replicate Flux)
2. **Generate clips** — AI-rendered video from your scene prompts (Google Veo, FAL Kling/Wan/MiniMax)
3. **Apply Ken Burns effects** — zoom, pan, and static effects on stills via FFmpeg
4. **Assemble** — concatenate everything in scene order with optional audio
5. **Export to Kdenlive** — full editing project (see below)

Multiple AI providers are supported — use one or mix and match per scene. See [docs/models.md](docs/models.md) for the full model reference.

### Kdenlive export

Where AI generation meets real video editing. The `kdenlive` command generates a complete Kdenlive project file — every scene on the timeline at the correct duration, Ken Burns effects as native Kdenlive transforms, and audio included. Open the `.kdenlive` file and you have a working first cut ready for editing: adjust timing, tweak keyframes, add titles, swap scenes, or re-render at any resolution.

```bash
storyboard-gen kdenlive                 # Export Kdenlive project for editing
```

<img width="2040" height="1279" alt="image" src="https://github.com/user-attachments/assets/62876b0d-e692-4615-b1d6-4553c26de6ce" />


## Quickstart

```bash
brew install tigger04/tap/storyboard-gen    # macOS (Homebrew)
pip install storyboard-gen[all]             # macOS / Linux / Windows (pip)

storyboard-gen init ~/Movies/my-project
cd ~/Movies/my-project
# Edit .env with your provider credentials
# Edit project.yaml with your storyboard

storyboard-gen generate --all               # Generate everything
storyboard-gen assemble                     # Assemble final video
storyboard-gen kdenlive                     # Export Kdenlive project
```

See [docs/quickstart.md](docs/quickstart.md) for full installation instructions (macOS, Linux, Windows), provider setup, and GUI.

<img width="803" height="783" alt="image" src="https://github.com/user-attachments/assets/ad0380aa-e18b-4c7d-b064-0c734321b941" />


## Dependencies

- Python 3.12+
- FFmpeg (must be on PATH — see [quickstart](docs/quickstart.md#installing-ffmpeg) for install commands)
- At least one provider SDK — see [docs/models.md](docs/models.md) for options

## Documentation

| Document | Description |
|----------|-------------|
| [docs/quickstart.md](docs/quickstart.md) | Installation (macOS, Linux, Windows), project setup, first run |
| [docs/VISION.md](docs/VISION.md) | Project vision, goals, and non-goals |
| [docs/architecture.md](docs/architecture.md) | Technical architecture and data flow |
| [docs/models.md](docs/models.md) | AI model reference — capabilities, options, safety defaults, choosing guide |
| [docs/project-yaml-spec.md](docs/project-yaml-spec.md) | Complete `project.yaml` schema with examples |

## Project structure

| File/Dir | Purpose |
|----------|---------|
| `src/storyboard_gen/` | Tool source code (CLI + optional GUI) |
| `src/storyboard_gen/gui/` | Optional PySide6 graphical interface |
| `tests/` | Test suite (1095 tests) |
| `scripts/release.sh` | Release automation |
| `Makefile` | Build, test, lint, release targets |

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
| `make app` | Build macOS .app bundle and DMG |
| `make release [VERSION=x.y.z]` | Full release: test, tag, GitHub release, Homebrew update |
| `make formula` | Update Homebrew formula SHA256 for current version |
| `make brew-upgrade` | Upgrade local Homebrew install (CLI + GUI) |
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
