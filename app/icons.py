from PySide6.QtWidgets import QApplication, QStyle, QAbstractButton
from PySide6.QtGui import QIcon, QGuiApplication
from PySide6.QtCore import QSize, QEvent, QObject, QTimer
import weakref
import logging
import time

log = logging.getLogger(__name__)

_ICON_THEME_CANDIDATES = {
    "add": ["list-add", "add", "document-new", "insert-object"],
    "copy": ["edit-copy", "copy", "document-duplicate"],
    "copy_all": ["edit-copy", "edit-select-all", "document-duplicate", "view-list-details"],
    "delete": ["edit-delete", "user-trash", "trash"],
    "edit": ["document-edit", "edit", "document-properties"],
    "filter": ["view-filter", "filter", "edit-find", "system-search"],
    "group": ["folder", "user-group", "system-users", "contact-group"],
    "group_add": ["list-add", "user-group-new", "list-add-user", "user-new"],
    "group_remove": ["list-remove", "list-remove-user", "user-group-delete", "user-trash"],
    "link": ["insert-link", "emblem-symbolic-link", "link", "mail-forward"],
    "more": ["view-more", "open-menu", "overflow-menu", "view-list"],
    "remove": ["list-remove", "remove", "edit-clear", "user-trash"],
    "settings": ["settings", "configure", "emblem-system", "preferences-system"],
}

_FALLBACK_STYLE_ICON = {
    "add": QStyle.SP_DialogYesButton,
    "copy": QStyle.SP_FileIcon,
    "copy_all": QStyle.SP_FileDialogListView,
    "delete": QStyle.SP_TrashIcon,
    "edit": QStyle.SP_FileDialogDetailedView,
    "filter": QStyle.SP_FileDialogContentsView,
    "group": QStyle.SP_DirIcon,
    "group_add": QStyle.SP_ArrowUp,
    "group_remove": QStyle.SP_ArrowDown,
    "link": QStyle.SP_DirLinkIcon,
    "more": QStyle.SP_TitleBarMenuButton,
    "remove": QStyle.SP_DialogNoButton,
    "settings": QStyle.SP_FileDialogDetailedView,
}

_icon_widgets = []                # list of (weakref, key, size)
_installed = False
_event_filter = None
_ICON_CACHE = {}                  # (key, size, style_name) -> QIcon

# debounce settings
_refresh_timer = None
_listener_installed_at = 0.0
GRACE_PERIOD_MS = 300
DEBOUNCE_MS = 50

# ------- utilities -------
def _current_style_name() -> str:
    app = QApplication.instance()
    if not app:
        return "no-app"
    try:
        style = app.style()
        return style.objectName() or style.metaObject().className()
    except Exception:
        return "unknown-style"

def _resolve_icon_uncached(key: str) -> QIcon:
    names = _ICON_THEME_CANDIDATES.get(key, [])
    for name in names:
        icon = QIcon.fromTheme(name)
        if not icon.isNull():
            return icon

    app = QApplication.instance()
    if app:
        style = app.style()
        fallback = _FALLBACK_STYLE_ICON.get(key)
        if fallback is not None:
            try:
                return style.standardIcon(fallback)
            except Exception:
                log.exception("style.standardIcon fallback failed")

    return QIcon()

def _resolve_icon(key: str, size: int) -> QIcon:
    style_name = _current_style_name()
    cache_key = (key, int(size), style_name)
    ico = _ICON_CACHE.get(cache_key)
    if ico is not None:
        return ico

    base = _resolve_icon_uncached(key)
    if not base.isNull():
        try:
            pm = base.pixmap(size, size)
            ico = QIcon(pm)
        except Exception:
            ico = base
    else:
        ico = base

    _ICON_CACHE[cache_key] = ico
    return ico

# ------- refresh logic -------
# Re-resolve icons for alive widgets; update only visible widgets.
def _refresh_icons():
    alive = []
    for ref, key, size in list(_icon_widgets):
        w = ref()
        if w is None:
            continue
        alive.append((ref, key, size))
        try:
            try:
                visible = w.isVisible()
            except Exception:
                visible = True
            if not visible:
                continue
            icon = _resolve_icon(key, size)
            w.setIcon(icon)
            w.setIconSize(QSize(size, size))
        except Exception:
            log.exception("Failed refreshing icon for %r", w)
    _icon_widgets[:] = alive

# Start or reset debounce timer.
def _refresh_icons_debounced():
    global _refresh_timer
    if _refresh_timer is None:
        _refresh_timer = QTimer()
        _refresh_timer.setSingleShot(True)
        _refresh_timer.timeout.connect(_refresh_icons)
    _refresh_timer.start(DEBOUNCE_MS)

# ------- event filter -------
class _IconEventFilter(QObject):
    def eventFilter(self, obj, event):
        if event.type() in (QEvent.PaletteChange, QEvent.StyleChange, QEvent.ApplicationPaletteChange):
            if (time.monotonic() - _listener_installed_at) * 1000.0 < GRACE_PERIOD_MS:
                return False
            _refresh_icons_debounced()
        return False

# ------- listener install -------
# Install listener deferred to avoid startup storms.
def _do_install():
    global _installed, _event_filter, _listener_installed_at
    if _installed:
        return
    _installed = True
    _listener_installed_at = time.monotonic()
    app = QApplication.instance()
    if not app:
        return
    try:
        QGuiApplication.paletteChanged.connect(lambda *_, **__: _refresh_icons_debounced())
        return
    except Exception:
        pass
    try:
        _event_filter = _IconEventFilter()
        app.installEventFilter(_event_filter)
    except Exception:
        log.exception("Failed to install event filter for icon refresh")

# Defer install to next event loop tick.
def _install_listener():
    app = QApplication.instance()
    if not app:
        return
    QTimer.singleShot(0, _do_install)

# ------- public API -------
# Apply a system icon to a QAbstractButton and auto-update on theme change.
def icon(widget: QAbstractButton, key: str, size: int = 14):
    _install_listener()

    ic = _resolve_icon(key, size)
    try:
        widget.setIcon(ic)
        widget.setIconSize(QSize(size, size))
    except Exception:
        pass

    # avoid duplicate entries
    for i, (ref, _, _) in enumerate(list(_icon_widgets)):
        if ref() is widget:
            del _icon_widgets[i]

    _icon_widgets.append((weakref.ref(widget), key, size))

def clear_cache():
    _ICON_CACHE.clear()