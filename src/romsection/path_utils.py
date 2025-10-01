import os


def resolve_abspath(path: str, reference_path: str) -> str:
    if os.path.isabs(path):
        return path
    return os.path.join(reference_path, path)
