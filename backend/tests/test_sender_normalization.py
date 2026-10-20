"""
Tests for sender normalization
"""
import pytest
from app.data.sender_normalizer import SenderNormalizer


@pytest.fixture
def normalizer():
    """Create normalizer instance."""
    return SenderNormalizer()


class TestHealthFunds:
    """Test health fund recognition."""
    
    def test_clalit_full_name(self, normalizer):
        """Test Clalit with full name."""
        canonical, confident, warning = normalizer.normalize("קופת חולים כללית")
        assert canonical == "כללית"
        assert confident is True
        assert warning is None
    
    def test_clalit_short_name(self, normalizer):
        """Test Clalit with short name."""
        canonical, confident, warning = normalizer.normalize("כללית")
        assert canonical == "כללית"
        assert confident is True
    
    def test_clalit_abbreviation(self, normalizer):
        """Test Clalit with abbreviation."""
        canonical, confident, warning = normalizer.normalize('קופ"ח כללית')
        assert canonical == "כללית"
        assert confident is True
    
    def test_maccabi(self, normalizer):
        """Test Maccabi."""
        canonical, confident, warning = normalizer.normalize("מכבי")
        assert canonical == "מכבי"
        assert confident is True
    
    def test_meuhedet(self, normalizer):
        """Test Meuhedet."""
        canonical, confident, warning = normalizer.normalize("מאוחדת")
        assert canonical == "מאוחדת"
        assert confident is True
    
    def test_leumit(self, normalizer):
        """Test Leumit."""
        canonical, confident, warning = normalizer.normalize("לאומית")
        assert canonical == "לאומית"
        assert confident is True


class TestHospitals:
    """Test hospital recognition."""
    
    def test_assaf_harofeh_full_name(self, normalizer):
        """Test Assaf Harofeh with full name."""
        canonical, confident, warning = normalizer.normalize("המרכז הרפואי שמיר (אסף הרופא)")
        assert "אסף הרופא" in canonical
        assert confident is True
    
    def test_assaf_harofeh_old_name(self, normalizer):
        """Test Assaf Harofeh with old name."""
        canonical, confident, warning = normalizer.normalize("אסף הרופא")
        assert "אסף הרופא" in canonical
        assert confident is True
    
    def test_sheba_tel_hashomer(self, normalizer):
        """Test Sheba with Tel HaShomer name."""
        canonical, confident, warning = normalizer.normalize("תל השומר")
        assert "שיבא" in canonical
        assert confident is True
    
    def test_ichilov(self, normalizer):
        """Test Ichilov."""
        canonical, confident, warning = normalizer.normalize("איכילוב")
        assert "איכילוב" in canonical or "תל אביב" in canonical
        assert confident is True
    
    def test_beilinson(self, normalizer):
        """Test Beilinson."""
        canonical, confident, warning = normalizer.normalize("בילינסון")
        assert "רבין" in canonical or "בילינסון" in canonical
        assert confident is True
    
    def test_bnai_zion(self, normalizer):
        """Test Bnai Zion with various names."""
        test_cases = ["בני ציון", "רוטשילד", "מ.ר. בני-ציון"]
        for name in test_cases:
            canonical, confident, warning = normalizer.normalize(name)
            assert "בני ציון" in canonical
            assert confident is True, f"Failed for {name}"
    
    def test_rambam(self, normalizer):
        """Test Rambam."""
        canonical, confident, warning = normalizer.normalize("רמבם")
        assert "רמב" in canonical
        assert confident is True
    
    def test_hadassah(self, normalizer):
        """Test Hadassah."""
        canonical, confident, warning = normalizer.normalize("הדסה")
        assert "הדסה" in canonical
        assert confident is True
    
    def test_schneider(self, normalizer):
        """Test Schneider Children's Hospital."""
        canonical, confident, warning = normalizer.normalize("שניידר")
        assert "שניידר" in canonical
        assert confident is True


class TestAmbiguousSenders:
    """Test handling of ambiguous sender descriptions."""
    
    def test_emergency_room_without_hospital(self, normalizer):
        """Test that 'emergency room' alone without hospital name returns None."""
        canonical, confident, warning = normalizer.normalize("חדר מיון")
        assert canonical is None
        assert confident is False
        assert warning is not None
    
    def test_generic_emergency(self, normalizer):
        """Test generic emergency department description."""
        canonical, confident, warning = normalizer.normalize("מיון כללי")
        assert canonical is None
        assert confident is False
    
    def test_city_name_only(self, normalizer):
        """Test that city name alone for city with no aliases is not matched."""
        canonical, confident, warning = normalizer.normalize("ירושלים")
        # City name alone is ambiguous - multiple hospitals in Jerusalem
        # "ירושלים" is not explicitly in any alias list
        assert canonical is None
        assert confident is False
    
    def test_department_without_hospital(self, normalizer):
        """Test that department name without hospital returns None."""
        canonical, confident, warning = normalizer.normalize("פנימית ד")
        assert canonical is None
        assert confident is False


class TestUnrecognizedInstitutions:
    """Test handling of unrecognized institutions."""
    
    def test_unknown_hospital(self, normalizer):
        """Test unknown hospital returns None."""
        canonical, confident, warning = normalizer.normalize("בית חולים אלמוני")
        assert canonical is None
        assert confident is False
        assert "not found" in warning.lower()
    
    def test_physician_name(self, normalizer):
        """Test physician name returns None."""
        canonical, confident, warning = normalizer.normalize("ד״ר משה כהן")
        assert canonical is None
        assert confident is False
    
    def test_empty_sender(self, normalizer):
        """Test empty sender."""
        canonical, confident, warning = normalizer.normalize("")
        assert canonical is None
        assert confident is False
        assert "empty" in warning.lower()
    
    def test_none_sender(self, normalizer):
        """Test None sender."""
        canonical, confident, warning = normalizer.normalize(None)
        assert canonical is None
        assert confident is False


class TestIllegibleText:
    """Test handling of illegible or unclear text."""
    
    def test_random_characters(self, normalizer):
        """Test random characters."""
        canonical, confident, warning = normalizer.normalize("קסדגכה")
        assert canonical is None
        assert confident is False
    
    def test_numbers_only(self, normalizer):
        """Test numbers only."""
        canonical, confident, warning = normalizer.normalize("12345")
        assert canonical is None
        assert confident is False


class TestMixedContent:
    """Test forms with both sending and receiving institutions."""
    
    def test_should_not_match_receiving_lab(self, normalizer):
        """Test that 'המעבדה המרכזית' does not match anything."""
        canonical, confident, warning = normalizer.normalize("המעבדה המרכזית לוירולוגיה")
        assert canonical is None
        assert confident is False


class TestNormalizerStats:
    """Test normalizer statistics."""
    
    def test_get_all_canonical_names(self, normalizer):
        """Test getting all canonical names."""
        names = normalizer.get_all_canonical_names()
        assert len(names) > 0
        assert "כללית" in names
        assert any("אסף הרופא" in name for name in names)
    
    def test_get_institution_count(self, normalizer):
        """Test institution count by type."""
        counts = normalizer.get_institution_count()
        assert counts['health_fund'] == 4
        assert counts['general_hospital'] > 0
        assert 'pediatric_hospital' in counts or counts.get('pediatric_hospital', 0) >= 0
    
    def test_total_institutions(self, normalizer):
        """Test total number of institutions."""
        names = normalizer.get_all_canonical_names()
        # Should have 4 health funds + ~30 hospitals
        assert len(names) >= 30
        assert len(names) <= 40


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
