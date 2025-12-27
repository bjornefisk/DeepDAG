import unittest
from HDRP.services.synthesizer.service import SynthesizerService
from HDRP.services.shared.claims import AtomicClaim, CritiqueResult

class TestSynthesizerService(unittest.TestCase):
    def setUp(self):
        self.synthesizer = SynthesizerService()

    def _wrap(self, claim, is_valid=True):
        return CritiqueResult(claim=claim, is_valid=is_valid, reason="Test")

    def test_synthesize_report_basic(self):
        claims = [
            AtomicClaim(
                statement="Quantum computing uses qubits.",
                support_text="Quantum computing uses qubits to perform calculations.",
                source_url="https://example.com/q1"
            ),
            AtomicClaim(
                statement="Shor's algorithm breaks RSA.",
                support_text="RSA encryption is vulnerable to Shor's algorithm.",
                source_url="https://example.com/q2"
            )
        ]
        # Wrap in valid CritiqueResults
        results = [self._wrap(c) for c in claims]
        report = self.synthesizer.synthesize(results)
        
        self.assertIn("# Research Report", report)
        self.assertIn("Quantum computing uses qubits.", report)
        # Updated: synthesizer now shows citations inline, not [Source] links
        self.assertIn("[1]", report)
        self.assertIn("## Bibliography", report)
        self.assertIn("https://example.com/q1", report)
        self.assertIn("https://example.com/q2", report)

    def test_synthesize_filters_invalid_claims(self):
        valid_claim = AtomicClaim(statement="Valid Fact", source_url="http://valid.com")
        invalid_claim = AtomicClaim(statement="Invalid Fact", source_url="http://fake.com")
        
        results = [
            self._wrap(valid_claim, is_valid=True),
            self._wrap(invalid_claim, is_valid=False)
        ]
        
        report = self.synthesizer.synthesize(results)
        
        self.assertIn("Valid Fact", report)
        self.assertNotIn("Invalid Fact", report)
        self.assertIn("http://valid.com", report)
        self.assertNotIn("http://fake.com", report)

    def test_synthesize_empty_results(self):
        report = self.synthesizer.synthesize([])
        self.assertEqual(report, "No verified information found.")

    def test_synthesize_only_invalid_results(self):
        claim = AtomicClaim(statement="Bad", source_url="http://bad.com")
        results = [self._wrap(claim, is_valid=False)]
        report = self.synthesizer.synthesize(results)
        self.assertEqual(report, "No verified information found.")

    def test_synthesize_duplicate_sources(self):
        claims = [
            AtomicClaim(statement="A", source_url="http://site.com/1"),
            AtomicClaim(statement="B", source_url="http://site.com/1"), # Duplicate source
            AtomicClaim(statement="C", source_url="http://site.com/2"),
        ]
        results = [self._wrap(c) for c in claims]
        report = self.synthesizer.synthesize(results)
        
        # Bibliography should list http://site.com/1 only once
        bib_section = report.split("## Bibliography")[1]
        self.assertEqual(bib_section.count("http://site.com/1"), 1)

    def test_synthesize_missing_support_text(self):
        claim = AtomicClaim(statement="Fact without support snippet.", source_url="http://site.com/3")
        results = [self._wrap(claim)]
        report = self.synthesizer.synthesize(results)
        self.assertIn("Fact without support snippet.", report)
        # Updated: synthesizer now shows support text as quotes, not "Support:" prefix
        # If support_text is missing or equals statement, no quote block is shown
        self.assertNotIn("> *\"", report) # Should not generate support block for missing support

if __name__ == "__main__":
    unittest.main()