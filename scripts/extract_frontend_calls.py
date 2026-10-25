import os, re, json

def extract_api_calls():
    """Extract all API calls from frontend JS/TS/Vue files"""
    api_calls = []
    
    for root, dirs, files in os.walk('static'):
        dirs[:] = [d for d in dirs if d not in ('node_modules', '__pycache__')]
        for f in files:
            if f.endswith(('.js', '.ts', '.vue', '.jsx', '.tsx')):
                path = os.path.join(root, f)
                try:
                    with open(path, encoding='utf-8') as fp:
                        content = fp.read()
                except:
                    continue
                
                # Pattern 1: fetch('/api/...')
                fetch_pattern = r'fetch\([\'"`]([^\'"`]+)[\'"`]'
                for m in re.finditer(fetch_pattern, content):
                    api_calls.append({
                        'file': os.path.relpath(path),
                        'method': 'fetch',
                        'url': m.group(1),
                        'line': content[:m.start()].count('\n') + 1
                    })
                
                # Pattern 2: axios.get/post/put/delete/patch
                axios_pattern = r'axios\.(get|post|put|patch|delete)\([\'"`]([^\'"`]+)[\'"`]'
                for m in re.finditer(axios_pattern, content):
                    api_calls.append({
                        'file': os.path.relpath(path),
                        'method': 'axios.' + m.group(1),
                        'url': m.group(2),
                        'line': content[:m.start()].count('\n') + 1
                    })
                
                # Pattern 3: $http.get/post/put/delete (Angular)
                http_pattern = r'\$http\.(get|post|put|delete|patch)\([\'"`]([^\'"`]+)[\'"`]'
                for m in re.finditer(http_pattern, content):
                    api_calls.append({
                        'file': os.path.relpath(path),
                        'method': '$http.' + m.group(1),
                        'url': m.group(2),
                        'line': content[:m.start()].count('\n') + 1
                    })
                
                # Pattern 4: this.$http or this.$axios
                this_http_pattern = r'this\.\$?(http|axios)\.(get|post|put|patch|delete)\([\'"`]([^\'"`]+)[\'"`]'
                for m in re.finditer(this_http_pattern, content):
                    api_calls.append({
                        'file': os.path.relpath(path),
                        'method': 'this.$' + m.group(1) + '.' + m.group(2),
                        'url': m.group(3),
                        'line': content[:m.start()].count('\n') + 1
                    })
                
                # Pattern 5: api.XXX() calls
                api_service_pattern = r'api\.(\w+)\([\'"]([^\'"`]+)[\'"]'
                for m in re.finditer(api_service_pattern, content):
                    api_calls.append({
                        'file': os.path.relpath(path),
                        'method': 'api.' + m.group(1),
                        'url': m.group(2),
                        'line': content[:m.start()].count('\n') + 1
                    })
    
    return api_calls

if __name__ == '__main__':
    api_calls = extract_api_calls()
    
    # Normalize URLs - remove query params, trailing slashes
    for call in api_calls:
        call['url_normalized'] = call['url'].split('?')[0].rstrip('/')
    
    with open('frontend_api_calls.json', 'w', encoding='utf-8') as f:
        json.dump(api_calls, f, ensure_ascii=False, indent=2)
    
    print(f'Total API calls found: {len(api_calls)}')
    
    # Group by URL
    url_counts = {}
    for call in api_calls:
        url = call['url_normalized']
        url_counts[url] = url_counts.get(url, 0) + 1
    
    print('\nTop 50 API endpoints called from frontend:')
    for url, count in sorted(url_counts.items(), key=lambda x: -x[1])[:50]:
        print(f'  {count:3} {url}')

if __name__ == '__main__':
    extract_api_calls()