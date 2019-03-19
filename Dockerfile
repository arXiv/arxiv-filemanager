# arXiv file manager

FROM arxiv/base:latest

WORKDIR /opt/arxiv/

RUN yum install -y which mariadb-devel
ADD Pipfile Pipfile.lock /opt/arxiv/
RUN pip install -U pip pipenv
ENV LC_ALL en_US.utf-8
ENV LANG en_US.utf-8
RUN pipenv install

ENV PATH "/opt/arxiv:${PATH}"

ADD wsgi.py uwsgi.ini bootstrap.py /opt/arxiv/
ADD filemanager/ /opt/arxiv/filemanager/

# TODO: remove this when possible.
RUN touch upload.log
RUN chmod 777 upload.log

EXPOSE 8000

ENV LOGLEVEL 10

ENTRYPOINT ["pipenv", "run"]
CMD ["uwsgi", "--http-socket", ":8000", \
     "-M", \
     "-t 3000", \
     "--manage-script-name", \
     "--processes", "1", \
     "--threads", "1", \
     "--async", "0", \
     "--queue", "0", \
     "--wsgi-disable-file-wrapper", \
     "--mount", "/=wsgi.py", \
     "--logformat", "%(addr) %(addr) - %(user_id)|%(session_id) [%(rtime)] [%(uagent)] \"%(method) %(uri) %(proto)\" %(status) %(size) %(micros) %(ttfb)"]
