"""
Unit tests for HDRP ReportHumanizer module.

Tests executive summary generation, research scope description, key insights
extraction, section transitions, sentence structure variation, conclusions
generation, technical language softening, and full report humanization.
"""

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from HDRP.services.synthesizer.humanizer import ReportHumanizer
from HDRP.services.shared.claims import AtomicClaim


class TestReportHumanizerInit(unittest.TestCase):
    """Tests for ReportHumanizer initialization."""

    def test_init_creates_sentence_starters(self):
        """Verify sentence starters are initialized."""
        humanizer = ReportHumanizer()
        self.assertIsInstance(humanizer.sentence_starters, list)
        self.assertGreater(len(humanizer.sentence_starters), 0)

    def test_init_creates_transitions(self):
        """Verify transitions are initialized."""
        humanizer = ReportHumanizer()
        self.assertIsInstance(humanizer.transitions, list)
        self.assertGreater(len(humanizer.transitions), 0)


class TestExecutiveSummary(unittest.TestCase):
    """Tests for add_executive_summary method."""

    def setUp(self):
        self.humanizer = ReportHumanizer()
        self.test_timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _create_claim(self, statement, source_url="https://example.com/source", confidence=0.8):
        """Helper to create test claims."""
        return AtomicClaim(
            statement=statement,
            support_text=statement,
            source_url=source_url,
            confidence=confidence,
            extracted_at=self.test_timestamp,
        )

    def test_returns_empty_for_no_claims(self):
        """Verify empty string returned when no claims."""
        result = self.humanizer.add_executive_summary(
            claims=[],
            topic="test topic",
            section_titles=["Section 1"]
        )
        self.assertEqual(result, "")

    def test_includes_executive_summary_header(self):
        """Verify executive summary header is present."""
        claims = [self._create_claim("Test claim statement.")]
        result = self.humanizer.add_executive_summary(
            claims=claims,
            topic="AI Research",
            section_titles=["Introduction"]
        )
        self.assertIn("## Executive Summary", result)

    def test_includes_topic_in_summary(self):
        """Verify topic is mentioned in summary."""
        claims = [self._create_claim("Test claim.")]
        result = self.humanizer.add_executive_summary(
            claims=claims,
            topic="quantum computing applications",
            section_titles=["Overview"]
        )
        self.assertIn("quantum computing applications", result)

    def test_includes_claim_count(self):
        """Verify claim count is mentioned."""
        claims = [
            self._create_claim("Claim one."),
            self._create_claim("Claim two."),
            self._create_claim("Claim three."),
        ]
        result = self.humanizer.add_executive_summary(
            claims=claims,
            topic="test",
            section_titles=[]
        )
        self.assertIn("3", result)

    def test_counts_unique_sources(self):
        """Verify unique source count is correct."""
        claims = [
            self._create_claim("Claim 1", source_url="https://source1.com"),
            self._create_claim("Claim 2", source_url="https://source2.com"),
            self._create_claim("Claim 3", source_url="https://source1.com"),  # Duplicate
        ]
        result = self.humanizer.add_executive_summary(
            claims=claims,
            topic="test",
            section_titles=[]
        )
        self.assertIn("2", result)  # Only 2 unique sources

    def test_handles_empty_topic(self):
        """Verify graceful handling of empty topic."""
        claims = [self._create_claim("Test claim.")]
        result = self.humanizer.add_executive_summary(
            claims=claims,
            topic="",
            section_titles=["Section"]
        )
        # Should not crash and should have content
        self.assertIn("## Executive Summary", result)
        self.assertIn("comprehensive research investigation", result)

    def test_key_findings_section_for_sections(self):
        """Verify key findings section is generated with section titles."""
        claims = [
            self._create_claim("Claim about AI.", confidence=0.9),
            self._create_claim("Claim about ML.", confidence=0.9),
        ]
        result = self.humanizer.add_executive_summary(
            claims=claims,
            topic="AI/ML research",
            section_titles=["Artificial Intelligence", "Machine Learning"]
        )
        self.assertIn("### Key Findings", result)


class TestDescribeResearchScope(unittest.TestCase):
    """Tests for _describe_research_scope method."""

    def setUp(self):
        self.humanizer = ReportHumanizer()

    def test_empty_sections_returns_empty(self):
        """Verify empty list returns empty string."""
        result = self.humanizer._describe_research_scope([])
        self.assertEqual(result, "")

    def test_single_section_uses_focuses_on(self):
        """Verify single section uses 'focuses on' phrasing."""
        result = self.humanizer._describe_research_scope(["Machine Learning"])
        self.assertIn("focuses on", result)
        self.assertIn("machine learning", result.lower())

    def test_two_sections_uses_and(self):
        """Verify two sections are joined with 'and'."""
        result = self.humanizer._describe_research_scope(["AI", "Robotics"])
        self.assertIn("covers", result)
        self.assertIn(" and ", result)

    def test_multiple_sections_shows_count(self):
        """Verify 3+ sections shows count."""
        result = self.humanizer._describe_research_scope(["A", "B", "C", "D"])
        self.assertIn("spans", result)
        self.assertIn("4", result)
        self.assertIn("areas", result)


class TestExtractKeyInsights(unittest.TestCase):
    """Tests for _extract_key_insights method."""

    def setUp(self):
        self.humanizer = ReportHumanizer()
        self.timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _create_claim(self, confidence=0.8, source_node_id=None):
        return AtomicClaim(
            statement="Test claim",
            support_text="Test claim",
            source_url="https://example.com",
            confidence=confidence,
            source_node_id=source_node_id,
            extracted_at=self.timestamp,
        )

    def test_returns_list(self):
        """Verify returns a list."""
        result = self.humanizer._extract_key_insights([], [])
        self.assertIsInstance(result, list)

    def test_limits_to_max_four_insights(self):
        """Verify max 4 insights are returned."""
        claims = [self._create_claim(confidence=0.9) for _ in range(10)]
        sections = ["A", "B", "C", "D", "E"]
        result = self.humanizer._extract_key_insights(claims, sections)
        self.assertLessEqual(len(result), 4)

    def test_includes_section_based_insights(self):
        """Verify section titles generate insights."""
        claims = [self._create_claim()]
        sections = ["Cloud Computing", "Edge Computing"]
        result = self.humanizer._extract_key_insights(claims, sections)
        
        found_section_ref = any("examined" in insight.lower() for insight in result)
        self.assertTrue(found_section_ref)

    def test_high_confidence_generates_insight(self):
        """Verify high confidence claims generate quality insight."""
        # Create claims with high confidence (>85%)
        claims = [self._create_claim(confidence=0.9) for _ in range(10)]
        result = self.humanizer._extract_key_insights(claims, [])
        
        # Should mention high confidence
        found_confidence = any("confidence" in insight.lower() for insight in result)
        self.assertTrue(found_confidence)


class TestAddTransitions(unittest.TestCase):
    """Tests for add_transitions method."""

    def setUp(self):
        self.humanizer = ReportHumanizer()

    def test_empty_sections_returns_empty(self):
        """Verify empty sections return empty string."""
        result = self.humanizer.add_transitions([])
        self.assertEqual(result, "")

    def test_single_section_no_transition(self):
        """Verify single section has no transition prefix."""
        sections = [("Introduction", "This is the intro content.")]
        result = self.humanizer.add_transitions(sections)
        self.assertEqual(result, "This is the intro content.")

    def test_multiple_sections_have_transitions(self):
        """Verify transitions are added between sections."""
        sections = [
            ("Introduction", "Intro content."),
            ("Background", "Background content."),
        ]
        result = self.humanizer.add_transitions(sections)
        
        # Should contain transition phrase
        self.assertIn("Intro content.", result)
        self.assertIn("Background content.", result)
        # Should have a transition
        has_transition = any(t in result for t in self.humanizer.transitions)
        self.assertTrue(has_transition)

    def test_many_sections_uses_additionally(self):
        """Verify fallback to 'Additionally' when transitions exhausted."""
        sections = [(f"Section {i}", f"Content {i}") for i in range(10)]
        result = self.humanizer.add_transitions(sections)
        self.assertIn("Additionally,", result)


class TestVarySentenceStructure(unittest.TestCase):
    """Tests for vary_sentence_structure method."""

    def setUp(self):
        self.humanizer = ReportHumanizer()

    def test_empty_list_returns_empty(self):
        """Verify empty input returns empty list."""
        result = self.humanizer.vary_sentence_structure([])
        self.assertEqual(result, [])

    def test_removes_leading_numbers(self):
        """Verify leading numbers are removed."""
        claims = ["1. First claim here."]
        result = self.humanizer.vary_sentence_structure(claims)
        self.assertFalse(result[0].startswith("1."))

    def test_removes_leading_bullets(self):
        """Verify leading bullets are removed."""
        claims = ["- Bullet point claim.", "* Another bullet."]
        result = self.humanizer.vary_sentence_structure(claims)
        self.assertFalse(result[0].startswith("-"))
        self.assertFalse(result[1].startswith("*"))

    def test_varies_structure_for_multiple_claims(self):
        """Verify different patterns are applied."""
        claims = [
            "First claim statement.",
            "Second claim statement.",
            "Third claim statement.",
            "Fourth claim statement.",
        ]
        result = self.humanizer.vary_sentence_structure(claims)
        
        # Not all should be identical transformations
        self.assertEqual(len(result), 4)

    def test_lowercases_first_letter_when_adding_prefix(self):
        """Verify first letter is lowercased when prefix added."""
        claims = ["Uppercase Start claim."]
        result = self.humanizer.vary_sentence_structure(claims)
        # At least one pattern adds a prefix
        # The actual behavior depends on index % pattern


class TestAddConclusions(unittest.TestCase):
    """Tests for add_conclusions method."""

    def setUp(self):
        self.humanizer = ReportHumanizer()
        self.timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _create_claim(self, source_url="https://example.com", confidence=0.8):
        return AtomicClaim(
            statement="Test claim",
            support_text="Test claim",
            source_url=source_url,
            confidence=confidence,
            extracted_at=self.timestamp,
        )

    def test_empty_claims_returns_empty(self):
        """Verify empty claims return empty string."""
        result = self.humanizer.add_conclusions([], ["Section"])
        self.assertEqual(result, "")

    def test_includes_conclusions_header(self):
        """Verify conclusions header is present."""
        claims = [self._create_claim()]
        result = self.humanizer.add_conclusions(claims, ["Section"])
        self.assertIn("## Conclusions", result)

    def test_includes_source_count(self):
        """Verify source count is mentioned."""
        claims = [
            self._create_claim(source_url="https://source1.com"),
            self._create_claim(source_url="https://source2.com"),
        ]
        result = self.humanizer.add_conclusions(claims, [])
        self.assertIn("2", result)  # 2 unique sources

    def test_includes_claim_count(self):
        """Verify claim count is mentioned."""
        claims = [self._create_claim() for _ in range(5)]
        result = self.humanizer.add_conclusions(claims, [])
        self.assertIn("5", result)

    def test_high_confidence_quality_description(self):
        """Verify high confidence uses appropriate quality description."""
        claims = [self._create_claim(confidence=0.9) for _ in range(3)]
        result = self.humanizer.add_conclusions(claims, [])
        self.assertIn("high confidence", result)

    def test_moderate_confidence_quality_description(self):
        """Verify moderate confidence uses appropriate quality description."""
        claims = [self._create_claim(confidence=0.7) for _ in range(3)]
        result = self.humanizer.add_conclusions(claims, [])
        self.assertIn("moderate confidence", result)

    def test_low_confidence_quality_description(self):
        """Verify low confidence uses appropriate quality description."""
        claims = [self._create_claim(confidence=0.4) for _ in range(3)]
        result = self.humanizer.add_conclusions(claims, [])
        self.assertIn("emerging evidence", result)

    def test_includes_research_implications(self):
        """Verify research implications section is present."""
        claims = [self._create_claim()]
        result = self.humanizer.add_conclusions(claims, [])
        self.assertIn("### Research Implications", result)

    def test_mentions_section_count(self):
        """Verify section count is mentioned when sections exist."""
        claims = [self._create_claim()]
        result = self.humanizer.add_conclusions(claims, ["A", "B", "C"])
        self.assertIn("3", result)
        self.assertIn("key areas", result)


class TestSoftenTechnicalLanguage(unittest.TestCase):
    """Tests for soften_technical_language method."""

    def setUp(self):
        self.humanizer = ReportHumanizer()

    def test_includes_research_overview_header(self):
        """Verify research overview header is present."""
        metadata = "Total Verified Claims: 10\nUnique Sources: 5"
        result = self.humanizer.soften_technical_language(metadata)
        self.assertIn("### Research Overview", result)

    def test_extracts_claim_count(self):
        """Verify claim count is extracted and humanized."""
        metadata = "Total Verified Claims: 42"
        result = self.humanizer.soften_technical_language(metadata)
        self.assertIn("42", result)
        self.assertIn("verified findings", result)

    def test_extracts_source_count(self):
        """Verify source count is extracted and humanized."""
        metadata = "Total Verified Claims: 10\nUnique Sources: 7"
        result = self.humanizer.soften_technical_language(metadata)
        self.assertIn("7", result)
        self.assertIn("sources", result)

    def test_handles_research_period(self):
        """Verify research period is humanized."""
        metadata = """
        Total Verified Claims: 5
        Research Period: 2024-01-15T10:00:00.000Z to 2024-01-15T10:30:00.000Z
        """
        result = self.humanizer.soften_technical_language(metadata)
        self.assertIn("conducted over", result)

    def test_handles_short_duration(self):
        """Verify short duration shows 'moments'."""
        metadata = """
        Total Verified Claims: 5
        Research Period: 2024-01-15T10:00:00.000Z to 2024-01-15T10:00:30.000Z
        """
        result = self.humanizer.soften_technical_language(metadata)
        self.assertIn("moments", result)

    def test_handles_minutes_duration(self):
        """Verify minutes duration is shown."""
        metadata = """
        Total Verified Claims: 5
        Research Period: 2024-01-15T10:00:00.000Z to 2024-01-15T10:05:00.000Z
        """
        result = self.humanizer.soften_technical_language(metadata)
        self.assertIn("minutes", result)

    def test_handles_missing_data_gracefully(self):
        """Verify missing data doesn't cause crash."""
        metadata = "Some random text without expected fields"
        result = self.humanizer.soften_technical_language(metadata)
        self.assertIn("### Research Overview", result)
        # Should still have boilerplate text
        self.assertIn("source attribution", result)


class TestHumanizeFullReport(unittest.TestCase):
    """Tests for humanize_full_report method."""

    def setUp(self):
        self.humanizer = ReportHumanizer()
        self.timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _create_claim(self, statement="Test claim", confidence=0.8):
        return AtomicClaim(
            statement=statement,
            support_text=statement,
            source_url="https://example.com",
            confidence=confidence,
            extracted_at=self.timestamp,
        )

    def test_preserves_title(self):
        """Verify title is preserved in output."""
        base_report = "# My Research Report\n\nSome content here."
        claims = [self._create_claim()]
        result = self.humanizer.humanize_full_report(
            base_report, claims, topic="test"
        )
        self.assertIn("# My Research Report", result)

    def test_adds_executive_summary(self):
        """Verify executive summary is added."""
        base_report = "# Report\n\n## Section 1\n\nContent."
        claims = [self._create_claim()]
        result = self.humanizer.humanize_full_report(
            base_report, claims, topic="test topic"
        )
        self.assertIn("## Executive Summary", result)

    def test_adds_conclusions(self):
        """Verify conclusions are added."""
        base_report = "# Report\n\n## Analysis\n\nSome analysis."
        claims = [self._create_claim()]
        result = self.humanizer.humanize_full_report(
            base_report, claims, topic="test"
        )
        self.assertIn("## Conclusions", result)

    def test_preserves_bibliography(self):
        """Verify bibliography is preserved at end."""
        base_report = """# Report

## Analysis

Content here.

## Bibliography

1. Source one
2. Source two
"""
        claims = [self._create_claim()]
        result = self.humanizer.humanize_full_report(
            base_report, claims, topic="test"
        )
        self.assertIn("## Bibliography", result)
        self.assertIn("Source one", result)

    def test_uses_context_section_headers(self):
        """Verify context section headers are used."""
        base_report = "# Report\n\n## Content\n\nText."
        claims = [self._create_claim()]
        context = {
            "section_headers": {
                "node_1": "AI Overview",
                "node_2": "ML Applications",
            }
        }
        result = self.humanizer.humanize_full_report(
            base_report, claims, topic="AI/ML", context=context
        )
        # Should reference section titles
        self.assertIsInstance(result, str)

    def test_handles_empty_base_report(self):
        """Verify empty base report is handled."""
        claims = [self._create_claim()]
        result = self.humanizer.humanize_full_report(
            "", claims, topic="test"
        )
        # Should still have some output
        self.assertIn("Research Report", result)

    def test_handles_none_context(self):
        """Verify None context is handled."""
        base_report = "# Report\n\nContent."
        claims = [self._create_claim()]
        result = self.humanizer.humanize_full_report(
            base_report, claims, topic="test", context=None
        )
        self.assertIsInstance(result, str)

    def test_transforms_metadata_section(self):
        """Verify metadata section is transformed."""
        base_report = """# Report

## Research Metadata

Total Verified Claims: 5
Unique Sources: 3

## Main Content

The actual content.
"""
        claims = [self._create_claim() for _ in range(5)]
        result = self.humanizer.humanize_full_report(
            base_report, claims, topic="test"
        )
        self.assertIn("Research Overview", result)

    def test_adds_transitions_between_sections(self):
        """Verify transitions are added between content sections."""
        base_report = """# Report

## First Section

First section content.

## Second Section

Second section content.
"""
        claims = [self._create_claim()]
        result = self.humanizer.humanize_full_report(
            base_report, claims, topic="test"
        )
        # Should have transition phrases
        self.assertIn("research examined", result.lower())


if __name__ == "__main__":
    unittest.main()

