import unittest
from HDRP.services.synthesizer.service import SynthesizerService
from HDRP.services.shared.claims import AtomicClaim

class TestSynthesizerService(unittest.TestCase):
    def setUp(self):
        self.synthesizer = SynthesizerService()

    def test_synthesize_report(self):
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
        print(report)

if __name__ == "__main__":
    unittest.main()
