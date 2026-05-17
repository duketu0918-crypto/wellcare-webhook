# -*- coding: utf-8 -*-
import os

BASE = r'C:\LineOA_Control'

# ── requirements.txt ──
req = """flask==3.0.3
line-bot-sdk==3.11.0
gunicorn==22.0.0
requests==2.32.3
"""

# ── render.yaml ──
render_yaml = """services:
  - type: web
    name: wellcare-webhook
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn webhook_server:app --bind 0.0.0.0:$PORT --workers 2 --timeout 60
    envVars:
      - key: PYTHON_VERSION
        value: 3.11.0
"""

# ── Procfile ──
procfile = "web: gunicorn webhook_server:app --bind 0.0.0.0:$PORT --workers 2 --timeout 60\n"

# ── runtime.txt ──
runtime = "python-3.11.0\n"

files = {
    'requirements.txt': req,
    'render.yaml': render_yaml,
    'Procfile': procfile,
    'runtime.txt': runtime,
}

for name, content in files.items():
    path = os.path.join(BASE, name)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'建立: {name} ({os.path.getsize(path)} bytes)')

print('\n全部完成！')
