import jinja2
import os
import imp
import requests
import time
from .logger import Logger
from .config import Config
from .discovery import Discovery
from .store import Store

__all__ = ['Apps']


class Apps:
    """ Public Apps object
    ==================================================
        format app config:
        'files': {
            '/destination/file1': 'Config data 1',
            '/destination/file2': 'Config data 2',
            '/destination/fileN': 'Config data N'
        },
        'environments': {
            'ENV1': 'Jinja2 template for value "{{ my.env.get('ENV1') }}"',
            'ENV2': 'Next Jinja2 template for value "{{ my.env.get('ENV2') }}"'
        }
    """

    def __init__(self):
        self._config = Config()
        self._logger = Logger()
        self._store = Store()
        self._discovery = Discovery()

    def update(self):
        self._discovery.update_data()
        self._store.check()
        for conf_name in sorted(self._config.apps):
            app = self._config.apps[conf_name]
            my = {"services": self._discovery.resolve(app),
                  "conf_name": conf_name,
                  "env": os.environ,
                  "timestamp": time.time()}
            _restart = False
            self._error = False
            for conf in [{
                            'env': x[0],
                            'value': self._render(my, x[1])
                        } for x in app['environments'].items()]:
                if self._store.check_update(conf):
                    _restart = True
                    os.environ[conf['env']] = conf['value']
            for conf in [{
                            'dest': x[0],
                            'value': self._render(my, x[1])
                        } for x in app['files'].items()]:
                if self._store.check_update(conf):
                    _restart = True
                    self._logger.info("Write new configuration of ", conf.get('dest'))
                    try:
                        f = open(conf.get('dest'), 'w')
                        f.write(conf.get('value'))
                        f.close()
                    except Exception as err:
                        self._logger.error(
                            'Config file %s open or write error. %s' % (conf.get('dest'), err))
                        pass
            if _restart and not self._error:
                if self._config['marathon']['restart']:
                    self._restart_self_in_marathon()
                else:
                    if app.get('reload_cmd'):
                        self._logger.info('Restart "%s" app:\n%s' % (
                            app['reload_cmd'], os.popen(app['reload_cmd']).read()))
        self._store.clear()

    def _render(self, my, temp):
        if type(temp).__name__ == 'str':
            data = None
            mod = LoadModules(_my=my)
            try:
                template = jinja2.Template(temp)
                data = template.render(my=my, mod=mod)
            except (jinja2.UndefinedError, Exception) as err:
                self._logger.error('Render Jinja2 error. %s' % err)
            finally:
                mod.dump_logs()
                self._error = mod.get_error()
            return data

    def _restart_self_in_marathon(self):
        env = os.environ.get('MARATHON_APP_ID')
        if env:
            r = requests.post('http://%s/v2/apps/%s/restart' % (self._config['marathon']['host'], env),
                              data={'force': self._config['marathon']['force']})
            if r.status_code != 200:
                self._logger.error('Restart container %s failed. %s' % (env, r.raise_for_status()))
        else:
            self._logger.error('Restart self container failed. Cannot find MARATHON_APP_ID.')


class LoadModules:
    _instance = None
    _get_module = True
    _orig = {}
    _logs = []

    def __new__(cls, **pars):
        if cls._instance is None:
            cls._instance = super(LoadModules, cls).__new__(cls)
        return cls._instance

    def __init__(self, **pars):
        for key in pars:
            if pars[key] is None:
                if hasattr(LoadModules, key):
                    delattr(LoadModules, key)
            else:
                setattr(LoadModules, key, pars[key])
        self._logerror = False
        if self._get_module:
            self._config = Config()
            self._logger = Logger()
            mpath = self._config['modules']
            for module in [os.path.join(mpath, f) for f in os.listdir(
                    mpath) if os.path.isfile(os.path.join(mpath, f))]:
                try:
                    m = imp.load_source('__surok.module__', module)
                except:
                    self._logger.error('Load module %s failed.' % module)
                finally:
                    for key in [x for x in dir(m) if type(
                            getattr(m, x)).__name__ == 'function' and not x.startswith('_')]:
                        self._orig[key] = _ExecModule(self, key, getattr(m, key))
                        setattr(LoadModules, key, self._orig[key].execute)
            self._get_module = False

    def _error(self):
        self._logerror = True
        self.dump_logs()

    def dump_logs(self):
        if self._logerror:
            for log in self._logs:
                self._logger.error(*log)
        else:
            for log in self._logs:
                self._logger.debug(*log)
        self._logs = []

    def get_error(self):
        return self._logerror


class _ExecModule:

    def __init__(self, *args):
        self.modules, self.name, self.function = args

    def get_error(self):
        return self.modules._logerror

    def addlogs(self, *log):
        self.modules._logs.append(log)

    def execute(self, *args, **kwargs):
        if self.get_error():
            self.addlogs('Not execute module: ', self.name)
        else:
            result = None
            self.addlogs('Execute module: ', self.name)
            self.addlogs('args: ', args)
            self.addlogs('kwargs: ', kwargs)
            try:
                result = self.function(self.modules, *args, **kwargs)
                self.addlogs('Return: ', result)
            except Exception as err:
                self.addlogs('Failed execute: ', self.name)
                self.addlogs('Error: %s' % err)
                self.modules._error()
            return result
