import hashlib
import json
import os
from .logger import Logger

__all__ = ['Config', 'AppConfig']


class _ConfigTemplate:

    """ Test values
    ==================================================
    key - key
    value - value of key
    type_value - type of value
    type_par - additional parameters for test
    """
    _conf = None
    _environ = None

    def _init_conf(self, params):
        conf = {}
        for key in params.keys():
            if params[key].get('params'):
                conf[key] = self._init_conf(params[key]['params'])
            else:
                value = params[key].get('value')
                if params[key].get('env'):
                    value = self._set_conf_params({},{key: value}, params).get(key)
                if value is not None:
                    if type(value) in [dict, list]:
                        conf[key] = value.copy()
                    else:
                        conf[key] = value
        return conf

    def __init__(self, *conf_data):
        self._logger = Logger()
        if self._conf is None:
            self._environ = os.environ
            self._conf = self._init_conf(self._params)
        for c in conf_data:
            self.set_config(c)

    # Testing testconf with params data, and update oldconf with data from
    # testconf
    def _set_conf_params(self, oldconf, testconf, params):
        conf = oldconf.copy() if oldconf else {}
        for key in testconf:
            resvalue = None
            param = params.get(key)
            oldvalue = conf.get(key)
            testvalue = testconf.get(key)
            if param is None:
                self._logger.error('Parameter "%s" value "' % key, testvalue,
                    '" type is "%s" not found' % type(testvalue).__name__)
            else:
                type_param = param['type']
                if param.get('env'):
                    testvalue = self._environ.get(param['env'], testvalue)
                    conv_type = [y for x, y in [('str', str), ('int', int), ('bool', bool)] if x in type_param]
                    if testvalue is not None and len(conv_type) > 0:
                        testvalue = conv_type[0](testvalue)
                    else:
                        continue
                resvalue = []
                reskeys = []
                if 'anykeys' in type_param:
                    if type(testvalue).__name__ == 'dict':
                        testvalue = testvalue.items()
                    else:
                        self._logger.warning('Parameter "%s" must be "dict" type' % key)
                        continue
                elif type(testvalue).__name__ != 'list':
                    testvalue = [testvalue]
                key_testitem = key
                for testitem in testvalue:
                    if 'anykeys' in type_param:
                        key_testitem, testitem = testitem
                    if self._test_value(key_testitem, testitem, param):
                        if 'dict' in type_param:
                            if param.get('params'):
                                res = self._set_conf_params(
                                    oldvalue, testitem, param['params'])
                                if res is not None:
                                    resvalue.append(res)
                                    reskeys.append(key_testitem)
                        else:
                            if 'group' in type_param:
                                testitem = self._group_normalize(testitem)
                            resvalue.append(testitem)
                            reskeys.append(key_testitem)
                if 'anykeys' in type_param:
                    resvalue = dict([(reskeys.pop(0), x) for x in resvalue])
                elif 'list' not in type_param:
                    resvalue = list([None] + resvalue).pop()
                if resvalue is not None and 'do' in type_param:
                    if not self._do_type_set(key, resvalue, param):
                        self._logger.warning('Parameter "%s" current "' % key, resvalue,
                            '" type is "%s" testing failed' % type(resvalue).__name__)
                        resvalue = None
                if resvalue is not None:
                    conf[key] = resvalue
        return conf

    def _test_value(self, key, value, param):
        type_param = param.get('type')
        type_value = [x for x in type_param if x in ['str', 'int', 'bool', 'dict']]
        if type_value:
            if type(value).__name__ not in type_value:
                self._logger.error('Parameter "%s" must be %s types, current "' % (
                    key, type_value), value, '" (%s)' % type(value).__name__)
                return False
            if 'value' in type_param:
                if value not in param.get('values', []):
                    self._logger.error('Value "', value, '" of key "%s" unknown' % key)
                    return False
            if 'dir' in type_param:
                if not os.path.isdir(value):
                    self._logger.error('Path "%s" not present' % value)
                    return False
            elif 'file' in type_param:
                if not os.path.isfile(value):
                    self._logger.error('File "%s" not present' % value)
                    return False
            return True
        else:
            self._logger.error('Type for testing "%s" unknown' % type_value)
            return False

    def _group_normalize(self, group):
        prefix = '/'
        if group.endswith('/'):
            return group
        if group.endswith('*'):
            prefix = ''
            group = group[0:-1]
        return '%s%s/' % (prefix, '/'.join(group.split('.')[::-1]))

    def set_config(self, conf_data):
        conf = {}
        if type(conf_data).__name__ == 'str':
            try:
                self._logger.debug('Open file ', conf_data)
                f = open(conf_data, 'r')
                json_data = f.read()
                f.close()
                conf = json.loads(json_data)
            except Exception as err:
                self._logger.error('Load config file failed. %s' % err)
                pass
        elif type(conf).__name__ == 'dict':
            conf = conf_data
        else:
            return False
        self._conf = self._set_conf_params(self._conf, conf, self._params)
        self._logger.debug('Conf=', self._conf)

    def keys(self):
        return self._conf.keys()

    def setdefault(self, key, value):
        self._conf.setdefault(key, value)

    def dump(self):
        return json.dumps(self._conf, sort_keys=True, indent=2)

    def _do_type_set(self, key, value, params):
        self._logger.error('_do_type_set handler is not defined')
        return False

    def hash(self):
        return hashlib.sha1(json.dumps(self._conf, sort_keys=True).encode()).hexdigest()

    def set(self, key, value):
        self._conf[key] = value

    def __setitem__(self, key, value):
        self.set(key, value)

    def get(self, key, default=None):
        return self._conf.get(key, default)

    def __getitem__(self, key):
        return self.get(key)

    def __delitem__(self, key):
        del self._conf[key]

    def __contains__(self, item):
        return bool(item in self._conf)

    def __len__(self):
        return self._conf.__len__()

    def __str__(self):
        return self.dump()

    def __repr__(self):
        return self.dump()


class Config(_ConfigTemplate):

    """ Public Config object
    ==================================================
    .set_config(conf_data) - set config data
        Use: conf_data(str type) - path of json config file
             conf_data(dict type) - dict with config
    .set(key,value) - set config key
    .get(key) - get config key
    .update_apps() - update apps config data
    .apps - Dict of AppConfig oblects
    """
    _instance = None
    apps = {}
    _params = {
        'marathon': {
            'params': {
                'force': {
                    'value': True,
                    'type': ['bool']
                },
                'host': {
                    'value': 'http://marathon.mesos:8080',
                    'type': ['str']
                },
                'enabled': {
                    'value': False,
                    'type': ['bool']
                },
                'restart': {
                    'value': False,
                    'type': ['bool']
                }
            },
            'type': ['dict']
        },
        'mesos': {
            'params': {
                'domain': {
                    'value': 'marathon.mesos',
                    'type': ['str'],
                    'env': 'SUROK_MESOS_DOMAIN'
                },
                'enabled': {
                    'value': False,
                    'type': ['bool']
                }
            },
            'type': ['dict']
        },
        'files': {
            'params': {
                'path': {
                    'value': '/var/tmp',
                    'type': ['str', 'dir']
                },
                'enabled': {
                    'value': False,
                    'type': ['bool']
                }
            },
            'type': ['dict']
        },
        'memcached': {
            'params': {
                'enabled': {
                    'value': False,
                    'type': ['bool']
                },
                'discovery': {
                    'params': {
                        'enabled': {
                            'value': False,
                            'type': ['bool']
                        },
                        'service': {
                            'type': ['str']
                        },
                        'group': {
                            'type': ['str', 'group']
                        }
                    },
                    'type': ['dict']
                },
                'host': {
                    'type': ['str']
                },
                'hosts': {
                    'type': ['list', 'str']
                }
            },
            'type': ['dict']
        },
        'defaults': {
            'params': {
                'discovery': {
                    'value': 'none',
                    'type': ['str', 'value'],
                    'values': ['none', 'mesos_dns', 'marathon_api']
                },
                'store': {
                    'value': 'memory',
                    'type': ['str', 'value'],
                    'values': ['memory', 'files', 'memcached']
                },
                'group': {
                    'type': ['str', 'group'],
                    'env': 'SUROK_DISCOVERY_GROUP'
                }
            },
            'type': ['dict']
        },
        'version': {
            'value': '0.7',
            'type': ['str', 'value'],
            'values': ['0.7', '0.8']
        },
        'confd': {
            'value': '/etc/surok/conf.d',
            'type': ['str', 'dir']
        },
        'modules': {
            'value': '/opt/surok/modules',
            'type': ['str', 'dir']
        },
        'wait_time': {
            'value': 20,
            'type': ['int']
        },
        'lock_dir': {
            'type': ['str', 'dir']
        },
        'loglevel': {
            'value': 'info',
            'type': ['str', 'do'],
            'do': 'set_loglevel',
            'env': 'SUROK_LOGLEVEL'
        },
        'domain': {
            'type': ['str']
        }
    }

    def __new__(cls, *args):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
        return cls._instance

    def __init__(self, *conf_data):
        super().__init__(*conf_data)

    def set_config(self, conf_data):
        super().set_config(conf_data)
        if self.get('version') == '0.7':
            domain = self.get('domain')
            if domain is not None:
                self['mesos'] = {'domain': domain, 'enabled': True}
                self['defaults']['discovery'] = 'mesos_dns'
            path = self.get('lock_dir')
            if path is not None:
                self['files'] = {'path': path, 'enabled': True}
            self['marathon']['restart'] = self['marathon']['enabled']
            self['marathon']['enabled'] = True
        if not self['defaults'].get('group','/').startswith('/'):
            del self['defaults']['group']
        if 'group' not in self['defaults']:
            marathon_id = self._environ.get('MARATHON_APP_ID')
            if marathon_id is not None:
                self['defaults']['group'] = '%s/' % '/'.join(marathon_id.split('/')[:-1])

    def _do_type_set(self, key, value, param):
        if param.get('do') == 'set_loglevel':
            if self._logger.set_level(value):
                return True
        return False

    def update_apps(self):
        self.apps = {}
        for app_conf in [x for x in [os.path.join(
                self['confd'], x) for x in os.listdir(self['confd'])] if os.path.isfile(x)]:
            app = AppConfig(app_conf)
            self.apps[app['conf_name']] = app


class AppConfig(_ConfigTemplate):

    """ Public AppConfig object
    ==================================================
    .set_config(conf_data) - set config data
        Use: conf_data(str type) - path of json config file
             conf_data(dict type) - dict with config
    .set(key,value) - set config key
    .get(key) - get config key
    """
    _params = {
        'conf_name': {
            'type': ['str']
        },
        'services': {
            'value': [],
            'params': {
                'name': {
                    'type': ['str']
                },
                'ports': {
                    'type': ['list', 'str']
                },
                'tcp': {
                    'type': ['list', 'str']
                },
                'udp': {
                    'type': ['list', 'str']
                },
                'discovery': {
                    'type': ['str']
                },
                'group': {
                    'type': ['str', 'group']
                }
            },
            'type': ['list', 'dict']
        },
        'files': {
            'value': {},
            'type': ['anykeys', 'str']
        },
        'environments': {
            'value': {},
            'type': ['anykeys', 'str']
        },
        'reload_cmd': {
            'type': ['str']
        },
        'discovery': {
            'type': ['str', 'value'],
            'values': ['none', 'mesos_dns', 'marathon_api']
        },
        'store': {
            'type': ['str', 'value'],
            'values': ['memory', 'files', 'memcached']
        },
        'group': {
            'type': ['str', 'group']
        },
        'template': {
            'type': ['str']
        },
        'dest': {
            'type': ['str']
        }
    }

    def __init__(self, *conf_data):
        if not hasattr(self, '_config'):
            self._config = Config()
        super().__init__(*conf_data)

    def set_config(self, conf_data):
        super().set_config(conf_data)
        if not self.get('group','/').startswith('/'):
            if self._config['defaults'].get('group'):
                self['group'] = self._config['defaults']['group'] + self['group']
            else:
                del self['group']
        for key, item in self._config['defaults'].items():
            self.setdefault(key, item)
        if 'dest' in self._conf and 'template' in self._conf:
            self._conf['files'].update(
                {self._conf['dest']:
                    '{{ mod.template(mod.from_file("%s")) }}' % self._conf['template']})
        services = self.get('services', [])
        i = 0
        while i < len(services):
            service = services[i]
            if not service.get('group','/').startswith('/'):
                if self.get('group'):
                    service['group'] = self['group'] + service['group']
                else:
                    self._logger.error('Some services haven\'t group.\n%s' % self)
                    del services[i]
                    continue
            if self.get('group'):
                services[i].setdefault('group', self['group'])
            if 'ports' in service or self._config['version'] == '0.7':
                service.setdefault('tcp', [])
                service['tcp'].extend(service.get('ports',[]))
            i += 1
        if type(conf_data).__name__ == 'str' and 'conf_name' not in self._conf:
            self._conf['conf_name'] = os.path.basename(conf_data)
