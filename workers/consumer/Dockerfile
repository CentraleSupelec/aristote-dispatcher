FROM python:3.12.4-alpine


RUN pip install --upgrade pip

RUN adduser --system consumer
USER consumer
WORKDIR /app

COPY --chown=consumer:consumer requirements.txt requirements.txt
RUN pip install -r requirements.txt

ENV PATH="/home/consumer/.local/bin:${PATH}"

COPY --chown=consumer:consumer . /app/consumer


CMD ["python3", "-m", "consumer.main"]
