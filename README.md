# hosts-to-prometheus
Tool to discover Prometheus exporters based on records in system `hosts` file

```text
usage: hosts-to-prometheus.py [-h] [--exporter_port EXPORTER_PORT] [--exporter_path EXPORTER_PATH] [--prometheus_config PROMETHEUS_CONFIG] [--prometheus_job PROMETHEUS_JOB]
                              [--prometheus_host PROMETHEUS_HOST] [--prometheus_port PROMETHEUS_PORT] [--restart]

This tool scans the network for the targets contained in the system hosts file which are also available for Prometheus metric scraping. Then the tool adds them into Prometheus
configuration file and updates the Prometheus server.

optional arguments:
  -h, --help            show this help message and exit
  --exporter_port EXPORTER_PORT
                        (Optional) Node Exporter listen port(s), single or range (via hyphen '-')
  --exporter_path EXPORTER_PATH
                        (Optional) Node Exporter metrics path
  --prometheus_config PROMETHEUS_CONFIG
                        (Optional) Prometheus Dashboard Server local configuration file
  --prometheus_job PROMETHEUS_JOB
                        (Optional) Target Prometheus configuration job entry name
  --prometheus_host PROMETHEUS_HOST
                        (Optional) Prometheus Dashboard Server host
  --prometheus_port PROMETHEUS_PORT
                        (Optional) Prometheus Dashboard Server port
  --restart             (Optional) Restart Prometheus server
```

## Setup

```shell script
sudo apt-get update -y

sudo apt-get install \
    --yes \
    nmap

sudo pip install -r \
    "https://raw.githubusercontent.com/ivasilyev/hosts-to-prometheus/main/requirements.txt"

cd "/opt"

export TOOL_DIR="/opt/hosts-to-prometheus/"

sudo mkdir -p -m 755 "${TOOL_DIR}"

cd "${TOOL_DIR}" && \
sudo curl -fsSLO \
    "https://raw.githubusercontent.com/ivasilyev/hosts-to-prometheus/main/hosts-to-prometheus.py"

sudo chmod -R a+rx "${TOOL_DIR}"
```

## Example run

```shell script
sudo python3 "/opt/hosts-to-prometheus/hosts-to-prometheus.py" \
    --logging 5 \
    --exporter_port 9100 \
    --prometheus_config "/etc/prometheus/prometheus.yml" \
    --prometheus_job "linux_servers" \
    --prometheus_port 9090

echo Check updated configuration
cat /etc/prometheus/prometheus.yml
```

## Create system service

```shell script
echo Export variables
export TOOL_NAME="hosts-to-prometheus"
export TOOL_SERVER_PORT=9090
export TOOL_EXPORTER_PORT=9100

export UN="root"
export TOOL_DIR="/opt/${TOOL_NAME}/"
export TOOL_OUT_FILE="/etc/prometheus/prometheus.yml"
export TOOL_BIN="${TOOL_DIR}hosts-to-prometheus.py"
export TOOL_SCRIPT="${TOOL_DIR}${TOOL_NAME}.sh"
export TOOL_SERVICE="/etc/systemd/system/${TOOL_NAME}.service"


echo Create ${TOOL_NAME} routine script
cat <<EOF | sudo tee "${TOOL_SCRIPT}"
#!/usr/bin/env bash
# bash "${TOOL_SCRIPT}"
export TOOL_BIN="${TOOL_BIN}"
export TOOL_OUT_FILE="${TOOL_OUT_FILE}"

while true
    do

    sudo python3 "\${TOOL_BIN}" \
        --logging 5 \
        --exporter_port 9100 \
        --prometheus_config "\${TOOL_OUT_FILE}" \
        --prometheus_job "my_servers" \
        --prometheus_port 9090

    sudo chmod a+r "\${TOOL_OUT_FILE}"

    sleep 1h    

    done
EOF

sudo chmod a+x "${TOOL_SCRIPT}"
# nano "${TOOL_SCRIPT}"



echo Create ${TOOL_NAME} system service
cat <<EOF | sudo tee "${TOOL_SERVICE}"
[Unit]
Description=${TOOL_NAME}
Documentation=https://google.com
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=${UN}
ExecReload=/usr/bin/env kill -s SIGTERM \$MAINPID
ExecStart=/usr/bin/env bash "${TOOL_SCRIPT}"
SyslogIdentifier=${TOOL_NAME}
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# nano "${TOOL_SERVICE}"



echo Activate ${TOOL_NAME} service
sudo systemctl daemon-reload
sudo systemctl enable "${TOOL_NAME}.service"
sudo systemctl restart "${TOOL_NAME}.service"
sleep 3
sudo systemctl status "${TOOL_NAME}.service"
```



## (Not recommended) Create and add `cron` rules

```shell script
while IFS= read -r LINE
    do 
    echo "
        0 15 * * * \"/usr/bin/python3\" \"${TOOL_BIN}\" --logging 5 --exporter_port 9100 --prometheus_config \"${TOOL_OUT_FILE}\" --prometheus_job my_servers --prometheus_port 9090 > /dev/null 2>&1
    " \
    | sed 's/^[ \t]*//;s/[ \t]*$//';
    done \
<<< "${NICS}"

sudo crontab -e
```
```shell script
sudo crontab -l
```
