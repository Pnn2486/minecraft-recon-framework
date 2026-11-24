"""Reads settings.ini (README section 6)"""

import configparser
import difflib
import os
import re
from pathlib import Path

from recon.utils.versions import protocol_for_name

ENV_VAR = "RECON_CONFIG"
FILE_NAME = "settings.ini"
PROJECT_FILE = Path(__file__).resolve().parents[2] / FILE_NAME

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]{1,16}$")
TRUE_WORDS = {"1", "true", "yes", "on"}
FALSE_WORDS = {"0", "false", "no", "off"}


class SettingsError(ValueError):
    """The settings file can not be used, the message says why and where"""


# section -> name -> (kind, default, lowest, highest)
# kinds: bool, int, float, username, protocol
SPEC: dict[str, dict[str, tuple]] = {
    "defaults": {
        "port": ("int", 25565, 1, 65535),
        "rcon_port": ("int", 25575, 1, 65535),
        "timeout": ("float", 5.0, 0.1, 3600),
        "username": ("username", "AuditNode", None, None),
        "protocol_version": ("protocol", "auto", None, None),
        "duration": ("int", 30, 1, 86400),
        "diagnostics": ("bool", False, None, None),
        "quiet": ("bool", False, None, None),
    },
    "limits": {
        "max_timeout_seconds": ("int", 60, 1, 3600),
        "max_duration_seconds": ("int", 120, 1, 86400),
        "max_command_chars": ("int", 1000, 1, 10000),
        "max_password_chars": ("int", 256, 1, 1024),
        "max_output_lines": ("int", 5000, 100, 1000000),
        "max_line_chars": ("int", 100000, 100, 1000000),
        "keep_jobs": ("int", 10, 1, 100),
    },
    "web": {
        "port": ("int", 8765, 1, 65535),
        "open_browser": ("bool", True, None, None),
    },
    "chat": {
        "show_player_chat": ("bool", True, None, None),
        "show_system_chat": ("bool", True, None, None),
        "show_disguised_chat": ("bool", True, None, None),
        "show_plain_chat": ("bool", True, None, None),
        "show_kind_label": ("bool", True, None, None),
        "show_undecoded": ("bool", True, None, None),
        "timestamps": ("bool", False, None, None),
    },
    "output": {
        "show_keep_alives": ("bool", True, None, None),
    },
    "diagnostics": {
        "top_packets": ("int", 12, 1, 100),
        "max_undecoded_samples": ("int", 5, 0, 50),
    },
}

Values = dict[str, dict[str, object]]


def defaults() -> Values:
    return {section: {name: spec[1] for name, spec in names.items()} for section, names in SPEC.items()}


def _range_text(low, high) -> str:
    return f"from {low} to {high}"


def _convert(section: str, name: str, raw: str, origin: str) -> object:
    kind, _default, low, high = SPEC[section][name]
    where = f"{origin}: [{section}] {name}"
    text = raw.strip()
    if kind == "bool":
        lowered = text.lower()
        if lowered in TRUE_WORDS:
            return True
        if lowered in FALSE_WORDS:
            return False
        raise SettingsError(f"{where} must be true or false (got {raw!r})")
    if kind == "int":
        try:
            value = int(text)
        except ValueError:
            raise SettingsError(f"{where} must be a whole number {_range_text(low, high)} (got {raw!r})") from None
        if not low <= value <= high:
            raise SettingsError(f"{where} must be a whole number {_range_text(low, high)} (got {value})")
        return value
    if kind == "float":
        try:
            number = float(text)
        except ValueError:
            raise SettingsError(f"{where} must be a number {_range_text(low, high)} (got {raw!r})") from None
        if not low <= number <= high:
            raise SettingsError(f"{where} must be a number {_range_text(low, high)} (got {number})")
        return number
    if kind == "username":
        if not USERNAME_PATTERN.match(text):
            raise SettingsError(f"{where} must be 1 to 16 letters, digits or underscores (got {raw!r})")
        return text
    if kind == "protocol":
        if text.lower() == "auto":
            return "auto"
        if text.isdigit() or protocol_for_name(text) is not None:
            return text
        raise SettingsError(f"{where} must be auto, a protocol number or a Minecraft version such as 1.16.5 (got {raw!r})")
    raise SettingsError(f"{where} has an unknown kind {kind!r}")


def parse(text: str, origin: str = FILE_NAME) -> Values:
    """Reads the text of a settings file and gives back every value, filled in with the defaults"""
    parser = configparser.ConfigParser(interpolation=None, inline_comment_prefixes=("#", ";"), strict=True)
    try:
        parser.read_string(text)
    except configparser.Error as exc:
        raise SettingsError(f"{origin}: {str(exc).splitlines()[0]}") from None
    values = defaults()
    for section in parser.sections():
        if section not in SPEC:
            hint = difflib.get_close_matches(section, list(SPEC), n=1)
            extra = f" Did you mean [{hint[0]}]?" if hint else ""
            raise SettingsError(f"{origin}: unknown section [{section}].{extra}")
        for name, raw in parser.items(section):
            if name not in SPEC[section]:
                hint = difflib.get_close_matches(name, list(SPEC[section]), n=1)
                extra = f" Did you mean {hint[0]}?" if hint else ""
                raise SettingsError(f"{origin}: unknown setting {name} in [{section}].{extra}")
            values[section][name] = _convert(section, name, raw, origin)
    return values


def load(path: str | os.PathLike) -> Values:
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SettingsError(f"Could not read the settings file {path}: {exc.strerror or exc}") from None
    except UnicodeDecodeError:
        raise SettingsError(f"{path} is not a text file in UTF-8.") from None
    return parse(text, origin=str(path))


def find_file(explicit: str | None = None) -> Path | None:
    """The settings file to use, or None when there is none (a path you gave yourself must exist)"""
    if explicit:
        return Path(explicit)
    from_env = os.environ.get(ENV_VAR)
    if from_env:
        return Path(from_env)
    for candidate in (Path.cwd() / FILE_NAME, PROJECT_FILE):
        if candidate.is_file():
            return candidate
    return None


# --- the settings the running program uses -------------------------------------------------

_current: Values = defaults()
_origin: str | None = None
_configured = False


def current() -> Values:
    return _current


def get(section: str, name: str):
    return _current[section][name]


def origin() -> str | None:
    """The file the current settings came from, or None for the built-in values"""
    return _origin


def configured() -> bool:
    return _configured


def use(values: Values, source: str | None = None) -> None:
    global _current, _origin, _configured
    _current, _origin, _configured = values, source, True


def use_file(path: str | os.PathLike | None = None) -> None:
    """Finds and loads the settings file (or keeps the built-in values) and makes it the current one"""
    found = find_file(str(path) if path else None)
    if found is None:
        use(defaults(), None)
    else:
        use(load(found), str(found))


def reset() -> None:
    """Back to the built-in values, the tests use this"""
    global _current, _origin, _configured
    _current, _origin, _configured = defaults(), None, False
