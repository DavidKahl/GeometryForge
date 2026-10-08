# Security policy

## Trust model

GeometryForge runs **project code as trusted local code**. A project's `models/` scripts run inside Blender or Houdini, and its `checks/` run in your Python environment, all with your user's permissions and without a sandbox. Only open and run projects whose code you trust, the same as you would for any Blender add-on or Python script.

The viewer (`geometryforge viewer`) is designed for one user on one machine:

- It only accepts requests addressed to `127.0.0.1`/`localhost`.
- Changes (adding, renaming, archiving projects) need a per-session token and a same-origin request.
- It serves files only from inside a registered project's run records, and only of known types.
- It never runs project code or starts builds.

Don't expose the viewer port to a network or put it behind a public proxy.

## Supported versions

Security fixes go into the latest release on the `main` branch.

## Reporting a vulnerability

Please **don't open a public issue** for security problems. Use GitHub's [private vulnerability reporting](https://github.com/DavidKahl/GeometryForge/security/advisories/new) for this repository. Include what you found, how to reproduce it, and the impact you expect. You'll get an answer as soon as possible, and credit in the fix's release notes if you'd like.
