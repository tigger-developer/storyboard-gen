#!/usr/bin/env bash
# ABOUTME: Release automation for storyboard-gen.
# ABOUTME: Bumps version, tags, creates GitHub release, updates Homebrew formula.

set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
HOMEBREW_TAP="${HOMEBREW_TAP_DIR:-$PROJECT_ROOT/../homebrew-tap}"
FORMULA="$HOMEBREW_TAP/Formula/storyboard-gen.rb"
CASK="$HOMEBREW_TAP/Casks/storyboard-gen-gui.rb"
GITHUB_REPO="tigger04/storyboard-gen"

SETUP_PY="$PROJECT_ROOT/setup.py"
INIT_PY="$PROJECT_ROOT/src/storyboard_gen/__init__.py"

usage() {
    cat >&2 <<USAGE
Usage: $(basename "$0") [VERSION]

  VERSION   Semantic version (x.y.z). If omitted, increments minor.

Examples:
  $(basename "$0")           # 0.1.0 -> 0.2.0
  $(basename "$0") 1.0.0     # explicit version
USAGE
    exit 2
}

get_current_version() {
    grep -E '__version__' "$INIT_PY" | sed 's/.*"\(.*\)".*/\1/'
}

increment_version() {
    local version="$1"
    local major minor patch
    IFS='.' read -r major minor patch <<< "$version"
    minor=$((minor + 1))
    patch=0
    echo "${major}.${minor}.${patch}"
}

update_version_files() {
    local new_version="$1"

    python3 << PYTHON
import re
from pathlib import Path

version = "${new_version}"

# Update setup.py
setup = Path("${SETUP_PY}")
content = setup.read_text()
content = re.sub(r'version=".*?"', f'version="{version}"', content)
setup.write_text(content)

# Update __init__.py
init = Path("${INIT_PY}")
content = init.read_text()
content = re.sub(r'__version__ = ".*?"', f'__version__ = "{version}"', content)
init.write_text(content)

print(f"Updated version to {version}")
PYTHON
}

create_github_release() {
    local version="$1"
    local tag="v${version}"

    echo "Creating GitHub release ${tag}..."
    gh release create "$tag" \
        --repo "$GITHUB_REPO" \
        --title "$tag" \
        --generate-notes
}

get_tarball_sha256() {
    local version="$1"
    local tag="v${version}"
    local url="https://github.com/${GITHUB_REPO}/archive/refs/tags/${tag}.tar.gz"

    echo "Fetching SHA256 for ${url}..." >&2
    curl -sL "$url" | shasum -a 256 | cut -d' ' -f1
}

build_and_upload_dmg() {
    local version="$1"
    local tag="v${version}"
    local dmg_name="storyboard-gen-gui-${version}.dmg"
    local dmg_path="$PROJECT_ROOT/dist/${dmg_name}"

    echo "Building macOS app bundle..."
    "$SCRIPT_DIR/build-macos.sh" "$version"

    if [[ ! -f "$dmg_path" ]]; then
        echo "Error: DMG not found at $dmg_path" >&2
        echo "App build may have failed. Skipping DMG upload." >&2
        return 1
    fi

    echo "Uploading DMG to GitHub release ${tag}..."
    gh release upload "$tag" "$dmg_path" \
        --repo "$GITHUB_REPO" \
        --clobber
}

get_dmg_sha256() {
    local version="$1"
    local dmg_path="$PROJECT_ROOT/dist/storyboard-gen-gui-${version}.dmg"

    if [[ ! -f "$dmg_path" ]]; then
        echo "Error: DMG not found at $dmg_path" >&2
        return 1
    fi

    shasum -a 256 "$dmg_path" | cut -d' ' -f1
}

update_homebrew_cask() {
    local version="$1"
    local sha256="$2"

    if [[ ! -f "$CASK" ]]; then
        echo "Warning: Cask file not found at $CASK — skipping cask update." >&2
        return 0
    fi

    python3 << PYTHON
import re
from pathlib import Path

version = "${version}"
sha256 = "${sha256}"
cask = Path("${CASK}")

content = cask.read_text()

# Update version
content = re.sub(
    r'version ".*?"',
    f'version "{version}"',
    content,
)

# Update SHA256
content = re.sub(
    r'sha256 ".*?"',
    f'sha256 "{sha256}"',
    content,
)

cask.write_text(content)
print(f"Updated cask to {version}")
PYTHON
}

update_homebrew_formula() {
    local version="$1"
    local sha256="$2"
    local tag="v${version}"

    if [[ ! -f "$FORMULA" ]]; then
        echo "Error: Homebrew formula not found at $FORMULA" >&2
        echo "Create the formula first, then re-run release." >&2
        exit 1
    fi

    # Sync tap repo before modifying formula (prevents push rejection)
    echo "Syncing Homebrew tap..."
    git -C "$HOMEBREW_TAP" pull --rebase origin main

    python3 << PYTHON
import re
from pathlib import Path

version = "${version}"
sha256 = "${sha256}"
tag = "${tag}"
formula = Path("${FORMULA}")

content = formula.read_text()

# Update URL
content = re.sub(
    r'url "https://github.com/${GITHUB_REPO}/archive/refs/tags/v.*\.tar\.gz"',
    f'url "https://github.com/${GITHUB_REPO}/archive/refs/tags/{tag}.tar.gz"',
    content,
)

# Update SHA256
content = re.sub(
    r'sha256 "[a-f0-9]+"',
    f'sha256 "{sha256}"',
    content,
)

formula.write_text(content)
print(f"Updated Homebrew formula to {version}")
PYTHON

    # Commit is handled by commit_homebrew_tap
}

commit_homebrew_tap() {
    local version="$1"

    echo "Committing Homebrew tap updates..."
    cd "$HOMEBREW_TAP"
    git add Formula/storyboard-gen.rb
    if [[ -f "$CASK" ]]; then
        git add Casks/storyboard-gen-gui.rb
    fi
    git commit -m "storyboard-gen ${version}"
    git push origin main
}

main() {
    cd "$PROJECT_ROOT"

    if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
        usage
    fi

    local current_version
    current_version=$(get_current_version)
    echo "Current version: ${current_version}"

    local new_version
    if [[ -n "${1:-}" ]]; then
        new_version="$1"
    else
        new_version=$(increment_version "$current_version")
    fi
    echo "New version: ${new_version}"

    if ! [[ "$new_version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        echo "Error: Invalid version format '${new_version}'. Use x.y.z" >&2
        exit 1
    fi

    # Ensure working directory is clean
    if ! git diff --quiet || ! git diff --cached --quiet; then
        echo "Error: Working directory has uncommitted changes" >&2
        exit 1
    fi

    # Run tests and lint
    echo "Running tests..."
    make test

    echo "Running lint..."
    make lint

    # Update version files
    echo "Updating version files..."
    update_version_files "$new_version"

    # Commit and tag
    git add "$SETUP_PY" "$INIT_PY"
    git commit -m "release: v${new_version}"
    git tag -a "v${new_version}" -m "Release v${new_version}"

    # Push
    echo "Pushing to origin..."
    git push origin master
    git push origin "v${new_version}"

    # Create GitHub release
    create_github_release "$new_version"

    # Wait for GitHub to process the release archive
    echo "Waiting for GitHub to generate release archive..."
    sleep 5

    # Fetch SHA256 and update Homebrew formula
    local sha256
    sha256=$(get_tarball_sha256 "$new_version")
    echo "SHA256: ${sha256}"

    update_homebrew_formula "$new_version" "$sha256"

    # Build macOS app bundle and upload DMG
    echo "Building macOS app bundle..."
    if build_and_upload_dmg "$new_version"; then
        local dmg_sha256
        dmg_sha256=$(get_dmg_sha256 "$new_version")
        echo "DMG SHA256: ${dmg_sha256}"
        update_homebrew_cask "$new_version" "$dmg_sha256"
    else
        echo "Warning: DMG build failed. Cask not updated." >&2
    fi

    # Commit and push all Homebrew tap changes
    commit_homebrew_tap "$new_version"

    echo ""
    echo "Release v${new_version} complete!"
    echo ""
    echo "Verify:"
    echo "  brew update"
    echo "  brew upgrade tigger04/tap/storyboard-gen"
    echo "  brew install --cask tigger04/tap/storyboard-gen-gui"
    echo "  storyboard-gen --version"
}

main "$@"
