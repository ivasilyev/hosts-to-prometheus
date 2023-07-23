#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import yaml
import logging
from shutil import copy2
import multiprocessing as mp
from requests import head, post
from subprocess import getoutput
from argparse import ArgumentParser


HOSTS_FILE = "/etc/hosts"


def get_logging_level():
    var = os.getenv("LOGGING_LEVEL", None)
    if (
        var is not None
        and len(var) > 0
        and hasattr(logging, var)
    ):
        val = getattr(logging, var)
        if isinstance(val, int) and val in [i * 10 for i in range(0, 6)]:
            return val
    return logging.ERROR


def join_lines(s: str):
    return re.sub("[\r\n ]+", " ", s)


def go(cmd: str):
    o = getoutput(cmd)
    logging.debug(f"Ran command: '{join_lines(cmd)}' with the output: '{o}'")
    return o


def remove_empty_values(x: list):
    return [i for i in x if len(i) > 0]


def sorted_set(x: list):
    return sorted(set(remove_empty_values(x)))


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
        row = [
            re.sub("^[^#]+(#.*)", "", i)
            for i in split_columns(line, is_space_delimiter)
        ]
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


def backup_file(file: str, force: bool = False):
    backup = f"{file}.bak"
    if not os.path.exists(backup) or force:
        copy2(file, backup)
        logging.info(f"Created backup: '{backup}'")


def dump_yaml(d: dict, file: str):
    backup_file(file)
    s = yaml.dump(d, Dumper=IndentDumper)
    dump_string(s, file)


def nmap(host: str, ports: str):
    o = go(f"sudo nmap -p {ports} -sT -oG - {host} | grep -oP '(?<= )[0-9]+(?=/open/tcp)' 2>/dev/null")
    out = sorted_set(split_lines(o))
    logging.debug(f"'nmap' with 'grep' for '{host}' returned '{out}'")
    return out


def is_url_ok(
    url: str,
    attempts: int = os.getenv("WEB_ATTEMPT_NUMBER", 5),
    timeout: int = os.getenv("WEB_ATTEMPT_TIMEOUT", 5)
):
    for attempt in range(attempts):
        try:
            response = head(url, timeout=timeout)
            response.close()
            out = response.status_code == 200
            if out:
                logging.debug(f"Succeed connection attempt {attempt + 1} (of {attempts}) for URL '{url}'")
            else:
                logging.debug(f"Failed connection attempt {attempt + 1} (of {attempts}) with "
                              f"code {response.status_code} for URL '{url}'")
            return out
        except Exception as e:
            logging.debug(f"Failed attempt {attempt + 1} (of {attempts}) with exception '{e}' for URL '{url}'")
            pass
    logging.debug(f"Unreachable url: '{url}'")
    return False


def check_ports(host: str, ports: list):
    logging.debug(f"Ports to check for '{host}': {len(ports)}")
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
        logging.debug(f"Opened port found for '{host}': {good_ports[0]}")
        return good_ports[0]
    logging.debug(f"No ports found opened for '{host}' within the range '{ports}'")
    return ""


def check_host(host: str, ports: str):
    logging.info(f"Check ports for host '{host}'")
    open_ports = nmap(host, ports)
    if len(open_ports) > 0:
        port = check_ports(host, open_ports)
        if len(port) > 0:
            return f"{host}:{port}"
    return ""


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
    ready = o.isnumeric() and int(o) < int(os.getenv("PING_PACKET_LOSS_PERCENTAGE", 50))
    if ready:
        logging.debug(f"The host is pingable: '{host}'")
    else:
        logging.debug(f"The host is not pingable: '{host}'")
    return dict(host=host, ready=ready)


def mp_queue(func, queue: list):
    with mp.Pool(min(len(queue), mp.cpu_count())) as p:
        out = p.map(func, queue)
        p.close()
        p.join()
    return out


def wrap(kwargs: dict):
    return kwargs["func"](**kwargs["kwargs"])


def process_prometheus_config(file: str, hosts: list):
    hosts = sorted_set(hosts)
    d = load_yaml(file)
    is_inserted = False
    if "scrape_configs" not in d.keys() or len(d["scrape_configs"]) == 0:
        d["scrape_configs"] = [{
            "job_name": input_prometheus_job_name,
            "metrics_path": input_node_exporter_metrics_path,
            "scheme": os.getenv("PROMETHEUS_DASHBOARD_SCHEME", "http"),
            "scrape_interval": os.getenv("PROMETHEUS_SCRAPE_INTERVAL", "15s"),
            "static_configs": [{
                "targets": hosts
            }]
        }]
        is_inserted = True
        logging.info("Added entire 'scrape_configs' section into Prometheus config")
    for scrape_config_index in range(len(d["scrape_configs"])):
        if not is_inserted and d["scrape_configs"][scrape_config_index]["job_name"] == input_prometheus_job_name:
            for static_config_index in range(len(d["scrape_configs"][scrape_config_index]["static_configs"])):
                if "targets" in d["scrape_configs"][scrape_config_index]["static_configs"][static_config_index].keys():
                    hosts_1 = sorted_set(
                        d["scrape_configs"][scrape_config_index]["static_configs"][static_config_index]["targets"] + hosts
                    )
                    d["scrape_configs"][scrape_config_index]["static_configs"][static_config_index]["targets"] = hosts_1
                    is_inserted = True
                    logging.info(f"Updated existing Prometheus config scrape section for job '{input_prometheus_job_name}'")
                if (
                    not is_inserted
                    and "targets" not in d["scrape_configs"][scrape_config_index]["static_configs"][static_config_index].keys()
                    and static_config_index == len(d["scrape_configs"][static_config_index]["static_configs"]) - 1
                ):
                    d["scrape_configs"][scrape_config_index]["static_configs"][static_config_index]["targets"] = sorted(hosts)
                    is_inserted = True
                    logging.info(f"Added new Prometheus config scrape section for job '{input_prometheus_job_name}'")
    dump_yaml(d, file)


def reload_prometheus_soft(
        host,
        port: int = 80,
        scheme: str = os.getenv("PROMETHEUS_DASHBOARD_SCHEME", "http"),
        path: str = os.getenv("PROMETHEUS_DASHBOARD_RELOAD_PATH", "/-/reload")
):
    url = f"{scheme}://{host}:{port}{path}"
    logging.info(f"Reload Prometheus via API URL: '{url}'")
    response = post(url, timeout=os.getenv("WEB_ATTEMPT_TIMEOUT", 5))
    response.close()
    if response.status_code != 200:
        pass


def reload_prometheus_hard(service_name: str = os.getenv("PROMETHEUS_SERVICE_NAME", "prometheus.service")):
    logging.info(f"Restart Prometheus service")
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
    p.add_argument("--exporter_port", help="(Optional) Node Exporter listen port(s), single or range (via hyphen '-')",
                   default="9100")
    p.add_argument("--exporter_path", help="(Optional) Node Exporter metrics path", default="/metrics")
    p.add_argument("--prometheus_config", help="(Optional) Prometheus Dashboard Server local configuration file",
                   default="/etc/prometheus/prometheus.yml")
    p.add_argument("--prometheus_job", help="(Optional) Target Prometheus configuration job entry name",
                   default="discovered")
    p.add_argument("--prometheus_host", help="(Optional) Prometheus Dashboard Server host", default="127.0.0.1")
    p.add_argument("--prometheus_port", help="(Optional) Prometheus Dashboard Server port", default=9090)
    p.add_argument("--restart", help="(Optional) Restart Prometheus server", action="store_true")
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
    input_is_restart = nameSpace.restart

    logger = logging.getLogger()
    logger.setLevel(get_logging_level())
    stream = logging.StreamHandler()
    stream.setFormatter(logging.Formatter(
        u"%(filename)s[LINE:%(lineno)d]# %(levelname)-8s [%(asctime)s]  %(message)s")
    )
    logger.addHandler(stream)

    logging.info("Load all system hosts")
    known_hosts = parse_known_hosts(HOSTS_FILE)

    logging.info("Filter hosts by network availability")
    online_hosts_0 = mp_queue(is_host_pingable, known_hosts)
    online_hosts = [i["host"] for i in online_hosts_0 if i["ready"] is True]

    wrapped_queue = [dict(func=check_host, kwargs=dict(host=i, ports=input_node_exporter_port)) for i in online_hosts]

    logging.info("Filter hosts by port availability")
    ready_hosts_0 = mp_queue(wrap, wrapped_queue)
    ready_hosts = sorted([i for i in ready_hosts_0 if not len(i) > 0])

    logging.info("Filter hosts by port availability")
    process_prometheus_config(
        file=input_prometheus_config_file,
        hosts=ready_hosts
    )

    logging.info("Reload Prometheus")
    reload_prometheus(input_is_restart)

    logging.info("Done")
