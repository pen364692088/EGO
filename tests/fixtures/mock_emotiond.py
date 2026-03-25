#!/usr/bin/env python3
"""
Mock emotiond service for integration testing.
Matches the real emotiond API contract.
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import uuid
from datetime import datetime
import threading
import time

# Use a different port for mock server to avoid conflicts with real daemon
MOCK_PORT = 18080

class MockEmotiondHandler(BaseHTTPRequestHandler):
    """Mock handler for emotiond HTTP endpoints."""
    
    # Class-level storage for persistence across requests
    storage = {
        'events': [],
        'predictions': {},
        'deltas': {},
        'decisions': {},
        'emotion_state': {
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
        },
        'relationships': {}
    }
    
    def log_message(self, format, *args):
        """Suppress default logging."""
        pass
    
    def do_GET(self):
        """Handle GET requests."""
        if self.path == '/health':
            # Match real API: {"ok": true, "ts": ..., "emotiond": {...}}
            self._send_json({
                'ok': True,
                'ts': datetime.utcnow().isoformat(),
                'emotiond': {
                    'version': '0.1.0',
                    'status': 'running',
                    'core_enabled': True
                }
            })
        elif self.path == '/events':
            self._send_json({'events': self.storage['events']})
        elif self.path.startswith('/predictions/'):
            prediction_id = self.path.split('/')[-1]
            prediction = self.storage['predictions'].get(prediction_id)
            if prediction:
                self._send_json(prediction)
            else:
                self._send_error(404, 'Prediction not found')
        elif self.path.startswith('/deltas/'):
            delta_id = self.path.split('/')[-1]
            delta = self.storage['deltas'].get(delta_id)
            if delta:
                self._send_json(delta)
            else:
                self._send_error(404, 'Delta not found')
        elif self.path.startswith('/decision'):
            # Return mock decision
            decision = {
                'status': 'ok',
                'action': 'seek',
                'explanation': 'Mock decision for testing',
                'decision_id': str(uuid.uuid4())
            }
            self._send_json(decision)
        else:
            self._send_error(404, 'Not found')
    
    def do_POST(self):
        """Handle POST requests."""
        if self.path == '/event':
            self._handle_event()
        elif self.path == '/plan':
            self._handle_plan()
        elif self.path == '/predict':
            self._handle_predict()
        elif self.path == '/decision':
            self._handle_decision()
        elif self.path.startswith('/events/external'):
            self._handle_external_event()
        else:
            self._send_error(404, 'Not found')
    
    def _handle_event(self):
        """Handle event submission - matches real API behavior."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self._send_error(400, 'Empty request body')
                return
                
            post_data = self.rfile.read(content_length)
            event = json.loads(post_data.decode('utf-8'))
            
            # Add metadata
            event['id'] = str(uuid.uuid4())
            event['timestamp'] = datetime.utcnow().isoformat()
            event['mock'] = True
            
            # Store event
            self.storage['events'].append(event)
            
            # Update emotion state based on event type
            self._update_emotion_state(event)
            
            # Generate mock response matching real API
            response = {
                'status': 'processed',
                'event_id': event['id'],
                'emotion_delta': {
                    'valence': 0.05,
                    'arousal': 0.02
                }
            }
            
            # Return 200 to match real API
            self._send_json(response, status=200)
            
        except json.JSONDecodeError:
            self._send_error(400, 'Invalid JSON')
        except Exception as e:
            self._send_error(500, f'Internal error: {str(e)}')
    
    def _handle_plan(self):
        """Handle plan generation - matches real API behavior."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self._send_error(400, 'Empty request body')
                return
                
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            # Generate mock plan matching real API response structure
            plan = {
                'tone': 'warm',
                'intent': 'seek',
                'focus_target': data.get('user_id', 'default'),
                'key_points': ['Acknowledge the user', 'Respond appropriately'],
                'constraints': ['Be respectful', 'Stay on topic'],
                'emotion': self.storage['emotion_state'].copy(),
                'relationship': {
                    'bond': 0.5,
                    'grudge': 0.0,
                    'trust': 0.5,
                    'repair_bank': 0.0
                },
                'mood': {
                    'valence': 0.0,
                    'arousal': 0.3,
                    'anxiety': 0.0,
                    'joy': 0.0,
                    'sadness': 0.0,
                    'anger': 0.0,
                    'loneliness': 0.0,
                    'uncertainty': 0.3
                },
                'uncertainty': 0.3
            }
            
            self._send_json(plan, status=200)
            
        except json.JSONDecodeError:
            self._send_error(400, 'Invalid JSON')
        except Exception as e:
            self._send_error(500, f'Internal error: {str(e)}')
    
    def _handle_decision(self):
        """Handle decision endpoint."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length) if content_length > 0 else b'{}'
            data = json.loads(post_data.decode('utf-8'))
            
            decision = {
                'status': 'ok',
                'action': 'seek',
                'explanation': 'Mock decision for testing',
                'decision_id': str(uuid.uuid4()),
                'target': data.get('user_id', 'default')
            }
            
            self._send_json(decision, status=200)
            
        except Exception as e:
            self._send_error(500, f'Internal error: {str(e)}')
    
    def _handle_external_event(self):
        """Handle external events endpoint."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self._send_error(400, 'Empty request body')
                return
            
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            response = {
                'status': 'accepted',
                'event_id': str(uuid.uuid4()),
                'degraded': False
            }
            
            self._send_json(response, status=200)
            
        except Exception as e:
            self._send_error(500, f'Internal error: {str(e)}')
    
    def _handle_predict(self):
        """Handle prediction requests."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self._send_error(400, 'Empty request body')
                return
                
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            prediction_id = str(uuid.uuid4())
            prediction = {
                'id': prediction_id,
                'predicted_delta': {
                    'valence': 0.1,
                    'arousal': 0.2,
                    'certainty': 0.8
                },
                'confidence': 0.85,
                'model': 'mock-model-v1',
                'timestamp': datetime.utcnow().isoformat(),
                'mock': True
            }
            
            self.storage['predictions'][prediction_id] = prediction
            self._send_json(prediction, status=200)
            
        except json.JSONDecodeError:
            self._send_error(400, 'Invalid JSON')
        except Exception as e:
            self._send_error(500, f'Internal error: {str(e)}')
    
    def _update_emotion_state(self, event):
        """Update mock emotion state based on event."""
        event_type = event.get('type', '')
        text = event.get('text', '').lower() if event.get('text') else ''
        
        if event_type == 'user_message':
            if any(w in text for w in ['good', 'great', 'thanks', 'love', 'happy']):
                self.storage['emotion_state']['valence'] = min(1.0, self.storage['emotion_state']['valence'] + 0.1)
                self.storage['emotion_state']['joy'] = min(1.0, self.storage['emotion_state']['joy'] + 0.1)
            elif any(w in text for w in ['bad', 'hate', 'stupid', 'wrong', 'angry']):
                self.storage['emotion_state']['valence'] = max(-1.0, self.storage['emotion_state']['valence'] - 0.1)
                self.storage['emotion_state']['anger'] = min(1.0, self.storage['emotion_state']['anger'] + 0.1)
        
        elif event_type == 'world_event':
            subtype = event.get('meta', {}).get('subtype', '')
            if subtype == 'care':
                self.storage['emotion_state']['valence'] = min(1.0, self.storage['emotion_state']['valence'] + 0.15)
                self.storage['emotion_state']['joy'] = min(1.0, self.storage['emotion_state']['joy'] + 0.15)
            elif subtype == 'rejection':
                self.storage['emotion_state']['valence'] = max(-1.0, self.storage['emotion_state']['valence'] - 0.2)
                self.storage['emotion_state']['sadness'] = min(1.0, self.storage['emotion_state']['sadness'] + 0.2)
    
    def _send_json(self, data, status=200):
        """Send JSON response."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        response = json.dumps(data)
        self.wfile.write(response.encode('utf-8'))
    
    def _send_error(self, code, message):
        """Send error response."""
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        error = {'error': message, 'mock': True}
        response = json.dumps(error)
        self.wfile.write(response.encode('utf-8'))


def start_mock_server(port=None, host='127.0.0.1'):
    """Start the mock emotiond server in background thread."""
    if port is None:
        port = MOCK_PORT
    server_address = (host, port)
    httpd = HTTPServer(server_address, MockEmotiondHandler)
    
    # Run in background thread
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()
    
    # Give server time to start
    time.sleep(0.5)
    
    return httpd, server_thread


if __name__ == '__main__':
    # Start server directly
    httpd, thread = start_mock_server()
    print(f"Mock emotiond service running on http://127.0.0.1:{MOCK_PORT}")
    print("Press Ctrl+C to stop")
    
    try:
        # Keep main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        httpd.shutdown()
