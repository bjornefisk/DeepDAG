"""Profiling utilities for performance analysis."""

import cProfile
import pstats
import io
import os
from functools import wraps
from contextlib import contextmanager
from typing import Optional


def profile_function(output_file: Optional[str] = None):
    """Decorator to profile a function with cProfile.
    
    Args:
        output_file: Optional path to save profiling stats. If None, prints to stdout.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            profiler = cProfile.Profile()
            profiler.enable()
            
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                profiler.disable()
                
                if output_file:
                    profiler.dump_stats(output_file)
                    print(f"Profiling data saved to {output_file}")
                    print(f"View with: snakeviz {output_file}")
                else:
                    s = io.StringIO()
                    ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
                    ps.print_stats(20)  # Top 20 functions
                    print(s.getvalue())
        
        return wrapper
    return decorator


@contextmanager
def profile_block(name: str, output_dir: Optional[str] = None):
    """Context manager to profile a block of code.
    
    Args:
        name: Name for this profiling block
        output_dir: Directory to save profiling stats
    
    Example:
        with profile_block("claim_extraction", "profiling_data"):
            # code to profile
            pass
    """
    profiler = cProfile.Profile()
    profiler.enable()
    
    try:
        yield profiler
    finally:
        profiler.disable()
        
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, f"{name}.prof")
            profiler.dump_stats(output_file)
            print(f"[Profiling] {name} saved to {output_file}")
        else:
            s = io.StringIO()
            ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
            ps.print_stats(10)
            print(f"[Profiling] {name}:")
            print(s.getvalue())


def enable_profiling_env() -> bool:
    """Check if profiling is enabled via environment variable.
    
    Returns:
        True if HDRP_ENABLE_PROFILING is set to "1" or "true"
    """
    env_val = os.getenv("HDRP_ENABLE_PROFILING", "").lower()
    return env_val in ("1", "true", "yes")
