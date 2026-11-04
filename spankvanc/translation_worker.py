"""Offline CPU OPUS-MT inference; JSON lines only, no caption output."""
import json
from pathlib import Path
import sys
import time


def main():
    import ctranslate2
    import sentencepiece
    root = Path(sys.argv[1])
    source = sentencepiece.SentencePieceProcessor(model_file=str(root / 'source.spm'))
    target = sentencepiece.SentencePieceProcessor(model_file=str(root / 'target.spm'))
    translator = ctranslate2.Translator(str(root / 'ct2'), device='cpu', compute_type='int8', inter_threads=1, intra_threads=4)
    print(json.dumps({'ready': True}), flush=True)
    for line in sys.stdin:
        request = json.loads(line)
        start = time.monotonic()
        tokens = source.encode(request['english'], out_type=str) + ['</s>']
        if len(tokens) > 512:
            print(json.dumps({'error': 'Phrase exceeds 512 model tokens'}), flush=True)
            continue
        result = translator.translate_batch([tokens], beam_size=4, max_decoding_length=512)
        print(json.dumps({'english': request['english'], 'spanish': target.decode(result[0].hypotheses[0]),
                          'latency_ms': round((time.monotonic()-start)*1000)}), flush=True)


if __name__ == '__main__':
    main()
