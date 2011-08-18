__all__ = ('FlagException', 'ModelCannotBeFlaggedException', 'ContentAlreadyFlaggedByUserException', 'ContentFlaggedEnoughException', 'FlagCommentException')

class FlagException(Exception):
    """
    Base class for django-flag exceptions
    """
    pass

class ModelCannotBeFlaggedException(FlagException):
    """
    Exception raised when a user try to flag a object that is not defined
    in the FLAG_MODELS settings (only if this settings if defined)
    """
    pass

class ContentAlreadyFlaggedByUserException(FlagException):
    """
    Exception raised when a user try to flag an object he had
    already flagged and the number of its flags raised the
    LIMIT_SAME_OBJECT_FOR_USER value
    """
    pass

class ContentFlaggedEnoughException(FlagException):
    """
    Exception raised when someone try to flag an object which is
    already flagged and the LIMIT_FOR_OBJECT is raised
    """
    pass

class FlagCommentException(FlagException):
    """
    Exception raised when someone try to add a comment while flagging an
    object but with the ALLOW_COMMENTS settings to False (or the opposite)
    """
    pass

