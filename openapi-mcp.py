import os
import sys
import json
import yaml
import httpx
import logging
import argparse
from urllib.parse import urljoin, urlparse
from typing import Any, Dict

from pygments import highlight
from pygments.lexers import JsonLexer, XmlLexer, YamlLexer, MarkdownLexer
from pygments.formatters import TerminalFormatter
from pygments.styles import get_style_by_name

from mcp.server.fastmcp import FastMCP

logging.basicConfig(
    level=logging.ERROR,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

mcp = FastMCP("openapi_proxy_server")

###############################################################################
# Authentication support using OAuth client_credentials flow
###############################################################################

def get_oauth_access_token() -> str:
    """
    Obtains an access token using the OAuth client_credentials flow.
    Expects the following environment variables:
      OAUTH_CLIENT_ID, OAUTH_CLIENT_SECRET, OAUTH_SCOPE, OAUTH_TOKEN_URL.
    Returns the access token string.
    """
    oauth_client_id = os.environ.get("OAUTH_CLIENT_ID")
    oauth_client_secret = os.environ.get("OAUTH_CLIENT_SECRET")
    oauth_scope = os.environ.get("OAUTH_SCOPE", "api")
    oauth_token_url = os.environ.get("OAUTH_TOKEN_URL")
    if oauth_client_id and oauth_client_secret and oauth_token_url:
        try:
            response = httpx.post(
                oauth_token_url,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "grant_type": "client_credentials",
                    "client_id": oauth_client_id,
                    "client_secret": oauth_client_secret,
                    "scope": oauth_scope
                }
            )
            response.raise_for_status()
            token_data = response.json()
            return token_data.get("access_token")
        except Exception as e:
            logging.error("Error obtaining access token: %s", str(e))
            sys.exit(1)
    return None

###############################################################################
# Syntax highlighting helpers
###############################################################################

STYLE = get_style_by_name("monokai")

def syntax_highlight(data: str, language: str) -> str:
    """Apply syntax highlighting to data in the given language if output is a TTY."""
    if not sys.stdout.isatty():
        return data
    lexers = {
        "json": JsonLexer(),
        "xml": XmlLexer(),
        "yaml": YamlLexer(),
        "markdown": MarkdownLexer(),
    }
    lexer = lexers.get(language.lower())
    if lexer:
        return highlight(data, lexer, TerminalFormatter(style=STYLE))
    return data

###############################################################################
# XML, Markdown, and other output formatting
###############################################################################

def dict_to_pretty_xml(data: Any, root_node: str = "response", indent: str = "  ", level: int = 0) -> str:
    """Recursively converts a dictionary or list to a pretty-formatted XML string."""
    xml = f"{indent * level}<{root_node}>"
    if isinstance(data, dict):
        xml += "\n"
        for key, value in data.items():
            xml += dict_to_pretty_xml(value, root_node=key, indent=indent, level=level + 1)
        xml += f"{indent * level}</{root_node}>\n"
    elif isinstance(data, list):
        xml += "\n"
        for item in data:
            xml += dict_to_pretty_xml(item, root_node="item", indent=indent, level=level + 1)
        xml += f"{indent * level}</{root_node}>\n"
    else:
        xml += f"{data}</{root_node}>\n"
    return xml

def dict_to_markdown(data: Any, level: int = 1) -> str:
    """Recursively converts a dictionary or list to a Markdown-formatted string."""
    md = ""
    if isinstance(data, dict):
        for key, value in data.items():
            md += f"{'#' * level} {key}\n\n"
            md += dict_to_markdown(value, level + 1)
    elif isinstance(data, list):
        for item in data:
            md += f"- {dict_to_markdown(item, level)}\n"
    else:
        md += f"{data}\n\n"
    return md

###############################################################################
# OpenAPI loading and endpoint extraction (supports JSON or YAML)
###############################################################################

def load_openapi(openapi_url: str) -> (Dict[str, Any], str, Dict[str, Dict[str, Any]]):
    """
    Loads the OpenAPI spec from the given URL (JSON or YAML),
    determines the server URL, and extracts endpoint information.
    """
    try:
        spec_response = httpx.get(openapi_url)
        spec_response.raise_for_status()
        try:
            openapi_spec = spec_response.json()
        except Exception:
            openapi_spec = yaml.safe_load(spec_response.text)
    except Exception as e:
        logging.error(f"Could not load OpenAPI specification: {e}")
        sys.exit(1)
    try:
        raw_server_url = openapi_spec["servers"][0]["url"]
    except (KeyError, IndexError):
        parsed = urlparse(openapi_url)
        base_path = parsed.path.rsplit('/', 1)[0]
        raw_server_url = f"{parsed.scheme}://{parsed.netloc}{base_path}"
    if raw_server_url.startswith("/"):
        parsed_openapi = urlparse(openapi_url)
        server_url = urljoin(f"{parsed_openapi.scheme}://{parsed_openapi.netloc}", raw_server_url)
    elif not raw_server_url.startswith(("http://", "https://")):
        server_url = f"https://{raw_server_url}"
    else:
        server_url = raw_server_url
    operations_info = {}
    for path, path_item in openapi_spec.get("paths", {}).items():
        for method, operation in path_item.items():
            if method.lower() not in ["get", "post", "put", "delete", "patch", "head", "options"]:
                continue
            operation_id = operation.get("operationId")
            if not operation_id:
                sanitized = path.replace("/", "_").replace("{", "").replace("}", "")
                operation_id = f"{method}_{sanitized}"
            operations_info[operation_id] = {
                "summary": operation.get("summary", ""),
                "parameters": operation.get("parameters", []),
                "path": path,
                "method": method.upper()
            }
    return openapi_spec, server_url, operations_info

###############################################################################
# Error and help text formatting
###############################################################################

def format_error_message(message: str) -> str:
    """Return error as plain text, ensuring error messages are prefixed to avoid syntax highlighting."""
    if not message.startswith("Error: "):
        return "Error: " + message
    return message

def format_help_text_plain(help_info: Dict[str, Any]) -> str:
    """Formats a help message in plain text."""
    lines = []
    lines.append(f"Endpoint: {help_info.get('endpoint', '')}")
    lines.append(f"  Method : {help_info.get('method', '')}")
    lines.append(f"  Path   : {help_info.get('path', '')}")
    summary = help_info.get("summary", "")
    if summary.strip():
        lines.append(f"  Summary: {summary}")
    if help_info.get("required_parameters"):
        lines.append("  Required parameters:")
        for param in help_info["required_parameters"]:
            for key, val in param.items():
                lines.append(f"    - {key}: [in: {val.get('in')}, type: {val.get('type')}] {val.get('description', '')}")
    if help_info.get("optional_parameters"):
        lines.append("  Optional parameters:")
        for param in help_info["optional_parameters"]:
            for key, val in param.items():
                lines.append(f"    - {key}: [in: {val.get('in')}, type: {val.get('type')}] {val.get('description', '')}")
    lines.append(f"Example: {help_info.get('example', '')}")
    lines.append("\nGlobal Options:")
    lines.append("  --output: Output format (json, yaml, xml, markdown)")
    lines.append("  --dry-run: Simulate execution without making an API call")
    lines.append("  --param: Provide parameters in key=value format (can be repeated)")
    return "\n".join(lines)

def get_endpoint_help(endpoint: str = "", response_format: str = "text", operations_info: Dict[str, Any] = None) -> str:
    """
    Provides help for a specific endpoint or lists all endpoints if none is specified.
    If an endpoint does not provide a description, it will list only the name.
    """
    response_format = response_format.lower()
    if not operations_info:
        result = "No OpenAPI specification loaded."
    else:
        if endpoint:
            info = operations_info.get(endpoint)
            if not info:
                result = f"Endpoint not found: {endpoint}"
            else:
                if response_format == "markdown":
                    md = f"# Endpoint: {endpoint}\n\n"
                    md += f"**Method:** {info.get('method')}\n\n"
                    md += f"**Path:** {info.get('path')}\n\n"
                    summary = info.get("summary", "")
                    if summary.strip():
                        md += f"**Summary:** {summary}\n\n"
                    params = info.get("parameters", [])
                    if params:
                        md += "## Parameters:\n\n"
                        for p in params:
                            required = " (required)" if p.get("required", False) else ""
                            schema = p.get("schema", {}).get("type", "unknown")
                            desc = p.get("description", "")
                            md += f"- **{p.get('name')}**: [in: {p.get('in')}, type: {schema}]{required} {desc}\n"
                    else:
                        md += "No parameters defined.\n"
                    result = md
                else:
                    lines = [f"Endpoint: {endpoint}",
                             f"  Method : {info.get('method')}",
                             f"  Path   : {info.get('path')}"]
                    summary = info.get("summary", "")
                    if summary.strip():
                        lines.append(f"  Summary: {summary}")
                    params = info.get("parameters", [])
                    if params:
                        lines.append("  Parameters:")
                        for p in params:
                            required = " (required)" if p.get("required", False) else ""
                            schema = p.get("schema", {}).get("type", "unknown")
                            desc = p.get("description", "")
                            lines.append(f"    - {p.get('name')}: [in: {p.get('in')}, type: {schema}]{required} {desc}")
                    else:
                        lines.append("  No parameters defined.")
                    result = "\n".join(lines)
        else:
            if response_format == "markdown":
                md = "# Available endpoints\n\n"
                for op_id, info_obj in operations_info.items():
                    summary = info_obj.get("summary", "").strip()
                    if summary:
                        md += f"- **{op_id}**: {summary}\n"
                    else:
                        md += f"- **{op_id}**\n"
                md += "\nFor details, run: `openapi-mcp api call-endpoint help --name <endpoint>`\n"
                result = md
            else:
                lines = ["Available endpoints:"]
                for op_id, info_obj in operations_info.items():
                    summary = info_obj.get("summary", "").strip()
                    if summary:
                        lines.append(f"  {op_id}: {summary}")
                    else:
                        lines.append(f"  {op_id}")
                lines.append("\nFor details, run: openapi-mcp api call-endpoint help --name <endpoint>")
                result = "\n".join(lines)
    if response_format == "markdown":
        result += "\n\n## Global Options\n"
        result += "- **--output**: Output format (json, yaml, xml, markdown)\n"
        result += "- **--dry-run**: Simulate execution without making an API call\n"
        result += "- **--param**: Provide parameters in key=value format (can be repeated)\n"
    elif response_format == "xml":
        global_options = (
            "  <global_options>\n"
            "    <option name='--output'>Output format (json, yaml, xml, markdown)</option>\n"
            "    <option name='--dry-run'>Simulate execution without making an API call</option>\n"
            "    <option name='--param'>Provide parameters in key=value format (can be repeated)</option>\n"
            "  </global_options>\n"
        )
        result += "\n" + global_options
    else:
        result += "\n\nGlobal Options:\n"
        result += "  --output: Output format (json, yaml, xml, markdown)\n"
        result += "  --dry-run: Simulate execution without making an API call\n"
        result += "  --param: Provide parameters in key=value format (can be repeated)\n"
    return result

###############################################################################
# Tool function generator with --dry-run support and registration
###############################################################################

def generate_tool_function(operation_id: str, method: str, path: str, parameters: list,
                           server_url: str, operations_info: Dict[str, Any], client: httpx.Client):
    """
    Creates a callable tool function for a given endpoint.
    Supports a --dry-run flag.
    """
    def tool_func(**kwargs):
        response_format = str(kwargs.get("response_format", "json")).lower()
        missing_params = []
        for param in parameters:
            if param.get("required", False) and (param["name"] not in kwargs):
                missing_params.append(param)
        if missing_params:
            help_info = {
                "endpoint": operation_id,
                "method": method.upper(),
                "path": path,
                "summary": operations_info.get(operation_id, {}).get("summary", ""),
                "required_parameters": [],
                "optional_parameters": []
            }
            for p in missing_params:
                schema = p.get("schema", {}).get("type", "unknown")
                help_info["required_parameters"].append({
                    p.get("name"): {"in": p.get("in"), "type": schema, "description": p.get("description", "")}
                })
            for p in parameters:
                if not p.get("required", False):
                    schema = p.get("schema", {}).get("type", "unknown")
                    help_info["optional_parameters"].append({
                        p.get("name"): {"in": p.get("in"), "type": schema, "description": p.get("description", "")}
                    })
            help_info["example"] = f"openapi-mcp api call-endpoint --name {operation_id} --param {missing_params[0]['name']}=yourValue"
            if response_format == "yaml":
                return yaml.dump(help_info, allow_unicode=True, default_flow_style=False)
            elif response_format == "markdown":
                md = (f"# Endpoint: {operation_id}\n\n"
                      f"**Method:** {method.upper()}\n\n"
                      f"**Path:** {path}\n\n")
                summary = help_info.get("summary", "")
                if summary.strip():
                    md += f"**Summary:** {summary}\n\n"
                if help_info.get("required_parameters"):
                    md += "## Required parameters:\n\n"
                    for param in help_info["required_parameters"]:
                        for key, val in param.items():
                            md += f"- **{key}**: [in: {val.get('in')}, type: {val.get('type')}] {val.get('description', '')}\n"
                    md += "\n"
                if help_info.get("optional_parameters"):
                    md += "## Optional parameters:\n\n"
                    for param in help_info["optional_parameters"]:
                        for key, val in param.items():
                            md += f"- **{key}**: [in: {val.get('in')}, type: {val.get('type')}] {val.get('description', '')}\n"
                    md += "\n"
                md += f"**Example:** `{help_info.get('example', '')}`\n"
                return md
            else:
                return format_help_text_plain(help_info)

        all_pages = str(kwargs.pop("all_pages", "false")).lower() == "true"
        dry_run = str(kwargs.pop("dry_run", "false")).lower() == "true"
        kwargs.pop("response_format", None)

        final_path = path
        for param in parameters:
            if param.get("in") == "path":
                name = param["name"]
                if name not in kwargs:
                    return format_error_message(f"Missing path parameter: {name}")
                final_path = final_path.replace("{" + name + "}", str(kwargs.pop(name)))
        query = {}
        for param in parameters:
            if param.get("in") == "query":
                name = param["name"]
                if name in kwargs:
                    query[name] = kwargs.pop(name)
        body = kwargs.pop("body", None)

        if kwargs:
            unknown_keys = list(kwargs.keys())
            help_text = get_endpoint_help(endpoint=operation_id, response_format=response_format, operations_info=operations_info)
            return format_error_message(f"Unknown parameter(s): {', '.join(unknown_keys)}.\nValid parameters are as follows:\n{help_text}")

        url_full = server_url.rstrip("/") + final_path

        def do_request():
            if dry_run:
                details = {
                    "dry_run": True,
                    "method": method.upper(),
                    "url": url_full,
                    "query": query,
                    "body": body
                }
                return json.dumps(details, indent=2, ensure_ascii=False)
            resp = client.request(method.upper(), url_full, params=query, json=body)
            resp.raise_for_status()
            if response_format == "xml":
                try:
                    data = resp.json()
                    return dict_to_pretty_xml(data, root_node="response")
                except Exception:
                    return dict_to_pretty_xml({"response": resp.text}, root_node="response")
            elif response_format in ["text", "yaml"]:
                try:
                    data = resp.json()
                    return yaml.dump(data, allow_unicode=True, default_flow_style=False)
                except Exception:
                    return resp.text
            elif response_format == "markdown":
                try:
                    data = resp.json()
                    return dict_to_markdown(data)
                except Exception:
                    return resp.text
            else:
                try:
                    return json.dumps(resp.json(), indent=2, ensure_ascii=False)
                except Exception:
                    return resp.text

        try:
            result = do_request()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                help_text = get_endpoint_help(endpoint=operation_id, response_format="text", operations_info=operations_info)
                err_msg = f"Client error '400 Bad Request' for url '{url_full}'\n{help_text}"
                return format_error_message(err_msg)
            else:
                return format_error_message(str(e))
        except Exception as e:
            return format_error_message(str(e))

        if not all_pages:
            return result

        results = []
        current_page = 0
        while True:
            query["page"] = current_page
            try:
                page_resp = client.request(method.upper(), url_full, params=query, json=body)
                page_resp.raise_for_status()
                try:
                    page_data = page_resp.json()
                except Exception:
                    page_data = page_resp.text
            except Exception as e:
                return format_error_message(str(e))
            results.append(page_data)
            if isinstance(page_data, dict) and "page" in page_data:
                page_info = page_data["page"]
                total_pages = page_info.get("totalPages", 1)
                if current_page >= total_pages - 1:
                    break
                current_page += 1
            else:
                break

        if response_format == "xml":
            return dict_to_pretty_xml({"pages": results}, root_node="response")
        elif response_format in ["text", "yaml"]:
            return yaml.dump({"pages": results}, allow_unicode=True, default_flow_style=False)
        elif response_format == "markdown":
            return dict_to_markdown({"pages": results})
        else:
            return json.dumps({"pages": results}, indent=2, ensure_ascii=False)

    tool_func.__name__ = operation_id
    return tool_func

###############################################################################
# Main CLI with hierarchical command structure (AWS CLI style)
###############################################################################

def main():
    parser = argparse.ArgumentParser(prog="openapi-mcp", description="CLI for OpenAPI-based API calls")
    subparsers = parser.add_subparsers(dest="service", required=True, help="Service (e.g., api)")

    # Service: api
    api_parser = subparsers.add_parser("api", help="API service commands")
    api_subparsers = api_parser.add_subparsers(dest="action", required=True, help="Action")

    # Action: help (API-level help)
    api_subparsers.add_parser("help", help="Show help for API commands")

    # Action: list-endpoints
    list_parser = api_subparsers.add_parser("list-endpoints", help="List available API endpoints")
    list_parser.add_argument("--output", choices=["json", "yaml", "xml", "markdown"], default="json",
                             help="Output format")

    # Action: call-endpoint
    call_parser = api_subparsers.add_parser("call-endpoint", help="Call a specific API endpoint")
    call_parser.add_argument("--name", help="Endpoint name to call")
    call_parser.add_argument("--param", action="append", help="Parameter for the API call (key=value). Can be specified multiple times.")
    call_parser.add_argument("--dry-run", action="store_true", help="Simulate execution without making an API call")
    call_parser.add_argument("--output", choices=["json", "yaml", "xml", "markdown"], default="json",
                             help="Output format")
    call_parser.add_argument("command_help", nargs="?", default="", help="If set to 'help', display help for call-endpoint")

    args = parser.parse_args()

    if args.service == "api" and args.action == "help":
        api_parser.print_help()
        sys.exit(0)

    if args.action == "call-endpoint" and getattr(args, "command_help", "").lower() == "help":
        openapi_url = os.environ.get("OPENAPI_URL", "").strip()
        ops_info = load_openapi(openapi_url)[2]
        if args.name:
            help_text = get_endpoint_help(endpoint=args.name, response_format=args.output, operations_info=ops_info)
            print(help_text)
        else:
            general_help = get_endpoint_help(response_format=args.output, operations_info=ops_info)
            print(general_help)
        sys.exit(0)

    OPENAPI_URL = os.environ.get("OPENAPI_URL", "").strip()
    if not OPENAPI_URL:
        parser.error("No OPENAPI_URL specified. Set the OPENAPI_URL environment variable.")

    openapi_spec, server_url, operations_info = load_openapi(OPENAPI_URL)

    # Support authentication via direct token or OAuth client_credentials flow.
    AUTH_TOKEN = os.environ.get("AUTH_TOKEN")
    if not AUTH_TOKEN:
        oauth_token = get_oauth_access_token()
        if oauth_token:
            AUTH_TOKEN = oauth_token

    default_headers = {"User-Agent": "openapi-proxy/1.0", "Accept": "application/json"}
    if AUTH_TOKEN:
        default_headers["Authorization"] = f"Bearer {AUTH_TOKEN}"
    client = httpx.Client(headers=default_headers, timeout=10.0)

    generated_tools = {}
    for path, path_item in openapi_spec.get("paths", {}).items():
        for method, operation in path_item.items():
            if method.lower() not in ["get", "post", "put", "delete", "patch", "head", "options"]:
                continue
            op_id = operation.get("operationId")
            if not op_id:
                sanitized = path.replace("/", "_").replace("{", "").replace("}", "")
                op_id = f"{method}_{sanitized}"
            tool_func = generate_tool_function(op_id, method, path, operation.get("parameters", []),
                                                 server_url, operations_info, client)
            globals()[op_id] = mcp.tool()(tool_func)
            generated_tools[op_id] = operation.get("summary", "")

    if args.action == "list-endpoints":
        capabilities = {
            "server_name": "openapi_proxy_server",
            "base_url": server_url,
            "tools": [
                {"name": name, **({"description": desc} if desc.strip() else {})}
                for name, desc in generated_tools.items()
            ]
        }
        output_format = args.output
        if output_format == "xml":
            result = dict_to_pretty_xml(capabilities, root_node="capabilities")
        elif output_format == "yaml":
            result = yaml.dump(capabilities, allow_unicode=True, default_flow_style=False)
        elif output_format == "markdown":
            result = dict_to_markdown(capabilities)
        else:
            result = json.dumps(capabilities, indent=2, ensure_ascii=False)
    elif args.action == "call-endpoint":
        if not args.name:
            parser.error("The --name argument is required for call-endpoint (or run call-endpoint help for available endpoints).")
        op_id = None
        for key in operations_info:
            if key.lower() == args.name.lower():
                op_id = key
                break
        if op_id is None:
            parser.error(f"Unknown endpoint: {args.name}")
        func = globals().get(op_id)
        if func is None:
            parser.error(f"Endpoint function not found for: {args.name}")
        param_dict = {}
        if args.param:
            for p in args.param:
                if '=' in p:
                    k, v = p.split('=', 1)
                    param_dict[k] = v
                else:
                    logging.warning(f"Ignoring parameter '{p}', expected format key=value")
        param_dict["response_format"] = args.output
        if args.dry_run:
            param_dict["dry_run"] = "true"
        try:
            if hasattr(func, "__wrapped__"):
                result = func.__wrapped__(**param_dict)
            else:
                result = func(**param_dict)
        except Exception as e:
            result = format_error_message(f"Error calling endpoint: {str(e)}")
    else:
        parser.error(f"Unknown action: {args.action}")

    if sys.stdout.isatty() and isinstance(result, str) and not result.startswith("Error: ") and getattr(args, "command_help", "").lower() != "help":
        if args.output in ["json", "xml", "yaml", "markdown"]:
            result = syntax_highlight(result, args.output)

    print(result)

if __name__ == "__main__":
    main()
