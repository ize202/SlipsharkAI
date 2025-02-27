# Research Workflow Tests

This directory contains tests for the research workflow, which is the main prompt chaining system for the sports betting research assistant.

## Test Structure

The tests are organized into two main categories:

- **Integration Tests**: Tests that verify the entire workflow or major components working together with real external services.
- **Unit Tests**: Tests for individual components with mocked dependencies.

## Running the Tests

### Prerequisites

Before running the tests, make sure you have:

1. Set up all required environment variables (see `.env.example` in the project root)
2. Installed all dependencies (`pip install -r requirements.txt`)

### Using the Test Runner

The easiest way to run the tests is using the test runner script:

```bash
# Run all workflow tests
python tests/run_workflow_test.py

# Run the quick test (only query analyzer, fastest option)
python tests/run_workflow_test.py --quick

# Run only the query analyzer test
python tests/run_workflow_test.py --query

# Run only the data gathering test
python tests/run_workflow_test.py --data

# Run only the data analysis test
python tests/run_workflow_test.py --analysis

# Run only the response generation test
python tests/run_workflow_test.py --response

# Run multiple test components
python tests/run_workflow_test.py --query --data
```

### Using pytest

You can also run the tests using pytest directly:

```bash
# Run all tests
pytest tests/

# Run only integration tests
pytest tests/integration/

# Run a specific test file
pytest tests/integration/test_research_workflow.py

# Run the quick test
pytest tests/integration/test_quick_workflow.py

# Run a specific test function
pytest tests/integration/test_research_workflow.py::test_query_analyzer
```

## Test Coverage

The integration tests cover the following components of the research workflow:

1. **Query Analysis**: Tests the first LLM call that analyzes the user's query to determine intent and required data.
2. **Data Gathering**: Tests the collection of data from various sources (web search, sports API, user data).
3. **Data Analysis**: Tests the second LLM call that analyzes the gathered data.
4. **Response Generation**: Tests the third LLM call that formats the final response.
5. **Full Workflow**: Tests the entire workflow from query to response.

## Quick vs. Full Tests

The test suite includes two main types of tests:

- **Quick Test**: Only tests the query analyzer step (first LLM call). This is the fastest test and is useful for quick verification that the workflow is functioning without making all the external API calls.
- **Full Tests**: Test the entire workflow or specific components with real external services.

## Live vs. Mock Tests

The integration tests in this directory use real external services (no mocking) to ensure the entire system works correctly with actual data. This means:

- Tests will make real API calls to OpenAI, Perplexity, API-Sports, and Supabase
- Tests will consume API quotas and may incur costs
- Tests will take longer to run than mocked tests

For development and CI/CD purposes, you may want to create mocked versions of these tests.

## Adding New Tests

When adding new tests:

1. For unit tests, use mocks for external dependencies
2. For integration tests, consider the API usage and costs
3. Add appropriate assertions to verify the expected behavior
4. Update this README if you add new test categories or runner options 