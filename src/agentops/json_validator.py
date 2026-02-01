"""
JSON contract validator for S1 regression cases.

This module validates that LLM outputs conform to expected JSON contracts
for critical external integration (S1) test cases.
"""

import json
from typing import Dict, Any, Optional, Tuple


class JSONContractValidator:
    """Validates JSON outputs against expected contracts for S1 cases."""
    
    @staticmethod
    def validate_contract(
        expected_output: str,
        actual_output: str
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Validate that actual_output conforms to the JSON contract in expected_output.
        
        Args:
            expected_output: JSON string defining the expected contract (required keys/types)
            actual_output: JSON string from the LLM to validate
            
        Returns:
            Tuple of (is_valid, failure_type, error_message)
            - is_valid: True if contract is satisfied
            - failure_type: "bad_json" | "quality_fail" | None
            - error_message: Human-readable error description
        """
        # Parse expected contract
        try:
            expected_json = json.loads(expected_output)
        except (json.JSONDecodeError, ValueError) as e:
            return False, "bad_json", f"Expected output is not valid JSON: {str(e)}"
        
        # Parse actual output
        try:
            actual_json = json.loads(actual_output)
        except (json.JSONDecodeError, ValueError) as e:
            return False, "bad_json", f"Actual output is not valid JSON: {str(e)}"
        
        # Validate required keys
        missing_keys = []
        for key in expected_json.keys():
            if key not in actual_json:
                missing_keys.append(key)
        
        if missing_keys:
            return False, "quality_fail", f"Missing required keys: {', '.join(missing_keys)}"
        
        # Validate types for keys present in expected contract
        type_mismatches = []
        for key, expected_value in expected_json.items():
            if key in actual_json:
                actual_value = actual_json[key]
                expected_type = type(expected_value)
                actual_type = type(actual_value)
                
                # Check type compatibility
                if not JSONContractValidator._types_compatible(expected_type, actual_type):
                    type_mismatches.append(
                        f"{key}: expected {expected_type.__name__}, got {actual_type.__name__}"
                    )
        
        if type_mismatches:
            return False, "quality_fail", f"Type mismatches: {'; '.join(type_mismatches)}"
        
        return True, None, None
    
    @staticmethod
    def _types_compatible(expected_type: type, actual_type: type) -> bool:
        """Check if two types are compatible for validation."""
        # Exact match
        if expected_type == actual_type:
            return True
        
        # Number compatibility (int/float)
        if expected_type in (int, float) and actual_type in (int, float):
            return True
        
        # Bool must match exactly (don't allow int 0/1)
        if expected_type == bool or actual_type == bool:
            return expected_type == actual_type
        
        return False
