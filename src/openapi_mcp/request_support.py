"""Reject selected operations that the current adapter cannot serialize safely."""

from typing import Any, Dict

from openapi_mcp.exceptions import OpenAPIError


def validate_operation_support(spec: Dict[str, Any], path: str, method: str) -> None:
    """Validate the supported request subset before registering any API tools."""
    item = spec["paths"][path]
    operation = item[method.lower()]

    def unsupported(detail: str) -> None:
        raise OpenAPIError(f"Unsupported request format for {method} {path}: {detail}")

    body = operation.get("requestBody")
    if body is not None:
        if "$ref" in body or "application/json" not in body.get("content", {}):
            unsupported("requestBody must declare application/json directly")

    parameters = {}
    for param in [*item.get("parameters", []), *operation.get("parameters", [])]:
        if "$ref" in param:
            unsupported("parameter references require resolution before use")
        parameters[(param.get("name"), param.get("in"))] = param

    for (_, location), param in parameters.items():
        if location == "body":
            consumes = operation.get("consumes", spec.get("consumes", ["application/json"]))
            if "application/json" not in consumes:
                unsupported("Swagger body parameters require application/json")
            continue
        if location not in {"path", "query", "header"}:
            unsupported(f"parameter location {location!r}")
        if "content" in param or param.get("allowReserved", False):
            unsupported("parameter content or allowReserved serialization")
        default_style = "form" if location == "query" else "simple"
        if param.get("style", default_style) != default_style:
            unsupported(f"parameter style {param['style']!r}")
        schema = param.get("schema", param)
        kind = schema.get("type")
        if kind is not None and kind not in ("string", "integer", "number", "boolean"):
            unsupported("only scalar path, query, and header parameters are supported")
        if any(key in schema for key in ("$ref", "allOf", "anyOf", "oneOf", "properties", "items")):
            unsupported("composed or referenced non-body parameter schemas")
