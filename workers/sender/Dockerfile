FROM python:3.12.4-alpine


RUN pip install --upgrade pip

RUN adduser --system sender
USER sender
WORKDIR /app

COPY --chown=sender:sender requirements.txt requirements.txt
RUN pip install -r requirements.txt

ENV PATH="/home/sender/.local/bin:${PATH}"

COPY --chown=sender:sender . .


EXPOSE 8080

CMD ["fastapi", "run", "--port", "8080", "main.py"]
