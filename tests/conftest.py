import pytest
from tests.fixtures.localstack_setup import setup_localstack_resources

def pytest_addoption(parser):
    parser.addoption("--run-integration", action="store_true", default=False,
                     help="run integration tests that require AWS/services")

def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-integration"):
        return
    skip_it = pytest.mark.skip(reason="use --run-integration to run integration tests")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_it)

@pytest.fixture(scope="session", autouse=True)
def _bootstrap_localstack():
    try:
        setup_localstack_resources(seed_artifact=True)
        return True
    except Exception as e:
        print(f"⚠️  LocalStack not available: {e}")
        print("ℹ️  Integration tests will be skipped. Start LocalStack to run them.")
        return False
