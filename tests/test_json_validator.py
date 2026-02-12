"""
Tests for JSON contract validation in S1 regression cases.
"""

import pytest
import json
from agentops.json_validator import JSONContractValidator


class TestJSONContractValidator:
    """Test JSON contract validation for S1 cases."""
    
    def test_valid_contract(self):
        """Test validation passes for matching JSON contract."""
        expected = json.dumps({
            "status": "success",
            "user_id": "usr_123",
            "count": 42
        })
        actual = json.dumps({
            "status": "success",
            "user_id": "usr_456",
            "count": 100,
            "extra_field": "allowed"
        })
        
        is_valid, failure_type, error = JSONContractValidator.validate_contract(expected, actual)
        assert is_valid is True
        assert failure_type is None
        assert error is None
    
    def test_missing_required_key(self):
        """Test validation fails when required key is missing."""
        expected = json.dumps({
            "transaction_id": "tx_123",
            "amount": 100.00,
            "status": "completed"
        })
        actual = json.dumps({
            "transaction_id": "tx_456",
            "amount": 50.00
            # Missing 'status'
        })
        
        is_valid, failure_type, error = JSONContractValidator.validate_contract(expected, actual)
        assert is_valid is False
        assert failure_type == "quality_fail"
        assert "status" in error
    
    def test_type_mismatch(self):
        """Test validation fails on type mismatch."""
        expected = json.dumps({
            "count": 42,
            "active": True
        })
        actual = json.dumps({
            "count": "42",  # String instead of int
            "active": True
        })
        
        is_valid, failure_type, error = JSONContractValidator.validate_contract(expected, actual)
        assert is_valid is False
        assert failure_type == "quality_fail"
        assert "count" in error
    
    def test_invalid_json_in_expected(self):
        """Test validation fails when expected output is not valid JSON."""
        expected = "not a json string"
        actual = json.dumps({"key": "value"})
        
        is_valid, failure_type, error = JSONContractValidator.validate_contract(expected, actual)
        assert is_valid is False
        assert failure_type == "bad_json"
        assert "Expected output is not valid JSON" in error
    
    def test_invalid_json_in_actual(self):
        """Test validation fails when actual output is not valid JSON."""
        expected = json.dumps({"key": "value"})
        actual = "not valid json"
        
        is_valid, failure_type, error = JSONContractValidator.validate_contract(expected, actual)
        assert is_valid is False
        assert failure_type == "bad_json"
        assert "Actual output is not valid JSON" in error
    
    def test_number_type_compatibility(self):
        """Test int/float are considered compatible."""
        expected = json.dumps({"amount": 100})
        actual = json.dumps({"amount": 100.0})
        
        is_valid, failure_type, error = JSONContractValidator.validate_contract(expected, actual)
        assert is_valid is True
        assert failure_type is None
    
    def test_bool_type_strict(self):
        """Test bool type must match exactly (not 0/1)."""
        expected = json.dumps({"active": True})
        actual = json.dumps({"active": 1})
        
        is_valid, failure_type, error = JSONContractValidator.validate_contract(expected, actual)
        assert is_valid is False
        assert failure_type == "quality_fail"
