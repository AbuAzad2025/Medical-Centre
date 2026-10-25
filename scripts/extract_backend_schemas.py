"""
Comprehensive backend schema extractor - extracts request/response schemas for all endpoints
"""
import os, sys, json, inspect, re
from typing import Dict, List, Any, Optional

sys.path.insert(0, r'D:\recovers\data\medical')

os.environ.setdefault('SECRET_KEY', 'ci-test-secret-key-for-jwt-hs256-min32')
os.environ.setdefault('APP_ENV', 'testing')
os.environ.setdefault('FLASK_ENV', 'testing')
os.environ.setdefault('TEST_DATABASE_URL', 'postgresql://med_app:med_app@127.0.0.1:5432/medical_centre_platform_test')
os.environ.setdefault('DATABASE_URL', 'postgresql://med_app:med_app@127.0.0.1:5432/medical_centre_platform_test')

from app_factory import create_app

app = create_app('testing')

def extract_route_info():
    """Extract all routes with their handler functions"""
    with app.app_context():
        routes = []
        for rule in app.url_map.iter_rules():
            methods = ','.join(sorted(m for m in rule.methods if m not in ('HEAD', 'OPTIONS')))
            endpoint = rule.endpoint
            view_func = app.view_functions.get(endpoint)
            
            routes.append({
                'endpoint': endpoint,
                'rule': rule.rule,
                'methods': methods,
                'blueprint': rule.endpoint.split('.')[0] if '.' in rule.endpoint else 'main',
                'has_view_func': view_func is not None,
                'view_func_name': view_func.__name__ if view_func else None,
                'view_func_module': view_func.__module__ if view_func else None,
                'view_func_doc': view_func.__doc__ if view_func else None,
            })
        return routes

def extract_view_function_signatures():
    """Extract parameter info from view functions"""
    with app.app_context():
        signatures = {}
        for rule in app.url_map.iter_rules():
            endpoint = rule.endpoint
            view_func = app.view_functions.get(endpoint)
            if not view_func:
                continue
            
            try:
                sig = inspect.signature(view_func)
                params = []
                for name, param in sig.parameters.items():
                    if name not in ('self', 'cls'):
                        param_info = {
                            'name': name,
                            'kind': str(param.kind),
                            'default': str(param.default) if param.default != inspect.Parameter.empty else 'required',
                            'annotation': str(param.annotation) if param.annotation != inspect.Parameter.empty else 'Any',
                        }
                        params.append(param_info)
                
                # Get return annotation
                return_annotation = str(sig.return_annotation) if sig.return_annotation != inspect.Signature.empty else 'Any'
                
                signatures[endpoint] = {
                    'params': params,
                    'return_annotation': return_annotation,
                    'docstring': view_func.__doc__,
                }
            except Exception as e:
                signatures[endpoint] = {'error': str(e)}
    
    return signatures

def extract_decorators_info():
    """Extract decorators from view functions"""
    decorators_info = {}
    for root, dirs, files in os.walk('routes'):
        for f in files:
            if f.endswith('.py'):
                path = os.path.join(root, f)
                try:
                    with open(path, encoding='utf-8') as fp:
                        content = fp.read()
                except:
                    continue
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    line_stripped = line.strip()
                    if '@' in line_stripped and 'route' in line_stripped and 'bp.route' in line_stripped:
                        m = re.search(r'@\w+_bp\.route\([\'"](.*?)[\'"]', line)
                        if m:
                            route_path = m.group(1)
                            # Look for decorators above
                            decorators = []
                            for j in range(i-1, max(-1, i-15), -1):
                                prev = lines[j].strip()
                                if prev.startswith('@'):
                                    decorators.append(prev)
                                elif prev == '':
                                    continue
                                else:
                                    break
                            if decorators:
                                decorators.reverse()  # Order from top to bottom
                            if route_path not in decorators_info:
                                decorators_info[route_path] = decorators
    return decorators_info

if __name__ == '__main__':
    print("=== Extracting backend routes ===")
    routes = extract_route_info()
    
    with open('backend_routes_complete.json', 'w', encoding='utf-8') as f:
        json.dump(routes, f, ensure_ascii=False, indent=2)
    
    print(f"Total routes: {len(routes)}")
    
    print("\n=== Extracting view function signatures ===")
    signatures = extract_view_function_signatures()
    with open('backend_signatures.json', 'w', encoding='utf-8') as f:
        json.dump(signatures, f, ensure_ascii=False, indent=2)
    
    print("\n=== Extracting decorators ===")
    decorators = extract_decorators_info()
    with open('backend_decorators.json', 'w', encoding='utf-8') as f:
        json.dump(decorators, f, ensure_ascii=False, indent=2)
    
    print("Done!")