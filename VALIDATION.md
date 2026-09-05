# Validation record

Validated locally on 2026-09-06 against the installed Omarchy Quattro shell.

| Check | Result |
| --- | --- |
| Official `omarchy plugin validate .` | Pass, schema v1 and safe entry points |
| Python unit and CLI subprocess tests | 53 passed |
| Actual QML composer and setup rendering | Rendered offscreen and visually inspected |
| Real Wayland plugin load | Pass, no QML errors in the final smoke run |
| QML → Python stdin protocol | Save, list and remove passed using private temporary storage |
| Panel lifecycle | Open/close repeated twice; state assertions passed |
| Explicit paste IPC | Temporary real IPC route opened the panel; clipboard worker mocked |
| Fault injection | Hung worker, GUI watchdog, malformed JSON and startup failure handled; recovery and event-loop heartbeat verified |
| Persistent-title configuration wiring | Title stored with the single device; default and reuse for subsequent sends verified |
| `qmllint` with resolved `qs` imports | Dynamic `QObject` properties and Quickshell `QProcess::ExitStatus` metadata warnings remain; runtime load passed |
| Real Bark / APNs / device delivery | Not exercised by automated checks; device receipt is not independently verified |
| Marketplace approval | Not submitted |

The Python tests cover HTTPS configuration, copied URLs and custom base paths,
private permissions, symlink rejection, corrupt files, credential redaction,
exact JSON text preservation, Unicode and JSON-escape chunk budgets, partial
failure without retries, a total send deadline, API errors, response size bounds,
redirect refusal, input limits, and the executable worker protocol. Network
responses are mocked, including the required pre-save test notification; no production endpoint is contacted by these tests.

The native smoke run uses `tests/smoke.py`; it copies runtime files into a
temporary harness and uses a dummy key, disposable configuration and a stubbed
HTTP transport in the temporary worker. One native rerun initially observed a closed panel at its open-state assertion;
the next complete run passed. The cause was not established; the native harness
shares the desktop and is sensitive to outside dismissal. No plugin
installation, shell.json changes or notification sends are performed.

Before publishing, finish hands-on checks of mouse, keyboard/IME, clipboard,
multiple monitors, narrow screens, theme changes, and enable/disable/removal in
an installed copy. Test real device receipt, offline behavior and numbered long
messages using your own Bark key. The shipped preview uses a dummy recipient.

Official references were checked on the same date and are linked in README.md.
This is a local source review and test record, not an independent security audit
or marketplace certification.

CLI subprocess tests cover argument/stdin Unicode text, trailing newlines, dash-prefixed text, JSON output, empty/invalid/oversized input, missing configuration, failures and partial results, symlink installation, help and usage exit codes. HTTP is stubbed only in a temporary helper; no production notification is sent.

## Security review, 2026-09-06

Reviewed all production QML, Python, manifest, installation/removal instructions
and the CLI against the current official marketplace security and submission
policies. No unresolved high-severity issue was identified within this scope.
This statement is not an automated marketplace baseline result.

The review fixed unhandled HTTP protocol failures (such as truncated responses)
so they produce redacted, structured errors with partial-send counts, and added
handling for JSON recursion errors in input, storage and server responses.
Additional regression tests cover CLI interruption stopping the worker before
a later simulated send, lock-file symlinks, FIFO storage without blocking,
shared directory permissions and concurrent changes during Test and Save.

The source contains no installer hook, privilege escalation, remote code
execution, service unit, bundled executable binary or plugin-internal symlink.
The CLI is a readable Python script. Private configuration is outside the
project. README documents dependencies, installation, removal and plaintext
storage/server trust. The Chinese README and its link were removed.

Before submission:

- Complete the real-device and remaining desktop acceptance checks above.
- Use the full published commit SHA when requesting marketplace validation.
- Check that `nerosong.omabark` is still globally available, including retired
  marketplace IDs, immediately before submission.
- Keep the repository's private vulnerability reporting channel enabled.
- Run marketplace validation/security-baseline checks for that exact SHA and
  obtain the required maintainer approval. The local schema validator does not
  run the marketplace baseline or grant approval.

Policy references: [security policy](https://github.com/omacom/omarchy-plugin-marketplace/blob/main/SECURITY.md)
and [submission requirements](https://github.com/omacom/omarchy-plugin-marketplace/blob/main/SUBMISSION.md).

The fault harness (`tests/failures.py`) copies the real backend into an isolated
Quickshell process and shortens deadlines only in that disposable copy. It
verifies that a QML heartbeat continues during hangs, the worker is terminated,
and a subsequent operation succeeds. A missing executable releases busy state
without waiting for the watchdog. This does not prove that all possible kernel,
compositor or Qt failures are recoverable.

The promotional `preview.png` was composed with image generation from
`assets/composer.png`, a real Wayland capture of the current composer in a
temporary harness with harmless sample text and no real device configuration.
