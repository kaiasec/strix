FROM kalilinux/kali-rolling:latest

LABEL description="AI Agent Penetration Testing Environment with Comprehensive Automated Tools"

# 1改动,设置清华源
RUN echo "deb http://mirrors.tuna.tsinghua.edu.cn/kali kali-rolling main non-free contrib" > /etc/apt/sources.list

RUN apt-get update && \
    apt-get install -y kali-archive-keyring sudo && \
    apt-get update && \
    apt-get upgrade -y

RUN useradd -m -s /bin/bash pentester && \
    usermod -aG sudo pentester && \
    echo "pentester ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

RUN mkdir -p /home/pentester/configs \
             /home/pentester/wordlists \
             /home/pentester/output \
             /home/pentester/scripts \
             /home/pentester/tools \
             /app/runtime \
             /app/tools \
             /app/certs && \
    chown -R pentester:pentester /app/certs /home/pentester/tools

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    wget curl git vim nano unzip tar \
    apt-transport-https ca-certificates gnupg lsb-release \
    build-essential software-properties-common \
    gcc libc6-dev pkg-config libpcap-dev libssl-dev \
    python3 python3-pip python3-dev python3-venv python3-setuptools \
    golang-go \
    net-tools dnsutils whois \
    jq parallel ripgrep grep \
    less man-db procps htop \
    iproute2 iputils-ping netcat-traditional \
    nmap ncat ndiff \
    sqlmap nuclei subfinder naabu ffuf \
    nodejs npm pipx \
    libcap2-bin \
    gdb \
    tmux \
    libnss3 libnspr4 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libatspi2.0-0 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libxkbcommon0 libpango-1.0-0 libcairo2 libasound2t64 \
    fonts-unifont fonts-noto-color-emoji fonts-freefont-ttf fonts-dejavu-core ttf-bitstream-vera \
    libnss3-tools

RUN setcap cap_net_raw,cap_net_admin,cap_net_bind_service+eip $(which nmap)

USER pentester
RUN openssl ecparam -name prime256v1 -genkey -noout -out /app/certs/ca.key && \
    openssl req -x509 -new -key /app/certs/ca.key \
    -out /app/certs/ca.crt \
    -days 3650 \
    -subj "/C=US/ST=CA/O=Security Testing/CN=Testing Root CA" \
    -addext "basicConstraints=critical,CA:TRUE" \
    -addext "keyUsage=critical,digitalSignature,keyEncipherment,keyCertSign" && \
    openssl pkcs12 -export \
    -out /app/certs/ca.p12 \
    -inkey /app/certs/ca.key \
    -in /app/certs/ca.crt \
    -passout pass:"" \
    -name "Testing Root CA" && \
    chmod 644 /app/certs/ca.crt && \
    chmod 600 /app/certs/ca.key && \
    chmod 600 /app/certs/ca.p12

USER root
RUN cp /app/certs/ca.crt /usr/local/share/ca-certificates/ca.crt && \
    update-ca-certificates

RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn

RUN curl -sSL https://install.python-poetry.org | POETRY_HOME=/opt/poetry python3 - && \
    ln -s /opt/poetry/bin/poetry /usr/local/bin/poetry && \
    chmod +x /usr/local/bin/poetry && \
    python3 -m venv /app/venv && \
    chown -R pentester:pentester /app/venv /opt/poetry

USER pentester
WORKDIR /tmp

# 改动3,加速go代理
ENV GOPROXY=https://mirrors.aliyun.com/goproxy/,https://goproxy.cn,direct

RUN go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest && \
    go install -v github.com/projectdiscovery/katana/cmd/katana@latest && \
    go install -v github.com/projectdiscovery/cvemap/cmd/vulnx@latest && \
    go install -v github.com/jaeles-project/gospider@latest && \
    go install -v github.com/projectdiscovery/interactsh/cmd/interactsh-client@latest

RUN nuclei -update-templates

# 改动4,加速pipx
ENV PIPX_DEFAULT_PYTHON=python3
ENV PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ENV PIP_EXTRA_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

RUN pipx install arjun && \
    pipx install dirsearch && \
    pipx inject dirsearch setuptools && \
    pipx install wafw00f

ENV NPM_CONFIG_PREFIX=/home/pentester/.npm-global
RUN mkdir -p /home/pentester/.npm-global

# 改动5,加速npm
ENV NPM_CONFIG_REGISTRY=https://registry.npmmirror.com
ENV NPM_CONFIG_DISTURL=https://npmmirror.com/dist
ENV NPM_CONFIG_ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/
ENV NPM_CONFIG_SASS_BINARY_SITE=https://npmmirror.com/mirrors/node-sass
ENV NPM_CONFIG_PUPPETEER_DOWNLOAD_HOST=https://npmmirror.com/mirrors

RUN npm install -g retire@latest && \
    npm install -g eslint@latest && \
    npm install -g js-beautify@latest

WORKDIR /home/pentester/tools
RUN git clone https://github.com/aravind0x7/JS-Snooper.git && \
    chmod +x JS-Snooper/js_snooper.sh && \
    git clone https://github.com/xchopath/jsniper.sh.git && \
    chmod +x jsniper.sh/jsniper.sh && \
    git clone https://github.com/ticarpi/jwt_tool.git && \
    chmod +x jwt_tool/jwt_tool.py

USER root

RUN curl -sSfL https://raw.githubusercontent.com/trufflesecurity/trufflehog/main/scripts/install.sh | sh -s -- -b /usr/local/bin

RUN apt-get update && apt-get install -y zaproxy

RUN curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | bash -x -s -- -b /usr/local/bin

RUN apt-get install -y wapiti

USER pentester

RUN pipx install semgrep && \
    pipx install bandit

RUN npm install -g jshint

USER root

RUN apt-get autoremove -y && \
    apt-get autoclean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

ENV PATH="/home/pentester/go/bin:/home/pentester/.local/bin:/home/pentester/.npm-global/bin:/app/venv/bin:$PATH"
ENV VIRTUAL_ENV="/app/venv"
ENV POETRY_HOME="/opt/poetry"

WORKDIR /app

RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "x86_64" ]; then \
        CAIDO_ARCH="x86_64"; \
    elif [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then \
        CAIDO_ARCH="aarch64"; \
    else \
        echo "Unsupported architecture: $ARCH" && exit 1; \
    fi && \
    wget -O caido-cli.tar.gz https://caido.download/releases/v0.48.0/caido-cli-v0.48.0-linux-${CAIDO_ARCH}.tar.gz && \
    tar -xzf caido-cli.tar.gz && \
    chmod +x caido-cli && \
    rm caido-cli.tar.gz && \
    mv caido-cli /usr/local/bin/

# Chrome 离线安装（替代 playwright install chromium）
RUN mkdir -p /opt/chrome_offline && \
    wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    dpkg -x google-chrome-stable_current_amd64.deb /opt/chrome_offline/ && \
    chown -R pentester:pentester /opt/chrome_offline && \
    chmod 755 /opt/chrome_offline/opt/google/chrome/chrome && \
    rm google-chrome-stable_current_amd64.deb

ENV STRIX_SANDBOX_MODE=true
ENV PYTHONPATH=/app
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

RUN mkdir -p /workspace && chown -R pentester:pentester /workspace /app

COPY pyproject.toml poetry.lock ./

USER pentester

RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn && \
    poetry config repositories.tsinghua https://pypi.tuna.tsinghua.edu.cn/simple/

RUN poetry install --no-root --without dev --extras sandbox
#RUN poetry run playwright install chromium

RUN poetry run python -c "import browser_use; print('browser_use已导入')"

RUN /app/venv/bin/pip install -r /home/pentester/tools/jwt_tool/requirements.txt && \
    ln -s /home/pentester/tools/jwt_tool/jwt_tool.py /home/pentester/.local/bin/jwt_tool

RUN echo "# Sandbox Environment" > README.md

COPY strix/__init__.py strix/
COPY strix/runtime/tool_server.py strix/runtime/__init__.py strix/runtime/runtime.py /app/strix/runtime/

COPY strix/tools/__init__.py strix/tools/registry.py strix/tools/executor.py strix/tools/argument_parser.py /app/strix/tools/

COPY strix/tools/browser_use/ /app/strix/tools/browser_use/
# COPY strix/tools/browser/ /app/strix/tools/browser/
COPY strix/tools/file_edit/ /app/strix/tools/file_edit/
COPY strix/tools/notes/ /app/strix/tools/notes/
COPY strix/tools/python/ /app/strix/tools/python/
COPY strix/tools/terminal/ /app/strix/tools/terminal/
COPY strix/tools/proxy/ /app/strix/tools/proxy/

RUN echo 'export PATH="/home/pentester/go/bin:/home/pentester/.local/bin:/home/pentester/.npm-global/bin:$PATH"' >> /home/pentester/.bashrc && \
    echo 'export PATH="/home/pentester/go/bin:/home/pentester/.local/bin:/home/pentester/.npm-global/bin:$PATH"' >> /home/pentester/.profile

USER root
COPY containers/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

#增加noVnc

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    # X11 显示相关
    xvfb \
    x11vnc \
    x11-xkb-utils \
    xfonts-base \
    xfonts-100dpi \
    xfonts-75dpi \
    xfonts-cyrillic \
    # 窗口管理器（可选，轻量级）
    fluxbox \
    # 或者更轻量的 openbox
    # openbox \
    # 字体补充
    fonts-liberation \
    # Python 依赖
    python3-websockify \
    && rm -rf /var/lib/apt/lists/*

# 下载 noVNC（使用离线或在线方式）
RUN git clone --depth 1 https://github.com/novnc/noVNC.git /opt/noVNC \
    && git clone --depth 1 https://github.com/novnc/websockify /opt/noVNC/utils/websockify \
    && cd /opt/noVNC && ln -sv vnc.html index.html \
    && rm -rf /opt/noVNC/.git /opt/noVNC/utils/websockify/.git

# 或者使用离线下载（如果网络受限）
# COPY noVNC.tar.gz /tmp/
# RUN tar -xzf /tmp/noVNC.tar.gz -C /opt/ \
#     && mv /opt/noVNC-* /opt/noVNC \
#     && ln -sv /opt/noVNC/vnc.html /opt/noVNC/index.html


USER pentester
WORKDIR /workspace

ENTRYPOINT ["docker-entrypoint.sh"]
