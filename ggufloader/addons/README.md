# Developing GGUF Loader Addons

> **Note:** Addons currently use PySide6 (Qt) widgets. The main app UI is
> React, but the addon system still runs in the Qt layer. This is a known
> gap — a future version may migrate addons to React.

Addons are small Python packages that plug into the GGUF Loader UI. The
**Floating Chat** addon (`ggufloader/addons/floating_chat/`) is the reference
implementation — read it alongside this guide.

## The addon contract

An addon is a **directory containing an `__init__.py`** that exposes a single
function:

```python
def register(parent=None) -> "QWidget | None":
    ...
```

- `parent` is the widget context the addon system provides (a dialog, or the
  main window when hosting in the sidebar).
- Return a **QWidget** to appear in the app (sidebar + an "Addon: \<name\>"
  dialog), or `None` for a purely background addon.
- The addon's package is imported as `ggufloader.addons.<name>`, so **relative
  imports inside the addon** (`from .widget import ...`) work as normal.

That's the whole API. Everything else — Qt widgets, `QSettings`, threads,
model access — is up to you.

## Where addons live

- **Bundled addons**: `ggufloader/addons/<name>/` in the repo. They ship inside
  the `ggufloader` package and are collected into the executable by
  `build_exe.spec` (which currently bundles only `floating_chat` — add your
  addon to `datas` and `hiddenimports` there to ship it in the exe).
- **User addons**: `AddonManager` scans the directory resolved by
  `ggufloader.resource_manager.find_addons_dir()` (in deployed apps this is the
  per-user data directory). Drop a folder with an `__init__.py` there and it is
  picked up on the next launch.

## How the manager loads an addon

`ggufloader/addon_manager.py` — `AddonManager`:

1. `scan_addons()` — lists subdirectories of the addons dir that contain an
   `__init__.py`.
2. `load_addon(name, path)` — imports the module as
   `ggufloader.addons.<name>`, checks it has `register`, and stores the callable.
3. The UI calls `get_addon_widget(name, parent)` to build the widget, and
   `open_addon_dialog(name, parent)` to host it in a non-modal dialog (reused
   while open).

If `register` is missing or raises, the addon is skipped and the error is
printed to the app log.

## Accessing the app and the model

Addons receive `parent` but shouldn't hard-code where the main window is.
The pattern used by Floating Chat:

1. If `parent` already looks like the main app (it exposes `model` and
   `model_loaded` attributes), use it directly.
2. Otherwise walk up the widget parent chain until you find the main window
   (the `ggufloader.ui.main_window.MainWindow` instance).

The main window is the only place to reach the loaded model. **Do not import
`llama_cpp` or instantiate your own runtime** — the app allows exactly one
model at a time, owned by `ModelBackend` (see `ARCHITECTURE.md`). Talk to the
model only through the app's engine/backend.

## Qt threading rules

- All widget creation and UI updates must happen on the **main thread** (the
  manager calls `register` there).
- Long-running work (model calls, file I/O) belongs in a worker thread; use
  `QThread`/signals like the app's services do (`ggufloader/services/`).

## Minimal example

```python
# my_addon/__init__.py  (drop into the addons dir, or ggufloader/addons/)
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel


def register(parent=None):
    widget = QWidget(parent)
    layout = QVBoxLayout(widget)
    layout.addWidget(QLabel("Hello from my GGUF Loader addon!"))
    return widget
```

## Checklist

- [ ] Directory with `__init__.py`
- [ ] Exposes `register(parent=None) -> QWidget | None`
- [ ] No direct `llama_cpp` imports — use the app's model only
- [ ] UI work on the main thread; blocking work in a worker thread
- [ ] Tested with `python main.py` (dev) — verify it loads in the sidebar
- [ ] If bundling in the exe: added to `build_exe.spec` datas + hiddenimports
