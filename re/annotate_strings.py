"""Annotates DAT_14xxxxxxx references in Ghidra output with the ASCII/UTF-16 string stored there.

Without whole-program analysis Ghidra does not define strings, so decompiled code shows bare DAT_
labels. This reads the bytes straight from the PE file and appends `/* "text" */` where a reference
points at printable text.

Usage: python -I re/annotate_strings.py <exe> <dir-with-.c-files>
"""
import re
import struct
import sys
from pathlib import Path


def load_sections(data):
    pe = struct.unpack_from('<I', data, 0x3c)[0]
    count = struct.unpack_from('<H', data, pe + 6)[0]
    optional_size = struct.unpack_from('<H', data, pe + 20)[0]
    optional = pe + 24
    image_base = struct.unpack_from('<Q', data, optional + 24)[0]
    sections = []
    for i in range(count):
        offset = optional + optional_size + i * 40
        vsize, va, rsize, raw = struct.unpack_from('<IIII', data, offset + 8)
        sections.append((va, max(vsize, rsize), raw))
    return image_base, sections


def read_string(data, image_base, sections, va):
    rva = va - image_base
    for start, size, raw in sections:
        if start <= rva < start + size:
            offset = raw + rva - start
            break
    else:
        return None
    chunk = data[offset:offset + 256]
    wide = re.match(rb'((?:[\x20-\x7e]\x00){3,})\x00\x00', chunk)
    if wide:
        return wide.group(1).decode('utf-16le')
    ascii_text = re.match(rb'([\x20-\x7e]{4,})\x00', chunk)
    if ascii_text:
        return ascii_text.group(1).decode('ascii')
    return None


def main():
    exe, folder = sys.argv[1], Path(sys.argv[2])
    data = Path(exe).read_bytes()
    image_base, sections = load_sections(data)
    pattern = re.compile(r'\b(?:DAT|PTR_DAT|UNK|s|u)_(14[0-9a-f]{7})\b')
    for path in sorted(folder.glob('*.c')):
        text = path.read_text(encoding='utf-8', errors='replace')

        def annotate(match):
            value = read_string(data, image_base, sections, int(match.group(1), 16))
            return f'{match.group(0)} /* "{value}" */' if value else match.group(0)

        path.write_text(pattern.sub(annotate, text), encoding='utf-8')


if __name__ == '__main__':
    main()
