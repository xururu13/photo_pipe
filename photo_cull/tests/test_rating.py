from pathlib import Path

from config import PhotoInfo, SHARPNESS_TERRIBLE
from rating import compute_composite_score, compute_composite_score_ai, apply_rating, rate_photos


def _make_photo(**kwargs) -> PhotoInfo:
    defaults = dict(path=Path("/test.jpg"))
    defaults.update(kwargs)
    return PhotoInfo(**defaults)


class TestCompositeScore:
    def test_all_perfect(self):
        p = _make_photo(
            sharpness_score=1.0,
            exposure_score=1.0,
            face_score=1.0,
            uniqueness_score=1.0,
            series_score=1.0,
        )
        assert compute_composite_score(p) == 1.0

    def test_all_zero(self):
        p = _make_photo(
            sharpness_score=0.0,
            exposure_score=0.0,
            face_score=0.0,
            uniqueness_score=0.0,
            series_score=0.0,
        )
        assert compute_composite_score(p) == 0.0

    def test_weights_sum_to_one(self):
        from config import (
            WEIGHT_SHARPNESS, WEIGHT_EXPOSURE, WEIGHT_FACES,
            WEIGHT_UNIQUENESS, WEIGHT_SERIES,
        )
        total = WEIGHT_SHARPNESS + WEIGHT_EXPOSURE + WEIGHT_FACES + WEIGHT_UNIQUENESS + WEIGHT_SERIES
        assert abs(total - 1.0) < 1e-6


class TestCompositeScoreAi:
    def test_all_perfect(self):
        p = _make_photo(
            sharpness_score=1.0,
            exposure_score=1.0,
            face_score=1.0,
            ai_score=1.0,
            uniqueness_score=1.0,
            series_score=1.0,
        )
        assert compute_composite_score_ai(p) == 1.0

    def test_all_zero(self):
        p = _make_photo(
            sharpness_score=0.0,
            exposure_score=0.0,
            face_score=0.0,
            ai_score=0.0,
            uniqueness_score=0.0,
            series_score=0.0,
        )
        assert compute_composite_score_ai(p) == 0.0

    def test_ai_weights_sum_to_one(self):
        from config import (
            AI_WEIGHT_SHARPNESS, AI_WEIGHT_EXPOSURE, AI_WEIGHT_FACES,
            AI_WEIGHT_COMPOSITION, AI_WEIGHT_UNIQUENESS, AI_WEIGHT_SERIES,
        )
        total = (AI_WEIGHT_SHARPNESS + AI_WEIGHT_EXPOSURE + AI_WEIGHT_FACES
                 + AI_WEIGHT_COMPOSITION + AI_WEIGHT_UNIQUENESS + AI_WEIGHT_SERIES)
        assert abs(total - 1.0) < 1e-6


class TestApplyRating:
    def test_hard_rule_low_sharpness(self):
        p = _make_photo(sharpness=10)
        apply_rating(p)
        assert p.rating == 1
        assert "sharpness" in p.rating_reason

    def test_hard_rule_eyes_closed(self):
        p = _make_photo(sharpness=500, all_eyes_closed=True)
        apply_rating(p)
        assert p.rating == 1
        assert "eyes" in p.rating_reason

    def test_hard_rule_worst_duplicate(self):
        p = _make_photo(sharpness=500, is_worst_duplicate=True)
        apply_rating(p)
        assert p.rating == 1
        assert "duplicate" in p.rating_reason

    def test_hard_rule_5(self):
        p = _make_photo(
            sharpness=500,
            is_best_in_series=True,
            face_count=1,
            all_eyes_closed=False,
            sharpness_score=1.0,
            exposure_score=1.0,
            face_score=1.0,
            uniqueness_score=1.0,
            series_score=1.0,
        )
        apply_rating(p)
        assert p.rating == 5
        assert "hard" in p.rating_reason

    def test_soft_rating_2(self):
        p = _make_photo(
            sharpness=200,
            sharpness_score=0.1,
            exposure_score=0.1,
            face_score=0.1,
            uniqueness_score=0.1,
            series_score=0.1,
        )
        apply_rating(p)
        assert p.rating == 2

    def test_soft_rating_3(self):
        p = _make_photo(
            sharpness=200,
            sharpness_score=0.5,
            exposure_score=0.5,
            face_score=0.3,
            uniqueness_score=0.5,
            series_score=0.5,
        )
        apply_rating(p)
        assert p.rating == 3

    def test_soft_rating_4(self):
        p = _make_photo(
            sharpness=200,
            sharpness_score=0.7,
            exposure_score=0.7,
            face_score=0.7,
            uniqueness_score=0.7,
            series_score=0.7,
        )
        apply_rating(p)
        assert p.rating == 4

    def test_soft_rating_5(self):
        p = _make_photo(
            sharpness=200,
            sharpness_score=0.9,
            exposure_score=0.9,
            face_score=0.9,
            uniqueness_score=0.9,
            series_score=0.9,
        )
        apply_rating(p)
        assert p.rating == 5

    def test_ai_mode_uses_ai_score(self):
        p = _make_photo(
            sharpness=500,
            sharpness_score=0.9,
            exposure_score=0.9,
            face_score=0.9,
            ai_score=0.9,
            uniqueness_score=0.9,
            series_score=0.9,
        )
        apply_rating(p, ai_mode=True)
        assert p.rating == 5
        assert p.composite_score > 0.8

    def test_ai_mode_skips_eyes_closed_hard_rule(self):
        p = _make_photo(
            sharpness=500,
            sharpness_score=0.7,
            exposure_score=0.7,
            face_score=0.7,
            ai_score=0.7,
            uniqueness_score=0.7,
            series_score=0.7,
            all_eyes_closed=True,
        )
        apply_rating(p, ai_mode=True)
        assert p.rating != 1  # should NOT trigger hard rule in AI mode

    def test_ai_mode_low_composition(self):
        p = _make_photo(
            sharpness=500,
            sharpness_score=0.1,
            exposure_score=0.1,
            face_score=0.1,
            ai_score=0.1,
            uniqueness_score=0.1,
            series_score=0.1,
        )
        apply_rating(p, ai_mode=True)
        assert p.rating == 2


class TestRatePhotos:
    def test_rates_all(self):
        photos = [_make_photo(sharpness=200) for _ in range(3)]
        result = rate_photos(photos)
        assert len(result) == 3
        assert all(1 <= p.rating <= 5 for p in result)

    def test_hard_rule_priority(self):
        """Hard rules проверяются до soft rules."""
        p = _make_photo(
            sharpness=10,  # hard rule → 1
            sharpness_score=1.0,
            exposure_score=1.0,
            face_score=1.0,
        )
        rate_photos([p])
        assert p.rating == 1
