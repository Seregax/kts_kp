FROM python:3.12-slim
WORKDIR /srv
COPY shared/ /shared/
RUN pip install --no-cache-dir -e /shared
COPY services/poller/ .
RUN pip install --no-cache-dir -r requirements.txt
CMD ["python", "main.py"]
