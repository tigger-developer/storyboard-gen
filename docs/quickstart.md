<!-- Version: 1.0 | Last updated: 2026-02-21 -->

# Quickstart

## Prerequisites

- **Python 3.12+**
- **FFmpeg** (must be on PATH)
- At least one AI provider account (see [models.md](models.md) for options)

### Installing FFmpeg

| Platform | Command |
|----------|---------|
| macOS | `brew install ffmpeg` |
| Ubuntu/Debian | `sudo apt install ffmpeg` |
| Fedora | `sudo dnf install ffmpeg` |
| Arch | `sudo pacman -S ffmpeg` |
| Windows | `winget install ffmpeg` or download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH |

---

## Install storyboard-gen

### macOS — Homebrew (recommended)

```bash
brew install tigger04/tap/storyboard-gen
```

This installs storyboard-gen with all provider SDKs. To upgrade later:

```bash
brew upgrade tigger04/tap/storyboard-gen
```

### macOS / Linux — pip

```bash
python3 -m venv ~/.local/share/storyboard-gen
source ~/.local/share/storyboard-gen/bin/activate
pip install storyboard-gen
```

Install provider SDKs as needed:

```bash
pip install storyboard-gen[google]      # Google Imagen + Veo
pip install storyboard-gen[fal]         # FAL.ai Flux, Kontext, Kling
pip install storyboard-gen[replicate]   # Replicate Flux
pip install storyboard-gen[all]         # All providers
pip install storyboard-gen[gui]         # Optional GUI (PySide6)
```

### Windows — pip

```powershell
python -m venv $env:LOCALAPPDATA\storyboard-gen
& "$env:LOCALAPPDATA\storyboard-gen\Scripts\Activate.ps1"
pip install storyboard-gen[all]
```

Or with `cmd.exe`:

```cmd
python -m venv %LOCALAPPDATA%\storyboard-gen
%LOCALAPPDATA%\storyboard-gen\Scripts\activate.bat
pip install storyboard-gen[all]
```

### From source (all platforms)

```bash
git clone https://github.com/tigger04/storyboard-gen.git
cd storyboard-gen
make install                            # macOS / Linux
source .venv/bin/activate
```

On Windows without `make`, use pip directly:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
```

---

## Set up a project

```bash
storyboard-gen init ~/Movies/my-project
cd ~/Movies/my-project
```

This creates:

| File | Purpose |
|------|---------|
| `project.yaml` | Storyboard definition — scenes, characters, style |
| `README.md` | Project overview |
| `.env` | API credentials (edit before use) |
| `.gitignore` | Excludes secrets and video output, keeps stills and Kdenlive |
| `references/` | Character/style reference images |
| `logs/` | Operation logs |

### Configure credentials

Edit `.env` with your provider credentials. You only need the providers you plan to use:

```bash
# Google (Vertex AI)
USE_VERTEX=true
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1

# OR Google (Gemini API key — simpler setup)
# GEMINI_API_KEY=your-key

# FAL.ai
# FAL_KEY=your-fal-key

# Replicate
# REPLICATE_API_TOKEN=your-token
```

See [models.md](models.md) for full authentication details per provider.

### Edit project.yaml

Define your storyboard — scenes, characters, visual style. See [project-yaml-spec.md](project-yaml-spec.md) for the full schema.

---

## Generate and assemble

```bash
storyboard-gen validate                # Check project.yaml
storyboard-gen list                    # List all scenes with status
storyboard-gen generate --scene 1      # Generate one scene
storyboard-gen generate --all          # Generate everything
storyboard-gen assemble                # Assemble final video with audio
storyboard-gen assemble --preview      # Assemble without audio
storyboard-gen kdenlive                # Export Kdenlive project for editing
```

### GUI (optional)

An optional graphical interface provides visual scene management, image preview, and generation controls:

```bash
pip install storyboard-gen[gui]        # Or: make install-gui (macOS/Linux)
storyboard-gen-gui                     # Launch the GUI
storyboard-gen-gui ~/Movies/my-proj    # Launch with a project
```

---

## See also

- [models.md](models.md) — full model reference with capabilities, options, and choosing guide
- [project-yaml-spec.md](project-yaml-spec.md) — complete `project.yaml` schema with examples
- [architecture.md](architecture.md) — technical architecture and data flow
- [VISION.md](VISION.md) — project goals and non-goals
