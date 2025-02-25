FROM mikenye/split2flac

RUN rm -f /etc/apt/sources.list.d/*

RUN echo "deb http://archive.ubuntu.com/ubuntu xenial main restricted universe multiverse" > /etc/apt/sources.list && \
    echo "deb http://archive.ubuntu.com/ubuntu xenial-updates main restricted universe multiverse" >> /etc/apt/sources.list && \
    echo "deb http://archive.ubuntu.com/ubuntu xenial-security main restricted universe multiverse" >> /etc/apt/sources.list

RUN apt update
RUN apt install -y build-essential zlib1g-dev libncurses5-dev libgdbm-dev libnss3-dev libssl-dev libsqlite3-dev libreadline-dev libffi-dev curl libbz2-dev liblzma-dev git wget

RUN wget https://www.python.org/ftp/python/3.7.4/Python-3.7.4.tgz
RUN tar xzf Python-3.7.4.tgz && cd Python-3.7.4 && ./configure && make -j8 && make install

RUN curl https://bootstrap.pypa.io/pip/3.7/get-pip.py | python3


# for ffmpeg
# RUN add-apt-repository ppa:mc3man/trusty-media
RUN apt-get install -y ffmpeg

ADD split2flac /usr/local/bin/split2flac
RUN chmod +x /usr/local/bin/split2flac

WORKDIR /app
ADD requirements.txt /app
RUN python3 -m pip install -r requirements.txt

ADD split.py /app

WORKDIR /workdir

ENTRYPOINT [""]
CMD ["python3", "/app/split.py", "."]
