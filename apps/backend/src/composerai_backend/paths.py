from composerai_store import PathRejected


def path_component(name: str) -> str:
    """Reject an empty name, '.', '..', or any name that contains a slash."""
    if name == "" or name in {".", ".."} or "/" in name:
        raise PathRejected(name)
    return name


def section_midi_path(project: str, section: str, file: str) -> str:
    return f"{path_component(project)}/{path_component(section)}/{path_component(file)}.mid"


def project_write_path(path: str) -> str:
    """Reject a write that is not <project>/<section>/<file>."""
    parts = path.split("/")
    if len(parts) < 3 or any(part == "" or part in {".", ".."} for part in parts):
        raise PathRejected(path)
    return path


def probe_path(project: str) -> str:
    return f"{path_component(project)}/verse-1/mounted.txt"
