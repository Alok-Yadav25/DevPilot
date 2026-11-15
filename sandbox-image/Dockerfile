# Build this trusted image before accepting untrusted repositories.
FROM python:3.11-slim
RUN pip install --no-cache-dir 'pytest==8.4.2' 'setuptools==80.9.0' 'wheel==0.45.1' \
    && groupadd --gid 10001 sandbox \
    && useradd --uid 10001 --gid 10001 --no-create-home sandbox
COPY wheels/ /opt/wheels/
COPY runner.py /opt/devpilot/runner.py
USER 10001:10001
WORKDIR /work
ENTRYPOINT []
CMD ["python", "-I", "/opt/devpilot/runner.py"]
