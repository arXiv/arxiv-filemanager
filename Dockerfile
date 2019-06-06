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

ENV APPLICATION_ROOT "/"

ENV LOGLEVEL 10

ENTRYPOINT ["pipenv", "run"]
CMD ["uwsgi", "--ini", "/opt/arxiv/uwsgi.ini"]
