# storyboard-gen

A CLI tool that generates video stills and clips from a YAML storyboard definition. Supports multiple AI providers: Google (Imagen/Veo), FAL.ai (Flux), and Replicate (Flux).

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
# Scaffold a new project directory
storyboard-gen init ~/Movies/social/my-project
cd ~/Movies/social/my-project

# Authenticate with Google Cloud
gcloud auth application-default login

# Edit .env with your credentials
# Edit project.yaml with your storyboard
# Add reference images to references/
```

### Use it

```bash
storyboard-gen init [directory]         # Create a new project
storyboard-gen validate                # Check project.yaml
storyboard-gen list                    # List all scenes
storyboard-gen generate --scene 1      # Generate one scene
storyboard-gen generate --all-stills   # All stills
storyboard-gen generate --all          # Everything
storyboard-gen assemble                # Assemble final video (with audio if configured)
storyboard-gen assemble --audio vo.m4a # Override audio track
storyboard-gen kdenlive                # Export Kdenlive project for editing
storyboard-gen kdenlive --dissolve 30  # Custom dissolve length
storyboard-gen kdenlive --no-dissolve  # Hard cuts, no transitions
storyboard-gen --version               # Show version
```

## Dependencies

- Python 3.12+
- FFmpeg (system install, must be on PATH)
- At least one provider SDK:
  - **Google:** `pip install storyboard-gen[google]` — requires GCP project or Gemini API key
  - **FAL.ai:** `pip install storyboard-gen[fal]` — requires FAL_KEY
  - **Replicate:** `pip install storyboard-gen[replicate]` — requires REPLICATE_API_TOKEN
  - **All providers:** `pip install storyboard-gen[all]`

## Project structure

| File/Dir | Purpose |
|----------|---------|
| `src/storyboard_gen/` | Tool source code |
| `tests/` | Test suite |
| `scripts/release.sh` | Release automation |
| `docs/VISION.md` | Project vision and goals |
| `docs/architecture.md` | Technical architecture |
| `docs/models.md` | AI model reference (capabilities, options, safety defaults) |
| `docs/project-yaml-spec.md` | project.yaml schema specification |
| `CLAUDE.md` | Claude Code configuration |
| `Makefile` | Build, test, lint, release targets |

## Makefile targets

| Target | Description |
|--------|-------------|
| `make install` | Create venv, install deps |
| `make test` | Run all tests |
| `make lint` | Ruff check + format check |
| `make lint-fix` | Auto-fix lint issues |
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
├── .env              # API credentials
├── audio.m4a         # Optional audio track for assembly
├── references/       # Character/style reference images
└── output/           # Generated assets (created by tool)
    ├── stills/       # Imagen output (PNG)
    ├── clips/        # Veo output (MP4)
    ├── intermediate/ # Ken Burns output (MP4)
    └── final/        # Assembled video
```

## Licence

MIT. Copyright Taḋg Paul
