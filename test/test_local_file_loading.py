#!/usr/bin/env python3
"""
Unit tests for local file loading functionality.
"""
import os
import sys
import json
import tempfile
from pathlib import Path

from openapi_mcp.openapi_loader import OpenAPILoader
from openapi_mcp.exceptions import OpenAPIError


def test_load_json_file():
    """Test loading local JSON OpenAPI spec."""
    print("Testing JSON file loading...")
    
    try:
        # Load the test fixture
        spec_path = "./test/fixtures/petstore.json"
        spec = OpenAPILoader.load_spec(spec_path)
        
        # Verify the spec was loaded correctly
        assert spec is not None, "Spec should not be None"
        assert "openapi" in spec, "Spec should contain 'openapi' field"
        assert "info" in spec, "Spec should contain 'info' field"
        assert "paths" in spec, "Spec should contain 'paths' field"
        assert spec["info"]["title"] == "Test Petstore API", "Title should match"
        assert "/pets" in spec["paths"], "Should have /pets path"
        
        print("✓ JSON file loading successful")
        return True
        
    except Exception as e:
        print(f"✗ JSON file loading failed: {e}")
        return False


def test_load_yaml_file():
    """Test loading local YAML OpenAPI spec."""
    print("Testing YAML file loading...")
    
    try:
        # Load the test fixture
        spec_path = "./test/fixtures/weather.yaml"
        spec = OpenAPILoader.load_spec(spec_path)
        
        # Verify the spec was loaded correctly
        assert spec is not None, "Spec should not be None"
        assert "openapi" in spec, "Spec should contain 'openapi' field"
        assert "info" in spec, "Spec should contain 'info' field"
        assert "paths" in spec, "Spec should contain 'paths' field"
        assert spec["info"]["title"] == "Test Weather API", "Title should match"
        assert "/forecast" in spec["paths"], "Should have /forecast path"
        
        print("✓ YAML file loading successful")
        return True
        
    except Exception as e:
        print(f"✗ YAML file loading failed: {e}")
        return False


def test_relative_path():
    """Test loading spec from relative path."""
    print("Testing relative path loading...")
    
    try:
        # Save current directory
        original_dir = os.getcwd()
        
        # Change to test directory
        os.chdir(os.path.dirname(__file__))
        
        # Load using relative path
        spec = OpenAPILoader.load_spec("./fixtures/petstore.json")
        
        assert spec["info"]["title"] == "Test Petstore API", "Should load from relative path"
        
        # Restore directory
        os.chdir(original_dir)
        
        print("✓ Relative path loading successful")
        return True
        
    except Exception as e:
        print(f"✗ Relative path loading failed: {e}")
        os.chdir(original_dir)  # Ensure we restore the directory
        return False


def test_absolute_path():
    """Test loading spec from absolute path."""
    print("Testing absolute path loading...")
    
    try:
        # Get absolute path to fixture
        abs_path = os.path.abspath("./test/fixtures/weather.yaml")
        spec = OpenAPILoader.load_spec(abs_path)
        
        assert spec["info"]["title"] == "Test Weather API", "Should load from absolute path"
        
        print("✓ Absolute path loading successful")
        return True
        
    except Exception as e:
        print(f"✗ Absolute path loading failed: {e}")
        return False


def test_missing_file():
    """Test error handling for missing file."""
    print("Testing missing file handling...")
    
    try:
        # Try to load non-existent file
        spec = OpenAPILoader.load_spec("./test/fixtures/does_not_exist.json")
        
        print("✗ Should have raised FileNotFoundError")
        return False
        
    except FileNotFoundError as e:
        assert "does_not_exist.json" in str(e), "Error should mention the file"
        print("✓ Missing file error handled correctly")
        return True
        
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False


def test_invalid_json():
    """Test error handling for invalid JSON."""
    print("Testing invalid JSON handling...")
    
    try:
        # Create a temporary invalid JSON file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{ invalid json }')
            temp_path = f.name
        
        try:
            spec = OpenAPILoader.load_spec(temp_path)
            print("✗ Should have raised OpenAPIError for invalid JSON")
            return False
        finally:
            os.unlink(temp_path)
            
    except OpenAPIError as e:
        assert "Failed to parse" in str(e), "Error should mention parse failure"
        print("✓ Invalid JSON error handled correctly")
        return True
        
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False


def test_invalid_yaml():
    """Test error handling for invalid YAML."""
    print("Testing invalid YAML handling...")
    
    try:
        # Try to load the invalid YAML fixture
        spec = OpenAPILoader.load_spec("./test/fixtures/invalid.yaml")
        
        print("✗ Should have raised OpenAPIError for invalid YAML")
        return False
        
    except OpenAPIError as e:
        assert "Failed to parse" in str(e) or "Failed to load" in str(e), "Error should mention parse failure"
        print("✓ Invalid YAML error handled correctly")
        return True
        
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False


def test_invalid_openapi_spec():
    """Test error handling for invalid OpenAPI spec structure."""
    print("Testing invalid OpenAPI spec handling...")
    
    try:
        # Try to load the invalid spec fixture (valid JSON but invalid OpenAPI)
        spec = OpenAPILoader.load_spec("./test/fixtures/invalid.json")
        
        print("✗ Should have raised OpenAPIError for invalid spec")
        return False
        
    except OpenAPIError as e:
        assert "Missing required properties" in str(e), "Error should mention missing properties"
        print("✓ Invalid OpenAPI spec error handled correctly")
        return True
        
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False


def test_file_size_limit():
    """Test that large files are rejected."""
    print("Testing file size limit...")
    
    try:
        # Create a file larger than 10MB
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            # Write a large JSON structure
            f.write('{"info": {"title": "Test"}, "paths": {')
            # Add lots of paths to exceed 10MB
            for i in range(500000):
                f.write(f'"/path{i}": {{"get": {{"operationId": "op{i}"}}}},')
            f.write('"/final": {"get": {"operationId": "final"}}}}')
            temp_path = f.name
        
        try:
            # Check file size
            file_size = os.path.getsize(temp_path)
            if file_size <= 10 * 1024 * 1024:
                print(f"✗ Test file not large enough ({file_size} bytes)")
                return False
                
            spec = OpenAPILoader.load_spec(temp_path)
            print("✗ Should have raised OpenAPIError for large file")
            return False
        finally:
            os.unlink(temp_path)
            
    except OpenAPIError as e:
        assert "too large" in str(e), "Error should mention file size"
        print("✓ File size limit enforced correctly")
        return True
        
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False


def test_remote_url_still_works():
    """Test that remote URLs still work (not treated as local files)."""
    print("Testing remote URL detection...")
    
    try:
        # These should be detected as remote URLs
        urls = [
            "https://example.com/openapi.json",
            "http://localhost:8000/spec.yaml"
        ]
        
        for url in urls:
            # We can't actually fetch these, but we can verify they're not treated as local files
            try:
                spec = OpenAPILoader.load_spec(url)
                # This will fail with connection error, not file not found
            except FileNotFoundError:
                print(f"✗ URL {url} was treated as local file")
                return False
            except Exception:
                # Any other error is fine - we just want to ensure it's not treated as a file
                pass
        
        print("✓ Remote URLs correctly identified")
        return True
        
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False


def run_all_tests():
    """Run all local file loading tests."""
    print("\n" + "="*50)
    print("Local File Loading Tests")
    print("="*50 + "\n")
    
    tests = [
        test_load_json_file,
        test_load_yaml_file,
        test_relative_path,
        test_absolute_path,
        test_missing_file,
        test_invalid_json,
        test_invalid_yaml,
        test_invalid_openapi_spec,
        test_file_size_limit,
        test_remote_url_still_works
    ]
    
    results = []
    for test in tests:
        try:
            success = test()
            results.append(success)
        except Exception as e:
            print(f"✗ Test {test.__name__} crashed: {e}")
            results.append(False)
        print()  # Add blank line between tests
    
    # Summary
    passed = sum(results)
    total = len(results)
    
    print("="*50)
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✓ All tests passed!")
        return True
    else:
        print(f"✗ {total - passed} tests failed")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)