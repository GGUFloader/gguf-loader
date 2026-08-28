"""
StructuredOutput - Enforce JSON schemas on agent responses.

Pattern from: Pydantic AI structured output + OpenAI function calling.
When the agent needs to return structured data (not free text),
this module validates the response against a JSON schema and
provides typed extraction.

Features:
- JSON Schema validation
- Type coercion for common patterns
- Default values for missing fields
- Error messages with repair suggestions
- Predefined schemas for common agent outputs
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Type, Union




# Predefined schemas for common agent outputs
SCHEMAS = {
    "file_change": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path"},
            "action": {"type": "string", "enum": ["create", "modify", "delete"]},
            "content": {"type": "string", "description": "New file content (for create/modify)"},
            "reason": {"type": "string", "description": "Why this change was made"},
        },
        "required": ["path", "action"],
    },
    "analysis": {
        "type": "object",
        "properties": {
            "summary": {"type": "string", "description": "One-line summary"},
            "issues": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "severity": {"type": "string", "enum": ["critical", "warning", "info"]},
                        "file": {"type": "string"},
                        "line": {"type": "integer"},
                        "message": {"type": "string"},
                    },
                    "required": ["severity", "message"],
                },
            },
            "suggestions": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["summary"],
    },
    "test_result": {
        "type": "object",
        "properties": {
            "passed": {"type": "boolean"},
            "total": {"type": "integer"},
            "failed": {"type": "integer"},
            "errors": {"type": "integer"},
            "details": {"type": "string"},
        },
        "required": ["passed", "total"],
    },
    "search_result": {
        "type": "object",
        "properties": {
            "files": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "relevance": {"type": "number"},
                        "snippet": {"type": "string"},
                    },
                    "required": ["path"],
                },
            },
            "total": {"type": "integer"},
        },
        "required": ["files", "total"],
    },
}


class SchemaValidation:
    """Result of schema validation."""

    def __init__(self, valid: bool, data: Any = None,
                 errors: List[str] = None) -> None:
        self.valid = valid
        self.data = data
        self.errors = errors or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "data": self.data,
            "errors": self.errors,
        }


class StructuredOutput:
    """Validate and extract structured data from agent responses.

    Usage:
        so = StructuredOutput()

        # Validate against a schema
        result = so.validate(response_text, SCHEMAS["file_change"])
        if result.valid:
            print(result.data)

        # Extract with predefined schema
        data = so.extract_file_change(response_text)
    """

    def validate(self, text: str, schema: Dict[str, Any]) -> SchemaValidation:
        """Validate text against a JSON schema.

        Args:
            text: Raw text (may contain JSON in fences or bare)
            schema: JSON Schema to validate against

        Returns:
            SchemaValidation with valid/data/errors.
        """
        # Extract JSON from text
        data = self._extract_json(text)
        if data is None:
            return SchemaValidation(
                valid=False,
                errors=["No valid JSON found in response"],
            )

        # Validate against schema
        errors = self._validate_schema(data, schema)
        if errors:
            return SchemaValidation(valid=False, data=data, errors=errors)

        # Apply defaults
        data = self._apply_defaults(data, schema)

        return SchemaValidation(valid=True, data=data)

    def extract(self, text: str, schema_name: str) -> SchemaValidation:
        """Extract using a predefined schema by name."""
        schema = SCHEMAS.get(schema_name)
        if schema is None:
            return SchemaValidation(
                valid=False,
                errors=[f"Unknown schema: {schema_name}"],
            )
        return self.validate(text, schema)

    def extract_file_change(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract a file change from agent response."""
        result = self.validate(text, SCHEMAS["file_change"])
        return result.data if result.valid else None

    def extract_analysis(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract a code analysis from agent response."""
        result = self.validate(text, SCHEMAS["analysis"])
        return result.data if result.valid else None

    def coerce_types(self, data: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
        """Coerce values to match schema types.

        Handles common patterns:
        - "true"/"false" → bool
        - "123" → int
        - "1.5" → float
        """
        properties = schema.get("properties", {})
        result = dict(data)

        for key, prop_schema in properties.items():
            if key not in result:
                continue
            expected = prop_schema.get("type")
            value = result[key]

            if expected == "boolean" and isinstance(value, str):
                result[key] = value.lower() in ("true", "1", "yes")
            elif expected == "integer" and isinstance(value, str):
                try:
                    result[key] = int(value)
                except ValueError:
                    pass
            elif expected == "number" and isinstance(value, str):
                try:
                    result[key] = float(value)
                except ValueError:
                    pass

        return result

    @staticmethod
    def _extract_json(text: str) -> Optional[Dict[str, Any]]:
        """Extract JSON from text (local copy to avoid circular import)."""
        if not text:
            return None
        # Code fences
        import re as _re
        for m in _re.finditer(r"```(?:json)?\s*(\{.*?\})\s*```", text, _re.DOTALL):
            try:
                data = json.loads(m.group(1))
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                continue
        # Balanced braces
        depth = 0
        start = -1
        for i, ch in enumerate(text):
            if ch == "{":
                if depth == 0:
                    start = i
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0 and start >= 0:
                    try:
                        data = json.loads(text[start:i + 1])
                        if isinstance(data, dict):
                            return data
                    except json.JSONDecodeError:
                        pass
                    start = -1
        return None

    def _validate_schema(self, data: Any, schema: Dict[str, Any]) -> List[str]:
        """Validate data against schema, returning list of errors."""
        errors = []
        schema_type = schema.get("type")

        if schema_type == "object":
            if not isinstance(data, dict):
                return [f"Expected object, got {type(data).__name__}"]

            required = schema.get("required", [])
            for key in required:
                if key not in data:
                    errors.append(f"Missing required field: '{key}'")

            properties = schema.get("properties", {})
            for key, value in data.items():
                if key in properties:
                    prop_errors = self._validate_field(value, properties[key])
                    errors.extend(f"'{key}': {e}" for e in prop_errors)

        elif schema_type == "array":
            if not isinstance(data, list):
                return [f"Expected array, got {type(data).__name__}"]
            items_schema = schema.get("items", {})
            for i, item in enumerate(data):
                item_errors = self._validate_field(item, items_schema)
                errors.extend(f"[{i}]: {e}" for e in item_errors)

        return errors

    def _validate_field(self, value: Any, schema: Dict[str, Any]) -> List[str]:
        """Validate a single field against its schema."""
        errors = []
        expected_type = schema.get("type")

        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
        }

        if expected_type in type_map:
            expected = type_map[expected_type]
            # Allow int where float is expected
            if expected_type == "number" and isinstance(value, int):
                pass  # int is a valid number
            elif not isinstance(value, expected):
                # Try coercion
                try:
                    if expected_type == "integer":
                        value = int(value)
                    elif expected_type == "number":
                        value = float(value)
                    elif expected_type == "boolean":
                        value = str(value).lower() in ("true", "1", "yes")
                except (ValueError, TypeError):
                    errors.append(f"Expected {expected_type}, got {type(value).__name__}")
                    return errors

        # Enum validation
        enum_values = schema.get("enum")
        if enum_values and value not in enum_values:
            errors.append(f"Value '{value}' not in allowed values: {enum_values}")

        return errors

    def _apply_defaults(self, data: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
        """Apply default values from schema."""
        properties = schema.get("properties", {})
        result = dict(data)

        for key, prop_schema in properties.items():
            if key not in result and "default" in prop_schema:
                result[key] = prop_schema["default"]

        return result
