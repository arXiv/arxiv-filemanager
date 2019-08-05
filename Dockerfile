# arXiv file manager

ARG BASE_VERSION=ARXIVNG-2462

FROM arxiv/base:${BASE_VERSION}

WORKDIR /opt/arxiv

EXPOSE 8000

ENV APPLICATION_ROOT="/" \
    LOGLEVEL=10 \
    PATH="/opt/arxiv:${PATH}"

COPY Pipfile Pipfile.lock /opt/arxiv/
RUN pipenv install && rm -rf ~/.cache/pip

COPY app.py wsgi.py uwsgi.ini bootstrap.py /opt/arxiv/
COPY filemanager/ /opt/arxiv/filemanager/

ENTRYPOINT ["pipenv", "run"]
CMD ["uwsgi", "--ini", "/opt/arxiv/uwsgi.ini"]
