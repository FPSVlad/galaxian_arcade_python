import argparse
import hashlib
import sys
import time
from typing import List

import cv2
import numpy as np


def lsb_bits_from_frame(frame: np.ndarray) -> List[int]:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    pixels = gray.flatten()
    return [(int(px) & 1) for px in pixels]


def von_neumann_extract(bits: List[int]) -> List[int]:
    out: List[int] = []
    for i in range(0, len(bits) - 1, 2):
        a, b = bits[i], bits[i + 1]
        if a == 0 and b == 1:
            out.append(0)
        elif a == 1 and b == 0:
            out.append(1)
    return out


def collect_raw_bits(cap: cv2.VideoCapture, target_bits: int, timeout_s: float) -> List[int]:
    start = time.time()
    raw: List[int] = []
    while len(raw) < target_bits and (time.time() - start) < timeout_s:
        ok, frame = cap.read()
        if not ok:
            continue
        raw.extend(lsb_bits_from_frame(frame))
    return raw


def bits_to_bytes(bits: List[int]) -> bytes:
    n = (len(bits) // 8) * 8
    bits = bits[:n]
    out = bytearray()
    for i in range(0, n, 8):
        byte = 0
        for b in bits[i : i + 8]:
            byte = (byte << 1) | b
        out.append(byte)
    return bytes(out)


def conditioned_random_bytes(cap: cv2.VideoCapture, nbytes: int, timeout_s: float = 8.0) -> bytes:
    # oversampling factor: collect a lot, then de-bias, then hash-condition
    needed_bits = nbytes * 8
    raw = collect_raw_bits(cap, target_bits=needed_bits * 16, timeout_s=timeout_s)
    if not raw:
        raise RuntimeError("Не удалось получить данные с камеры")

    debiased = von_neumann_extract(raw)
    if len(debiased) < needed_bits:
        raise RuntimeError(
            f"Слишком мало энтропии после дебайаса: {len(debiased)} бит, нужно {needed_bits}"
        )

    material = bits_to_bytes(debiased)

    # expand deterministicly from entropy pool using SHA-256 counter mode
    out = bytearray()
    counter = 0
    while len(out) < nbytes:
        h = hashlib.sha256()
        h.update(material)
        h.update(counter.to_bytes(8, "big"))
        out.extend(h.digest())
        counter += 1
    return bytes(out[:nbytes])


def monobit_ratio(data: bytes) -> float:
    ones = sum(bin(b).count("1") for b in data)
    return ones / (len(data) * 8)


def main() -> int:
    parser = argparse.ArgumentParser(description="Webcam entropy RNG (camera noise based)")
    parser.add_argument("--device", type=int, default=0, help="Camera index")
    parser.add_argument("--width", type=int, default=64)
    parser.add_argument("--height", type=int, default=48)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--bytes", type=int, default=32, help="How many random bytes to output")
    parser.add_argument("--timeout", type=float, default=8.0)
    args = parser.parse_args()

    cap = cv2.VideoCapture(args.device)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    cap.set(cv2.CAP_PROP_FPS, args.fps)

    if not cap.isOpened():
        print("Ошибка: камера не открылась", file=sys.stderr)
        return 2

    time.sleep(0.5)
    print("Сбор энтропии с матрицы...")

    try:
        random_data = conditioned_random_bytes(cap, nbytes=args.bytes, timeout_s=args.timeout)
    except RuntimeError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        cap.release()
        return 3

    cap.release()

    print(f"Random bytes: {len(random_data)}")
    print(f"HEX: 0x{random_data.hex().upper()}")
    print(f"Monobit ratio: {monobit_ratio(random_data):.4f} (идеально ~0.5)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
