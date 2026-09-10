import re


def normalize_task_slug(title: str, max_length: int = 50) -> str:
    """
    Normalizes a task title into a slug string.

    Contracts:
    C1: convert to lowercase
    C2: replace whitespace and symbols with hyphens
    C3: collapse consecutive hyphens into single hyphen
    C4: strip leading and trailing hyphens
    C5: truncate to max_length without trailing hyphen
    C6: return fallback 'task' for empty or non-alphanumeric input
    C7: pure function without external dependencies
    """
    # C1: convert to lowercase
    slug = title.lower()

    # C2 & C3: replace non-alphanumeric characters with hyphens, and collapse consecutive hyphens
    slug = re.sub(r'[^a-z0-9]+', '-', slug)

    # C4: strip leading and trailing hyphens
    slug = slug.strip('-')

    # C5: truncate to max_length without trailing hyphen
    if len(slug) > max_length:
        slug = slug[:max_length].rstrip('-')

    # C6: return fallback 'task' for empty or non-alphanumeric input
    if not slug:
        return 'task'

    return slug
