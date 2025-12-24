import unittest
from HDRP.services.shared.claims import ClaimExtractor

class TestClaimExtractor(unittest.TestCase):
    def setUp(self):
        self.extractor = ClaimExtractor()

    def test_basic_extraction(self):
        text = "Quantum computing uses qubits to perform calculations. RSA encryption is vulnerable to Shor's algorithm. I think it is very cool."
        response = self.extractor.extract(text, source_uri="https://example.com")
        
        # Should extract the first two but ignore the opinion
        self.assertEqual(len(response.claims), 2)
        self.assertEqual(response.claims[0].statement, "Quantum computing uses qubits to perform calculations.")
        self.assertEqual(response.claims[1].statement, "RSA encryption is vulnerable to Shor's algorithm.")
        self.assertEqual(response.claims[0].source_uri, "https://example.com")

    def test_empty_input(self):
        response = self.extractor.extract("")
        self.assertEqual(len(response.claims), 0)

    def test_filtering(self):
        # Questions and very short sentences should be filtered
        text = "What is quantum? It is cold. This is a very important factual statement about physics."
        response = self.extractor.extract(text)
        self.assertEqual(len(response.claims), 1)
        self.assertTrue("physics" in response.claims[0].statement)

if __name__ == "__main__":
    unittest.main()
