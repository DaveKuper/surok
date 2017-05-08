#!/usr/bin/python3
import unittest
import json
import os
import re
import sys
import hashlib
import surok.apps
import surok.config
import surok.logger
import surok.discovery
import surok.store


def dict_cmp(a, b, eq='in'):
    type_a = type(a)
    type_b = type(b)
    if type_a != type_b:
        return False
    if type_a in (int, str, bool):
        return a == b
    ca = a.copy()
    cb = b.copy()
    if type_a == list:
        if eq == 'eq' and len(ca) != len(cb):
            return False
        while len(ca):
            if not (len(cb) and dict_cmp(ca.pop(0), cb.pop(0))):
                return False
    elif type_a == dict:
        if eq == 'eq' and not dict_cmp(sorted(list(ca)), sorted(list(cb))):
            return False
        for key in ca:
            if key not in cb or not dict_cmp(ca[key], cb[key]):
                return False
    return True


class Logger(surok.logger.Logger):
    _out = ''
    _err = ''

    def __new__(cls, *args):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            surok.logger.Logger._instance = cls._instance
        return cls._instance

    def _log2err(self, out):
        self._err += out

    def _log2out(self, out):
        self._out += out

    def geterr(self):
        return self._err

    def getout(self):
        return self._out

    def reset(self):
        self._err = ''
        self._out = ''


class Config(surok.config.Config):

    def __new__(cls, *args):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            surok.config.Config._instance = cls._instance
        return cls._instance

    def clear(self):
        self._conf = None
        self.__init__()


class AppConfig(surok.config.AppConfig):
    pass


class DiscoveryTestingTemplate:
    _testing = {}
    _testing_fqdn_a = {
        "test.zzz0.test": ['10.0.0.1', '10.1.0.1'],
        "test.zzz1.test": ['10.0.1.1', '10.1.1.1'],
        "test.zzz2.test": ['10.0.2.1', '10.1.2.1'],
        "test.zzz3.test": ['10.0.3.1', '10.1.3.1'],
        "localhost": ['127.0.0.1']
    }
    _testing_fqdn_srv = {}

    def do_query_a(self, fqdn):
        res = self._testing_fqdn_a.get(fqdn, [])
        if res:
            return res
        else:
            self._logger.error(
                'Testing FQDN ' + fqdn + ' not found in test A records')
            sys.exit(2)

    def do_query_srv(self, fqdn):
        res = self._testing_fqdn_srv.get(fqdn, [])
        if res or fqdn.startswith('_tname_e.') or fqdn.find('._udp.'):
            return res
        else:
            self._logger.error(
                'Testing FQDN ' + fqdn + ' not found in test SRV records')
            sys.exit(2)

    def update_data(self):
        class_name = self.__class__.__name__
        if self._testing.get(class_name, True):
            tgen = {
                "name": ["zzz0", "zzy0", "zzy1", "zzz1"],
                "host": ["test.zzz0.test", "test.zzz1.test", "test.zzz2.test", "test.zzz3.test"],
                "serv": ["tname_aa", "tname_ab", "tname_ba", "tname_bb"],
                "ports": [12341, 12342, 12343, 12344],
                "servicePorts": [21221, 21222, 21223, 21224]
            }
            if class_name == 'DiscoveryMarathon':
                _tasks = []
                _ports = {}
                for id in (0, 1, 2, 3):
                    ports = [] + tgen['ports']
                    servicePorts = [] + tgen['servicePorts']
                    appId = '/'.join(
                        str(tgen['name'][id] + '.xxx.yyy.').split('.')[::-1])
                    _ports[appId] = []
                    for pid in (0, 1, 2, 3):
                        ports[pid] += pid * 10
                        servicePorts[pid] += pid * 100
                        for prot in ['tcp', 'udp']:
                            if pid < 2 or prot == 'tcp':
                                _ports[appId].append({'containerPort': 0,
                                                      'hostPort': 0,
                                                      'labels': {},
                                                      'name': tgen['serv'][pid],
                                                      'protocol': prot,
                                                      'servicePort': servicePorts[pid]})

                    _tasks.append({'appId': appId,
                                   'host': tgen['host'][id],
                                   'ports': ports,
                                   'servicePorts': servicePorts})
                #_tname_a._zzy0.yyy.xxx._tcp.marathon.mesos
                self._tasks = _tasks
                self._ports = _ports
            elif class_name == 'DiscoveryMesos':
                for id in (0, 1, 2, 3):
                    ports = [] + tgen['ports']
                    for pid in (0, 1, 2, 3):
                        ports[pid] += pid * 10
                        for prot in ['tcp', 'udp']:
                            if pid < 2 or prot == 'tcp':
                                for fqdn in ['_%s._%s.xxx.yyy._%s.%s' % (tgen['serv'][pid], tgen['name'][id], prot, self._config['mesos']['domain']),
                                                 '_%s.xxx.yyy._%s.%s' %                    (tgen['name'][id], prot, self._config['mesos']['domain'])]:
                                    if not self._testing_fqdn_srv.get(fqdn):
                                        self._testing_fqdn_srv[fqdn] = []
                                    self._testing_fqdn_srv[fqdn].append(
                                        {'name': tgen['host'][id], 'port': ports[pid]})

                if os.environ.get('MEMCACHE_PORT'):
                    memcached = os.environ[
                        'MEMCACHE_PORT'].split('/')[2].split(':')
                    self._testing_fqdn_a[memcached[0]] = [memcached[0]]
                else:
                    memcached = ['localhost', '11211']
                self._testing_fqdn_srv['_memcached.system._tcp.%s' % self._config['mesos']['domain']] = [
                    {'name': memcached[0], 'port':memcached[1]}]
            self._testing[class_name] = False


class DiscoveryMesos(DiscoveryTestingTemplate, surok.discovery.DiscoveryMesos):
    pass


class DiscoveryMarathon(DiscoveryTestingTemplate, surok.discovery.DiscoveryMarathon):
    pass


class Discovery(surok.discovery.Discovery):

    def __new__(cls, *args):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            surok.discovery.Discovery._instance = cls._instance
        return cls._instance

    def __init__(self):
        if 'mesos_dns' not in self._discoveries:
            self._discoveries['mesos_dns'] = DiscoveryMesos()
        if 'marathon_api' not in self._discoveries:
            self._discoveries['marathon_api'] = DiscoveryMarathon()
        super().__init__()


class Store(surok.store.Store):

    def __new__(cls, *args):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            surok.store.Store._instance = cls._instance
        return cls._instance


class LoadModules(surok.apps.LoadModules):

    def __new__(cls, *args):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            surok.apps.LoadModules._instance = cls._instance
        return cls._instance


class Test01_Logger(unittest.TestCase):

    def test_01_logger_default_level(self):
        logger = Logger()
        self.assertEqual(logger.get_level(), 'info')

    def test_02_logger_output_levels(self):
        message = 'log message'
        tests = {
            'debug': {
                'assertIn': ['ERROR: {}', 'WARNING: {}', 'INFO: {}', 'DEBUG: {}'],
                'assertNotIn': []
            },
            'info': {
                'assertIn': ['ERROR: {}', 'WARNING: {}', 'INFO: {}'],
                'assertNotIn': ['DEBUG: {}']
            },
            'warning': {
                'assertIn': ['ERROR: {}', 'WARNING: {}'],
                'assertNotIn': ['INFO: {}', 'DEBUG: {}']
            },
            'error': {
                'assertIn': ['ERROR: {}'],
                'assertNotIn': ['WARNING: {}', 'INFO: {}', 'DEBUG: {}']
            }
        }
        logger = Logger()
        for value01 in tests.keys():
            logger.reset()
            logger.set_level(value01)
            logger.error(message)
            logger.warning(message)
            logger.info(message)
            logger.debug(message)
            resmessage = logger.geterr() + logger.getout()
            for test_name in tests[value01].keys():
                for test_value in tests[value01][test_name]:
                    with self.subTest(msg='Testing Logger for ...', loglevel=value01):
                        test_message = test_value.format(message)
                        eval('self.{}(test_message,resmessage)'.format(test_name))


class Test02_LoadConfig(unittest.TestCase):

    def test_01_default_values(self):
        config = Config()
        default = {
            'confd': '/etc/surok/conf.d',
                    'defaults': {
                        'discovery': 'none',
                        'store': 'memory'
                    },
            'files': {
                'enabled': False,
                'path': '/var/tmp'
            },
            'loglevel': 'info',
            'marathon': {
                'enabled': False,
                'force': True,
                'host': 'http://marathon.mesos:8080',
                'restart': False
            },
            'memcached': {
                'discovery': {
                    'enabled': False
                },
                'enabled': False
            },
            'mesos': {
                'domain': 'marathon.mesos',
                'enabled': False
            },
            'modules': '/opt/surok/modules',
            'version': '0.7',
            'wait_time': 20
        }
        with self.subTest(msg='Testing default values for Config...\nConfig:\n' + config.dump()):
            self.assertTrue(dict_cmp(default, dict(config), 'eq'))
        config.clear()

    def test_02_main_conf_loader(self):
        tests = [
            ('/usr/share/surok/conf/surok_07.json',
                {
                    'confd': '/etc/surok/conf.d',
                    'defaults': {
                        'discovery': 'mesos_dns',
                        'store': 'memory'
                    },
                    'domain': 'marathon.mesos',
                    'files': {
                        'enabled': True,
                        'path': '/var/tmp'
                    },
                    'lock_dir': '/var/tmp',
                    'loglevel': 'info',
                    'marathon': {
                        'enabled': True,
                        'force': False,
                        'host': 'http://marathon.mesos:8080',
                        'restart': False
                    },
                    'memcached': {
                        'discovery': {
                            'enabled': False,
                            'service': 'memcached'
                        },
                        'enabled': False,
                        'hosts': ['localhost:11211']
                    },
                    'mesos': {
                        'domain': 'marathon.mesos',
                        'enabled': True
                    },
                    'modules': '/opt/surok/modules',
                    'version': '0.7',
                    'wait_time': 20
                }
             ),
            ('/usr/share/surok/conf/surok_08.json',
                {
                    'confd': '/usr/share/surok/conf.d',
                    'defaults': {
                        'discovery': 'mesos_dns',
                        'store': 'memory'
                    },
                    'files': {
                        'enabled': False,
                        'path': '/var/tmp'
                    },
                    'loglevel': 'info',
                    'marathon': {
                        'enabled': False,
                        'force': True,
                        'host': 'http://marathon.mesos:8080',
                        'restart': False
                    },
                    'memcached': {
                        'discovery': {
                            'enabled': False,
                            'service': 'memcached'
                        },
                        'enabled': False,
                        'host': 'localhost:11211'
                    },
                    'mesos': {
                        'domain': 'marathon.mesos',
                        'enabled': False
                    },
                    'modules': '/opt/surok/modules',
                    'version': '0.8',
                    'wait_time': 20
                }
             )
        ]
        for test_file, test_item in tests:
            logger = Logger('info')
            logger.reset()
            config = Config(test_file)
            with self.subTest(msg='Testing hash load config for Config...\nConfig:\n' + config.dump()):
                self.assertTrue(dict_cmp(test_item, dict(config)))
            with self.subTest(msg='Check logger ERR/OUT output for Config...\nConfig:\n' + config.dump()):
                self.assertEqual(logger.getout() + logger.geterr(), '')
            config.clear()

    def test_03_loading_group_environ(self):
        tests = [
            {
                'env': {'MARATHON_APP_ID': '/yyy/xxx/zzz'},
                'group': {'defaults':{'group':'/yyy/xxx/'}}
            },
            {
                'env': {'SUROK_DISCOVERY_GROUP': 'xxx.yyy'},
                'group': {'defaults':{'group':'/yyy/xxx/'}}
            }
        ]
        for key in ['SUROK_DISCOVERY_GROUP', 'MARATHON_APP_ID']:
            if os.environ.get(key) is not None:
                del os.environ[key]
        config = Config()
        config.clear()
        with self.subTest(msg='Testing empty testing parameter.'):
            self.assertEqual(config.get('defaults', {}).get('group'), None)
        for test in tests:
            for key, item in test['env'].items():
                os.environ[key] = item
            config.clear()
            config.set_config({})
            with self.subTest(msg='Testing Config for ...\n%s' % config, env=test['env']):
                self.assertTrue(dict_cmp(test['group'], dict(config)))
            for key in ['SUROK_DISCOVERY_GROUP', 'MARATHON_APP_ID']:
                if os.environ.get(key) is not None:
                    del os.environ[key]
        config.clear()


    def test_03_configs_groups(self):
        groups = (
            (None, 'aaa.bbb', '/aaa.bbb/', 'aaa.bbb*', 'aaa.bbb/'),
            (None, 'ccc.ddd', '/ccc.ddd/', 'ccc.ddd*', 'ccc.ddd/'),
            (None, 'eee.fff', '/eee.fff/', 'eee.fff*', 'eee.fff/')
        )
        groups_res = (
            (None, '/bbb/aaa/', '/aaa.bbb/', 'bbb/aaa/', 'aaa.bbb/'),
            (None, '/ddd/ccc/', '/ccc.ddd/', 'ddd/ccc/', 'ccc.ddd/'),
            (None, '/fff/eee/', '/eee.fff/', 'fff/eee/', 'eee.fff/')
        )
        config = Config()
        for gr_cfg in range(5):
            for gr_app in range(5):
                for gr_srv in range(5):
                    result_cfg = ''
                    if gr_cfg:
                        config.clear()
                        config.set_config({'defaults':{'group': groups[0][gr_cfg]}})
                        result_srv = result_cfg = groups_res[0][gr_cfg]
                    app_cfg = {'services': [{'name':'test'}]}
                    result_app = result_cfg
                    if gr_app:
                        app_cfg['group'] = groups[1][gr_app]
                        result_app = result_app + groups_res[1][gr_app] if gr_app > 2 else groups_res[1][gr_app]
                    result_srv = result_app
                    if gr_srv:
                        app_cfg['services'][0]['group'] = groups[2][gr_srv]
                        result_srv = result_srv + groups_res[2][gr_srv] if gr_srv > 2 else groups_res[2][gr_srv]
                    app_config = AppConfig(app_cfg)
                    if not result_cfg.startswith('/'):
                        result_cfg = ''
                    if not result_app.startswith('/'):
                        result_app = ''
                    if not result_srv.startswith('/'):
                        result_srv = ''
                    with self.subTest(msg='Testing group for Config and AppConfig for ...\nConfig: %s\nAppConfig: %s' % (config, app_config), 
                            gr_cfg=groups[0][gr_cfg], gr_app=groups[1][gr_app], gr_srv=groups[2][gr_srv]):
                        self.assertEqual(config['defaults'].get('group',''), result_cfg)
                        self.assertEqual(app_config.get('group',''), result_app)
                        if len(app_config['services']) > 0:
                            self.assertEqual(app_config['services'][0].get('group',''), result_srv)

    def test_04_apps_config_loader(self):
        test={
            'self_check.json': {
                'conf_name': 'self_check.json',
                'files': {
                    '/tmp/test_old': '{{ mod.template(mod.from_file("/usr/share/surok/templates/self_check.jj2")) }}'
                },
                'services': [
                    {
                        'name': 'zzy0',
                        'tcp': ['tname_aa', 'tname_ab', 'tname_ba', 'tname_bb', 'tname_d']
                    },
                    {
                        'name': 'zzy1',
                        'tcp': ['tname_aa', 'tname_ab', 'tname_ba', 'tname_bb']
                    },
                    {
                        'name': 'zzz0',
                        'tcp': ['tname_aa', 'tname_bb']
                    },
                    {
                        'name': 'zzz1'
                    }
                ],
                'reload_cmd': '/bin/echo selfcheck ok'
            },
            'marathon_check.json': {
                'conf_name': 'marathon_check.json',
                'services': [
                    {
                        'name': 'zzy*',
                        'tcp': ['tname_a*']
                    }
                ],
                'environments': {
                    'TEST1': 'Test env host \'zzy0.tname_aa\' {{ my[\'services\'][\'zzy0\'][0][\'name\'] }}',
                    'TEST2': 'Test env port \'zzy0.tname_aa\' {{ my[\'services\'][\'zzy0\'][0][\'tcp\'][\'tname_aa\'] }}'
                },
                'files': {
                    '/tmp/test_1': '{{ mod.template(mod.from_file(\'/usr/share/surok/templates/marathon_check.jj2\')) }}',
                    '/tmp/test_2': '{{ mod.from_file(\'/usr/share/surok/templates/marathon_check.jj2\') }}'
                },
                'discovery': 'marathon_api',
                'reload_cmd': '/bin/echo selfcheck TEST1=${TEST1} TEST2=${TEST2} > /tmp/test_cmd'
            }

        }
        config = Config({'confd': '/usr/share/surok/conf.d', 'defaults': {'group': '/test/'}})
        config.update_apps()
        for conf_name, app in config.apps.items():
            with self.subTest(msg='Testing AppConfig for ...\n' + app.dump(), conf_name=conf_name):
                self.assertTrue(dict_cmp(test[conf_name],dict(app)))
        config.clear()


    def test_04_main_config_change(self):
        tests={
            'confd':{
                'assertEqual': ['/var', '/var/tmp', '/etc/surok/conf.d'],
                'assertNotEqual': [20, '/var/tmp1', '/etc/surok/conf/surok.json', 1, None, True]
            },
            'loglevel':{
                'assertEqual':['error', 'debug', 'info', 'warning'],
                'assertNotEqual':['errrr', 'DEBUG','warn', 'test', 1, None, True]
            },
            'version':{
                'assertEqual': ['0.7', '0.8'],
                'assertNotEqual': ['0,7', '07', '0.9', 0.7, 0.8, None]
            },
            'wait_time':{
                'assertEqual': [10, 15, 20],
                'assertNotEqual': ['10', '15', None, True]
            }
        }
        config = Config()
        for name01 in tests.keys():
            oldvalue = config.get(name01)
            for test_name in tests[name01].keys():
                for value01 in tests[name01][test_name]:
                    config.set_config({name01:value01})
                    test_value = config.get(name01)
                    with self.subTest(msg='Testing Config Change for values...', name=name01, value=value01, test_value=test_value):
                        eval('self.{}(test_value, value01)'.format(test_name))
            config.set(name01,oldvalue)
        config.clear()

class Test03_Discovery(unittest.TestCase):

    def test_01_discovery(self):
        dict_selfcheck_07 = {
            'zzy0': {
                'tname_aa': [
                    {
                        'ip': ['10.0.1.1', '10.1.1.1'],
                        'name': 'test.zzz1.test',
                        'port': 12341
                    }
                ],
                'tname_ab': [
                    {
                        'ip': ['10.0.1.1', '10.1.1.1'],
                        'name': 'test.zzz1.test',
                        'port': 12352
                    }
                ],
                'tname_ba': [
                    {
                        'ip': ['10.0.1.1', '10.1.1.1'],
                        'name': 'test.zzz1.test',
                        'port': 12363
                    }
                ],
                'tname_bb': [
                    {
                        'ip': ['10.0.1.1', '10.1.1.1'],
                        'name': 'test.zzz1.test',
                        'port': 12374
                    }
                ]
            },
            'zzy1': {
                'tname_aa': [
                    {
                        'ip': ['10.0.2.1', '10.1.2.1'],
                        'name': 'test.zzz2.test',
                        'port': 12341
                    }
                ],
                'tname_ab': [
                    {
                        'ip': ['10.0.2.1', '10.1.2.1'],
                        'name': 'test.zzz2.test',
                        'port': 12352
                    }
                ],
                'tname_ba': [
                    {
                        'ip': ['10.0.2.1', '10.1.2.1'],
                        'name': 'test.zzz2.test',
                        'port': 12363
                    }
                ],
                'tname_bb': [
                    {
                        'ip': ['10.0.2.1', '10.1.2.1'],
                        'name': 'test.zzz2.test',
                        'port': 12374
                    }
                ]
            },
            'zzz0': {
                'tname_aa': [
                    {
                        'ip': ['10.0.0.1', '10.1.0.1'],
                        'name': 'test.zzz0.test',
                        'port': 12341
                    }
                ],
                'tname_bb': [
                    {
                        'ip': ['10.0.0.1', '10.1.0.1'],
                        'name': 'test.zzz0.test',
                        'port': 12374
                    }
                ]
            },
            'zzz1': [
                {
                    'ip': ['10.0.3.1', '10.1.3.1'],
                    'name': 'test.zzz3.test',
                    'port': '12341'
                },
                {
                    'ip': ['10.0.3.1', '10.1.3.1'],
                    'name': 'test.zzz3.test',
                    'port': '12352'
                },
                {
                    'ip': ['10.0.3.1', '10.1.3.1'],
                    'name': 'test.zzz3.test',
                    'port': '12363'
                },
                {
                    'ip': ['10.0.3.1', '10.1.3.1'],
                    'name': 'test.zzz3.test',
                    'port': '12374'
                }
            ]
        }
        dict_marathon_07 = {
            'zzy0': {
                'tname_aa': [
                    {
                        'ip': ['10.0.1.1', '10.1.1.1'],
                        'name': 'test.zzz1.test',
                        'port': 12341
                    }
                ],
                'tname_ab': [
                    {
                        'ip': ['10.0.1.1', '10.1.1.1'],
                        'name': 'test.zzz1.test',
                        'port': 12352
                    }
                ]
            },
            'zzy1': {
                'tname_aa': [
                    {
                        'ip': ['10.0.2.1', '10.1.2.1'],
                        'name': 'test.zzz2.test',
                        'port': 12341
                    }
                ],
                'tname_ab': [
                    {
                        'ip': ['10.0.2.1', '10.1.2.1'],
                        'name': 'test.zzz2.test',
                        'port': 12352
                    }
                ]
            }
        }
        dict_marathon_08 = {
            'zzy0': [
                {
                    'ip': ['10.0.1.1', '10.1.1.1'],
                    'name': 'test.zzz1.test',
                    'tcp': {
                        'tname_aa': 12341,
                        'tname_ab': 12352
                    }
                }
            ],
            'zzy1': [
                {
                    'ip': ['10.0.2.1', '10.1.2.1'],
                    'name': 'test.zzz2.test',
                    'tcp': {
                        'tname_aa': 12341,
                        'tname_ab': 12352
                    }
                }
            ]
        }
        dict_selfcheck_08 = {
            'zzy0': [
                {
                    'ip': ['10.0.1.1', '10.1.1.1'],
                    'name': 'test.zzz1.test',
                    'tcp': {
                        'tname_aa': 12341,
                        'tname_ab': 12352,
                        'tname_ba': 12363,
                        'tname_bb': 12374
                    }
                }
            ],
            'zzy1': [
                {
                    'ip': ['10.0.2.1', '10.1.2.1'],
                    'name': 'test.zzz2.test',
                    'tcp': {
                        'tname_aa': 12341,
                        'tname_ab': 12352,
                        'tname_ba': 12363,
                        'tname_bb': 12374
                    }
                }
            ],
            'zzz0': [
                {
                    'ip': ['10.0.0.1', '10.1.0.1'],
                    'name': 'test.zzz0.test',
                    'tcp': {
                        'tname_aa': 12341,
                        'tname_bb': 12374
                    }
                }
            ],
            'zzz1': []
        }
        tests={
            'T':{                                                                                   #mesos_enabled
                'T':{                                                                               #marathon_enabled
                    '0.7':{                                                                         #version
                        'mesos_dns':{                                                               #default_discovery
                            'marathon_check.json': dict_marathon_07,                                #app['conf_name']
                            'self_check.json': dict_selfcheck_07
                        },
                        'marathon_api':{
                            'marathon_check.json': dict_marathon_07,
                            'self_check.json': dict_selfcheck_07
                        },
                        'none':{
                            'marathon_check.json': dict_marathon_07
                        }
                    },
                    '0.8':{
                        'mesos_dns':{
                            'marathon_check.json':dict_marathon_08,
                            'self_check.json': dict_selfcheck_08
                        },
                        'marathon_api':{
                            'marathon_check.json':dict_marathon_08,
                            'self_check.json': dict_selfcheck_08
                        },
                        'none':{
                            'marathon_check.json':dict_marathon_08
                        }
                    }
                },
                'F':{
                    '0.7':{
                        'mesos_dns':{
                            'self_check.json': dict_selfcheck_07
                        }
                    },
                    '0.8':{
                        'mesos_dns':{
                            'self_check.json': dict_selfcheck_08
                        }
                    }
                }
            },
            'F':{
                'T':{
                    '0.7':{
                        'mesos_dns':{
                            'marathon_check.json': dict_marathon_07
                        },
                        'marathon_api':{
                            'marathon_check.json': dict_marathon_07,
                            'self_check.json': dict_selfcheck_07
                        },
                        'none':{
                            'marathon_check.json':dict_marathon_07
                        }
                    },
                    '0.8':{
                        'mesos_dns':{
                            'marathon_check.json':dict_marathon_08
                        },
                        'marathon_api':{
                            'marathon_check.json':dict_marathon_08,
                            'self_check.json': dict_selfcheck_08
                        },
                        'none':{
                            'marathon_check.json':dict_marathon_08
                        }
                    }
                }
            }
        }
        config = Config('/usr/share/surok/conf/surok_check.json')
        discovery = Discovery()
        for mesos_enabled in ['F', 'T']:
            for marathon_enabled in ['F', 'T']:
                for version in ['0.7', '0.8']:
                    for default_discovery in ['none', 'mesos_dns', 'marathon_api'] :
                        config['defaults']['discovery'] = default_discovery
                        config['mesos']['enabled'] = mesos_enabled == 'T'
                        config['marathon']['enabled'] = marathon_enabled == 'T'
                        config['version'] = version
                        config.update_apps()
                        discovery.update_data()
                        for app in [config.apps[x] for x in config.apps]:
                            conf_name = app.get('conf_name')
                            res = discovery.resolve(app)
                            with self.subTest(
                                    msg='Testing Discovery for values...\nConfig:\n %s\nApp config:\n%s\nDiscovery dump:\n%s' % (
                                        config, app, json.dumps(res, sort_keys=True, indent=2)),
                                    conf_name=conf_name,
                                    mesos_enabled=mesos_enabled,
                                    marathon_enabled=marathon_enabled,
                                    version=version,
                                    default_discovery=default_discovery):
                                self.assertTrue(dict_cmp(tests.get(mesos_enabled, {}).get(marathon_enabled, {}).get(version, {}).get(default_discovery, {}).get(conf_name, {}), res))

        config.clear()

class Test04_Store(unittest.TestCase):
    def test01_Store_Objects(self):
        store = Store()
        logger = Logger()
        logger.reset()
        conf = {'217c2c25755ce4ca91046d21c3243b7f7589bf73': {'dest': '/tmp/test.dest', 'value': 'Testing config'},
                '3ef62a84abe248f25c91e7fac9da6d581ffc3461': {'env': 'TEST', 'value': 'Testing environment'},
                'f9ac6090c76fd9e62fb0319abcea7ebb2266fab2': {'localid': 'TEST', 'data': {
                    'confd': '/usr/share/surok/conf.d',
                    'default_discovery': 'mesos_dns',
                    'default_store': 'memory',
                    'files': {
                        'enabled': False,
                        'path': '/var/tmp'
                    },
                    'loglevel': 'info',
                    'marathon': {
                        'enabled': False,
                        'force': True,
                        'host': 'http://marathon.mesos:8080',
                        'restart': False
                    },
                    'memcached': {
                        'discovery': {
                            'enabled': False
                        },
                        'enabled': True,
                        'host': 'localhost:11211'
                    },
                    'mesos': {
                        'domain': 'marathon.mesos',
                        'enabled': False
                    },
                    'version': '0.8',
                    'wait_time': 20
                }
            }
        }

        conf['217c2c25755ce4ca91046d21c3243b7f7589bf73'].update({'hash':hashlib.sha1(conf['217c2c25755ce4ca91046d21c3243b7f7589bf73']['value'].encode()).hexdigest(),
                                                                 'hashid': hashlib.sha1(conf['217c2c25755ce4ca91046d21c3243b7f7589bf73']['dest'].encode()).hexdigest()})
        conf['3ef62a84abe248f25c91e7fac9da6d581ffc3461'].update({'hash': hashlib.sha1(conf['3ef62a84abe248f25c91e7fac9da6d581ffc3461']['value'].encode()).hexdigest(),
                                                                 'hashid': hashlib.sha1(str('env:%s' % conf['3ef62a84abe248f25c91e7fac9da6d581ffc3461']['env']).encode()).hexdigest()})
        conf['f9ac6090c76fd9e62fb0319abcea7ebb2266fab2'].update({'hash': hashlib.sha1(json.dumps(conf['f9ac6090c76fd9e62fb0319abcea7ebb2266fab2']['data'], sort_keys = True).encode()).hexdigest(),
                                                                 'hashid': hashlib.sha1(str('data:%s' % conf['f9ac6090c76fd9e62fb0319abcea7ebb2266fab2']['localid']).encode()).hexdigest()})
        tests = [
            {
                'name': 'memory',
                'store': surok.store.StoreMemory()
            },
            {
                'enabled': True,
                'name': 'files',
                'store': surok.store.StoreFiles()
            },
            {
                'enabled': True,
                'name': 'memcached',
                'store': surok.store.StoreMemcached()
            }
        ]

        for test in tests:
            # Enabled and check enabled
            config = Config('/usr/share/surok/conf/surok_check.json')
            store = test['store']
            store.check()
            with self.subTest(msg='Testing enabled for default %s object...\nConfig:\n%s' % (store.__class__.__name__, config), test=test):
                self.assertEqual(store.enabled(), test['name'] == 'memory') # Enabled only for memory store
            if test.get('enabled'):
                config[test['name']]['enabled'] = True
            if test.get('name') == 'memcached':
                config['memcached']['host'] = 'localhost:11211'
                if os.environ.get('MEMCACHE_PORT'):
                    config['memcached']['host'] = os.environ['MEMCACHE_PORT'].split('/')[2]
            store.check()
            with self.subTest(msg='Testing enabled for %s object...\nConfig:\n%s' % (store.__class__.__name__, config), test=test):
                self.assertTrue(store.enabled())
            # Testing empty store and set keys
            for key in conf:
                store_data = store.get(conf[key]['hashid'])
                with self.subTest(msg='Testing get keys from empty %s object...\nKey:\n%s' % (store.__class__.__name__, json.dumps(key, sort_keys = True)), test=test):
                    self.assertEqual(store_data, None)
                if conf[key].get('dest'):
                    store.set(conf[key]['hashid'], {'hash': conf[key]['hash'], 'dest': conf[key].get('dest')})
                elif conf[key].get('env'):
                    store.set(conf[key]['hashid'], {'hash': conf[key]['hash'], 'env': conf[key].get('env')})
                else:
                    store.set(conf[key]['hashid'], {'hash': conf[key]['hash']})

            keys = sorted(store.keys())
            with self.subTest(msg='Testing set keys for %s object...\nKeys:\n%s' % (store.__class__.__name__, json.dumps(keys, sort_keys = True)), test=test):
                self.assertEqual(hashlib.sha1(json.dumps(keys, sort_keys=True).encode()).hexdigest(), '479f31609545203de17cc9ba71e649003966388d')
            #Testing get and delete store data
            for key in conf.keys():
                store_data = store.get(conf[key]['hashid'])
                store_data['hashid'] = conf[key]['hashid']
                store_data = json.dumps(store_data, sort_keys=True)
                with self.subTest(msg='Testing set/get data for %s object...\nStore data:\n%s\nTest data:\n%s\n' % (store.__class__.__name__, store_data, json.dumps(conf[key], sort_keys=True, indent=2)), key=key, test=test):
                    self.assertEqual(hashlib.sha1(store_data.encode()).hexdigest(), key)
                    store.delete(conf[key]['hashid'])
            keys=list(store.keys())
            with self.subTest(msg='Testing delete keys for %s object...' % (store.__class__.__name__), keys=keys, test=test):
                self.assertEqual(keys,[])
            #Testing error from logs
            with self.subTest(msg='Check logger ERR/OUT output for Config...\nConfig:\n%s' % config.dump(), test=test):
                self.assertEqual(logger.getout() + logger.geterr(), '')
            config.clear()

    def test02_Main_Store(self):
        logger = Logger()
        logger.reset()
        conf = {'217c2c25755ce4ca91046d21c3243b7f7589bf73': {'dest': '/tmp/test.dest', 'value': 'Testing config'},
                '3ef62a84abe248f25c91e7fac9da6d581ffc3461': {'env': 'TEST', 'value': 'Testing environment'},
                'f9ac6090c76fd9e62fb0319abcea7ebb2266fab2': {'localid': 'TEST', 'data': {
                    'confd': '/usr/share/surok/conf.d',
                    'default_discovery': 'mesos_dns',
                    'default_store': 'memory',
                    'files': {
                    'enabled': False,
                        'path': '/var/tmp'
                    },
                    'loglevel': 'info',
                    'marathon': {
                        'enabled': False,
                        'force': True,
                        'host': 'http://marathon.mesos:8080',
                        'restart': False
                    },
                    'memcached': {
                        'discovery': {
                            'enabled': False
                        },
                        'enabled': True,
                        'host': 'localhost:11211'
                    },
                    'mesos': {
                        'domain': 'marathon.mesos',
                        'enabled': False
                    },
                    'version': '0.8',
                    'wait_time': 20
                }
            }
        }
        conf_update = {'8f6357358fba9a1f5162f6603ae54ccdf573cf7f': {'dest': '/tmp/test.dest', 'value': 'New testing config'},
                       '0346fc7691daa29001ff92155b57f9b6abeeaed8': {'env': 'TEST', 'value': 'New testing environment'},
                       'fb6af582df2a771fe731c3a0898485fc6268c66d': {'localid': 'TEST', 'data': {}}}
        store = Store()
        config = Config()
        with self.subTest(msg='Check logger ERR/OUT output for Store init...\nConfig:\n%s' % config.dump()):
            self.assertEqual(logger.getout() + logger.geterr(), '')
        #, 'files', 'memcached', 'memcached_discovery'
        for conf_store in ['memory']:
            logger.reset()
            config.clear()
            config.set_config('/usr/share/surok/conf/surok_check.json')
            if conf_store == 'memcached_discovery':
                config.set_config(
                    {
                        'defaults':{'store': 'memcached'},
                        'memcached':{
                            'enabled': True,
                            'discovery': {
                                'enabled': True,
                                'service': 'memcached',
                                'group': 'system'
                            }
                        },
                        'mesos':{'enabled': True}
                    }
                )
                discovery = Discovery()
                discovery.update_data()
            else:
                if conf_store in ['files', 'memcached']:
                    config[conf_store]['enabled'] = True
                config['defaults']['store'] = conf_store
                if conf_store == 'memcached':
                    config['memcached']['host'] = 'localhost:11211'
                    if os.environ.get('MEMCACHE_PORT'):
                        config['memcached']['host'] = os.environ['MEMCACHE_PORT'].split('/')[2]
            store.check()

            for key in conf.keys():
                store.set(conf[key])
            keys = list(store.keys())
            keys.sort()
            hash_keys = hashlib.sha1(json.dumps(keys, sort_keys=True).encode()).hexdigest()
            discovery_key = [x for x in keys if x not in conf_update]
            with self.subTest(msg='Testing set keys for Store(%s) object...\nConfig:\n%s' % (conf_store, config.dump()), keys = keys, discovery_key = discovery_key):
                self.assertEqual(len(discovery_key), 1 if conf_store == 'memcached_discovery' else 0)

            for key in conf.keys():
                store_data = store.get(conf[key])
                store_json = store_data.copy()
                del store_json['store']
                store_json = json.dumps(store_json, sort_keys=True)
                orig_data = json.dumps(conf[key], sort_keys=True, indent=2)
                with self.subTest(msg='Testing set/get data for Store(%s) object...\nConfig:\n%s\nStore data:\n%s\nOrigin data:\n%s' % (conf_store, config.dump(), store_json, orig_data),
                                  key = key, store = store_data.get('store')):
                    self.assertEqual(hashlib.sha1(store_json.encode()).hexdigest(), key)
                    self.assertEqual(store_data.get('store'), config['defaults']['store'])
                    store.delete(conf[key])

            keys=list(store.keys())
            with self.subTest(msg='Testing delete keys for Store(%s) object...\nConfig:\n%s' % (conf_store, config.dump()), keys = keys):
                self.assertEqual(keys, discovery_key)

            for key in conf.keys():
                store_data = json.dumps(store.get(conf[key]), sort_keys=True)
                with self.subTest(msg='Testing check_update for Store(%s) object...\nConfig:\n%s\nStore data:\n%s' % (conf_store, config.dump(), store_data), keys = keys):
                    self.assertTrue(store.check_update(conf[key]))

            store.clear()
            keys = list(store.keys())
            keys.sort()
            with self.subTest(msg='Testing clear for Store({0}) object...\nConfig:\n{1}'.format(conf_store, config.dump()), keys=keys):
                self.assertEqual(hashlib.sha1(json.dumps(keys, sort_keys=True).encode()).hexdigest(), hash_keys)

            for key in conf_update.keys():
                store_data = json.dumps(store.get(conf_update[key]), sort_keys = True)
                with self.subTest(msg='Testing update data with check_update for Store({0}) object...\nConfig:\n{1}\nStore data:\n{2}'.format(conf_store, config.dump(), store_data), keys = keys):
                    self.assertTrue(store.check_update(conf_update[key]))

            store.check()
            store.clear()
            keys = list(store.keys())
            keys.sort()
            with self.subTest(msg='Testing update data with clear for Store(%s) object...\nConfig:\n%s' % (conf_store, config.dump()), keys = keys):
                self.assertEqual(hashlib.sha1(json.dumps(keys, sort_keys=True).encode()).hexdigest(), hash_keys)

            store.check_update(conf['217c2c25755ce4ca91046d21c3243b7f7589bf73'])
            store.check()
            store.clear()
            keys = list(store.keys())
            keys.sort()
            test_keys = ['8f6357358fba9a1f5162f6603ae54ccdf573cf7f'] + discovery_key
            test_keys.sort()
            with self.subTest(msg = 'Testing remove 1 key data with clear for Store(%s) object...\nConfig:\n%s' % (conf_store, config.dump()), keys = keys, discovery_key = discovery_key):
                self.assertEqual(keys, test_keys)

            store.check()
            store.clear()
            keys=list(store.keys())
            keys.sort()
            with self.subTest(msg='Testing remove 2 key data with clear for Store(%s) object...\nConfig:\n%s' % (conf_store, config.dump()), keys = keys):
                self.assertEqual(keys, discovery_key)

            output = logger.getout() + logger.geterr()
            with self.subTest(msg='Check logger ERR/OUT output for Store(%s) object...\nConfig:\n%s\nOutput:\n%s' % (conf_store, config.dump(), output)):
                self.assertEqual(output, '')
        config.clear()

class Test05_Apps(unittest.TestCase):
    def test01_Apps(self):
        def get_file(path):
            data = None
            if os.path.isfile(path):
                f = open(path, 'r')
                data = f.read()
                f.close()
            return data

        def hash_data(data):
            return None if data is None else hashlib.sha1(data.encode()).hexdigest()

        config = Config('/usr/share/surok/conf/surok_check.json')
        config['marathon']['enabled'] = True
        config['mesos']['enabled'] = True
        logger = Logger()
        logger.reset()
        apps = surok.apps.Apps()
        apps.update()
        tests = {
            '/tmp/test_1': '162165ae96553d94b803728bb870e571c304de5d',
            '/tmp/test_2': 'e899d5ee7c5dd11e614a7c67abbb47f3ab1646fc',
            '/tmp/test_cmd': 'a325fb4bca52825ff80289a49f8a6fe2df32ff08',
            '/tmp/test_old': '4afc5ac4f1a2f0ec45596b798c311fe1fc9bfbbf'
        }
        tests_2 = {
            '/tmp/test_1': '162165ae96553d94b803728bb870e571c304de5d',
            '/tmp/test_2': None,
            '/tmp/test_cmd': 'a325fb4bca52825ff80289a49f8a6fe2df32ff08',
            '/tmp/test_old': None
        }

        for file_name in tests:
            data = get_file(file_name)
            with self.subTest(msg='Testing result for Apps object...\nFile:\n%s\nData:\n%s' % (file_name, data)):
                self.assertEqual(hash_data(data), tests[file_name])
        with self.subTest(msg='Testing environments 1 for Apps object...\nFile:\n%s\nData:\n%s' % (file_name, data)):
             self.assertEqual(hash_data(os.environ.get('TEST1')), '3d6c95ac5893fea2bfdc56ceb286f1f168754bc3')
             self.assertEqual(hash_data(os.environ.get('TEST2')), '5be7bb08d246fe9b4e7f35ee637baeea1c02948f')

        config.set_config({'confd': '/usr/share/surok/conf.d_2'})
        apps.update()
        for file_name in tests_2:
            data = get_file(file_name)
            with self.subTest(msg='Testing result for Apps object...\nFile:\n%s\nData:\n%s' % (file_name, data)):
                self.assertEqual(hash_data(data), tests_2[file_name])
        with self.subTest(msg='Testing environments 2 for Apps object...\nFile:\n%s\nData:\n%s' % (file_name, data)):
             self.assertEqual(hash_data(os.environ.get('TEST1')), '3d6c95ac5893fea2bfdc56ceb286f1f168754bc3')
             self.assertEqual(hash_data(os.environ.get('TEST2')), None)

        output = logger.getout() + logger.geterr()
        with self.subTest(msg='Check logger ERR/OUT output for Apps object...\nOutput:\n%s' % output):
            self.assertNotIn(' ERROR: ', output)
            self.assertNotIn(' WARNING: ', output)

if __name__ == '__main__':
    unittest.main()
