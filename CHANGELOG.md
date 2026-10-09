# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [semantic versioning](https://semver.org/).

## [1.0.0] - 2026-10-09

First public release.

### Added

- Agent skill for Claude Code and Codex: brief, printer-aware planning, native modeling, incremental runs and honest reporting.
- Toolkit with incremental runs, evidence reuse, safe points, candidates, restore and adoption of manually edited Blender/Houdini scenes.
- Native Blender and Houdini backends with cross-application parity checks.
- Print exports (STL, 3MF) with mesh, bed-fit and round-trip checks, plus project-defined functional checks.
- Whole-model 3MF files on every run: an assembled model and a print kit with per-part filament slots. Optional Bambu Studio packaging arranges the kit onto plates with filament colours and verifies the result.
- Local browser viewer: projects, runs, part selection and isolation, assembly/print pose, side-by-side and overlay run comparison, filament colours, image viewer, downloads.
- `geometryforge doctor` reports Blender, Houdini and Bambu Studio.
- Showcase project: Astraeus Heavy Lander (22 parts, Blender + Houdini, four-filament plan).
- Bundled example: desk organizer.
- Self-contained browser tests on generated fixture projects, and CI on Windows and Linux.

[1.0.0]: https://github.com/DavidKahl/GeometryForge/releases/tag/v1.0.0
