class StiltException(Exception):
    """Base class for STILT exceptions."""


class MeteorologyNotFound(StiltException):
    """Meteorological data not found in object storage."""


class NotFound(StiltException):
    """Resource does not exist."""


class SimulationResultException(StiltException):
    """Simulation completed but found unexpected result."""


class SimulationRuntimeException(StiltException):
    """A simulation execution error occurred."""


class XtrctException(StiltException):
    """Unable to subset input file to xtrct specifications."""


class XtrctGridException(XtrctException):
    """Unable to subset space subdomain from input file."""


class XtrctTimeException(XtrctException):
    """Unable to subset time subdomain from input file."""
