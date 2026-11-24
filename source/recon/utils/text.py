"""Turns Minecraft text components into plain text"""

import json
import re
from typing import Any

SECTION_CODES = re.compile("§.")
MAX_DEPTH = 32

# A short list of the keys that chat and join/leave messages use. Everything else falls back to "key: args".
TRANSLATIONS = {
    "chat.type.text": "<%s> %s",
    "chat.type.announcement": "[%s] %s",
    "chat.type.emote": "* %s %s",
    "chat.type.admin": "[%s: %s]",
    "chat.type.team.text": "%s <%s> %s",
    "commands.message.display.incoming": "%s whispers to you: %s",
    "commands.message.display.outgoing": "You whisper to %s: %s",
    "multiplayer.player.joined": "%s joined the game",
    "multiplayer.player.left": "%s left the game",
    "multiplayer.player.joined.renamed": "%s (formerly known as %s) joined the game",
    "chat.type.advancement.task": "%s has made the advancement %s",
    "chat.type.advancement.goal": "%s has reached the goal %s",
    "chat.type.advancement.challenge": "%s has completed the challenge %s",
    "death.attack.generic": "%s died",
    "death.attack.player": "%s was slain by %s",
    "death.attack.mob": "%s was slain by %s",
    "death.attack.fall": "%s hit the ground too hard",
    "death.attack.lava": "%s tried to swim in lava",
    "death.attack.drown": "%s drowned",
    "death.attack.outOfWorld": "%s fell out of the world",
    "commands.list.players": "There are %s of a max of %s players online: %s",
}


def strip_codes(text: str) -> str:
    return SECTION_CODES.sub("", text)


def _fill(template: str, args: list[str]) -> str:
    """Fills %s and %1$s style placeholders. Missing arguments become empty text"""
    counter = iter(range(len(args)))

    def pick(match: re.Match) -> str:
        if match.group(1):
            index = int(match.group(1)) - 1
        else:
            index = next(counter, len(args))
        return args[index] if 0 <= index < len(args) else ""

    return re.sub(r"%(?:(\d+)\$)?s", pick, template).replace("%%", "%")


def component_to_text(component: Any, depth: int = 0) -> str:
    if depth > MAX_DEPTH or component is None:
        return ""
    if isinstance(component, bool):
        return "true" if component else "false"
    if isinstance(component, str):
        return component
    if isinstance(component, int | float):
        return str(component)
    if isinstance(component, list):
        return "".join(component_to_text(part, depth + 1) for part in component)
    if not isinstance(component, dict):
        return ""
    text = ""
    if "text" in component:
        text = component_to_text(component["text"], depth + 1)
    elif "translate" in component:
        key = str(component["translate"])
        raw_args = component.get("with")
        args = [component_to_text(arg, depth + 1) for arg in raw_args] if isinstance(raw_args, list) else []
        fallback = component.get("fallback")
        template = TRANSLATIONS.get(key) or (fallback if isinstance(fallback, str) else None)
        text = _fill(template, args) if template else (f"{key}: {', '.join(args)}" if args else key)
    elif "score" in component and isinstance(component["score"], dict):
        text = component_to_text(component["score"].get("value", ""), depth + 1)
    elif "selector" in component:
        text = component_to_text(component["selector"], depth + 1)
    elif "keybind" in component:
        text = component_to_text(component["keybind"], depth + 1)
    extra = component.get("extra")
    if isinstance(extra, list):
        text += "".join(component_to_text(part, depth + 1) for part in extra)
    return text


def json_text_to_plain(raw: str) -> str:
    """Plain text of a JSON text component. Text that is not JSON is returned as it is"""
    try:
        return strip_codes(component_to_text(json.loads(raw)))
    except (ValueError, RecursionError):
        return strip_codes(raw)
