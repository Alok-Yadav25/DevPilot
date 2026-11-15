# ruff: noqa: E501
"""Generate the standalone sandbox workflow. Only this YAML needs publishing."""

from pathlib import Path

root = Path(__file__).resolve().parents[1]
inner = (root / "sandbox-image/actions_inner.py").read_text()
header = """name: run-tests
run-name: run-tests ${{ inputs.job_id }}
on:
  workflow_dispatch:
    inputs:
      job_id: {required: true, type: string}
      target_repo: {required: true, type: string}
      target_ref: {required: true, type: string}
permissions:
  contents: read
concurrency:
  group: devpilot-sandbox
  cancel-in-progress: false
jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
        with:
          persist-credentials: false
      - name: Validate public target
        env:
          TARGET_REPO: ${{ inputs.target_repo }}
          TARGET_REF: ${{ inputs.target_ref }}
          ALLOWED_TARGET_REPOS: ${{ vars.ALLOWED_TARGET_REPOS }}
          ALLOWED_TARGET_OWNER: ${{ vars.ALLOWED_TARGET_OWNER }}
        shell: python
        run: |
          import json, os, re, urllib.request
          target = os.environ['TARGET_REPO']
          assert re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*', target)
          assert re.fullmatch(r'[0-9a-f]{40}', os.environ['TARGET_REF'])
          allowed = {r.strip().lower() for r in os.environ['ALLOWED_TARGET_REPOS'].split(',') if r.strip()}
          owner = os.environ.get('ALLOWED_TARGET_OWNER', '').strip().lower()
          assert target.lower() in allowed or (owner and target.split('/')[0].lower() == owner)
          with urllib.request.urlopen('https://api.github.com/repos/' + target, timeout=30) as response:
              assert json.load(response)['private'] is False
      - name: Prepare trusted Python image
        shell: bash
        run: |
          mkdir -p /tmp/devpilot-image
          cat > /tmp/devpilot-image/runner.py <<'PYTHON'
"""
footer = """          PYTHON
          cat > /tmp/devpilot-image/Dockerfile <<'DOCKER'
          FROM python:3.11-slim
          RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/* && pip install --no-cache-dir pytest==8.4.2
          COPY runner.py /opt/runner.py
          USER 10001:10001
          WORKDIR /work
          CMD ["python", "-I", "/opt/runner.py"]
          DOCKER
          docker build -q -t devpilot-actions /tmp/devpilot-image
      - name: Apply patch and run pytest inside isolated container
        env:
          TARGET_REPO: ${{ inputs.target_repo }}
          TARGET_REF: ${{ inputs.target_ref }}
        shell: python
        run: |
          import json, os, pathlib, subprocess, tempfile, time, uuid
          output = pathlib.Path('results')
          output.mkdir()
          name = 'devpilot-' + uuid.uuid4().hex
          payload = json.dumps({'target_repo': os.environ['TARGET_REPO'], 'target_ref': os.environ['TARGET_REF'], 'diff': pathlib.Path('patch.diff').read_text()})
          data = {'results': {'applied': False, 'exit_code': 4, 'outcomes': {}, 'infrastructure_error': 'Container failed to produce results.'}, 'pytest_log': '', 'install_log': ''}
          command = ['docker', 'run', '--name', name, '-i', '--read-only', '--user=10001:10001', '--cap-drop=ALL', '--security-opt=no-new-privileges', '--cpus=1', '--memory=512m', '--memory-swap=512m', '--pids-limit=128', '--log-driver=none', '--tmpfs=/work:rw,nosuid,nodev,size=128m,uid=10001,gid=10001', '--tmpfs=/tmp:rw,nosuid,nodev,size=256m,uid=10001,gid=10001', '--env=HOME=/tmp', 'devpilot-actions']
          try:
              with tempfile.TemporaryFile() as captured:
                  process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=captured, stderr=captured)
                  process.stdin.write((payload + "\\n").encode()); process.stdin.flush()
                  deadline = time.monotonic() + 300
                  isolated = False
                  while process.poll() is None:
                      captured.seek(0)
                      if not isolated and b'DEVPILOT_TEST_READY\\n' in captured.read(1000000):
                          subprocess.run(['docker', 'network', 'disconnect', 'bridge', name], check=True, capture_output=True)
                          networks = subprocess.check_output(['docker', 'inspect', '--format', '{{json .NetworkSettings.Networks}}', name], text=True).strip()
                          if networks != '{}':
                              raise RuntimeError('Container still has a network attached')
                          process.stdin.write(b'continue\\n'); process.stdin.close()
                          isolated = True
                          deadline = time.monotonic() + 120
                      if time.monotonic() >= deadline or os.fstat(captured.fileno()).st_size > 1000000:
                          subprocess.run(['docker', 'kill', name], capture_output=True)
                          process.kill(); process.wait()
                          data['results'].update(exit_code=124, timed_out=True)
                          break
                      time.sleep(.2)
                  else:
                      captured.seek(0)
                      raw = captured.read(1000000).decode(errors='replace').split('DEVPILOT_TEST_READY\\n')[-1]
                      try:
                          data = json.loads(raw)
                      except ValueError:
                          data['install_log'] = raw[-4000:]
          finally:
              subprocess.run(['docker', 'rm', '-f', name], capture_output=True)
              (output/'results.json').write_text(json.dumps(data['results']))
              (output/'pytest.log').write_text(data['pytest_log'][-4000:])
              (output/'install.log').write_text(data['install_log'][-4000:])
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: results
          retention-days: 1
          path: results/
          if-no-files-found: error
"""
path = root / "sandbox-repo/.github/workflows/run-tests.yml"
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(
    header
    + "".join(("          " + line if line else "") + "\n" for line in inner.splitlines())
    + footer
)
print(path)
