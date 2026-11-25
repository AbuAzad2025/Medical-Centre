"""Generate a static Arabic→English UI dictionary from the extracted strings.

Translations are produced by an online translation service at audit time and
committed as a static JSON file. The running app never calls an external
service. Strings are batched one per line, which the endpoint preserves.
"""

import json
import os
import re
import sys
import time

import requests

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC = os.path.join(ROOT, 'docs', 'PAGE_AUDIT', 'ui_strings.json')
OUT = os.path.join(ROOT, 'app', 'shared', 'i18n_catalog.json')
ENDPOINT = 'https://translate.googleapis.com/translate_a/single'
BATCH = 40


def translate_batch(items):
    params = {'client': 'gtx', 'sl': 'ar', 'tl': 'en', 'dt': 't', 'q': '\n'.join(items)}
    for attempt in range(4):
        try:
            resp = requests.get(ENDPOINT, params=params, timeout=40)
            resp.raise_for_status()
            data = resp.json()
            segs = data[0]
            results = [seg[0].rstrip('\n') for seg in segs]
            if len(results) == len(items):
                return results
            return None
        except Exception as exc:  # noqa: BLE001
            if attempt == 3:
                print('  batch failed:', str(exc)[:120], file=sys.stderr)
            time.sleep(1 + attempt)
    return None


def main():
    with open(SRC, encoding='utf-8') as fh:
        strings = json.load(fh)['strings']

    # Newlines break the one-line-per-segment batch protocol. Jinja control
    # blocks are masked with tokens (preserved by the endpoint) and restored.
    usable = [s for s in strings if '\n' not in s and len(s) <= 300]
    print(f'translating {len(usable)} strings in batches of {BATCH}')

    def mask(value):
        tokens = {}

        def repl(m):
            key = f'ZZZ{len(tokens)}ZZZ'
            tokens[key] = m.group(0)
            return key

        return re.sub(r'\{\{.*?\}\}|\{%.*?%\}', repl, value), tokens

    def unmask(value, tokens):
        for key, original in tokens.items():
            value = value.replace(key, original)
        return value

    catalog = {}
    done = 0
    for i in range(0, len(usable), BATCH):
        chunk = usable[i : i + BATCH]
        masked = [mask(s) for s in chunk]
        results = translate_batch([m[0] for m in masked])
        if results:
            for source, (masked_source, tokens), target in zip(
                chunk, masked, results, strict=False
            ):
                if target and target.strip() and target.strip() != masked_source:
                    catalog[source] = unmask(target.strip(), tokens)
        done += len(chunk)
        if done % 400 == 0:
            print(f'  {done}/{len(usable)} -> {len(catalog)} translations')
        time.sleep(0.15)

    with open(OUT, 'w', encoding='utf-8') as fh:
        json.dump(catalog, fh, ensure_ascii=False, indent=2)
        fh.write('\n')
    print(f'wrote {OUT}: {len(catalog)} entries')


if __name__ == '__main__':
    main()
