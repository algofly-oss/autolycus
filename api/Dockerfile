FROM python:3.10-buster
WORKDIR /app
COPY . .

# Install dependencies
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update -y \
    && apt-get install python3-libtorrent ffmpeg -y \
    && apt-get install gcc libpq-dev rsync -y

# Install python packages
ENV PYTHONPATH="/usr/lib/python3/dist-packages":$PYTHONPATH
RUN pip install -r /app/requirements.txt --no-cache-dir

CMD chmod +x /app/entrypoint.sh && /app/entrypoint.sh