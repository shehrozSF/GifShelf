# Gif Library

A small Windows desktop app for keeping your favourite GIF links in one place.
Save a GIF by URL (or local file), tag it, and copy its link back out with one click when you want to paste it into a chat.

- Animated or single-frame thumbnails for every saved GIF
- Tags, with the most-used tags listed first
- Search by title, URL or tag, and filter by several tags at once
- Light, dark or system theme
- Your library lives in one folder you can move (Settings > Database)

## Download

Get the installer from the [latest release](../../releases/latest) and run `GifLibrary-<version>-setup.exe`. It installs for your user only, so it doesn't need administrator rights.

Releases are currently not code-signed, so Windows may warn you:

- **SmartScreen** ("Windows protected your PC"): click *More info*, then *Run anyway*.
- **Smart App Control** blocks unsigned apps outright, with no option to run them. On those PCs, wait for a signed release or [run from source](#building-from-source).

## Where your data is stored

| | |
|---|---|
| Library (database + thumbnails) | `%LOCALAPPDATA%\GifLibrary` by default, or the folder you chose under Settings > Database |
| Settings (theme, library location) | `%LOCALAPPDATA%\GifLibrary\settings.ini` |

## Uninstalling

Uninstall from *Settings > Apps > Installed apps > Gif Library*. The
uninstaller asks separately whether to delete your library and your settings;
both default to *No*, so a reinstall picks up where you left off.

## Building from source

Requires Python 3.14 on Windows.

```bat
pip install -r requirements.txt
python main.py :: run the app
build.bat      :: build dist\GifLibrary\ and the installer
```

The installer step needs [Inno Setup 6](https://jrsoftware.org/isinfo.php)(`winget install JRSoftware.InnoSetup`).

Releases are built by GitHub Actions (`.github/workflows/release.yml`): bump `__version__` in `app/__init__.py`, then push a matching tag such as `v1.0.1`.
The workflow builds the installer and creates a draft release to review and
publish.

## Code signing policy

Free code signing provided by [SignPath.io](https://about.signpath.io/), certificate by [SignPath Foundation](https://signpath.org/).

> Signing is pending approval by SignPath Foundation; releases are unsigned until then.

Signed releases are built from this repository by GitHub Actions, and each
release is approved manually before it is signed.

Team roles:

- Committers and reviewers: [shehrozSF](https://github.com/shehrozSF)
- Approvers: [shehrozSF](https://github.com/shehrozSF)

## Privacy policy

This program will not transfer any information to other networked systems unless specifically requested by the user or the person installing or operating it.

The only network access is when you click *Load preview* for a web URL:
the app then downloads that GIF from the server you entered (which, like any web request, sees your IP address). There is no telemetry, analytics or update check. Everything else stays on your computer.

## License

[MIT](LICENSE)
