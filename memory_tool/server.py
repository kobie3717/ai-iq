"""HTTP server for memory-tool API."""

import sys
import json
import sqlite3
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Dict, Any, Optional

from .config import get_logger
from .database import get_db
from .memory_ops import add_memory, search_memories, list_memories, get_memory
from .graph import graph_stats
from . import __version__

logger = get_logger(__name__)


class MemoryAPIHandler(BaseHTTPRequestHandler):
    """HTTP request handler for memory-tool API."""

    def log_message(self, format, *args):
        """Log requests to stderr (not stdout)."""
        sys.stderr.write(f"{self.address_string()} - {format % args}\n")

    def _send_json(self, data: Any, status: int = 200):
        """Send JSON response with CORS headers."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

        response = json.dumps(data, ensure_ascii=False)
        self.wfile.write(response.encode('utf-8'))

    def _send_error_json(self, message: str, status: int = 400):
        """Send error response."""
        self._send_json({"error": message}, status)

    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        """Handle GET requests."""
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        try:
            if path == '/health':
                self._handle_health()
            elif path == '/search':
                self._handle_search(params)
            elif path == '/list':
                self._handle_list(params)
            elif path == '/stats':
                self._handle_stats()
            elif path.startswith('/get/'):
                # Extract ID from path like /get/123
                try:
                    mem_id = int(path.split('/')[-1])
                    self._handle_get(mem_id)
                except ValueError:
                    self._send_error_json("Invalid memory ID", 400)
            else:
                self._send_error_json("Not found", 404)
        except Exception as e:
            logger.error(f"Error handling GET {path}: {e}", exc_info=True)
            self._send_error_json(str(e), 500)

    def do_POST(self):
        """Handle POST requests."""
        parsed = urlparse(self.path)
        path = parsed.path

        try:
            # Read and parse request body
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')

            try:
                data = json.loads(body) if body else {}
            except json.JSONDecodeError as e:
                self._send_error_json(f"Invalid JSON: {e}", 400)
                return

            if path == '/add':
                self._handle_add(data)
            else:
                self._send_error_json("Not found", 404)
        except Exception as e:
            logger.error(f"Error handling POST {path}: {e}", exc_info=True)
            self._send_error_json(str(e), 500)

    def _handle_health(self):
        """Handle /health endpoint."""
        self._send_json({
            "ok": True,
            "version": __version__
        })

    def _handle_add(self, data: Dict[str, Any]):
        """Handle POST /add endpoint."""
        # Validate required fields
        if 'category' not in data or 'content' not in data:
            self._send_error_json("Missing required fields: category, content", 400)
            return

        category = data['category']
        content = data['content']
        tags = data.get('tags', '')
        project = data.get('project')
        priority = int(data.get('priority', 0))

        # Add memory
        mem_id = add_memory(
            category=category,
            content=content,
            tags=tags,
            project=project,
            priority=priority
        )

        if mem_id:
            self._send_json({
                "ok": True,
                "id": mem_id
            }, 201)
        else:
            self._send_error_json("Failed to add memory (duplicate?)", 400)

    def _handle_search(self, params: Dict[str, list]):
        """Handle GET /search?q=...&limit=10 endpoint."""
        query = params.get('q', [''])[0]
        if not query:
            self._send_error_json("Missing query parameter 'q'", 400)
            return

        limit = int(params.get('limit', ['10'])[0])
        mode = params.get('mode', ['hybrid'])[0]

        # Search memories
        rows, search_id, temporal_range = search_memories(query, mode=mode)

        # Convert to list of dicts and limit
        results = [dict(r) for r in rows[:limit]]

        self._send_json(results)

    def _handle_list(self, params: Dict[str, list]):
        """Handle GET /list?category=...&project=...&limit=50 endpoint."""
        category = params.get('category', [None])[0]
        project = params.get('project', [None])[0]
        limit = int(params.get('limit', ['50'])[0])

        # List memories
        rows = list_memories(category=category, project=project)

        # Convert to list of dicts and limit
        results = [dict(r) for r in rows[:limit]]

        self._send_json(results)

    def _handle_get(self, mem_id: int):
        """Handle GET /get/<id> endpoint."""
        mem = get_memory(mem_id)

        if mem:
            self._send_json(dict(mem))
        else:
            self._send_error_json(f"Memory {mem_id} not found", 404)

    def _handle_stats(self):
        """Handle GET /stats endpoint."""
        conn = get_db()

        stats = conn.execute("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN active = 1 THEN 1 ELSE 0 END) as active,
                   SUM(CASE WHEN stale = 1 AND active = 1 THEN 1 ELSE 0 END) as stale,
                   SUM(CASE WHEN expires_at IS NOT NULL AND expires_at < datetime('now') AND active = 1 THEN 1 ELSE 0 END) as expired,
                   COUNT(DISTINCT project) as projects,
                   COUNT(DISTINCT category) as categories,
                   SUM(access_count) as total_accesses
            FROM memories
        """).fetchone()

        cats = conn.execute("""
            SELECT category, COUNT(*) as count
            FROM memories WHERE active = 1 GROUP BY category ORDER BY count DESC
        """).fetchall()

        g_stats = graph_stats()
        conn.close()

        result = {
            "total": stats['total'],
            "active": stats['active'],
            "stale": stats['stale'],
            "expired": stats['expired'] or 0,
            "projects": stats['projects'],
            "categories": stats['categories'],
            "total_accesses": stats['total_accesses'] or 0,
            "by_category": [dict(c) for c in cats],
            "graph": {
                "entities": g_stats['entities'],
                "relationships": g_stats['relationships'],
                "facts": g_stats['facts'],
                "memory_links": g_stats['memory_links']
            }
        }

        self._send_json(result)


def run_server(host: str = '127.0.0.1', port: int = 37777):
    """Start the HTTP API server.

    Args:
        host: Host to bind to (default: 127.0.0.1)
        port: Port to listen on (default: 37777)
    """
    server_address = (host, port)
    httpd = HTTPServer(server_address, MemoryAPIHandler)

    print(f"Memory-tool HTTP API server starting on {host}:{port}", file=sys.stderr)
    print(f"", file=sys.stderr)
    print(f"Endpoints:", file=sys.stderr)
    print(f"  GET  /health                     - Health check", file=sys.stderr)
    print(f"  POST /add                        - Add memory", file=sys.stderr)
    print(f"  GET  /search?q=...&limit=10      - Search memories", file=sys.stderr)
    print(f"  GET  /list?category=...&limit=50 - List memories", file=sys.stderr)
    print(f"  GET  /get/<id>                   - Get single memory", file=sys.stderr)
    print(f"  GET  /stats                      - Get statistics", file=sys.stderr)
    print(f"", file=sys.stderr)
    print(f"Press Ctrl+C to stop", file=sys.stderr)
    print(f"", file=sys.stderr)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print(f"\nShutting down server...", file=sys.stderr)
        httpd.server_close()
        sys.exit(0)
