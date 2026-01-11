import unittest
from datetime import datetime, timezone
from HDRP.services.shared.claims import ClaimExtractor, AtomicClaim, CritiqueResult
from HDRP.services.researcher.service import ResearcherService
from HDRP.services.critic.service import CriticService
from HDRP.services.synthesizer.service import SynthesizerService
from HDRP.tools.search.simulated import SimulatedSearchProvider


class TestClaimTraceability(unittest.TestCase):
    """Tests that verify complete claim-to-source traceability throughout the pipeline."""
    
    def setUp(self):
        self.extractor = ClaimExtractor()
        self.search_provider = SimulatedSearchProvider()
        self.researcher = ResearcherService(self.search_provider, run_id="test-traceability")
        self.critic = CriticService()
        self.synthesizer = SynthesizerService()
    
    def test_extractor_populates_all_traceability_fields(self):
        """Verify that the extractor creates claims with complete traceability metadata."""
        text = "Quantum computers use superposition to process information. This enables parallel computation at scale."
        source_url = "https://example.com/quantum"
        source_title = "Introduction to Quantum Computing"
        source_rank = 1
        source_node_id = "node_test_1"
        
        response = self.extractor.extract(
            text, 
            source_url=source_url,
            source_node_id=source_node_id,
            source_title=source_title,
            source_rank=source_rank
        )
        
        self.assertGreater(len(response.claims), 0, "Should extract at least one claim")
        
        for claim in response.claims:
            # Check all core traceability fields
            self.assertIsNotNone(claim.extracted_at, "extracted_at should be set")
            self.assertEqual(claim.source_url, source_url)
            self.assertEqual(claim.source_node_id, source_node_id)
            self.assertEqual(claim.source_title, source_title)
            self.assertEqual(claim.source_rank, source_rank)
            self.assertIsNotNone(claim.support_text, "support_text should be set")
            
            # Verify timestamp format
            self.assertTrue(claim.extracted_at.endswith('Z'), "Timestamp should be UTC with Z suffix")
            # Should be parseable as ISO format
            datetime.fromisoformat(claim.extracted_at[:-1])
    
    def test_extraction_timestamp_consistency(self):
        """All claims from the same extraction should have the same timestamp."""
        text = "First fact here. Second fact there. Third fact everywhere."
        
        response = self.extractor.extract(text, source_url="https://test.com")
        
        if len(response.claims) > 1:
            timestamps = [c.extracted_at for c in response.claims]
            # All timestamps should be identical since they're from same extraction
            self.assertEqual(len(set(timestamps)), 1, "All claims should share the same timestamp")
    
    def test_support_offset_calculation(self):
        """Verify that support_offset correctly identifies the claim location in source text."""
        text = "Some introductory text here. Quantum computing enables new algorithms. More text follows."
        
        response = self.extractor.extract(text, source_url="https://test.com")
        
        for claim in response.claims:
            if claim.support_offset is not None:
                # The support text should be found at the calculated offset
                extracted_portion = text[claim.support_offset:claim.support_offset + len(claim.support_text)]
                self.assertEqual(extracted_portion, claim.support_text,
                               "support_offset should point to correct location in source")
    
    def test_researcher_propagates_source_metadata(self):
        """Verify that researcher passes title and rank info to extracted claims."""
        query = "quantum computing research"
        
        claims = self.researcher.research(query, source_node_id="node_researcher_test")
        
        self.assertGreater(len(claims), 0, "Should extract claims from search results")
        
        for claim in claims:
            # All claims should have extraction timestamps
            self.assertIsNotNone(claim.extracted_at, "Researcher should ensure claims have timestamps")
            
            # Should have source metadata
            self.assertIsNotNone(claim.source_url, "Should have source URL")
            self.assertIsNotNone(claim.source_title, "Should have source title")
            self.assertIsNotNone(claim.source_rank, "Should have search rank")
            
            # Rank should be a positive integer
            self.assertIsInstance(claim.source_rank, int)
            self.assertGreater(claim.source_rank, 0, "Search rank should be 1-indexed")
    
    def test_critic_validates_timestamp_presence(self):
        """Critic should reject claims missing required traceability fields."""
        # Create a claim WITHOUT timestamp (simulating old data)
        incomplete_claim = AtomicClaim(
            statement="This claim lacks a timestamp.",
            support_text="This claim lacks a timestamp.",
            source_url="https://example.com/test",
            confidence=0.8
            # Note: extracted_at is intentionally omitted
        )
        
        results = self.critic.verify([incomplete_claim], task="test task")
        
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].is_valid, "Should reject claims without timestamps")
        self.assertIn("timestamp", results[0].reason.lower(), 
                     "Rejection reason should mention timestamp")
    
    def test_critic_validates_timestamp_format(self):
        """Critic should reject claims with malformed timestamps."""
        malformed_claim = AtomicClaim(
            statement="This claim has a bad timestamp.",
            support_text="This claim has a bad timestamp.",
            source_url="https://example.com/test",
            confidence=0.8,
            extracted_at="not-a-valid-timestamp"
        )
        
        results = self.critic.verify([malformed_claim], task="test task")
        
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].is_valid, "Should reject claims with invalid timestamps")
        self.assertIn("timestamp", results[0].reason.lower())
    
    def test_critic_adjusts_confidence_scores(self):
        """Critic should adjust confidence based on verification outcome."""
        valid_claim = AtomicClaim(
            statement="Water boils at 100 degrees Celsius at sea level.",
            support_text="Water boils at 100 degrees Celsius at sea level.",
            source_url="https://example.com/chemistry",
            confidence=0.6,
            extracted_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        )
        
        results = self.critic.verify([valid_claim], task="water boiling chemistry")
        
        self.assertEqual(len(results), 1)
        if results[0].is_valid:
            # Confidence should increase for verified claims
            self.assertGreater(results[0].claim.confidence, 0.6,
                             "Verified claims should have increased confidence")
    
    def test_synthesizer_includes_metadata_section(self):
        """Synthesizer should include Deep Research Report structure."""
        claim = AtomicClaim(
            statement="Quantum entanglement enables quantum teleportation.",
            support_text="Quantum entanglement enables quantum teleportation.",
            source_url="https://example.com/quantum",
            source_title="Quantum Mechanics Review",
            source_rank=1,
            confidence=0.9,
            extracted_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        )
        
        result = CritiqueResult(claim=claim, is_valid=True, reason="Verified", entailment_score=0.95)
        report = self.synthesizer.synthesize([result], context={"query": "quantum computing"}, run_id="test-123")
        
        # Verify new report structure sections
        self.assertIn("HDRP Deep Research Report", report, "Should include report header")
        self.assertIn("1. Executive Synthesis", report, "Should include Executive Synthesis section")
        self.assertIn("2. Verified Findings", report, "Should include Verified Findings section")
        self.assertIn("3. Evidence & Traceability", report, "Should include Evidence & Traceability section")
        self.assertIn("4. DAG Execution Summary", report, "Should include DAG Execution Summary section")
        self.assertIn("5. Bibliography", report, "Should include Bibliography section")
        self.assertIn("Run ID", report, "Should include run ID")
        self.assertIn("Generated", report, "Should include generation timestamp")
    
    def test_synthesizer_bibliography_includes_titles(self):
        """Bibliography should show source titles, not just URLs."""
        claim = AtomicClaim(
            statement="Machine learning improves with more data.",
            support_text="Machine learning improves with more data.",
            source_url="https://example.com/ml",
            source_title="Machine Learning Fundamentals",
            source_rank=2,
            confidence=0.85,
            extracted_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        )
        
        result = CritiqueResult(claim=claim, is_valid=True, reason="Verified", entailment_score=0.90)
        report = self.synthesizer.synthesize([result], context={"query": "machine learning"}, run_id="test-ml")
        
        self.assertIn("5. Bibliography", report)
        self.assertIn("Machine Learning Fundamentals", report,
                     "Bibliography should include source title")
        self.assertIn("https://example.com/ml", report,
                     "Bibliography should include URL")
    
    def test_synthesizer_shows_search_rank_in_bibliography(self):
        """Bibliography should indicate search ranking for transparency."""
        claim = AtomicClaim(
            statement="Neural networks consist of interconnected layers.",
            support_text="Neural networks consist of interconnected layers.",
            source_url="https://example.com/nn",
            source_title="Neural Network Basics",
            source_rank=3,
            confidence=0.9,
            extracted_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        )
        
        result = CritiqueResult(claim=claim, is_valid=True, reason="Verified", entailment_score=0.92)
        report = self.synthesizer.synthesize([result], context={"query": "neural networks"}, run_id="test-nn")
        
        self.assertIn("Search rank: 3", report,
                     "Bibliography should show search rank")
    
    def test_end_to_end_traceability_preservation(self):
        """Verify that traceability metadata survives the entire pipeline."""
        # Run through complete pipeline
        query = "quantum computing applications"
        
        # Step 1: Research
        claims = self.researcher.research(query, source_node_id="node_e2e_test")
        self.assertGreater(len(claims), 0)
        
        # Verify all claims have complete traceability after extraction
        for claim in claims:
            self.assertIsNotNone(claim.extracted_at)
            self.assertIsNotNone(claim.source_url)
            self.assertIsNotNone(claim.source_title)
            self.assertIsNotNone(claim.source_rank)
        
        # Step 2: Critic
        critique_results = self.critic.verify(claims, task=query)
        verified_claims = [r.claim for r in critique_results if r.is_valid]
        
        # Traceability should still be intact after criticism
        for claim in verified_claims:
            self.assertIsNotNone(claim.extracted_at, "Timestamp lost in critic stage")
            self.assertIsNotNone(claim.source_title, "Title lost in critic stage")
            self.assertIsNotNone(claim.source_rank, "Rank lost in critic stage")
        
        # Step 3: Synthesizer
        report = self.synthesizer.synthesize(critique_results, context={"query": query}, run_id="test-e2e")
        
        # Report should contain new Deep Research Report structure
        self.assertIn("HDRP Deep Research Report", report)
        self.assertIn("1. Executive Synthesis", report)
        self.assertIn("3. Evidence & Traceability", report)
        self.assertIn("5. Bibliography", report)
        
        # Should show at least one source title
        source_titles = [c.source_title for c in verified_claims if c.source_title]
        if source_titles:
            self.assertTrue(any(title in report for title in source_titles),
                           "At least one source title should appear in report")
    
    def test_empty_optional_fields_dont_break_pipeline(self):
        """System should handle missing optional traceability fields gracefully."""
        # Create a claim with only mandatory fields
        minimal_claim = AtomicClaim(
            statement="This is a minimal but valid claim with timestamp.",
            support_text="This is a minimal but valid claim with timestamp.",
            source_url="https://example.com/minimal",
            confidence=0.7,
            extracted_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            # source_title and source_rank are omitted
        )
        
        # Should pass critic (has timestamp)
        results = self.critic.verify([minimal_claim], task="minimal test")
        self.assertEqual(len(results), 1)
        
        # Should synthesize successfully
        report = self.synthesizer.synthesize(results, context={"query": "minimal test"}, run_id="test-minimal")
        self.assertIsInstance(report, str)
        self.assertGreater(len(report), 0)
    
    def test_verification_hash_generation(self):
        """Test that verification hashes are generated correctly."""
        claim = AtomicClaim(
            statement="Test claim for hash generation.",
            support_text="Test claim for hash generation.",
            source_url="https://example.com/test",
            source_title="Test Source",
            confidence=0.8,
            extracted_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        )
        
        result = CritiqueResult(claim=claim, is_valid=True, reason="Verified", entailment_score=0.85)
        report = self.synthesizer.synthesize([result], context={"query": "test"}, run_id="test-hash")
        
        # Should include verification hash in Evidence & Traceability section
        self.assertIn("Verification Hash", report, "Should include verification hash")
        self.assertIn("3. Evidence & Traceability", report)
    
    def test_confidence_level_mapping(self):
        """Test that confidence levels are correctly mapped to High/Medium/Low."""
        high_conf_claim = AtomicClaim(
            statement="High confidence claim.",
            support_text="High confidence claim.",
            source_url="https://example.com/high",
            confidence=0.9,
            extracted_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        )
        
        result = CritiqueResult(claim=high_conf_claim, is_valid=True, reason="Verified", entailment_score=0.95)
        report = self.synthesizer.synthesize([result], context={"query": "test"}, run_id="test-conf")
        
        # Should show High confidence in Verified Findings section
        self.assertIn("2. Verified Findings", report)
        self.assertIn("Confidence: High", report, "Should map high scores to 'High' confidence")
    
    def test_rejected_claims_in_separate_section(self):
        """Test that rejected claims appear in a separate subsection."""
        verified_claim = AtomicClaim(
            statement="This claim is verified.",
            support_text="This claim is verified.",
            source_url="https://example.com/verified",
            confidence=0.8,
            extracted_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        )
        
        rejected_claim = AtomicClaim(
            statement="This claim is rejected.",
            support_text="This claim is rejected.",
            source_url="https://example.com/rejected",
            confidence=0.5,
            extracted_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        )
        
        results = [
            CritiqueResult(claim=verified_claim, is_valid=True, reason="Verified", entailment_score=0.85),
            CritiqueResult(claim=rejected_claim, is_valid=False, reason="Insufficient evidence", entailment_score=0.3)
        ]
        
        report = self.synthesizer.synthesize(results, context={"query": "test"}, run_id="test-rejected")
        
        # Should have both verified and rejected sections
        self.assertIn("Verified Claims Evidence", report)
        self.assertIn("Rejected Claims", report)
        self.assertIn("✔ Entails", report)
        self.assertIn("✖ Rejected", report)


if __name__ == "__main__":
    unittest.main()

