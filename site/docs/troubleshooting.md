# Troubleshooting

Use the job or preview's exact status and issue code where possible; the suggestions below cover common states.

| State or symptom | What to do |
| --- | --- |
| **Port is occupied** / `Cannot listen on port` | If Orion is already running, open its existing local browser tab. Otherwise choose a different port, such as `--port 0`, which asks the launcher to select an available port. Do not terminate an unknown process just to free a port. |
| **Source unavailable** or scan finds nothing | Check that the folder exists and is accessible to your Windows account. Reconnect a NAS or external drive, verify permissions, then scan again. Symbolic links are not accepted as source roots. |
| **Provider credentials required/rejected** | Enter or replace the key in the provider's write-only settings field. Check that the provider supports the selected collection, then retry the lookup. |
| **Provider unavailable / rate limited** | Check network access and provider status, wait before retrying, or use another compatible provider. You can edit metadata manually while offline. |
| **Preview is stale / revalidation fails** | Source files, metadata, settings or destination contents changed. Read the new issue details, resolve them, and generate a fresh preview. Do not approve an old path list after changing settings. |
| **Destination exists / conflict** | Orion will not replace an existing file. Inspect both items, choose a supported conflict behavior, or select another destination, then preview again. |
| **Changed or missing file during retry/undo** | Leave the affected item protected. Find the file at its current location and review the operation record before attempting manual recovery. Orion will not assume changed content is the original file. |
| **Credential storage unavailable** | Follow Orion's explicit session-only option if you want to continue for this session, or restore OS keychain access and re-enter the credential. |
| **`fpcalc` unavailable** | Install the separately required AcoustID fingerprint utility and make it available to Orion, or use another compatible music provider. Fingerprinting remains optional. |
| **Local page says interface must be built** | From the repository, build with `npm --prefix frontend ci` and `npm --prefix frontend run build`, then restart Orion. |

For database migration or restore, first stop Orion and follow [recovery guidance](./recovery.html) and [runtime data details](./runtime.html). Keep a copy of the existing data directory before changing files. A database backup does not back up media files.

For an installation problem, check [install instructions](./install.html). For server authentication or refresh errors, see [Jellyfin and Emby](./integrations.html). When reporting a reproducible issue, include Orion version, OS, the visible error code and sanitized steps; never include API keys, credential-bearing URLs or personal media paths.
