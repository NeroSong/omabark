# Security

OmaBark is an independent, unsandboxed Omarchy community plugin. It runs with
the current user's permissions. Source review and marketplace checks do not
provide a sandbox, certification or guarantee.

## Trust boundaries

- Explicit Send, Test and Save, or CLI send actions transmit the notification
  title, text and device key to the configured Bark server over HTTPS. That
  server can read them. Optional Bark payload encryption is not implemented.
- Certificates are verified using Python's default trust store. Redirects are
  refused, including redirects to another HTTPS host. System proxy environment
  variables are respected. Users must trust their chosen server and local TLS
  trust configuration.
- Keys are plaintext in owner-only private configuration (`0700` directory,
  `0600` files), separate from the plugin and bar settings. Files are checked
  for ownership, type and permissions, opened without following symlinks, read
  with size limits, and replaced atomically under a lock. These permissions
  do not protect against root or another process running as the same user.
- The worker receives JSON over stdin. Text and keys are never interpolated
  into a shell command. Python runs in isolated mode with a fixed executable
  path. CLI message arguments can be visible in process listings and shell
  history; use stdin for private text.
- No response bodies or credentials are included in errors. There is no
  telemetry, message history, automatic clipboard access, background polling,
  privilege elevation, downloaded executable code, or service installation.
- The explicit `paste` IPC action reads clipboard text once through a bounded,
  asynchronous worker. It never sends automatically or installs a keybinding.
  Clipboard failures leave the draft intact. Ordinary open does not read it.
- A test must be accepted before replacing configuration. Concurrent changes
  are detected. Failure preserves the previous configuration. Reusing a saved
  key cannot silently change its destination server.
- Input, response and file sizes are bounded. Requests have socket timeouts
  and workers have an independent alarm, outer process deadline and GUI
  watchdog. Startup failure and termination are handled without synchronous
  waits in QML. Sends are never automatically
  retried. An interrupted connection may already have delivered a notification;
  acceptance does not confirm that an Apple device displayed it.

## Reporting

Do not post real keys, copied Bark URLs, message text, or private configuration
in public issues. Use [GitHub private vulnerability reporting](https://github.com/NeroSong/omabark/security/advisories/new)
to report a suspected vulnerability confidentially.

See [VALIDATION.md](VALIDATION.md) for the dated local review and remaining
release checks. Marketplace review applies to an exact submitted commit and
does not automatically cover later edits.
