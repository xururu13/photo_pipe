# ── Поиск дубликатов (perceptual hashing + Union-Find) ────────────────────────

from __future__ import annotations

from config import DHASH_SIZE, DHASH_THRESHOLD, PhotoInfo


def compute_dhash(image) -> str:
    """Вычисляет dHash (difference hash) изображения. Возвращает hex-строку."""
    import cv2

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, (DHASH_SIZE + 1, DHASH_SIZE))

    bits = []
    for y in range(DHASH_SIZE):
        for x in range(DHASH_SIZE):
            bits.append(1 if resized[y, x] < resized[y, x + 1] else 0)

    # Конвертируем биты в hex-строку
    hash_int = 0
    for bit in bits:
        hash_int = (hash_int << 1) | bit
    return format(hash_int, f"0{DHASH_SIZE * DHASH_SIZE // 4}x")


def hamming_distance(hash1: str, hash2: str) -> int:
    """Расстояние Хэмминга между двумя hex-хешами."""
    val1 = int(hash1, 16)
    val2 = int(hash2, 16)
    return bin(val1 ^ val2).count("1")


# ── Union-Find ────────────────────────────────────────────────────────────────

class UnionFind:
    """Union-Find (Disjoint Set Union) для группировки дубликатов."""

    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, x: int, y: int):
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return
        if self.rank[rx] < self.rank[ry]:
            rx, ry = ry, rx
        self.parent[ry] = rx
        if self.rank[rx] == self.rank[ry]:
            self.rank[rx] += 1


def find_duplicate_groups(photos: list[PhotoInfo]) -> list[PhotoInfo]:
    """
    Сравнивает dHash всех пар, группирует дубликаты через Union-Find.
    Заполняет duplicate_group и is_worst_duplicate / uniqueness_score.
    """
    n = len(photos)
    if n < 2:
        return photos

    # Пропускаем фото без хеша
    valid = [(i, p) for i, p in enumerate(photos) if p.dhash]
    if len(valid) < 2:
        return photos

    uf = UnionFind(n)

    # Сравниваем все пары
    for a in range(len(valid)):
        for b in range(a + 1, len(valid)):
            idx_a, photo_a = valid[a]
            idx_b, photo_b = valid[b]
            if hamming_distance(photo_a.dhash, photo_b.dhash) <= DHASH_THRESHOLD:
                uf.union(idx_a, idx_b)

    # Собираем группы
    groups: dict[int, list[int]] = {}
    for i in range(n):
        root = uf.find(i)
        groups.setdefault(root, []).append(i)

    group_id = 0
    for root, members in groups.items():
        if len(members) < 2:
            continue

        # Назначаем группу
        for idx in members:
            photos[idx].duplicate_group = group_id

        # Худший — с наименьшей резкостью
        worst_idx = min(members, key=lambda i: photos[i].sharpness)
        photos[worst_idx].is_worst_duplicate = True
        photos[worst_idx].uniqueness_score = 0.3

        group_id += 1

    return photos
