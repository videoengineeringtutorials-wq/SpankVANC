# Local English → Spanish translation research — November 2, 2026

Recommendation: evaluate the OPUS-MT English/Spanish pair with CTranslate2 INT8
on CPU first, alongside the existing GPU Whisper worker. Use the compact Apache
2.0 model as the straightforward baseline and compare the larger, attributed
model for quality. This is a researched shortlist, not a measured latency or
quality ranking on this workstation. No translator, model or dependencies have
been installed and no cloud translation service is required for local inference.

| Candidate | Model license | Role in a caption trial |
| --- | --- | --- |
| [Helsinki-NLP/opus-mt-en-es](https://huggingface.co/Helsinki-NLP/opus-mt-en-es) | Apache 2.0 | Compact, dedicated English → Spanish baseline. Training/preprocessing and news/Tatoeba evaluations are linked from its card. |
| [Helsinki-NLP/opus-mt-tc-big-en-es](https://huggingface.co/Helsinki-NLP/opus-mt-tc-big-en-es) | CC BY 4.0 | Approximately 0.2B parameters, dedicated English → Spanish. Larger alternative; weights require attribution. Same-name news test sets on the cards show modest improvements on several sets, not a universal quality guarantee. |
| [google/madlad400-3b-mt](https://huggingface.co/google/madlad400-3b-mt) | Apache 2.0 | Larger 3B multilingual translation candidate if pair models underperform on actual program material. CPU/GPU local examples are provided. Higher resource use is an architectural expectation, not a workstation measurement. |
| [facebook/m2m100_418M](https://huggingface.co/facebook/m2m100_418M) | MIT | Local multilingual alternative if more languages become necessary; not the first choice for a single fixed language pair. |

[CTranslate2](https://opennmt.net/CTranslate2/guides/transformers.html) supports
MarianMT, M2M100 and T5 conversion. Its official [installation guide](https://opennmt.net/CTranslate2/installation.html)
lists Windows x64 wheels; its [quantization guide](https://opennmt.net/CTranslate2/quantization.html)
documents CPU INT8 execution. CPU translation is the initial deployment proposal
to avoid adding GPU contention to Whisper; benchmark both CPU and GPU before
choosing the actual configuration. Download/cache once, then run from local
model/tokenizer paths with offline mode. Pin source revisions, artifact hashes,
model license/attribution, converter and runtime versions separately.

Excluded from the unrestricted open-source shortlist:

- [NLLB-200](https://huggingface.co/facebook/nllb-200-distilled-600M): the published model weights are CC BY-NC 4.0; its card describes research rather than production deployment.
- [TranslateGemma 4B](https://huggingface.co/google/translategemma-4b-it): locally runnable weights use the custom Gemma license, rather than the unrestricted licenses of the baseline candidates. Do not describe it as satisfying a strict open-source requirement without examining the user's exact license criteria.

## Proposed SpankVANC evaluation

Keep the existing English transcription. Translate completed phrases/sentences
before output line wrapping and caption encoding; translating each word or
already-wrapped 32-character row would lose context. Preserve names, numbers,
negation, speaker intent and program terminology. A future translator needs a
bounded queue, explicit overload behavior and reported added latency, while
English outputs remain independently usable.

Use representative news/weather/sports/interview material, including local names,
idioms, numbers, emergency wording and partial speech segments. Have a fluent
Spanish reviewer compare candidates. Measure warm and cold latency, p50/p95,
CPU/RAM/VRAM, sustained throughput and backlog while Whisper is active. Published
BLEU results alone cannot establish live caption suitability. Test no-network
operation and keep translation output free of explanations or added content.

The current generated caption encoder normalizes text to a basic transliterated
alphabet. Spanish translation text can retain accents, but preserving ñ, accented
vowels, ¿ and ¡ on air requires extending both the 608 character mapping and the
native 708 text encoding. That work is outside this research task. Do not promise
accent-preserving Spanish caption output with the existing encoder.
