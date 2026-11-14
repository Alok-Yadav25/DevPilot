class DevPilotError(Exception):
    """An actionable, safe-to-display agent error (after redaction)."""


class UnsuitableRepository(DevPilotError):
    pass


class PatchRejected(DevPilotError):
    pass


class RunTimeout(DevPilotError):
    pass


class RunCancelled(DevPilotError):
    pass


class WorkerPaused(DevPilotError):
    """Internal control flow: persist the run and let another worker resume."""
