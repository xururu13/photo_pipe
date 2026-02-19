import numpy as np
from pathlib import Path

from config import PhotoInfo
from duplicates import compute_dhash, hamming_distance, UnionFind, find_duplicate_groups


def _make_image(brightness=128):
    return np.full((100, 100, 3), brightness, dtype=np.uint8)


class TestComputeDhash:
    def test_returns_hex_string(self):
        img = _make_image(128)
        h = compute_dhash(img)
        assert isinstance(h, str)
        int(h, 16)  # должен быть валидный hex

    def test_same_image_same_hash(self):
        img = _make_image(128)
        assert compute_dhash(img) == compute_dhash(img)

    def test_different_images_different_hash(self):
        img1 = _make_image(50)
        img2 = _make_image(200)
        # Добавляем разные градиенты, чтобы dHash отличался
        img1[:, 50:, :] = 200
        img2[:50, :, :] = 50
        h1 = compute_dhash(img1)
        h2 = compute_dhash(img2)
        assert h1 != h2


class TestHammingDistance:
    def test_identical(self):
        assert hamming_distance("ff", "ff") == 0

    def test_one_bit(self):
        assert hamming_distance("00", "01") == 1

    def test_all_different(self):
        assert hamming_distance("00", "ff") == 8

    def test_symmetric(self):
        assert hamming_distance("0f", "f0") == hamming_distance("f0", "0f")


class TestUnionFind:
    def test_initial_state(self):
        uf = UnionFind(5)
        for i in range(5):
            assert uf.find(i) == i

    def test_union(self):
        uf = UnionFind(5)
        uf.union(0, 1)
        assert uf.find(0) == uf.find(1)

    def test_transitive(self):
        uf = UnionFind(5)
        uf.union(0, 1)
        uf.union(1, 2)
        assert uf.find(0) == uf.find(2)

    def test_separate_groups(self):
        uf = UnionFind(4)
        uf.union(0, 1)
        uf.union(2, 3)
        assert uf.find(0) != uf.find(2)


class TestFindDuplicateGroups:
    def test_no_duplicates(self):
        photos = [
            PhotoInfo(path=Path("/a.jpg"), dhash="0000000000000000"),
            PhotoInfo(path=Path("/b.jpg"), dhash="ffffffffffffffff"),
        ]
        result = find_duplicate_groups(photos)
        assert all(p.duplicate_group == -1 for p in result)

    def test_duplicates_grouped(self):
        photos = [
            PhotoInfo(path=Path("/a.jpg"), dhash="0000000000000000", sharpness=100),
            PhotoInfo(path=Path("/b.jpg"), dhash="0000000000000001", sharpness=200),
        ]
        result = find_duplicate_groups(photos)
        assert result[0].duplicate_group == result[1].duplicate_group
        assert result[0].duplicate_group >= 0

    def test_worst_duplicate_marked(self):
        photos = [
            PhotoInfo(path=Path("/a.jpg"), dhash="0000000000000000", sharpness=50),
            PhotoInfo(path=Path("/b.jpg"), dhash="0000000000000001", sharpness=200),
        ]
        result = find_duplicate_groups(photos)
        assert result[0].is_worst_duplicate  # sharpness=50 — worst
        assert not result[1].is_worst_duplicate

    def test_single_photo(self):
        photos = [PhotoInfo(path=Path("/a.jpg"), dhash="abc")]
        result = find_duplicate_groups(photos)
        assert result[0].duplicate_group == -1

    def test_empty_list(self):
        assert find_duplicate_groups([]) == []

    def test_transitive_grouping(self):
        photos = [
            PhotoInfo(path=Path("/a.jpg"), dhash="0000000000000000", sharpness=100),
            PhotoInfo(path=Path("/b.jpg"), dhash="0000000000000003", sharpness=200),
            PhotoInfo(path=Path("/c.jpg"), dhash="0000000000000007", sharpness=300),
        ]
        result = find_duplicate_groups(photos)
        # A~B (dist=2), B~C (dist=1) → все в одной группе
        groups = {p.duplicate_group for p in result}
        assert len(groups) == 1
        assert -1 not in groups
