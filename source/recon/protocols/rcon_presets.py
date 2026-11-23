"""Ready-made RCON command sets, they only read and never change anything"""

PRESETS: dict[str, tuple[str, ...]] = {
    "overview": ("list", "version", "difficulty", "seed", "time query daytime", "whitelist list", "tps"),
    "performance": ("tps", "mspt", "forge tps", "spark tps", "list"),
    "plugins": ("plugins", "version", "paper version"),
    "players": ("list uuids", "whitelist list", "banlist players", "banlist ips"),
    "world": ("seed", "time query daytime", "time query gametime", "time query day", "difficulty", "worldborder get"),
}

PRESET_LABELS: dict[str, str] = {
    "overview": "Overview (players, version, time, whitelist)",
    "performance": "Performance (TPS and tick time)",
    "plugins": "Plugins and software version",
    "players": "Players, whitelist and bans",
    "world": "World (seed, time, difficulty, border)",
}
