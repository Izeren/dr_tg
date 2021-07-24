FROM python:3.8-alpine
LABEL maintainer="Alex <izeren.ml@gmail.com>" \
      description="Dozor aiogram Telegram bot"

COPY requirements.txt /requirements.txt
RUN apk add --update alpine-sdk chromium chromium-chromedriver && \
    python -m pip install -r /requirements.txt

WORKDIR /app
ENV PYTHONPATH "/app"
COPY ./pewpewbot /app/pewpewbot
COPY ./test_game_states /app/test_game_states

CMD ["python", "pewpewbot/bot.py"]