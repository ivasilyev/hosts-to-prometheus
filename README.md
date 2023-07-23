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

cd
```

## Example run

```shell script
sudo python3 /opt/hosts-to-prometheus/hosts-to-prometheus.py \
    --exporter_port 9100 \
    --prometheus_config "/etc/prometheus/prometheus.yml" \
    --prometheus_job "linux_servers" \
    --prometheus_port 9090
```
