# storyboard-gen Command Help

Documentation version 1.0.

## Workflow

1. `storyboard-gen init [directory]` creates a project scaffold.
2. Edit `project.yaml` to define scenes, characters, and visual style.
3. Edit `.env` to configure provider credentials.
4. `storyboard-gen generate --all` generates stills and clips.
5. `storyboard-gen assemble` combines clips and stills into a final video.
6. `storyboard-gen kdenlive` exports a Kdenlive project for editing.
7. `storyboard-gen fcpxml` exports a Final Cut Pro project for editing.

## Providers

- Google: Imagen for stills and Veo for clips. Configure `GEMINI_API_KEY`, or set `USE_VERTEX=true` with Google Cloud credentials.
- FAL.ai: Flux, Kontext, and image/video models. Configure `FAL_KEY`.
- Replicate: Flux still models. Configure `REPLICATE_API_TOKEN`.

Configure providers in the `providers` section of `project.yaml` or with per-scene overrides. Store credentials in the project `.env` file.

## Project layout

- `project.yaml`: Storyboard definition with scenes, characters, and visual style.
- `.env`: API credentials. Do not commit this file.
- `references/`: Character and style reference images.
- `output/`: Generated stills, clips, editor projects, and assembled video.

For command-specific options, run `storyboard-gen <command> --help`.

README: {README_POINTER}
