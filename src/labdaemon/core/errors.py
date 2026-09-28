"""Exception hierarchy. `message` is shown to users; `detail` goes to the log."""


class LabError(Exception):
    def __init__(self, message: str, *, detail: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail


class TransportError(LabError):
    """The link to a board failed: port missing, busy, not permitted, or gone."""


class PortNotFound(TransportError):
    pass


class PortBusy(TransportError):
    pass


class PermissionDenied(TransportError):
    pass


class ProtocolError(LabError):
    """The board answered, but not as the LabInt wire protocol requires."""


class ProtocolTimeout(ProtocolError):
    pass


class BadReply(ProtocolError):
    pass


class UnsupportedProtocol(ProtocolError):
    pass


class DeviceError(LabError):
    """The board reported `ERR code message`."""

    def __init__(self, code: int, message: str, *, detail: str | None = None) -> None:
        super().__init__(message, detail=detail)
        self.code = code


class LimitReached(DeviceError):
    pass


class Interrupted(DeviceError):
    pass


class ParameterError(LabError):
    """A value is not valid for a parameter."""


class PolicyLocked(LabError):
    """A setting is fixed by the machine policy."""


class PluginError(LabError):
    pass


class PluginLoadError(PluginError):
    pass


class ApiVersionMismatch(PluginError):
    pass


class ExperimentError(LabError):
    pass


class NotReady(ExperimentError):
    pass
