import unittest
from HDRP.services.shared.claims import ClaimExtractor

class TestClaimExtractor(unittest.TestCase):
    def setUp(self):
        self.extractor = ClaimExtractor()

    def test_basic_extraction(self):
        text = "Quantum computing uses qubits to perform calculations. RSA encryption is vulnerable to Shor's algorithm. I think it is very cool."
        response = self.extractor.extract(text, source_url="https://example.com")
        
        # Should extract the first two but ignore the opinion
        self.assertEqual(len(response.claims), 2)
        self.assertEqual(response.claims[0].statement, "Quantum computing uses qubits to perform calculations.")
        self.assertEqual(response.claims[1].statement, "RSA encryption is vulnerable to Shor's algorithm.")
        self.assertEqual(response.claims[0].source_url, "https://example.com")
        self.assertEqual(response.claims[0].support_text, "Quantum computing uses qubits to perform calculations.")

    def test_empty_input(self):
        response = self.extractor.extract("")
        self.assertEqual(len(response.claims), 0)

    def test_filtering(self):
        # Questions and very short sentences should be filtered
        text = "What is quantum? It is cold. This is a very important factual statement about physics."
        response = self.extractor.extract(text)
        self.assertEqual(len(response.claims), 1)
        self.assertTrue("physics" in response.claims[0].statement)

    def test_entity_discovery(self):
        text = "The launch of Apollo 11 was a major event for NASA and the USA."
        response = self.extractor.extract(text)
        self.assertEqual(len(response.claims), 1)
        claim = response.claims[0]
        # "Apollo", "NASA", "USA" should be found. "The" is skipped as first word.
        self.assertIn("NASA", claim.discovered_entities)
        self.assertIn("USA", claim.discovered_entities)
        # "Apollo" might be found if "11" is handled, or just "Apollo" depending on split
        # My regex only captures words starting with capital. 
        # "11" is not captured.
        
if __name__ == "__main__":
    unittest.main()
