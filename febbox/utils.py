import math
from hashlib import md5
from pathlib import Path


def get_file_hash(path: Path):
    size = path.stat().st_size
    if size < 52428800:
        hash = md5()
        with open(path, 'rb') as f:
            while True:
                chunk = f.read(2 * 1024 * 1024)

                if not chunk:
                    break

                hash.update(chunk)

        return hash.hexdigest()

    def get_hashes(bytes):
        hash = md5(bytes).hexdigest()
        return hash

    with open(path, 'rb') as f:
        start = 4096
        f.seek(start)
        h1 = get_hashes(f.read(4096))

        start = math.floor(size / 3) * 2
        f.seek(start)
        h2 = get_hashes(f.read(4096))

        start = math.floor(size / 3)
        f.seek(start)
        h3 = get_hashes(f.read(4096))

        start = math.floor(size - 8192)
        f.seek(start)
        h4 = get_hashes(f.read(4096))

        hash = h1 + h2 + h3 + h4 + '_' + str(size)

        hash = md5(hash.encode()).hexdigest()

        return hash


def chunk_hash(chunk):
    size = len(chunk)

    def get_hash(hash):
        return md5(hash).hexdigest()

    start = 4096
    h1 = chunk[start : start + 4096]
    h1 = get_hash(h1)

    start = math.floor(size / 3) * 2
    h2 = chunk[start : start + 4096]
    h2 = get_hash(h2)

    start = math.floor(size / 3)
    h3 = chunk[start : start + 4096]
    h3 = get_hash(h3)

    start = math.floor(size - 8192)
    if start <= 0:
        start = math.floor(size / 3) + 4096
    h4 = chunk[start : start + 4096]
    h4 = get_hash(h4)

    hash = h1 + h2 + h3 + h4 + '_' + str(size)

    hash = md5(hash.encode()).hexdigest()

    return hash


def get_files(folder):
    path = Path(folder)
    files = path.iterdir()

    fls = []

    for file in files:
        if file.is_dir():
            fs = get_files(file)
            fls.extend(fs)
        else:
            fls.append(str(file))

    return fls
