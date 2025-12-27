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
    
    # Step 4: Create artifact bundle with human-like report and DAG visualization
    print("=" * 80)
    print("📦 Step 4: Creating artifact bundle (human-like report + DAG)...")
    print("=" * 80)
    print()
    
    # Reconstruct graph data from claims (MVP approach)
    graph_data = _reconstruct_graph_from_claims(verified_claims)
    
    context = {
        'report_title': 'Quantum Computing: Recent Developments',
        'section_headers': {
            'quantum_research_2025': 'Current State of Quantum Computing'
        }
    }
    
    artifact_files = synthesizer.create_artifact_bundle(
        verification_results=critique_results,
        output_dir="HDRP/artifacts",
        graph_data=graph_data,
        context=context,
        run_id="traceability-demo",
        query=query
    )
    
    print("   ✓ Artifact bundle created successfully!\n")
    print("   📁 Output files:")
    for output_type, file_path in artifact_files.items():
        print(f"      - {output_type}: {file_path}")
    print()
    
    # Display a preview of the humanized report
    if 'report' in artifact_files:
        with open(artifact_files['report'], 'r', encoding='utf-8') as f:
            humanized_report = f.read()
        
        print("=" * 80)
        print("HUMANIZED REPORT PREVIEW (First 1000 chars)")
        print("=" * 80)
        print()
        print(humanized_report[:1000])
        print("\n... (see full report at", artifact_files['report'], ")")
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
    print("New Artifact Bundle Features:")
    print("  ✓ Human-like report with executive summary")
    print("  ✓ Natural transitions between sections")
    print("  ✓ Mermaid DAG visualization embedded in report")
    print("  ✓ Structured outputs (JSON metadata, claims, DAG)")
    print("  ✓ Complete provenance and traceability")
    print()

def _reconstruct_graph_from_claims(claims):
    """Reconstruct a simple graph structure from claims for visualization."""
    nodes = []
    edges = []
    
    # Add root node
    nodes.append({
        'id': 'root',
        'type': 'root',
        'status': 'SUCCEEDED',
        'relevance_score': 1.0
    })
    
    # Extract unique source nodes
    unique_nodes = set()
    for claim in claims:
        if claim.source_node_id:
            unique_nodes.add(claim.source_node_id)
    
    # Add researcher nodes
    for node_id in unique_nodes:
        node_claims = [c for c in claims if c.source_node_id == node_id]
        nodes.append({
            'id': node_id,
            'type': 'researcher',
            'status': 'SUCCEEDED',
            'relevance_score': sum(c.confidence for c in node_claims) / len(node_claims) if node_claims else 0.7
        })
        # Connect root to researcher
        edges.append({'from': 'root', 'to': node_id})
    
    # Add critic node
    nodes.append({
        'id': 'critic_verify',
        'type': 'critic',
        'status': 'SUCCEEDED',
        'relevance_score': 0.9
    })
    
    # Connect researchers to critic
    for node_id in unique_nodes:
        edges.append({'from': node_id, 'to': 'critic_verify'})
    
    # Add synthesizer node
    nodes.append({
        'id': 'synthesizer_final',
        'type': 'synthesizer',
        'status': 'SUCCEEDED',
        'relevance_score': 1.0
    })
    edges.append({'from': 'critic_verify', 'to': 'synthesizer_final'})
    
    return {'nodes': nodes, 'edges': edges}


if __name__ == "__main__":
    main()

