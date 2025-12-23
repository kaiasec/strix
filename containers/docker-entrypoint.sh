#!/bin/bash
set -e

if [ -z "$CAIDO_PORT" ]; then
    echo "Error: CAIDO_PORT must be set."
    exit 1
fi


echo "Starting noVNC services..."

# 创建必要的 X11 目录
mkdir -p /tmp/.X11-unix
chmod 1777 /tmp/.X11-unix

# 设置显示变量
export DISPLAY=:99

# 1. 启动虚拟显示服务器
Xvfb ${DISPLAY} -screen 0 1920x1080x24 -ac +extension RANDR > /dev/null 2>&1 &
sleep 2

# 2. 启动窗口管理器
fluxbox > /dev/null 2>&1 &

# 3. 启动 VNC 服务器
x11vnc -display ${DISPLAY} -forever -shared -nopw -listen 0.0.0.0 > /dev/null 2>&1 &

# 4. 启动 noVNC web 代理
/opt/noVNC/utils/novnc_proxy --vnc localhost:5900 --listen 6080 > /dev/null 2>&1 &

# 打印 noVNC 访问信息
if [ -n "$NOVNC_PORT" ]; then
    echo "✅ noVNC web interface available at: http://<host>:$NOVNC_PORT"
else
    echo "⚠️  NOVNC_PORT environment variable not set, using default port 6080"
    echo "✅ noVNC web interface available at: http://<host>:6080"
fi



# caido-cli --listen 127.0.0.1:${CAIDO_PORT} \
#           --allow-guests \
#           --no-logging \
#           --no-open \
#           --import-ca-cert /app/certs/ca.p12 \
#           --import-ca-cert-pass "" > /dev/null 2>&1 &
# 写到/tmp目录并开启调试模式
caido-cli \
  --listen 127.0.0.1:${CAIDO_PORT} \
  --allow-guests \
  --no-open \
  --debug \
  --import-ca-cert /app/certs/ca.p12 \
  --import-ca-cert-pass "" \
  --data-path /tmp/caido_data \
  >> /tmp/caido.log 2>&1 &

echo "Waiting for Caido API to be ready..."
for i in {1..30}; do
  if curl -s -o /dev/null http://localhost:${CAIDO_PORT}/graphql; then
    echo "Caido API is ready."
    break
  fi
  sleep 1
done

sleep 2

echo "Fetching API token..."
TOKEN=$(curl -s -X POST \
  -H "Content-Type: application/json" \
  -d '{"query":"mutation LoginAsGuest { loginAsGuest { token { accessToken } } }"}' \
  http://localhost:${CAIDO_PORT}/graphql | jq -r '.data.loginAsGuest.token.accessToken')

if [ -z "$TOKEN" ] || [ "$TOKEN" == "null" ]; then
  echo "Failed to get API token from Caido."
  curl -s -X POST -H "Content-Type: application/json" -d '{"query":"mutation { loginAsGuest { token { accessToken } } }"}' http://localhost:${CAIDO_PORT}/graphql
  exit 1
fi

export CAIDO_API_TOKEN=$TOKEN
echo "Caido API token has been set."

echo "Creating a new Caido project..."
CREATE_PROJECT_RESPONSE=$(curl -s -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query":"mutation CreateProject { createProject(input: {name: \"sandbox\", temporary: true}) { project { id } } }"}' \
  http://localhost:${CAIDO_PORT}/graphql)

PROJECT_ID=$(echo $CREATE_PROJECT_RESPONSE | jq -r '.data.createProject.project.id')

if [ -z "$PROJECT_ID" ] || [ "$PROJECT_ID" == "null" ]; then
  echo "Failed to create Caido project."
  echo "Response: $CREATE_PROJECT_RESPONSE"
  exit 1
fi

echo "Caido project created with ID: $PROJECT_ID"

echo "Selecting Caido project..."
SELECT_RESPONSE=$(curl -s -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query":"mutation SelectProject { selectProject(id: \"'$PROJECT_ID'\") { currentProject { project { id } } } }"}' \
  http://localhost:${CAIDO_PORT}/graphql)

SELECTED_ID=$(echo $SELECT_RESPONSE | jq -r '.data.selectProject.currentProject.project.id')

if [ "$SELECTED_ID" != "$PROJECT_ID" ]; then
    echo "Failed to select Caido project."
    echo "Response: $SELECT_RESPONSE"
    exit 1
fi

echo "✅ Caido project selected successfully."

echo "Configuring system-wide proxy settings..."

cat << EOF | sudo tee /etc/profile.d/proxy.sh
export http_proxy=http://127.0.0.1:${CAIDO_PORT}
export https_proxy=http://127.0.0.1:${CAIDO_PORT}
export HTTP_PROXY=http://127.0.0.1:${CAIDO_PORT}
export HTTPS_PROXY=http://127.0.0.1:${CAIDO_PORT}
export ALL_PROXY=http://127.0.0.1:${CAIDO_PORT}
export REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
export SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
export CAIDO_API_TOKEN=${TOKEN}
EOF

cat << EOF | sudo tee /etc/environment
http_proxy=http://127.0.0.1:${CAIDO_PORT}
https_proxy=http://127.0.0.1:${CAIDO_PORT}
HTTP_PROXY=http://127.0.0.1:${CAIDO_PORT}
HTTPS_PROXY=http://127.0.0.1:${CAIDO_PORT}
ALL_PROXY=http://127.0.0.1:${CAIDO_PORT}
CAIDO_API_TOKEN=${TOKEN}
EOF

cat << EOF | sudo tee /etc/wgetrc
use_proxy=yes
http_proxy=http://127.0.0.1:${CAIDO_PORT}
https_proxy=http://127.0.0.1:${CAIDO_PORT}
EOF

echo "source /etc/profile.d/proxy.sh" >> ~/.bashrc
echo "source /etc/profile.d/proxy.sh" >> ~/.zshrc

source /etc/profile.d/proxy.sh

echo "✅ System-wide proxy configuration complete"

echo "Adding CA to browser trust store..."
sudo -u pentester mkdir -p /home/pentester/.pki/nssdb
sudo -u pentester certutil -N -d sql:/home/pentester/.pki/nssdb --empty-password
sudo -u pentester certutil -A -n "Testing Root CA" -t "C,," -i /app/certs/ca.crt -d sql:/home/pentester/.pki/nssdb
#sudo -u pentester certutil -A -n "Testing Root CA" -t "TC,," -i /app/certs/ca.crt -d sql:/home/pentester/.pki/nssdb
echo "✅ CA added to browser trust store"

echo "Container initialization complete - agents will start their own tool servers as needed"
echo "✅ Shared container ready for multi-agent use"



# echo "Starting Chrome in headless mode..."
# /opt/chrome_offline/opt/google/chrome/chrome \
#     --headless=new \
#     --no-sandbox \
#     --disable-dev-shm-usage \
#     --remote-debugging-port=9222 \
#     --remote-allow-origins=* \
#     --disable-gpu \
#     --window-size=1920,1080 \
#     --no-first-run \
#     --mute-audio \
#     > /dev/null 2>&1 &
echo "Starting Chrome with GUI and remote debugging..."

/opt/chrome_offline/opt/google/chrome/chrome \
    --no-sandbox \
    --disable-dev-shm-usage \
    --remote-debugging-port=9222 \
    --remote-allow-origins=* \
    --disable-gpu \
    --window-size=1920,1080 \
    --start-maximized \
    --no-first-run \
    --user-data-dir=/tmp/chrome-data \
    --proxy-server="http://127.0.0.1:${CAIDO_PORT}" \
    > /dev/null 2>&1 &
  

cd /workspace

exec "$@"
