#!/usr/bin/env python3
"""
Simple script to test the load generator directly
Useful for quick testing without running the full API server

Usage:
    # Test specific combinations
    python scripts/test_load_generator.py --s3 --ecs
    python scripts/test_load_generator.py --s3 --lambda
    python scripts/test_load_generator.py --rds --ecs
    python scripts/test_load_generator.py --rds --lambda
    
    # Test all combinations and display comparison
    python scripts/test_load_generator.py --all
    
    # Test with custom base URL
    python scripts/test_load_generator.py --s3 --ecs --base-url http://localhost:8000
"""
import asyncio
import sys
import uuid
import argparse
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

# Add parent directory to path to allow imports from src
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.performance.load_generator import LoadGenerator


@dataclass
class TestResult:
    """Container for test results."""
    storage_backend: str
    compute_backend: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    total_duration_seconds: float
    mean_latency_ms: float
    median_latency_ms: float
    p99_latency_ms: float
    throughput_bps: float
    total_bytes_transferred: int
    success_rate: float


async def test_load_generator(
    storage_backend: str = "s3",
    compute_backend: str = "ecs",
    base_url: str = "http://localhost:8000"
) -> Tuple[int, Optional[TestResult]]:
    """
    Test the load generator per ACME Corporation requirements:
    - 100 concurrent clients downloading Tiny-LLM model
    - From a registry containing 500 distinct models
    - Measure throughput, mean, median, and 99th percentile latency
    
    Args:
        storage_backend: Storage backend to test ('s3' or 'rds')
        compute_backend: Compute backend to test ('ecs' or 'lambda')
        base_url: Base URL of the API server
    
    Returns:
        Tuple of (exit_code, TestResult or None)
    
    Prerequisites:
    1. Ensure 500 models are populated in registry
       - For S3: run populate_registry.py --performance
       - For RDS: run populate_registry.py --rds --performance
    2. Ensure Tiny-LLM model is fully ingested with binary (required for performance testing)
    3. Start the FastAPI server with correct environment variables:
       - STORAGE_BACKEND=s3 or rds
       - COMPUTE_BACKEND=ecs or lambda
    """
    # Validate backends
    storage_backend = storage_backend.lower()
    compute_backend = compute_backend.lower()
    
    if storage_backend not in ["s3", "rds"]:
        print(f"✗ Error: Invalid storage backend '{storage_backend}'. Must be 's3' or 'rds'")
        return (1, None)
    
    if compute_backend not in ["ecs", "lambda"]:
        print(f"✗ Error: Invalid compute backend '{compute_backend}'. Must be 'ecs' or 'lambda'")
        return (1, None)
    
    print("=" * 80)
    print("Performance Load Generator Test")
    print("ACME Corporation Performance Testing")
    print("=" * 80)
    
    # Configuration - matching assignment requirements
    num_clients = 100  # Assignment requirement: 100 concurrent clients
    model_id = "arnir0/Tiny-LLM"  # Assignment requirement: Tiny-LLM from HuggingFace
    run_id = str(uuid.uuid4())
    
    print(f"Configuration:")
    print(f"  Base URL: {base_url}")
    print(f"  Storage Backend: {storage_backend.upper()}")
    print(f"  Compute Backend: {compute_backend.upper()}")
    print(f"  Number of clients: {num_clients} (assignment requirement)")
    print(f"  Model ID: {model_id} (must be fully ingested with binary)")
    print(f"  Expected registry: 500 distinct models")
    print(f"  Run ID: {run_id}")
    print()
    
    print("⚠️  Prerequisites:")
    if storage_backend == "rds":
        print(f"  1. Run: python scripts/populate_registry.py --rds --performance")
    else:
        print(f"  1. Run: python scripts/populate_registry.py --performance")
    print(f"  2. Ensure Tiny-LLM has full model binary (for performance testing)")
    print(f"  3. Start API server with correct environment variables:")
    print(f"     STORAGE_BACKEND={storage_backend}")
    print(f"     COMPUTE_BACKEND={compute_backend}")
    print(f"     Example:")
    print(f"       $env:STORAGE_BACKEND='{storage_backend}'; $env:COMPUTE_BACKEND='{compute_backend}'; python run_server.py")
    print(f"  4. Verify server is using {storage_backend.upper()} storage and {compute_backend.upper()} compute (check server logs)")
    print()
    
    # Create load generator
    # Set use_performance_path=True to use performance/ S3 path instead of models/
    generator = LoadGenerator(
        run_id=run_id,
        base_url=base_url,
        num_clients=num_clients,
        model_id=model_id,
        version="main",
        duration_seconds=None,  # Single request per client
        use_performance_path=True,  # Use performance/ path for performance testing
    )
    
    print("Starting load generation...")
    print(f"URL: {generator._get_download_url()}")
    print()
    
    # Run the load generator
    try:
        await generator.run()
        
        # Get results
        metrics = generator.get_metrics()
        summary = generator.get_summary()
        
        # Calculate success rate
        success_rate = 0.0
        if summary['total_requests'] > 0:
            success_rate = (summary['successful_requests'] / summary['total_requests']) * 100
        
        # Create result object
        result = TestResult(
            storage_backend=storage_backend,
            compute_backend=compute_backend,
            total_requests=summary['total_requests'],
            successful_requests=summary['successful_requests'],
            failed_requests=summary['failed_requests'],
            total_duration_seconds=summary['total_duration_seconds'],
            mean_latency_ms=summary['mean_latency_ms'],
            median_latency_ms=summary['median_latency_ms'],
            p99_latency_ms=summary['p99_latency_ms'],
            throughput_bps=summary['throughput_bps'],
            total_bytes_transferred=summary['total_bytes_transferred'],
            success_rate=success_rate
        )
        
        print()
        print("=" * 80)
        print("Performance Test Results")
        print(f"Storage: {storage_backend.upper()} | Compute: {compute_backend.upper()}")
        print("=" * 80)
        print()
        print("Request Statistics:")
        print(f"  Total requests: {result.total_requests}")
        print(f"  Successful: {result.successful_requests}")
        print(f"  Failed: {result.failed_requests}")
        print(f"  Success rate: {result.success_rate:.2f}%")
        print(f"  Total duration: {result.total_duration_seconds:.2f}s")
        print()
        print("Latency Statistics (Required Measurements):")
        print(f"  Mean latency: {result.mean_latency_ms:.2f} ms ({result.mean_latency_ms / 1000:.2f} s)")
        print(f"  Median latency: {result.median_latency_ms:.2f} ms ({result.median_latency_ms / 1000:.2f} s)")
        print(f"  99th percentile (P99) latency: {result.p99_latency_ms:.2f} ms ({result.p99_latency_ms / 1000:.2f} s)")
        print()
        print("Throughput Statistics (Required Measurement):")
        print(f"  Throughput: {result.throughput_bps / (1024 * 1024):.2f} MB/sec")
        print(f"  Total bytes transferred: {result.total_bytes_transferred / (1024 * 1024):.2f} MB")
        print()
        
        # Show sample metrics
        if metrics:
            print("Sample Metrics (first 5 clients):")
            for i, metric in enumerate(metrics[:5], 1):
                status = "✓" if metric['status_code'] == 200 else "✗"
                print(f"  {i}. Client {metric['client_id']:3d}: {status} "
                      f"Status {metric['status_code']}, "
                      f"Latency {metric['request_latency_ms']:.2f}ms, "
                      f"Bytes {metric['bytes_transferred']:,}")
            print()
        
        return (0, result)
        
    except Exception as e:
        print(f"\n✗ Error running load generator: {e}")
        import traceback
        traceback.print_exc()
        return (1, None)


def print_comparison_table(results: List[TestResult]):
    """Print a comparison table of all test results."""
    print()
    print("=" * 100)
    print("COMPARISON TABLE: All Backend Combinations")
    print("=" * 100)
    print()
    
    # Header
    print(f"{'Configuration':<20} {'Success':<10} {'Mean (s)':<12} {'Median (s)':<12} {'P99 (s)':<12} {'Throughput':<15}")
    print(f"{'Storage+Compute':<20} {'Rate %':<10} {'Latency':<12} {'Latency':<12} {'Latency':<12} {'MB/sec':<15}")
    print("-" * 100)
    
    # Results
    for result in results:
        config = f"{result.storage_backend.upper()}+{result.compute_backend.upper()}"
        print(f"{config:<20} "
              f"{result.success_rate:>6.2f}%   "
              f"{result.mean_latency_ms/1000:>10.2f}   "
              f"{result.median_latency_ms/1000:>10.2f}   "
              f"{result.p99_latency_ms/1000:>10.2f}   "
              f"{result.throughput_bps/(1024*1024):>12.2f}")
    
    print("-" * 100)
    print()
    
    # Summary statistics
    if len(results) > 1:
        print("Summary:")
        best_throughput = max(results, key=lambda r: r.throughput_bps)
        best_mean_latency = min(results, key=lambda r: r.mean_latency_ms)
        best_p99_latency = min(results, key=lambda r: r.p99_latency_ms)
        
        print(f"  Best Throughput: {best_throughput.storage_backend.upper()}+{best_throughput.compute_backend.upper()} "
              f"({best_throughput.throughput_bps/(1024*1024):.2f} MB/sec)")
        print(f"  Best Mean Latency: {best_mean_latency.storage_backend.upper()}+{best_mean_latency.compute_backend.upper()} "
              f"({best_mean_latency.mean_latency_ms/1000:.2f} s)")
        print(f"  Best P99 Latency: {best_p99_latency.storage_backend.upper()}+{best_p99_latency.compute_backend.upper()} "
              f"({best_p99_latency.p99_latency_ms/1000:.2f} s)")
        print()


async def run_all_combinations(base_url: str = "http://localhost:8000") -> int:
    """Run all four backend combinations and display comparison."""
    combinations = [
        ("s3", "ecs"),
        ("s3", "lambda"),
        ("rds", "ecs"),
        ("rds", "lambda"),
    ]
    
    results: List[TestResult] = []
    
    print("=" * 100)
    print("RUNNING ALL BACKEND COMBINATIONS")
    print("=" * 100)
    print()
    print("This will test all four combinations:")
    print("  1. S3 + ECS")
    print("  2. S3 + Lambda")
    print("  3. RDS + ECS")
    print("  4. RDS + Lambda")
    print()
    print("⚠️  IMPORTANT: You must restart the server with the correct environment variables")
    print("   between each test. The script will prompt you before each test.")
    print()
    
    for i, (storage, compute) in enumerate(combinations, 1):
        print()
        print("=" * 100)
        print(f"TEST {i}/4: {storage.upper()} Storage + {compute.upper()} Compute")
        print("=" * 100)
        print()
        print(f"⚠️  Please ensure your server is running with:")
        print(f"   STORAGE_BACKEND={storage}")
        print(f"   COMPUTE_BACKEND={compute}")
        print()
        input("Press Enter when the server is configured correctly and ready...")
        print()
        
        exit_code, result = await test_load_generator(storage, compute, base_url)
        
        if exit_code == 0 and result:
            results.append(result)
        else:
            print(f"✗ Test failed for {storage.upper()}+{compute.upper()}")
            print()
    
    # Display comparison
    if results:
        print_comparison_table(results)
        return 0
    else:
        print("✗ No successful test results to compare")
        return 1


def main():
    """Parse command-line arguments and run the load generator test."""
    parser = argparse.ArgumentParser(
        description="Test the performance load generator with configurable storage and compute backends",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test specific combinations
  python scripts/test_load_generator.py --s3 --ecs
  python scripts/test_load_generator.py --s3 --lambda
  python scripts/test_load_generator.py --rds --ecs
  python scripts/test_load_generator.py --rds --lambda
  
  # Test all combinations and display comparison
  python scripts/test_load_generator.py --all
  
  # Test with custom server URL
  python scripts/test_load_generator.py --s3 --ecs --base-url http://localhost:8000

Note: The server must be started with the matching environment variables:
  - STORAGE_BACKEND: 's3' or 'rds'
  - COMPUTE_BACKEND: 'ecs' or 'lambda'
  
  Example:
    $env:STORAGE_BACKEND='s3'; $env:COMPUTE_BACKEND='ecs'; python run_server.py
        """
    )
    
    # Storage backend flags (mutually exclusive)
    storage_group = parser.add_mutually_exclusive_group()
    storage_group.add_argument(
        "--s3",
        action="store_true",
        help="Use S3 storage backend"
    )
    storage_group.add_argument(
        "--rds",
        action="store_true",
        help="Use RDS storage backend"
    )
    
    # Compute backend flags (mutually exclusive)
    compute_group = parser.add_mutually_exclusive_group()
    compute_group.add_argument(
        "--ecs",
        action="store_true",
        help="Use ECS compute backend"
    )
    compute_group.add_argument(
        "--lambda",
        dest="use_lambda",
        action="store_true",
        help="Use Lambda compute backend"
    )
    
    # All combinations flag
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all four combinations (S3+ECS, S3+Lambda, RDS+ECS, RDS+Lambda) and display comparison"
    )
    
    parser.add_argument(
        "--base-url",
        type=str,
        default="http://localhost:8000",
        help="Base URL of the API server (default: http://localhost:8000)"
    )
    
    args = parser.parse_args()
    
    # Handle --all flag
    if args.all:
        exit_code = asyncio.run(run_all_combinations(base_url=args.base_url))
        sys.exit(exit_code)
    
    # Determine storage and compute backends
    storage_backend = "s3" if args.s3 else ("rds" if args.rds else "s3")  # Default to s3
    compute_backend = "ecs" if args.ecs else ("lambda" if args.use_lambda else "ecs")  # Default to ecs
    
    # Run the async test
    exit_code, _ = asyncio.run(test_load_generator(
        storage_backend=storage_backend,
        compute_backend=compute_backend,
        base_url=args.base_url
    ))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

