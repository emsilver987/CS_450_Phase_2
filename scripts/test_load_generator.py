#!/usr/bin/env python3
"""
Simple script to test the load generator directly
Useful for quick testing without running the full API server

Usage:
    # Test with ECS backend (default)
    python scripts/test_load_generator.py --backend ecs
    
    # Test with Lambda backend
    python scripts/test_load_generator.py --backend lambda
    
    # Test with custom base URL
    python scripts/test_load_generator.py --backend lambda --base-url http://localhost:8000
"""
import asyncio
import sys
import uuid
import argparse
from pathlib import Path

# Add parent directory to path to allow imports from src
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.performance.load_generator import LoadGenerator

# Default URLs
DEFAULT_API_URL = "https://pwuvrbcdu3.execute-api.us-east-1.amazonaws.com/prod"
DEFAULT_LOCAL_URL = "http://localhost:8000"


async def test_load_generator(compute_backend: str = "ecs", storage_backend: str = "s3", base_url: str = None):
    """
    Test the load generator per ACME Corporation requirements:
    - 100 concurrent clients downloading Tiny-LLM model
    - From a registry containing 500 distinct models
    - Measure throughput, mean, median, and 99th percentile latency
    
    Args:
        compute_backend: Compute backend to test ('ecs' or 'lambda')
        storage_backend: Storage backend to test ('s3' or 'rds')
        base_url: Base URL of the API server (defaults to production URL)
    
    Prerequisites:
    1. Ensure 500 models are populated in registry (run populate_registry.py --s3 or --rds)
    2. Ensure Tiny-LLM model is fully ingested with binary (required for performance testing)
    3. Start the FastAPI server with COMPUTE_BACKEND environment variable set
    """
    # Set default base_url if not provided
    if base_url is None:
        base_url = DEFAULT_API_URL
    
    # Validate compute backend
    compute_backend = compute_backend.lower()
    if compute_backend not in ["ecs", "lambda"]:
        print(f"✗ Error: Invalid compute backend '{compute_backend}'. Must be 'ecs' or 'lambda'")
        return 1
    
    # Validate storage backend
    storage_backend = storage_backend.lower()
    if storage_backend not in ["s3", "rds"]:
        print(f"✗ Error: Invalid storage backend '{storage_backend}'. Must be 's3' or 'rds'")
        return 1
    
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
    print(f"  Compute Backend: {compute_backend.upper()} (feature flag)")
    print(f"  Number of clients: {num_clients} (assignment requirement)")
    print(f"  Model ID: {model_id} (must be fully ingested with binary)")
    print(f"  Expected registry: 500 distinct models")
    print(f"  Run ID: {run_id}")
    print()
    
    print("⚠️  Prerequisites:")
    print(f"  1. Run: python scripts/populate_registry.py --{storage_backend}")
    print(f"  2. Ensure Tiny-LLM has full model binary (for performance testing)")
    print(f"  3. Start API server with correct COMPUTE_BACKEND:")
    if compute_backend == "lambda":
        print(f"     $env:COMPUTE_BACKEND='lambda'; python run_server.py")
        print(f"     OR: set COMPUTE_BACKEND=lambda && python run_server.py")
    else:
        print(f"     $env:COMPUTE_BACKEND='ecs'; python run_server.py")
        print(f"     OR: set COMPUTE_BACKEND=ecs && python run_server.py")
    print(f"  4. Verify server is using {compute_backend.upper()} compute backend (check server logs)")
    print()
    
    # Create load generator
    # Set use_performance_path=True to use performance/ path instead of models/
    # Pass storage_backend to LoadGenerator so it can use the correct endpoint
    generator = LoadGenerator(
        run_id=run_id,
        base_url=base_url,
        num_clients=num_clients,
        model_id=model_id,
        version="main",
        duration_seconds=None,  # Single request per client
        use_performance_path=True,  # Use performance/ path for performance testing
        storage_backend=storage_backend,  # Pass storage backend to use correct endpoint
    )
    
    print("Starting load generation...")
    print(f"URL: {generator._get_download_url()}")
    print()
    
    # Run the load generator
    try:
        # Check if model exists before starting (for RDS backend)
        if storage_backend == "rds":
            print("Checking if model exists in RDS...")
            exists, info = await generator.check_model_exists()
            if not exists:
                print(f"✗ Error: Model {model_id} not found in RDS")
                if info:
                    if "similar_models" in info and info["similar_models"]:
                        print(f"  Similar models found: {[m['model_id'] for m in info['similar_models']]}")
                    elif "message" in info:
                        print(f"  {info['message']}")
                print()
                print("Please run: python scripts/populate_registry.py --rds")
                print("to populate the RDS registry before running load tests.")
                return 1
            print(f"✓ Model {model_id} found in RDS")
            if info and "models" in info:
                for model in info["models"]:
                    print(f"  - {model['model_id']} v{model['version']} ({model['component']}) - {model['file_size']} bytes")
            print()
        
        await generator.run()
        
        # Get results
        metrics = generator.get_metrics()
        summary = generator.get_summary()
        
        print()
        print("=" * 80)
        print("Performance Test Results")
        print(f"Storage Backend: {storage_backend.upper()}")
        print(f"Compute Backend: {compute_backend.upper()}")
        print("=" * 80)
        print()
        print("Request Statistics:")
        print(f"  Total requests: {summary['total_requests']}")
        print(f"  Successful: {summary['successful_requests']}")
        print(f"  Failed: {summary['failed_requests']}")
        print(f"  Total duration: {summary['total_duration_seconds']:.2f}s")
        print()
        print("Latency Statistics (Required Measurements):")
        print(f"  Mean latency: {summary['mean_latency_ms']:.2f} ms")
        print(f"  Median latency: {summary['median_latency_ms']:.2f} ms")
        print(f"  99th percentile (P99) latency: {summary['p99_latency_ms']:.2f} ms")
        print(f"  Min latency: {summary['min_latency_ms']:.2f} ms")
        print(f"  Max latency: {summary['max_latency_ms']:.2f} ms")
        print()
        print("Throughput Statistics (Required Measurement):")
        print(f"  Throughput: {summary['throughput_bps']:.2f} bytes/sec")
        print(f"  Throughput: {summary['throughput_bps'] / (1024 * 1024):.2f} MB/sec")
        print(f"  Total bytes transferred: {summary['total_bytes_transferred']:,} bytes")
        print(f"  Total bytes transferred: {summary['total_bytes_transferred'] / (1024 * 1024):.2f} MB")
        print()
        
        # Calculate requests per second for additional insight
        if summary['total_duration_seconds'] > 0:
            req_per_sec = summary['total_requests'] / summary['total_duration_seconds']
            print(f"Additional Metrics:")
            print(f"  Requests per second: {req_per_sec:.2f} req/s")
            if summary['successful_requests'] > 0:
                success_rate = (summary['successful_requests'] / summary['total_requests']) * 100
                print(f"  Success rate: {success_rate:.2f}%")
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
        print("=" * 80)
        print("Next Steps for Performance Analysis:")
        print("=" * 80)
        print("1. Identify Bottlenecks:")
        print("   - Compare mean vs P99 latency (large gap = tail latency issues)")
        print("   - Check if throughput plateaus before reaching expected values")
        print("   - Analyze failed requests (may indicate resource exhaustion)")
        print()
        print("2. White-box Analysis:")
        print("   - Check CloudWatch metrics for S3 download latency")
        print("   - Monitor DynamoDB query times")
        print("   - Review API Gateway latency metrics")
        print()
        print("3. Component Comparison:")
        print("   - Run this script with different --s3/--rds and --backend ecs/lambda combinations")
        print("   - Compare S3 vs RDS performance metrics")
        print("   - Compare Lambda vs ECS performance metrics")
        print("   - Use /health/performance/workload endpoint with different configs")
        print()
        print(f"✓ Load generator test completed successfully!")
        print(f"   Storage: {storage_backend.upper()}, Compute: {compute_backend.upper()}")
        print()
        print(f"💡 To compare backends, run:")
        print(f"   python scripts/test_load_generator.py --s3 --backend ecs")
        print(f"   python scripts/test_load_generator.py --s3 --backend lambda")
        print(f"   python scripts/test_load_generator.py --rds --backend ecs")
        print(f"   python scripts/test_load_generator.py --rds --backend lambda")
        print()
        return 0
        
    except Exception as e:
        print(f"\n✗ Error running load generator: {e}")
        import traceback
        traceback.print_exc()
        return 1


def main():
    """Parse command-line arguments and run the load generator test."""
    parser = argparse.ArgumentParser(
        description="Test the performance load generator with configurable storage and compute backends",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test with S3 storage and ECS compute (default)
  python scripts/test_load_generator.py --s3 --backend ecs
  
  # Test with S3 storage and Lambda compute
  python scripts/test_load_generator.py --s3 --backend lambda
  
  # Test with RDS storage and ECS compute
  python scripts/test_load_generator.py --rds --backend ecs
  
  # Test with RDS storage and Lambda compute
  python scripts/test_load_generator.py --rds --backend lambda
  
  # Test with local server
  python scripts/test_load_generator.py --rds --backend lambda --local
  
  # Test with custom server URL
  python scripts/test_load_generator.py --rds --backend lambda --base-url http://localhost:3000
  
  # Compare all combinations (run sequentially)
  python scripts/test_load_generator.py --s3 --backend ecs
  python scripts/test_load_generator.py --s3 --backend lambda
  python scripts/test_load_generator.py --rds --backend ecs
  python scripts/test_load_generator.py --rds --backend lambda

Note: The server must be started with the matching COMPUTE_BACKEND environment variable:
  - For ECS: set COMPUTE_BACKEND=ecs (or leave unset, defaults to ecs)
  - For Lambda: set COMPUTE_BACKEND=lambda
        """
    )
    
    # Storage backend flags (mutually exclusive)
    storage_group = parser.add_mutually_exclusive_group()
    storage_group.add_argument(
        "--s3",
        action="store_true",
        help="Use S3 storage backend (default)"
    )
    storage_group.add_argument(
        "--rds",
        action="store_true",
        help="Use RDS storage backend"
    )
    
    parser.add_argument(
        "--backend",
        type=str,
        choices=["ecs", "lambda"],
        default="ecs",
        help="Compute backend to test against: 'ecs' (default) or 'lambda'"
    )
    
    parser.add_argument(
        "--local",
        action="store_true",
        help=f"Use local server at {DEFAULT_LOCAL_URL}"
    )
    
    parser.add_argument(
        "--base-url",
        type=str,
        default=None,
        help="Custom API base URL (e.g., http://localhost:8000). Overrides --local if specified."
    )
    
    args = parser.parse_args()
    
    # Determine base URL: --base-url > --local > default (production)
    if args.base_url:
        base_url = args.base_url
    elif args.local:
        base_url = DEFAULT_LOCAL_URL
    else:
        base_url = DEFAULT_API_URL
    
    # Determine storage backend (default to S3)
    storage_backend = "rds" if args.rds else "s3"
    
    # Run the async test
    exit_code = asyncio.run(test_load_generator(compute_backend=args.backend, storage_backend=storage_backend, base_url=base_url))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
