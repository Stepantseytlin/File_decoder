#!/usr/bin/env python3
"""
Преобразование текстового дампа FO_179 в строковый CAN-лог вида:

22.05.2024 17:34:42.000 CAN1 ID=0x01150000, D(8)=0xFC-FC-25-10-30-12-04-39

Важно:
- Исходный FO_179 не содержит явных CAN ID и номера канала.
- Поэтому по умолчанию создаются СИНТЕТИЧЕСКИЕ 29-битные ID:
    [код маркера: 5 бит][страница: 8 бит][строка: 8 бит][номер кадра: 8 бит]
- Каждые два 32-битных слова объединяются в один 8-байтовый кадр.
- Такое преобразование сохраняет все слова дампа, но не восстанавливает
  реальные CAN ID без отдельной спецификации протокола.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Iterator, TextIO
from itertools import chain, pairwise

HEADER_RE = re.compile(
    r"^Время СЕВ:\s*(?P<sev>\d{2}:\d{2}:\d{2}\.\d{3})\s+"
    r"Маркер:\s*(?P<marker>[0-9A-Fa-f]{4})\s+"
    r"Время БДВ:\s*(?P<bdv>\d{2}:\d{2}:\d{2})\s+"
    r"Страница:\s*(?P<page>[0-9A-Fa-f]+)\s+"
    r"Строка:\s*(?P<row>[0-9A-Fa-f]+)\s*\r?\n"
    r"\s*(?P=marker)(?P<date>\d{4})\s*"
)
WORD_RE = re.compile(r"\b[0-9A-Fa-f]{8}\b")

# Известные типы блоков в предоставленном файле.
MARKER_CODES = {
    "FCFC": 0x01,
    "FBFB": 0x02,
    "FDFD": 0x03,
}


@dataclass(frozen=True)
class Block:
    sev: str
    marker: str
    bdv: str
    page: int
    row: int
    date : str
    words: tuple[str, ...]
    header_line: int


def parse_date(value: str) -> datetime:
    """Принимает YYYY-MM-DD или DD.MM.YYYY."""
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    raise argparse.ArgumentTypeError(
        "Дата должна иметь вид YYYY-MM-DD или DD.MM.YYYY"
    )


def parse_int(value: str) -> int:
    """Принимает десятичное или шестнадцатеричное число, например 123 или 0x123."""
    try:
        return int(value, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Некорректное число: {value}") from exc


def iter_blocks(stream: TextIO) -> Iterator[Block]:
    current_header: tuple[str, str, str, int, int, str, int] | None = None
    current_words: list[str] = []

    def make_block() -> Block | None:
        nonlocal current_header, current_words
        if current_header is None:
            return None

        sev, marker, bdv, page, row, date, header_line = current_header
        if not current_words:
            raise ValueError(
                f"После заголовка в строке {header_line} нет 32-битных слов"
            )
        if len(current_words) % 2:
            raise ValueError(
                f"Блок из строки {header_line} содержит нечётное число слов: "
                f"{len(current_words)}"
            )

        block = Block(
            sev=sev,
            marker=marker,
            bdv=bdv,
            page=page,
            row=row,
            date=date,
            words=tuple(current_words),
            header_line=header_line,
        )
        current_header = None
        current_words = []
        return block

    lines = chain(stream, ("",))
    for line_number, (raw_line, next_raw_line) in enumerate(pairwise(lines), start=1):
        line = (raw_line).strip()
        
        match_text = raw_line + next_raw_line
        print("starting matching and")
        match = HEADER_RE.match(match_text)
        print(match, line)

        if match:
            previous = make_block()
            if previous is not None:
                yield previous
            current_header = (
                match.group("sev"),
                match.group("marker").upper(),
                match.group("bdv"),
                int(match.group("page"), 16),
                int(match.group("row"), 16),
                match.group("date")[0:2] + "." + match.group("date")[2:4],
                line_number,
            )
            continue

        if current_header is not None:
            current_words.extend(word.upper() for word in WORD_RE.findall(line))

    last = make_block()
    if last is not None:
        yield last


def word_to_bytes(word: str, byte_order: str) -> bytes:
    raw = bytes.fromhex(word)
    return raw if byte_order == "big" else raw[::-1]


def synthetic_can_id(block: Block, frame_index: int) -> int:
    marker_code = MARKER_CODES.get(block.marker, 0x1F)

    if not 0 <= block.page <= 0xFF:
        raise ValueError(f"Страница вне диапазона 00..FF: {block.page:X}")
    if not 0 <= block.row <= 0xFF:
        raise ValueError(f"Строка вне диапазона 00..FF: {block.row:X}")
    if not 0 <= frame_index <= 0xFF:
        raise ValueError(f"Слишком много кадров в одном блоке: {frame_index + 1}")

    can_id = (
        (marker_code << 24)
        | (block.page << 16)
        | (block.row << 8)
        | frame_index
    )
    if can_id > 0x1FFFFFFF:
        raise ValueError(f"CAN ID превышает 29 бит: 0x{can_id:X}")
    return can_id


def block_datetime(
    block: Block,
    base_date: datetime,
    time_field: str,
    frame_index: int,
    frame_step_ms: int,
) -> datetime:
    time_text = block.bdv + ".000"# для переключения на sev: = block.sev if time_field == "sev" else
    time_value = datetime.strptime(time_text, "%H:%M:%S.%f").time()
    date_text = block.date + ".2026"
    date = parse_date(date_text)
    result = datetime.combine(date.date(), time_value)#datetime.combine(base_date.date(), time_value)
    return result + timedelta(milliseconds=frame_index * frame_step_ms)


def format_timestamp(value: datetime) -> str:
    # Имитирует формат примера: час без обязательного ведущего нуля.
    milliseconds = value.microsecond // 1000
    return (
        f"{value:%d.%m.%Y} {value.hour}:{value:%M:%S}."
        f"{milliseconds:03d}"
    )


def convert(
    input_path: Path,
    output_path: Path,
    *,
    date: datetime,
    encoding: str,
    channel: str,
    time_field: str,
    byte_order: str,
    frame_step_ms: int,
    fixed_id: int | None,
    max_blocks: int | None,
) -> tuple[int, int]:
    block_count = 0
    frame_count = 0

    with input_path.open("r", encoding=encoding, errors="strict") as source, \
         output_path.open("w", encoding="ascii", newline="") as target:

        print("starting blocks iterations")
        for block in iter_blocks(source):
            print("going")
            if max_blocks is not None and block_count >= max_blocks:
                break

            for frame_index in range(0, len(block.words), 2):
                pair_index = frame_index // 2
                payload = (
                    word_to_bytes(block.words[frame_index], byte_order)
                    + word_to_bytes(block.words[frame_index + 1], byte_order)
                )

                can_id = (
                    fixed_id
                    if fixed_id is not None
                    else synthetic_can_id(block, pair_index)
                )
                timestamp = block_datetime(
                    block,
                    date,
                    time_field,
                    pair_index,
                    frame_step_ms,
                )
                payload_text = "-".join(f"{byte:02X}" for byte in payload)

                target.write(
                    f"{format_timestamp(timestamp)} "
                    f"{channel} ID=0x{can_id:08X}, "
                    f"D(8)=0x{payload_text}\r\n"
                )
                frame_count += 1

            block_count += 1

    return block_count, frame_count


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Преобразует дамп FO_179 в текстовый CAN-лог."
    )
    parser.add_argument("input", type=Path, help="Исходный файл FO_179")
    parser.add_argument("output", type=Path, help="Выходной TXT-файл")
    parser.add_argument(
        "--date",
        required=True,
        type=parse_date,
        help="Дата для выходных строк: YYYY-MM-DD или DD.MM.YYYY",
    )
    parser.add_argument(
        "--encoding",
        default="cp1251",
        help="Кодировка исходного файла, по умолчанию cp1251",
    )
    parser.add_argument(
        "--channel",
        choices=("CAN1", "CAN2"),
        default="CAN1",
        help="Канал для выходных строк, по умолчанию CAN1",
    )
    parser.add_argument(
        "--time-field",
        choices=("sev", "bdv"),
        default="bdv",
        help="Использовать время СЕВ или БДВ, по умолчанию СЕВ",
    )
    parser.add_argument(
        "--word-byte-order",
        choices=("big", "little"),
        default="big",
        help=(
            "Порядок байтов внутри каждого 32-битного слова; "
            "по умолчанию big: FCFC2510 -> FC-FC-25-10"
        ),
    )
    parser.add_argument(
        "--frame-step-ms",
        type=int,
        default=0,
        help=(
            "Сдвиг времени между соседними кадрами блока в миллисекундах; "
            "по умолчанию 0"
        ),
    )
    parser.add_argument(
        "--fixed-id",
        type=parse_int,
        help=(
            "Использовать один заданный ID вместо синтетических, "
            "например --fixed-id 0x123"
        ),
    )
    parser.add_argument(
        "--max-blocks",
        type=int,
        help="Обработать только первые N блоков, удобно для проверки",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    if args.frame_step_ms < 0:
        print("--frame-step-ms не может быть отрицательным", file=sys.stderr)
        return 2
    if args.fixed_id is not None and not 0 <= args.fixed_id <= 0x1FFFFFFF:
        print("--fixed-id должен быть в диапазоне 0..0x1FFFFFFF", file=sys.stderr)
        return 2
    if args.max_blocks is not None and args.max_blocks <= 0:
        print("--max-blocks должен быть положительным", file=sys.stderr)
        return 2

    try:
        blocks, frames = convert(
            args.input,
            args.output,
            date=args.date,
            encoding=args.encoding,
            channel=args.channel,
            time_field=args.time_field,
            byte_order=args.word_byte_order,
            frame_step_ms=args.frame_step_ms,
            fixed_id=args.fixed_id,
            max_blocks=args.max_blocks,
        )
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1

    print(
        f"Готово: обработано блоков {blocks}, записано CAN-кадров {frames}. "
        f"Файл: {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
