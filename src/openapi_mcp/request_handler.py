# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Roger Gujord
# https://github.com/gujord/OpenAPI-MCP

__all__ = ["KwargsParser", "ParameterProcessor", "RequestHandler"]

import re
import json
import logging
from urllib.parse import parse_qsl
from typing import Dict, Any, List, Optional, Tuple, Union, TYPE_CHECKING
try:
    from .exceptions import ParameterError
except ImportError:
    from exceptions import ParameterError

if TYPE_CHECKING:
    try:
        from .auth import AuthenticationManager
    except ImportError:
        from auth import AuthenticationManager


class KwargsParser:
    """Handles parsing of various kwargs string formats."""
    
    @staticmethod
    def parse_kwargs_string(s: str) -> Dict[str, Any]:
        """
        Parse a kwargs string with multiple format support.
        Supports:
        - Standard JSON (with numbers as numbers or strings)
        - Double-escaped JSON strings (e.g. \\" instead of ")
        - Query string formats using '&'
        - Comma-separated key/value pairs (e.g. "lat=63.1115,lon=7.7327")
        """
        s = s.strip()
        s = re.sub(r"^`+|`+$", "", s)  # Remove surrounding backticks
        s = re.sub(r"^```+|```+$", "", s)  # Remove surrounding triple backticks
        if s.startswith('?'):
            s = s[1:]
            
        logging.debug("Parsing kwargs string: %s", s)
        
        # Try standard JSON parsing first
        try:
            parsed = json.loads(s)
            if isinstance(parsed, dict):
                logging.debug("Standard JSON parsing succeeded")
                return parsed
        except Exception as e:
            logging.debug("Standard JSON parsing failed: %s", e)
        
        # Try with various unescaping methods
        for method_name, transform in [
            ("simple unescaping", lambda x: x.replace('\\"', '"')),
            ("double unescaping", lambda x: x.replace('\\\\', '\\')),
            ("full unescaping", lambda x: x.replace('\\\\', '\\').replace('\\"', '"'))
        ]:
            try:
                transformed = transform(s)
                parsed = json.loads(transformed)
                if isinstance(parsed, dict):
                    logging.debug("%s succeeded", method_name)
                    return parsed
            except Exception as e:
                logging.debug("%s failed: %s", method_name, e)
                
        # Try extracting JSON substring
        json_pattern = r'(\{.*?\})'
        json_matches = re.findall(json_pattern, s)
        if json_matches:
            for json_str in json_matches:
                try:
                    parsed = json.loads(json_str)
                    if isinstance(parsed, dict):
                        logging.debug("Extracted JSON substring parsing succeeded")
                        return parsed
                except Exception:
                    continue
                    
        # Try standard query string parsing
        parsed_qsl = dict(parse_qsl(s))
        if parsed_qsl:
            logging.debug("Query string parsing succeeded")
            return parsed_qsl
            
        # Fallback: comma-separated pairs
        if ',' in s and '&' not in s:
            result = {}
            pairs = s.split(',')
            for pair in pairs:
                pair = pair.strip()
                if not pair or '=' not in pair:
                    continue
                    
                key, value = pair.split('=', 1)
                key = key.strip()
                value = value.strip()
                
                # Try to convert to appropriate type
                try:
                    float_val = float(value)
                    result[key] = int(float_val) if float_val.is_integer() else float_val
                except ValueError:
                    result[key] = value
                    
            if result:
                logging.debug("Comma-separated parsing succeeded")
                return result
                
        logging.warning("All parsing methods failed for string: %s", s)
        return {}


class ParameterProcessor:
    """Processes and validates API parameters."""
    
    @staticmethod
    def process_parameters(
        kwargs: Dict[str, Any], 
        parameters: List[Dict[str, Any]]
    ) -> Tuple[Dict[str, Any], Dict[str, str], Any]:
        """Process parameters into query params, headers, and body."""
        req_params = {}
        req_headers = {}
        req_body = None
        
        for param in parameters:
            name = param["name"]
            location = param.get("in", "query")
            
            if name not in kwargs:
                continue
                
            # Type conversion
            try:
                value = ParameterProcessor._convert_parameter_type(
                    kwargs[name], param.get("schema", {})
                )
            except ValueError as e:
                raise ParameterError(f"Parameter '{name}' conversion error: {e}")
                
            # Route to appropriate location
            if location == "query":
                req_params[name] = value
            elif location == "header":
                req_headers[name] = value
            elif location == "body":
                req_body = value
                
        return req_params, req_headers, req_body
    
    @staticmethod
    def _convert_parameter_type(value: Any, schema: Dict[str, Any]) -> Any:
        """Convert parameter value to correct type based on schema."""
        param_type = schema.get("type", "string")
        
        if param_type == "integer":
            return int(value)
        elif param_type == "number":
            return float(value)
        elif param_type == "boolean":
            return str(value).lower() in {"true", "1", "yes", "y"}
        else:
            return value


class RequestHandler:
    """Handles request preparation and validation."""
    
    def __init__(self, authenticator: "AuthenticationManager"):
        self.authenticator = authenticator
        self.kwargs_parser = KwargsParser()
        self.param_processor = ParameterProcessor()

    def prepare_request(
        self,
        req_id: Any,
        kwargs: Dict[str, Any],
        parameters: List[Dict[str, Any]],
        path: str,
        server_url: str,
        op_id: str
    ) -> Tuple[Optional[Tuple[str, Dict, Dict, Any, bool]], Optional[Dict]]:
        """Prepare request data or return error response."""
        try:
            # Process kwargs if present
            processed_kwargs = self._process_kwargs(kwargs)
            
            # Validate required parameters
            error = self._validate_required_parameters(req_id, processed_kwargs, parameters)
            if error:
                return None, error
                
            # Check for dry run
            dry_run = processed_kwargs.pop("dry_run", False)
            
            # Process parameters
            req_params, req_headers, req_body = self.param_processor.process_parameters(
                processed_kwargs, parameters
            )
            
            # Replace path parameters
            processed_path = self._replace_path_parameters(path, processed_kwargs, parameters)
            
            # Add authentication
            req_headers = self.authenticator.add_auth_headers(req_headers)
            req_headers.setdefault("User-Agent", "OpenAPI-MCP/1.0")
            
            # Build full URL
            full_url = server_url.rstrip("/") + "/" + processed_path.lstrip("/")
            
            return (full_url, req_params, req_headers, req_body, dry_run), None
            
        except ParameterError as e:
            return None, {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32602, "message": str(e)}
            }
        except Exception as e:
            logging.error("Unexpected error preparing request: %s", e)
            return None, {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32603, "message": f"Internal error: {e}"}
            }

    def _process_kwargs(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Process and parse kwargs."""
        if 'kwargs' not in kwargs:
            return kwargs
            
        kwargs_value = kwargs.pop('kwargs')
        
        if isinstance(kwargs_value, str):
            # Remove backticks and parse
            raw = re.sub(r"^`+|`+$", "", kwargs_value)
            logging.info("Parsing kwargs string: %s", raw)
            
            parsed_kwargs = self.kwargs_parser.parse_kwargs_string(raw)
            if not parsed_kwargs:
                raise ParameterError(f"Could not parse kwargs string: '{raw}'. Please check format.")
                
            kwargs.update(parsed_kwargs)
            logging.info("Parsed kwargs: %s", kwargs)
            
        elif isinstance(kwargs_value, dict):
            kwargs.update(kwargs_value)
            logging.info("Using provided kwargs dict: %s", kwargs)
            
        return kwargs

    def _validate_required_parameters(
        self, 
        req_id: Any, 
        kwargs: Dict[str, Any], 
        parameters: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Validate that all required parameters are present."""
        expected = [p["name"] for p in parameters if p.get("required", False)]
        logging.info("Expected required parameters: %s", expected)
        logging.info("Available parameters: %s", list(kwargs.keys()))
        
        missing = [name for name in expected if name not in kwargs]
        if missing:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"help": f"Missing parameters: {missing}"}
            }
        return None

    def _replace_path_parameters(
        self, 
        path: str, 
        kwargs: Dict[str, Any], 
        parameters: List[Dict[str, Any]]
    ) -> str:
        """Replace path parameters in URL path."""
        processed_path = path
        
        for param in parameters:
            if param.get("in") == "path" and param["name"] in kwargs:
                placeholder = f"{{{param['name']}}}"
                processed_path = processed_path.replace(placeholder, str(kwargs[param["name"]]))
                
        return processed_path