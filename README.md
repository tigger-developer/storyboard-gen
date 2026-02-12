# storyboard-gen

A CLI tool that generates video stills and clips from a YAML storyboard definition, using Google AI APIs (Imagen for stills, Veo for video clips).

## Quickstart

```bash
# Install
git clone <repo-url> && cd storyboard-gen
make install
source .venv/bin/activate

# Authenticate (Vertex AI)
gcloud auth application-default login

# Create a project directory
mkdir -p ~/Movies/social/my-project/references
cd ~/Movies/social/my-project

# Create .env with your credentials
cp /path/to/storyboard-gen/.env.example .env
# Edit .env with your GCP project details

# Create project.yaml (see docs/VISION.md for schema)
# Add reference images to references/

# Validate
storyboard-gen validate

# List scenes
storyboard-gen list

# Generate
storyboard-gen generate --scene 1        # Single scene
storyboard-gen generate --all-stills     # All stills
storyboard-gen generate --all            # Everything

# Assemble (applies Ken Burns to stills, concatenates all)
storyboard-gen assemble
```

## Dependencies

- Python 3.12+
- FFmpeg (system install, must be on PATH)
- Google Cloud SDK (`gcloud`) for Vertex AI authentication
- A Google Cloud project with Vertex AI enabled, or a Gemini API key

## Project structure

| File/Dir | Purpose |
|----------|---------|
| `src/storyboard_gen/` | Tool source code |
| `tests/` | Test suite |
| `docs/VISION.md` | Project vision and goals |
| `docs/architecture.md` | Technical architecture |
| `CLAUDE.md` | Claude Code configuration |
| `Makefile` | Build, test, lint targets |

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
