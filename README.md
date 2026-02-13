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

### Set up credentials

```bash
# Authenticate with Google Cloud
gcloud auth application-default login

# Create a project directory
mkdir -p ~/Movies/social/my-project/references
cd ~/Movies/social/my-project

# Create .env with your credentials
cat > .env <<EOF
USE_VERTEX=true
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GCS_OUTPUT_BUCKET=gs://your-bucket-name/
EOF
```

### Use it

```bash
# Create project.yaml (see docs/VISION.md for schema)
# Add reference images to references/

storyboard-gen validate                # Check project.yaml
storyboard-gen list                    # List all scenes
storyboard-gen generate --scene 1      # Generate one scene
storyboard-gen generate --all-stills   # All stills
storyboard-gen generate --all          # Everything
storyboard-gen assemble                # Assemble final video
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
├── references/       # Character/style reference images
└── output/           # Generated assets (created by tool)
    ├── stills/       # Imagen output (PNG)
    ├── clips/        # Veo output (MP4)
    ├── intermediate/ # Ken Burns output (MP4)
    └── final/        # Assembled video
```

## Licence

MIT. Copyright Taḋg Paul O'Brien.
