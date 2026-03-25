#!/usr/bin/env python3
"""
Lightweight mock daemon for integration tests.
Starts up instantly, provides minimal contract compliance.
"""

import json
import socket
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs


class LightweightMockHandler(BaseHTTPRequestHandler):
    """Minimal mock daemon handler."""
    
    # Simple in-memory storage
    state = {
        'events': [],
        'emotion': {
            'valence': 0.0,
            'arousal': 0.3,
            'anger': 0.0,
            'sadness': 0.0,
            'anxiety': 0.0,
            'joy': 0.0,
            'loneliness': 0.0,
            'social_safety': 0.5,
            'energy': 0.7,
            'uncertainty': 0.3
        }
    }
    
    def log_message(self, format, *args):
        """Suppress logging."""
        pass
    
    def do_GET(self):
        """Handle GET requests."""
        if self.path == '/health':
            self._send_json({
                'ok': True,
                'ts': '2026-03-02T12:00:00Z',
                'emotiond': {
                    'version': '0.1.0',
                    'status': 'running',
                    'core_enabled': True
                }
            })
        else:
            self._send_error(404)
    
    def do_POST(self):
        """Handle POST requests."""
        parsed = urlparse(self.path)
        
        if parsed.path == '/event':
            # Accept event, return success
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                event = json.loads(post_data.decode('utf-8'))
                
                # Store event
                self.state['events'].append(event)
                
                # Update emotion based on event type
                if event.get('type') == 'user_message':
                    if 'happy' in event.get('text', '').lower():
                        self.state['emotion']['valence'] += 0.1
                    if 'sad' in event.get('text', '').lower():
                        self.state['emotion']['valence'] -= 0.1
                
                self._send_json({'success': True, 'event_id': f"evt_{len(self.state['events'])}"})
                
            except Exception:
                self._send_error(400)
        
        elif parsed.path == '/plan':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                request = json.loads(post_data.decode('utf-8'))
                
                # Generate plan with current emotion
                plan = {
                    'tone': 'neutral',
                    'intent': 'respond',
                    'focus_target': request.get('user_id', 'user'),
                    'key_points': ['Mock response'],
                    'constraints': [],
                    'emotion': self.state['emotion'].copy(),
                    'relationship': {
                        'bond': 0.0,
                        'trust': 0.5,
                        'grudge': 0.0
                    }
                }
                
                self._send_json(plan)
                
            except Exception:
                self._send_error(400)
        
        else:
            self._send_error(404)
    
    def _send_json(self, data, status=200):
        """Send JSON response."""
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def _send_error(self, status):
        """Send error response."""
        self.send_response(status)
        self.end_headers()


def start_lightweight_mock(port=18080):
    """Start lightweight mock daemon."""
    server = HTTPServer(('127.0.0.1', port), LightweightMockHandler)
    
    # Start in background thread
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    
    # Give it a moment to start
    time.sleep(0.1)
    
    return server


if __name__ == '__main__':
    server = start_lightweight_mock()
    print("Lightweight mock daemon running on port 18080")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.shutdown()
        print("\nMock daemon stopped")
