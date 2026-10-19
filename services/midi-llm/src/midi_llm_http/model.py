import io

import torch
from anticipation.convert import events_to_midi
from transformers import AutoModelForCausalLM, AutoTokenizer

CHECKPOINT = "slseanwu/MIDI-LLM_Llama-3.2-1B"
LLAMA_VOCAB_SIZE = 128256
MIDI_BOS_ID = 55026
SYSTEM_PROMPT = (
    "You are a world-class composer. Please compose some music according to the following description: "
)


def _cpu_dtype() -> torch.dtype:
    try:
        sample = torch.ones(2, 2, dtype=torch.bfloat16)
        torch.mm(sample, sample)
    except RuntimeError:
        print("bfloat16 matmul is not implemented on this CPU; loading float32", flush=True)
        return torch.float32
    return torch.bfloat16


def _midi_tokens(shifted: list[int]) -> list[int]:
    # generate() can end on a text EOS id. events_to_midi only accepts whole MIDI events.
    tokens: list[int] = []
    for token in shifted:
        if token < 0 or token >= MIDI_BOS_ID:
            break
        tokens.append(token)
    extra = len(tokens) % 3
    if extra:
        del tokens[-extra:]
    return tokens


class CheckpointGenerator:
    def __init__(self) -> None:
        dtype = _cpu_dtype()
        self._tokenizer = AutoTokenizer.from_pretrained(CHECKPOINT, pad_token="<|eot_id|>")
        self._model = AutoModelForCausalLM.from_pretrained(
            CHECKPOINT,
            dtype=dtype,
            trust_remote_code=True,
        )
        self._model.eval()
        print(f"loaded {CHECKPOINT} on cpu ({dtype})", flush=True)

    def __call__(self, prompt: str, temperature: float, top_p: float, max_tokens: int) -> bytes:
        full_prompt = SYSTEM_PROMPT + prompt + " "
        input_ids = self._tokenizer(full_prompt, return_tensors="pt", padding=False)["input_ids"]
        midi_bos = torch.tensor([[MIDI_BOS_ID + LLAMA_VOCAB_SIZE]])
        input_ids = torch.cat([input_ids, midi_bos], dim=1)
        input_ids = input_ids.to(next(self._model.parameters()).device)
        with torch.no_grad():
            outputs = self._model.generate(
                input_ids=input_ids,
                do_sample=True,
                max_new_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                num_return_sequences=1,
                return_dict_in_generate=False,
                pad_token_id=self._tokenizer.pad_token_id,
            )
        generated = outputs[0, input_ids.shape[1] :]
        shifted = (generated - LLAMA_VOCAB_SIZE).tolist()
        midi = events_to_midi(_midi_tokens(shifted))
        buffer = io.BytesIO()
        midi.save(file=buffer)
        return buffer.getvalue()
