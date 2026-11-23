"""Summary of a test player session"""

import time
from collections import Counter
from dataclasses import dataclass, field

from recon import settings
from recon.protocols.chat import hex_preview, packet_kinds, readable_strings
from recon.protocols.ghost_profiles import GhostProfile


@dataclass
class SessionStats:
    profile: GhostProfile
    started: float = field(default_factory=time.monotonic)
    marks: dict[str, float] = field(default_factory=dict)
    counts: Counter = field(default_factory=Counter)
    sizes: Counter = field(default_factory=Counter)
    keep_alive_times: list[float] = field(default_factory=list)
    chat_ok: int = 0
    chat_failed: int = 0
    compression: int = -1
    end_reason: str = "time limit reached"
    samples: list[tuple[int, bytes]] = field(default_factory=list)

    def mark(self, name: str) -> None:
        self.marks.setdefault(name, time.monotonic() - self.started)

    def packet(self, state: str, pkt_id: int, size: int) -> None:
        self.counts[(state, pkt_id)] += 1
        self.sizes[(state, pkt_id)] += size

    def keep_alive(self) -> None:
        self.keep_alive_times.append(time.monotonic() - self.started)

    def chat(self, decoded: bool, pkt_id: int, data: bytes) -> None:
        if decoded:
            self.chat_ok += 1
            return
        self.chat_failed += 1
        if len(self.samples) < settings.get("diagnostics", "max_undecoded_samples"):
            self.samples.append((pkt_id, data))

    def _name(self, state: str, pkt_id: int) -> str:
        profile = self.profile
        if state == "play":
            if pkt_id == profile.play_keep_alive_in:
                return "keep alive"
            if pkt_id == profile.play_disconnect:
                return "disconnect"
            kind = packet_kinds(profile).get(pkt_id)
            if kind:
                return f"{kind} chat"
        if state == "configuration":
            names = {
                profile.config_keep_alive_in: "keep alive",
                profile.config_ping_in: "ping",
                profile.config_known_packs_in: "known packs",
                profile.config_finish_in: "finish configuration",
                profile.config_disconnect_in: "disconnect",
            }
            return names.get(pkt_id, "")
        return ""

    def report(self) -> list[str]:
        elapsed = max(time.monotonic() - self.started, 0.001)
        total_packets = sum(self.counts.values())
        total_bytes = sum(self.sizes.values())
        lines = ["[#] --- Session diagnostics ---", f"[#] protocol: {self.profile.protocol} ({self.profile.name})"]
        steps = [f"{label} {self.marks[key] * 1000:.0f} ms" for key, label in (("connected", "connected"), ("login", "login success"), ("play", "play state")) if key in self.marks]
        if steps:
            lines.append("[#] timeline: " + ", ".join(steps))
        if self.compression >= 0:
            lines.append(f"[#] compression threshold: {self.compression} bytes")
        lines.append(f"[#] packets received: {total_packets} ({total_bytes} bytes) in {elapsed:.1f} s, {total_packets / elapsed:.1f} per second")
        if self.keep_alive_times:
            gaps = [b - a for a, b in zip(self.keep_alive_times, self.keep_alive_times[1:], strict=False)]
            interval = f", about every {sum(gaps) / len(gaps):.1f} s" if gaps else ""
            lines.append(f"[#] keep-alives echoed: {len(self.keep_alive_times)}{interval}")
        lines.append(f"[#] chat packets: {self.chat_ok} decoded, {self.chat_failed} not decoded")
        lines.append(f"[#] ended because: {self.end_reason}")
        for (state, pkt_id), count in self.counts.most_common(settings.get("diagnostics", "top_packets")):
            lines.append(f"[#] packet {state} 0x{pkt_id:02X} count={count} bytes={self.sizes[(state, pkt_id)]} name={self._name(state, pkt_id) or 'other'}")
        for pkt_id, data in self.samples:
            hints = readable_strings(data)
            lines.append(f"[#] undecoded chat 0x{pkt_id:02X}: {hex_preview(data)}")
            if hints:
                lines.append("[#] readable text inside it: " + " | ".join(hints))
        return lines
