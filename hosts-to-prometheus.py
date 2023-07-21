#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import yaml
import logging
from shutil import copy2
import multiprocessing as mp
from requests import head, post
from argparse import ArgumentParser
from subprocess import getoutput as go


HOSTS_FILE = "/etc/hosts"


def split_lines(s: str):
    return [i.strip() for i in re.split("[\r\n]+", s)]


def split_columns(s: str, is_space_delimiter: bool = False):
    r = "[\t]+"
    if is_space_delimiter:
        r = "[\t ]+"
    return [i.strip() for i in re.split(r, s)]


def split_table(s: str, is_space_delimiter: bool = False):
    o = list()
    for line in split_lines(s):
        row = [re.sub("^[^#]+(#.*)", "", i) for i in split_columns(line, is_space_delimiter)]
        o.append(row)
    return o


def load_string(file: str):
    logging.debug(f"Read file: '{file}'")
    with open(file, mode="r", encoding="utf-8") as f:
        o = f.read()
        f.close()
    return o


def dump_string(s: str, file: str):
    logging.debug(f"Write file: '{file}'")
    with open(file, mode="w", encoding="utf-8") as f:
        f.write(s)
        f.close()


def load_yaml(file: str):
    d = yaml.load(load_string(file), Loader=yaml.SafeLoader)
    return d


class IndentDumper(yaml.Dumper):
    def increase_indent(self, flow=False, indentless=False):
        return super(IndentDumper, self).increase_indent(flow, False)


def dump_yaml(d: dict, file: str):
    s = yaml.dump(d, Dumper=IndentDumper)
    dump_string(s, file)


def is_url_ok(
    url: str,
    attempts: int = os.getenv("WEB_ATTEMPT_NUMBER", 5),
    timeout: int = os.getenv("WEB_ATTEMPT_TIMEOUT", 5)
):
    for attempt in range(attempts):
        try:
            response = head(url, timeout=timeout)
            response.close()
            return response.status_code == 200
        except Exception as e:
            pass
    return False


def nmap(host: str, ports: str):
    o = go(f"sudo nmap -p {ports} -sT -oG - {host} | grep -oP '(?<= )[0-9]+(?=/open/tcp)' 2>/dev/null")
    return sorted(split_lines(o))


def check_ports(host: str, ports: list):
    template = "{scheme}://{host}:{port}{metrics_path}"
    urls = {
        port: template.format(
            scheme=os.getenv("PROMETHEUS_DASHBOARD_SCHEME", "http"),
            host=host,
            port=port,
            metrics_path=input_node_exporter_metrics_path,
        ) for port in ports
    }
    good_ports = [k for k, v in urls.items() if is_url_ok(v)]
    if len(good_ports) > 0:
        return good_ports[0]
    return 0


def check_host(host: str, ports: str):
    open_ports = nmap(host, ports)
    port = check_ports(host, open_ports)
    return f"{host}:{port}"


def is_ip_loopback(s: str):
    return any(s.startswith(i) for i in ["127.", "::1", "fe00:", "ff00:", "ff02:"])


def is_ip_valid(s: str):
    return (
        len(s) > 0
        and not(is_ip_loopback(s))
        and len(re.findall("[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}", s)) > 0
    )


def is_hostname_valid(s: str):
    return len(re.findall("[^A-Za-z0-9\.\-_]+", s[1])) == 0


def parse_known_hosts(file: str):
    hosts_table = split_table(load_string(file))
    return sorted([
        i[-1] for i in hosts_table
        if len(i) > 1
        and is_ip_valid(i[0])
        and is_hostname_valid(i[1])
    ])


def is_host_pingable(host: str):
    o = go(f"ping -c 5 {host} | grep -oP '(?<= )[0-9]+(?=% packet loss)' 2>/dev/null")
    return dict(host=host, ready=o.isnumeric() and int(o) < int(os.getenv("PING_PACKET_LOSS_PERCENTAGE", 50)))


def mp_queue(func, queue: list):
    with mp.Pool(min(len(queue), mp.cpu_count())) as p:
        out = p.map(func, queue)
        p.close()
        p.join()
    return out


def wrap(kwargs: dict):
    return kwargs["func"](**kwargs["kwargs"])


def backup_file(file: str, force: bool = False):
    backup = f"{file}.bak"
    if not os.path.exists(backup) or force:
        copy2(file, file)
        logging.info(f"Created backup: '{file}'")


def reload_prometheus_soft(
        host,
        port: int = 80,
        scheme: str = os.getenv("PROMETHEUS_DASHBOARD_SCHEME", "http"),
        path: str = os.getenv("PROMETHEUS_DASHBOARD_RELOAD_PATH", "/-/reload")
):
    response = post(f"{scheme}://{host}:{port}{path}", timeout=os.getenv("WEB_ATTEMPT_TIMEOUT", 5))
    response.close()
    if response.status_code != 200:
        pass


def reload_prometheus_hard(service_name: str = os.getenv("PROMETHEUS_SERVICE_NAME", "prometheus.service")):
    return go(f"systemctl restart {service_name}")


def reload_prometheus(hard: bool = False):
    if hard:
        reload_prometheus_soft(input_prometheus_host, input_prometheus_port)
    else:
        reload_prometheus_hard()


def parse_args():
    p = ArgumentParser(
        description="This tool scans the network for the targets contained in the system hosts file which are also "
                    "available for Prometheus metric scraping. Then the tool adds them into Prometheus configuration "
                    "file and updates the Prometheus server. ",
        epilog=""
    )
    p.add_argument("--exporter_port", help="Node Exporter listen port(s), single or range (with hyphen '-')",
                   default="9100")
    p.add_argument("--exporter_path", help="Node Exporter metrics path", default="/metrics")
    p.add_argument("--prometheus_config", help="Prometheus Dashboard Server local configuration file",
                   default="/etc/prometheus/prometheus.yml")
    p.add_argument("--prometheus_job", help="Target Prometheus configuration job entry name", default="discovered")
    p.add_argument("--prometheus_host", help="Prometheus Dashboard Server host", default="127.0.0.1")
    p.add_argument("--prometheus_port", help="Prometheus Dashboard Server port", default=9090)
    ns = p.parse_args()
    return ns


if __name__ == '__main__':
    nameSpace = parse_args()
    input_node_exporter_port = nameSpace.exporter_port
    input_node_exporter_metrics_path = nameSpace.exporter_path
    input_prometheus_config_file = nameSpace.prometheus_config
    input_prometheus_job_name = nameSpace.prometheus_job
    input_prometheus_host = nameSpace.prometheus_host
    input_prometheus_port = nameSpace.prometheus_port

    known_hosts = parse_known_hosts(HOSTS_FILE)

    online_hosts_0 = mp_queue(is_host_pingable, known_hosts)
    online_hosts = [i["host"] for i in online_hosts_0 if i["ready"] is True]

    wrapped_queue = [dict(func=check_host, kwargs=dict(host=i, ports=input_node_exporter_port)) for i in online_hosts]

    ready_hosts_0 = mp_queue(wrap, wrapped_queue)
    ready_hosts = sorted([i for i in ready_hosts_0 if not i.endswith(":0")])

    yaml_dict = load_yaml(input_prometheus_config_file)

    yaml_dict["scrape_configs"].append({
        "job_name": input_prometheus_job_name,
        "metrics_path": input_node_exporter_metrics_path,
        "scheme": os.getenv("PROMETHEUS_DASHBOARD_SCHEME", "http"),
        "scrape_interval": "15s",
        "static_configs": [{
            "targets": ready_hosts
        }]
    })

    backup_file(input_prometheus_config_file)
    dump_yaml(yaml_dict, input_prometheus_config_file)

    reload_prometheus()
