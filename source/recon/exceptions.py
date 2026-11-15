"""Structured exception hierarchy for minecraft-recon-framework."""


class ReconError(Exception):
    """Base exception for all recon network and protocol errors."""


class ProtocolFramingError(ReconError):
    """Raised when incoming wire bytes violate protocol framing or VarInt bounds."""


class AuthenticationError(ReconError):
    """Raised when RCON authentication fails (Request ID == -1) or login is rejected."""


class OnlineModeRequiredError(AuthenticationError):
    """Raised when an offline ghost client encounters an Encryption Request (0x01)."""
