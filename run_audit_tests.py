import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Mock pytest fixture behavior
class MockMonkeyPatch:
    def setenv(self, key, value):
        os.environ[key] = value

# Mock pytest module
import types
mock_pytest = types.ModuleType("pytest")
mock_pytest.fixture = lambda *args, **kwargs: lambda f: f
sys.modules["pytest"] = mock_pytest

def run_tests():
    print("Running LLM Integration Audit Tests...")
    
    try:
        from tests.test_llm_integration_audit import (
            test_llm_client_offline_mode_basic,
            test_llm_client_offline_mode_empty_input,
            test_llm_metric_is_registered_in_registry,
            test_llm_metric_scores_and_populates_meta
        )
        
        # Setup fixture
        mp = MockMonkeyPatch()
        mp.setenv("ENABLE_LLM", "false")
        
        # Run tests
        print("1. Testing Offline Mode Basic...")
        test_llm_client_offline_mode_basic()
        print("   ✅ Passed")
        
        print("2. Testing Offline Mode Empty Input...")
        test_llm_client_offline_mode_empty_input()
        print("   ✅ Passed")
        
        print("3. Testing Metric Registration...")
        test_llm_metric_is_registered_in_registry()
        print("   ✅ Passed")
        
        print("4. Testing Metric Scoring & Metadata...")
        test_llm_metric_scores_and_populates_meta()
        print("   ✅ Passed")
        
        print("\n🎉 ALL AUDIT TESTS PASSED!")
        
    except ImportError as e:
        print(f"❌ Import Error: {e}")
        print("Make sure you are running from the project root.")
    except AssertionError as e:
        print(f"❌ Assertion Failed: {e}")
        import traceback
        traceback.print_exc()
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_tests()
