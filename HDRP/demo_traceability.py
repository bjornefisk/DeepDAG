#!/usr/bin/env python3
"""
Demo script showing the enhanced claim-to-source traceability in action.
This demonstrates how claims flow through the entire pipeline with complete
traceability metadata.
"""

from HDRP.tools.search.simulated import SimulatedSearchProvider
from HDRP.services.researcher.service import ResearcherService
from HDRP.services.critic.service import CriticService
from HDRP.services.synthesizer.service import SynthesizerService

def main():
    print("=" * 80)
    print("CLAIM-TO-SOURCE TRACEABILITY DEMONSTRATION")
    print("=" * 80)
    print()
    
    # Initialize services
    search_provider = SimulatedSearchProvider()
    researcher = ResearcherService(search_provider, run_id="traceability-demo")
    critic = CriticService(run_id="traceability-demo")
    synthesizer = SynthesizerService()
    
    query = "Latest developments in quantum computing"
    
    # Step 1: Research and extract claims with traceability
    print(f"🔍 Step 1: Researching '{query}'...")
    claims = researcher.research(query, source_node_id="quantum_research_2025")
    print(f"   ✓ Found {len(claims)} claims with complete traceability\n")
    
    # Show detailed traceability for first claim
    if claims:
        first_claim = claims[0]
        print("   📋 Sample Claim Details:")
        print(f"      - Statement: {first_claim.statement[:60]}...")
        print(f"      - Source URL: {first_claim.source_url}")
        print(f"      - Source Title: {first_claim.source_title}")
        print(f"      - Search Rank: #{first_claim.source_rank}")
        print(f"      - Extracted At: {first_claim.extracted_at}")
        print(f"      - Support Offset: {first_claim.support_offset}")
        print(f"      - Confidence: {first_claim.confidence:.2f}")
        print()
    
    # Step 2: Verify claims with traceability validation
    print("✅ Step 2: Verifying claims (including traceability checks)...")
    critique_results = critic.verify(claims, task=query)
    verified_count = sum(1 for r in critique_results if r.is_valid)
    rejected_count = len(critique_results) - verified_count
    print(f"   ✓ Verified: {verified_count} claims")
    print(f"   ✗ Rejected: {rejected_count} claims")
    print()
    
    # Show confidence adjustment
    verified_claims = [r.claim for r in critique_results if r.is_valid]
    if verified_claims:
        print("   📊 Confidence Score Adjustments:")
        for claim in verified_claims[:3]:
            print(f"      - {claim.statement[:50]}: confidence={claim.confidence:.2f}")
        print()
    
    # Step 3: Synthesize report with rich traceability info
    print("📄 Step 3: Synthesizing report with traceability metadata...")
    report = synthesizer.synthesize(critique_results)
    print(f"   ✓ Generated report with {len(verified_claims)} verified claims\n")
    
    # Display the report
    print("=" * 80)
    print("GENERATED RESEARCH REPORT")
    print("=" * 80)
    print()
    print(report)
    print()
    print("=" * 80)
    print("DEMONSTRATION COMPLETE")
    print("=" * 80)
    print()
    print("Key Traceability Features Demonstrated:")
    print("  ✓ Timestamp tracking (extracted_at)")
    print("  ✓ Source metadata (title, rank, URL)")
    print("  ✓ Support text with character offsets")
    print("  ✓ Confidence score propagation and adjustment")
    print("  ✓ Rich bibliography with search rankings")
    print("  ✓ Research metadata section in report")
    print()

if __name__ == "__main__":
    main()

