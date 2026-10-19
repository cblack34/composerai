import threading
import traceback

from midi_llm_http.server import Service, serve


def _load(service: Service) -> None:
    try:
        from midi_llm_http.model import CheckpointGenerator

        service.mark_ready(CheckpointGenerator())
    except Exception:
        traceback.print_exc()


def main() -> None:
    service = Service()
    threading.Thread(target=_load, args=(service,), daemon=True).start()
    serve(service)


if __name__ == "__main__":
    main()
