import unittest
from HDRP.services.synthesizer.service import SynthesizerService
from HDRP.services.shared.claims import AtomicClaim

class TestSynthesizerService(unittest.TestCase):
    def setUp(self):
        self.synthesizer = SynthesizerService()

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
        report = self.synthesizer.synthesize(claims)
        
        self.assertIn("# Research Report", report)
        self.assertIn("Quantum computing uses qubits.", report)
        self.assertIn("[Source](https://example.com/q1)", report)
        self.assertIn("## Bibliography", report)
        self.assertIn("- https://example.com/q1", report)
        self.assertIn("- https://example.com/q2", report)

    def test_synthesize_empty_claims(self):
        report = self.synthesizer.synthesize([])
        self.assertEqual(report, "No verified information found.")

    def test_synthesize_duplicate_sources(self):
        claims = [
            AtomicClaim(statement="A", source_url="http://site.com/1"),
            AtomicClaim(statement="B", source_url="http://site.com/1"), # Duplicate source
            AtomicClaim(statement="C", source_url="http://site.com/2"),
        ]
        report = self.synthesizer.synthesize(claims)
        
        # Bibliography should list http://site.com/1 only once
        self.assertEqual(report.count("http://site.com/1"), 3) # 2 in text + 1 in bib
        # Actually: 
        # Text: [Source](http://site.com/1) x2
        # Bib: - http://site.com/1 x1
        # Total 3.
        
        # Let's check the Bibliography section specifically
        bib_section = report.split("## Bibliography")[1]
        self.assertEqual(bib_section.count("http://site.com/1"), 1)

    def test_synthesize_missing_support_text(self):
        claims = [
            AtomicClaim(statement="Fact without support snippet.", source_url="http://site.com/3")
        ]
        report = self.synthesizer.synthesize(claims)
        self.assertIn("Fact without support snippet.", report)
        self.assertNotIn("> *Support:", report) # Should not generate support block

if __name__ == "__main__":
    unittest.main()