# ABOUTME: Package configuration for storyboard-gen CLI tool.
# ABOUTME: Enables `pip install .` and `storyboard-gen` CLI entry point.

from setuptools import find_packages, setup

setup(
    name="storyboard-gen",
    version="0.19.0",
    description="Generate video stills and clips from a YAML storyboard using AI image/video APIs",
    author="Taḋg Paul O'Brien",
    license="MIT",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
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
        "all": [
            "google-genai>=1.0.0",
            "fal-client>=0.5.0",
            "replicate>=1.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "storyboard-gen=storyboard_gen.cli:main",
        ],
    },
)
