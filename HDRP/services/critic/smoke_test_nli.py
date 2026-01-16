#!/usr/bin/env python3
"""
Quick smoke test for NLI verifier (does not require sentence-transformers)

Tests basic functionality to verify the implementation is correct.
"""

import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

print("=" * 60)
print("NLI VERIFIER SMOKE TEST")
print("=" * 60)

try:
    print("\n1. Testing import...")
    from HDRP.services.critic.nli_verifier import NLIVerifier
    print("   ✓ Import successful")
    
    print("\n2. Testing initialization...")
    verifier = NLIVerifier()
    print("   ✓ NLIVerifier instantiated")
    
    print("\n3. Testing cache stats...")
    stats = verifier.get_cache_stats()
    assert 'cache_size' in stats
    assert 'hit_rate' in stats
    print(f"   ✓ Cache stats: {stats}")
    
    print("\n4. Testing lazy loading (model not loaded yet)...")
    assert verifier._model is None
    print("   ✓ Model is lazy-loaded")
    
    print("\n5. Testing cache clear...")
    verifier.clear_cache()
    stats_after = verifier.get_cache_stats()
    assert stats_after['cache_hits'] == 0
    assert stats_after['cache_misses'] == 0
    print("   ✓ Cache cleared successfully")
    
    print("\n" + "=" * 60)
    print("SMOKE TEST: PASSED ✓")
    print("=" * 60)
    print("\nNote: Full tests require sentence-transformers dependency.")
    print("Run: python3 -m unittest HDRP/services/critic/test_nli_verifier.py")
    
except Exception as e:
    print(f"\n✗ SMOKE TEST FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
