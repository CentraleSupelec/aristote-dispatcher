FROM python:3.12.3-alpine

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["fastapi", "run", "--port", "8080", "sender.py"]
