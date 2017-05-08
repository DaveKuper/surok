import dns.resolver
import dns.query
import requests
import dns.exception
from .config import Config
from .logger import Logger

__all__ = ['Discovery', 'DiscoveryMesos', 'DiscoveryMarathon']


class DiscoveryTemplate:

    def __init__(self):
        self._config = Config()
        self._logger = Logger()

    def enabled(self):
        return self._config[self._config_section].get('enabled', False)

    def update_data(self):
        pass

    # Do DNS queries
    # Return array:
    # ["10.10.10.1", "10.10.10.2"]
    def do_query_a(self, fqdn):
        servers = []
        try:
            resolver = dns.resolver.Resolver()
            for a_rdata in resolver.query(fqdn, 'A'):
                servers.append(a_rdata.address)
        except dns.exception.DNSException as err:
            self._logger.error('Could not resolve %s. Error: %s' % (fqdn, err))
        return servers

    # Do DNS queries
    # Return array:
    # [{"name": "f.q.d.n", "port": 8876, "ip": ["10.10.10.1", "10.10.10.2"]}]
    def do_query_srv(self, fqdn):
        servers = []
        try:
            resolver = dns.resolver.Resolver()
            resolver.lifetime = 1
            resolver.timeout = 1
            query = resolver.query(fqdn, 'SRV')
            for rdata in query:
                info = str(rdata).split()
                servers.append({'name': info[3][:-1], 'port': info[2]})
        except dns.exception.DNSException as err:
            self._logger.error('Could not resolve %s. Error: %s' % (fqdn, err))
        return servers


class Discovery:
    _instance = None
    _discoveries = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Discovery, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        self._config = Config()
        self._logger = Logger()
        if 'mesos_dns' not in self._discoveries:
            self._discoveries['mesos_dns'] = DiscoveryMesos()
        if 'marathon_api' not in self._discoveries:
            self._discoveries['marathon_api'] = DiscoveryMarathon()
        if 'none' not in self._discoveries:
            self._discoveries['none'] = DiscoveryNone()

    def keys(self):
        return self._discoveries.keys()

    def resolve(self, app):
        if app['services']:
            discovery = app.get('discovery', self._config['defaults']['discovery'])
            if discovery in self.keys():
                if self._discoveries[discovery].enabled():
                    return self.compatible(self._discoveries[discovery].resolve(app))
                else:
                    self._logger.error('Discovery "%s" is disabled' % discovery)
            else:
                self._logger.warning('Discovery "%s" isn\'t present' % discovery)
        return {}

    def update_data(self):
        self._config.update_apps()
        for d in self.keys():
            if self._discoveries[d].enabled():
                self._discoveries[d].update_data()

    def compatible(self, hosts):
        compatible_hosts = {}
        if self._config.get('version') == '0.7':
            for service in hosts.keys():
                for host in hosts[service]:
                    ports = host.get('tcp', [])
                    if type(ports).__name__ == 'list':
                        compatible_hosts[service] = []
                        for port in ports:
                            compatible_hosts[service].append({'name': host['name'],
                                                              'ip': host['ip'],
                                                              'port': str(port)})
                    else:
                        compatible_hosts[service] = {}
                        for port in ports.keys():
                            compatible_host = compatible_hosts[service].setdefault(port, [])
                            compatible_host.append({'name': host['name'],
                                                    'ip': host['ip'],
                                                    'port': ports[port]})

            return compatible_hosts
        return hosts


class DiscoveryMesos(DiscoveryTemplate):
    _config_section = 'mesos'

    def resolve(self, app):
        hosts = {}
        domain = self._config['mesos']['domain']
        for service in app['services']:
            group = '.'.join(service['group'].split('/')[-2:0:-1])
            name = service['name']
            hosts[name] = {}
            serv = hosts[name]
            for prot in [x for x in ['tcp', 'udp'] if x in service]:
                ports = service[prot]
                if len(ports):
                    for port_name in ports:
                        for hostname, port in [(x['name'], x['port']) for x in self.do_query_srv(
                                '_%s._%s.%s._%s.%s' % (port_name, name, group, prot, domain))]:
                            if hostname not in serv:
                                serv[hostname] = {'name': hostname,
                                                  'ip': self.do_query_a(hostname)}
                            serv[hostname].setdefault(prot, {})
                            serv[hostname][prot][port_name] = port
                else:
                    for hostname, port in [(x['name'], x['port']) for x in self.do_query_srv(
                            '_%s.%s._%s.%s' % (name, group, prot, domain))]:
                        if hostname not in serv:
                            serv[hostname] = {'name': hostname,
                                              'ip': self.do_query_a(hostname)}
                        serv[hostname].setdefault(prot, [])
                        serv[hostname][prot].append(port)
            hosts[name] = list(serv.values())
        return hosts


class DiscoveryMarathon(DiscoveryTemplate):
    _config_section = 'marathon'
    _tasks = []
    _ports = {}

    def update_data(self):
        hostname = self._config[self._config_section].get('host')
        try:
            ports = {}
            for app in requests.get('%s/v2/apps' % hostname).json()['apps']:
                ports[app['id']] = {}
                if app.get('container') is not None and app['container'].get('type') == 'DOCKER':
                    ports[app['id']] = app['container']['docker'].get('portMappings', [])
            self._ports = ports
        except:
            self._logger.warning('Apps (%s/v2/apps) request from Marathon API is failed' % hostname)
            pass
        try:
            self._tasks = requests.get('%s/v2/tasks' % hostname).json()['tasks']
        except:
            self._logger.warning(
                'Tasks (%s/v2/tasks) request from Marathon API is failed' % hostname)
            pass

    def _test_mask(self, mask, value):
        return (mask.endswith('*') and value.startswith(mask[:-1])) or mask == value

    def resolve(self, app):
        hosts = {}
        for service in app['services']:
            group = service['group']
            service_mask = group + service['name']
            for task in self._tasks:
                if self._test_mask(service_mask, task['appId']):
                    name = '.'.join(task['appId'][len(group):].split('/')[::-1])
                    hosts[name] = {}
                    serv = hosts[name]
                    hostname = task['host']
                    for task_port in self._ports[task['appId']]:
                        prot = task_port['protocol']
                        port_name = task_port['name']
                        port = task['ports'][task['servicePorts'].index(task_port['servicePort'])]
                        if prot in service:
                            ports = service.get(prot, [])
                            if len(ports):
                                for port_mask in service.get(prot, []):
                                    if self._test_mask(port_mask, port_name):
                                        if hostname not in serv:
                                            serv[hostname] = {'name': hostname,
                                                              'ip': self.do_query_a(hostname)}
                                        serv[hostname].setdefault(prot, {})
                                        serv[hostname][prot][port_name] = port
                            else:
                                if hostname not in serv:
                                    serv[hostname] = {'name': hostname,
                                                      'ip': self.do_query_a(hostname)}
                                serv[hostname].setdefault(prot, [])
                                serv[hostname][prot].extend([port])
                    hosts[name] = list(serv.values())
        return hosts


class DiscoveryNone(DiscoveryTemplate):
    _config_section = 'none'

    def __init__(self):
        pass

    def resolve(self, app):
        return {}

    def enabled(self):
        return True
