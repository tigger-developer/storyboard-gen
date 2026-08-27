# ABOUTME: Package configuration for storyboard-gen CLI tool and optional GUI.
# ABOUTME: Enables `pip install .` for CLI and `pip install .[gui]` for GUI.

from setuptools import find_packages, setup

setup(
    name="storyboard-gen",
    version="0.72.0",
    description="Generate video stills and clips from a YAML storyboard using AI image/video APIs",
    author="Tadhg O'Brien O'Brien",
    license="MIT",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    package_data={"storyboard_gen": ["templates/*"]},
    data_files=[("share/storyboard-gen/docs", ["docs/storyboard-gen-help.md"])],
    python_requires=">=3.12",
    install_requires=[
        "google-genai>=1.0.0",
        "python-dotenv>=1.0.0",
        "Pillow>=10.0.0",
        "pyyaml>=6.0",
    ],
    extras_require={
        "fal": ["fal-client>=0.5.0"],
        "replicate": ["replicate>=1.0.0"],
        "gui": ["PySide6>=6.6.0", "ruamel.yaml>=0.18.0"],
        "all": [
            "google-genai>=1.0.0",
            "fal-client>=0.5.0",
            "replicate>=1.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "storyboard-gen=storyboard_gen.cli:main",
            "storyboard-gen-gui=storyboard_gen.gui.__main__:main",
        ],
    },
)
