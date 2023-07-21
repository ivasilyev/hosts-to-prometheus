# hosts-to-prometheus
Tool to discover Prometheus exporters based on records in system `hosts` file

```text
usage: hosts-to-prometheus.py [-h] [--exporter_port EXPORTER_PORT]
                              [--exporter_path EXPORTER_PATH]
                              [--prometheus_config PROMETHEUS_CONFIG]
                              [--prometheus_job PROMETHEUS_JOB]
                              [--prometheus_host PROMETHEUS_HOST]
                              [--prometheus_port PROMETHEUS_PORT]

This tool scans the network for the targets contained in the system hosts file
which are also available for Prometheus metric scraping. Then the tool adds
them into Prometheus configuration file and updates the Prometheus server.

optional arguments:
  -h, --help            show this help message and exit
  --exporter_port EXPORTER_PORT
                        Node Exporter listen port(s), single or range (with
                        hyphen '-')
  --exporter_path EXPORTER_PATH
                        Node Exporter metrics path
  --prometheus_config PROMETHEUS_CONFIG
                        Prometheus Dashboard Server local configuration file
  --prometheus_job PROMETHEUS_JOB
                        Target Prometheus configuration job entry name
  --prometheus_host PROMETHEUS_HOST
                        Prometheus Dashboard Server host
  --prometheus_port PROMETHEUS_PORT
                        Prometheus Dashboard Server port
```

## Setup

```shell script
sudo apt-get update -y

sudo apt-get install \
    --yes \
    nmap

cd "/opt"

export TOOL_DIR="/opt/hosts-to-prometheus/"

sudo mkdir -p -m 755 "${TOOL_DIR}"

cd "${TOOL_DIR}" && \
sudo curl -fsSLO \
    "https://raw.githubusercontent.com/ivasilyev/hosts-to-prometheus/main/hosts-to-prometheus.py"
sudo pip install -r \
    "https://raw.githubusercontent.com/ivasilyev/hosts-to-prometheus/main/requirements.txt"

sudo chmod a+rx "${TOOL_DIR}"

cd
```

## Example run

```shell script
python3 /opt/hosts-to-prometheus/hosts-to-prometheus.py \
    --exporter_port 9100 \
    --prometheus_config "/etc/prometheus/prometheus.yml" \
    --prometheus_job "linux_servers" \
    --prometheus_port 9090
```
