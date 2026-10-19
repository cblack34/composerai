import threading
import traceback

import uvicorn

from midi_llm_http.server import Service, create_app


def _load(service: Service) -> None:
    try:
        from midi_llm_http.model import CheckpointGenerator

        service.mark_ready(CheckpointGenerator())
    except Exception:
        traceback.print_exc()


def main() -> None:
    service = Service()
    threading.Thread(target=_load, args=(service,), daemon=True).start()
    uvicorn.run(create_app(service), host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
