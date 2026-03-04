class BaseAppError(Exception):
    """Base class for custom application errors."""
    pass


class ParsingError(BaseAppError):
    """Raised when parser fails to extract required information."""
    pass


class ClassificationError(BaseAppError):
    """Raised on classification rule mismatches."""
    pass


class CorrelationError(BaseAppError):
    """Raised on correlation problems."""
    pass


class EventBuildError(BaseAppError):
    """General event builder failure."""
    pass