FROM jenkins/jenkins:lts

USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates \
        python3 python3-pip python3-venv python-is-python3 \
        make git \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m pip install --break-system-packages --no-cache-dir pipenv \
    && git config --system --add safe.directory '*'

ARG DOCKER_VERSION=24.0.7
RUN ARCH="$(uname -m)" \
    && curl -fsSL "https://download.docker.com/linux/static/stable/${ARCH}/docker-${DOCKER_VERSION}.tgz" \
       | tar zxf - --strip-components=1 -C /usr/bin/ docker/docker

ARG COMPOSE_VERSION=v2.26.1
RUN ARCH="$(uname -m)" \
    && mkdir -p /usr/libexec/docker/cli-plugins \
    && curl -fSL "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-linux-${ARCH}" \
       -o /usr/libexec/docker/cli-plugins/docker-compose \
    && chmod +x /usr/libexec/docker/cli-plugins/docker-compose \
    && ln -s /usr/libexec/docker/cli-plugins/docker-compose /usr/bin/docker-compose

COPY plugins.txt /usr/share/jenkins/ref/plugins.txt
RUN jenkins-plugin-cli --plugin-file /usr/share/jenkins/ref/plugins.txt

COPY init.groovy.d/ /usr/share/jenkins/ref/init.groovy.d/

ENV JAVA_OPTS="-Djenkins.install.runSetupWizard=false"
ENV CASC_JENKINS_CONFIG=/var/jenkins_home/casc.yaml

USER jenkins
