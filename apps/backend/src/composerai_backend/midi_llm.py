import asyncio
import http.client
import json
import urllib.error
import urllib.request
from typing import Protocol


class MidiLlmError(Exception):
    pass


class MidiLlmClient(Protocol):
    async def generate(self, prompt: str) -> bytes: ...


class HttpMidiLlmClient:
    def __init__(self, url: str) -> None:
        self.url = url

    async def generate(self, prompt: str) -> bytes:
        return await asyncio.to_thread(self._post, prompt)

    def _post(self, prompt: str) -> bytes:
        request = urllib.request.Request(
            f"{self.url}/generate",
            data=json.dumps({"prompt": prompt}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request) as response:
                return response.read()
        except urllib.error.URLError as exc:
            if isinstance(exc, urllib.error.HTTPError):
                exc.close()
            raise MidiLlmError(str(exc)) from exc
        except (http.client.HTTPException, OSError) as exc:
            raise MidiLlmError(str(exc)) from exc
