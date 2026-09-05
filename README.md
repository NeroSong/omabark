# OmaBark

Send text from your Omarchy bar or terminal to your Apple device with [Bark](https://github.com/Finb/Bark).

![OmaBark — send text to your Apple device from your bar or terminal](preview.png)

## Installation

Requires Omarchy Quattro, Quickshell with Qt Quick Controls/Layouts, Python 3.10+
and GNU coreutils. Open-and-paste also requires `wl-clipboard` and Wayland.

```sh
omarchy plugin add https://github.com/NeroSong/omabark
omarchy plugin enable nerosong.omabark
```

## Usage

Open OmaBark from the bar, paste the test URL copied from Bark, and click
**Test and Save**. Custom HTTPS servers are supported. The notification title
is optional and defaults to **From Omarchy**.

Type or paste your text, then click **Send** or press **Ctrl+Enter**.
Long messages are split into numbered notifications, up to 32,000 UTF-8 bytes.
If a send fails, check your device before retrying; **Accepted** means the
server accepted it, not that the device displayed it.

## Keyboard shortcuts

Optional examples for `~/.config/hypr/bindings.lua`; choose unused key combinations:

```lua
-- Open OmaBark.
o.bind("SUPER + ALT + B", "Open OmaBark", "omarchy-shell shell summon nerosong.omabark '{}'")

-- Open and replace the draft with clipboard text.
o.bind("SUPER + ALT + SHIFT + B", "Paste into OmaBark", "omarchy-shell nerosong.omabark paste")
```

Paste does not send automatically. Bindings are configured manually.

## Command line

After configuring your device in the panel, add the command to `~/.local/bin`
(which must be on your PATH):

```sh
mkdir -p "$HOME/.local/bin"
ln -s "$HOME/.config/omarchy/plugins/nerosong.omabark/omabark" "$HOME/.local/bin/omabark"
```

```sh
omabark send "Build completed"
omabark send < notes.txt
omabark send --json "Build completed"
```

The CLI reuses your saved device and title. Use stdin for private text to avoid
shell history and process arguments. See `omabark send --help` for options.

## Privacy

Keys are stored in `~/.config/omabark/devices.json` (or under `$XDG_CONFIG_HOME`),
with owner-only permissions. They are not encrypted; keep this directory out of
public dotfile repositories. The selected Bark server can read notification
content. There is no telemetry, clipboard monitoring or message history.

Like other Omarchy plugins, OmaBark runs with your user permissions, without a
sandbox. See [SECURITY.md](SECURITY.md) for security details.

## Uninstall

```sh
omarchy plugin remove nerosong.omabark
```

If you installed the CLI link, remove it with `rm "$HOME/.local/bin/omabark"`.
Saved device configuration is retained; delete it separately to forget the device.

## License

[MIT](LICENSE). The bar/panel lifecycle follows Omarchy's MIT-licensed examples.
The original monochrome bar mark is inspired by the [Bark app icon](https://apps.apple.com/app/id1403753865).
OmaBark is an independent community plugin.
