# Install and launch Orion

Orion is a local media app. Its public website includes a clearly labelled sample organiser; that demo uses fictional files and never accesses your computer. The standalone bundled app is for Windows; you can also run Orion from source on supported Python platforms.

## Windows bundle

If you have a verified Orion release archive, download it from the project's release page, verify the archive and checksum using the release instructions, then extract the entire archive into a new application folder. Keep the `_internal` directory beside `Orion.exe`; moving only the executable will break the app. Start `Orion.exe` and let it open its local browser window. The bundle does not require Node or a system Python installation. Windows builds are unsigned, so Windows may show an unknown-publisher prompt.

No published release is asserted by this guide. A CI artifact or locally built ZIP is not automatically a published release. To check release files, use the [release verification instructions](./github-delivery.html#draft-release-guard) and confirm the assets and checksums belong to the approved tag.

## Build and run from source

For source operation, use Python 3.11 or 3.12 and Node 24. The following PowerShell commands build and run Orion from a cloned repository on Windows:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install --require-hashes -r requirements-web.lock
npm --prefix frontend ci
npm --prefix frontend run build
.venv\Scripts\python -m orion --port 0
```

The launcher prints its loopback URL and opens it in your browser. Node is needed to build the interface, but not to run a Windows bundle. Keep Orion bound to the local machine; public network hosting is unsupported.

On Linux or macOS, install Python 3.11 or 3.12 and Node 24, then run these commands from the cloned repository:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements-web.lock
npm --prefix frontend ci
npm --prefix frontend run build
.venv/bin/python -m orion --port 0
```

The source launcher prints its loopback URL. To use a separate data directory and stop that instance later, for example on Linux or macOS:

```sh
.venv/bin/python -m orion --data-dir "$HOME/OrionData" --port 0 --no-browser
.venv/bin/python -m orion stop --data-dir "$HOME/OrionData"
```

Native Linux and macOS installers have not been verified; these commands describe source operation only.

To create a separate workspace for a trial or test, set its data directory explicitly:

```powershell
.venv\Scripts\python -m orion --data-dir "D:\OrionData" --port 0 --no-browser
.venv\Scripts\python -m orion stop --data-dir "D:\OrionData"
```

The default Windows data directory is `%APPDATA%\Orion`. The app stores its SQLite database and preferences there; provider credentials use the OS keychain. See [runtime data](./runtime.html) before migrating an existing installation, and [recovery](./recovery.html) for backup and restore steps.

## First launch

In Settings, add a source folder and a destination folder you control. Then follow the [first workflow](./workflow.html). Begin with a small test folder and inspect the generated preview carefully before approving any operation. Orion does not overwrite an existing destination file; an occupied path must be resolved through the selected conflict behavior.
