import uuid

from fastapi_common.util.context_util import get_request_execution_ctx


def is_empty(obj):
    """
    Checks if an object is empty.

    Handles edge cases and various data types:
    - Strings: "" (empty string)
    - Tuples: () (empty tuple)
    - Lists: [] (empty list)
    - Dictionaries: {} (empty dictionary)
    - Sets: set() (empty set)
    - Objects: Checks if object has any attributes (using __dict__)
    - None: `None` is considered empty.
    - Other types: Returns False.

    Args:
        obj: The object to check for emptiness.

    Returns:
        True if the object is empty, False otherwise.
    """

    if obj is None:
        return True

    if isinstance(obj, (str, tuple, list, set)):
        return len(obj) == 0

    if isinstance(obj, dict):
        return len(obj) == 0

    if hasattr(obj, "__dict__"):  # Check for objects with attributes
        return len(obj.__dict__) == 0

    if isinstance(obj, str) and obj.strip() == "":  # Handle empty strings
        return True

    return False  # Default to not empty for other types


def get_grid() -> str:
    """
    Returns Grid Id from Request Execution Context
    """
    return get_request_execution_ctx().grid or str(uuid.uuid4())

