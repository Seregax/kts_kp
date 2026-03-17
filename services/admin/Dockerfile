FROM python:3.12-slim
WORKDIR /srv
COPY shared/ /shared/
RUN pip install --no-cache-dir -e /shared
COPY services/admin/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/admin/ .
CMD ["python", "main.py"]
