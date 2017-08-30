# Конфигурация Surok (0.8.x)
**/etc/surok/conf/surok.json** Разберем конфигурационный файл по опциям
```
{
    "version": "0.8",
    "marathon": {
        "enabled": false,
        "restart": false,
        "force": true,
        "host": "http://marathon.mesos:8080"
    },
    "mesos":{
        "enabled": true,
        "domain": "marathon.mesos"
    },
    "default_discovery": "mesos_dns",
    "default_store": "memory",
    "confd": "/etc/surok/conf.d",
    "modules": "/opt/surok/modules",
    "wait_time": 20,
    "files":{
        "enabled": false,
        "path": "/var/tmp"
    },
    "loglevel": "info",
    "memcached": {
        "enabled": false,
        "discovery": {
            "enabled": false,
            "service": "memcached",
            "group": "system"
        },
        "host": "localhost:11211"
    },
    "group":"default.group"
}
```
## Опции файла конфигурации
* **version** - *string. Не обязательный. По умолчанию "0.7".*
Версия файлов конфигурации, шаблонов. На текущий момент может принимать значения "0.7" или "0.8".
  * значение "0.7" - файлы конфигурации версии 0.7.х и более ранних
  * значение "0.8" - файлы конфигурации версии 0.8

##### версия 0.8
* **marathon**, **mesos**, **memcached**, **files** - *dict/hash. Не обязательный. По умолчанию '{"enable":false}'.*
Системы с которыми работает сурок. Если система выключена, то параметры системы и их наличие уже не важны.
  * **enable** - *boolean. Не обязательный. По умолчанию false.*
    Доступность системы для использования.

    специфичные параметры:
    * для Marathon API "marathon"
      * **force** - *boolean. Не обязательный. По умолчанию true.*
        Рестарт контейнера с force или нет.
      * **restart** - *boolean. Не обязательный. По умолчанию false.*
        Вкл/выкл. рестарта контейнера
      * **host** - *string. Не обязательный. По умолчанию "http://marathon.mesos:8080".*
        Адрес Marathon.
    * для mesos DNS "mesos"
      * **domain** - *string. Не обязательный. По умолчанию "marathon.mesos".*
        Приватный домен Mesos DNS
    * для Memcached "memcached"
      * **host** - string. Адрес Memcached сервера в формате, "FQDN:порт" или "IP-адрес:порт"
                   В случае отсутствия обнаруженных хостов через обнаружение, используется как "резерв".
      * **discovery** - Параметры обнаружения Memcached в Mesos
        * **enabled** - *boolean. Не обязательный. По умолчанию false.*
           Вкл/выкл. обнаружение
        * **service** - *string. Обязательный, если обнаружение включено."
           Имя сервиса в Mesos
        * **group** - *string. Обязательный, если обнаружение включено."
           Имя группы в Mesos
    * для файлового хранилища "files"
      * **path** - *string. Абсолютный путь к хранилищу.*

* **default_discovery** - *string. Не обязательный. По умолчанию "none"(для версии 0.7 "mesos_dns").*

  Может принимать значения:
  * "mesos_dns" - Mesos DNS
  * "marathon_api"- Marathon API
  * "none" - Не использовать
* **default_store** - *string. Не обязательный. По умолчанию "memory".*

  Может принимать значения:
  * "memory" - Оперативная память в рамках процесса Surok
  * "files"- Файловое хранилище
  * "memcached"- Memcached
* **confd** - *strig. Не обязательный. По умолчанию "/etc/surok/conf.d"*
  Абсолютный путь до директории с конфигурационными файлами приложений.
* **modules** - *strig. Не обязательный. По умолчанию "/opt/surok/modules"*
  Абсолютный путь до директории с модулями.
* **wait_time** - *int. Не обязательный. По умолчению 20*
  Время в секундах сколько Surok ждет до того, как начать заново делать запросы на обнаружение сервисов.
* **loglevel** - *string. Не обязательный. По умолчанию "info".*
  Уровень логирования. Может принимать значения: "debug", "info", "warning", "error"
* **group** - *string. Не обязательный. По умолчнию заполняется из MARATHON_APP_ID*
  Базавая группа для всех приложений.

##### версия 0.8 (0.8.2)
Для версии 0.8.2 есть отличия по сравнению с версией 0.8.1. 

**"default_discovery"**, **"default_store"** - значения в версии 0.8.1.
Пример для 0.8.1:
```
{
    "version": "0.8",
    "mesos":{
        "enabled": true,
        "domain": "marathon.mesos"
    },
    "default_discovery": "mesos_dns",
    "confd": "/etc/surok/conf.d",
    "wait_time": 5,
    "lock_dir": "/var/tmp",
    "loglevel": "info"
}

```

В 0.8.2 теперь вместо этих двух параметров принимается следующая структура **"defaults"**:
В неё входят: 
* **"discovery"**. Принимает значения: "none", "mesos_dns", "matarhon_api". По умолчанию "none".
* **"store"**. Принимает значения "memory", "files", "memcached".
* **"group"**. Группа по умолчанию для поиска сервисов. Её можно так же передать с помощью переменной окружения SUROK_DISCOVERY_GROUP.

Пример для 0.8.2:
```
{
    "version": "0.8",
    "mesos":{
        "enabled": true,
        "domain": "marathon.mesos"
    },
    "defaults": {
        "discovery": "mesos_dns"
    },
    "confd": "/etc/surok/conf.d",
    "wait_time": 5,
    "lock_dir": "/var/tmp",
    "loglevel": "info"
}
```
Замечание по указанию группы для поиска сервисов.
Группа может быть определена в главном конфиге, в конфиге приложения и внутри секции "services" конфига приложения.
В таком порядке, если указаны группы во всех трех местах, самой приоритетной будет та, что указана в "services".
Например, группа, указанная в конфиге приложения будет переопределена той, что указана в "services".
Если группа указана в конфиге приложения и в главном конфиге сурка, то будет приоритетна та, что в конфиге приложения.


##### версия 0.7 и более ранние
Особенности для файла конфигурации
* **marathon**
  * **enabled** - boolean. Вкл/выкл. рестарта контейнера. В версии 0.8 переименована в "restart".
* **domain** - string. Приватный домен Mesos DNS. В версии 0.8 перемещен в dict "mesos".
  Обнаружение Mesos DNS включено всегда.
* **lock_dir** - string. Абсолютный путь до директории с файловым хранилищем.
  В версии 0.8 перемещен в dict "files", параметр "path".
* **mamcached**
  * **hosts** - string. Адрес Memcached сервера в формате, ["FQDN:порт"] или ["IP-адрес:порт"]

## Переменные среды

Переменные среды заменяют значения из файла конфигурации.

### Конфигурация surok
```
{
    "mesos": {
        "domain": SUROK_MESOS_DOMAIN
    },
    "group": SUROK_DISCOVERY_GROUP,
    "loglevel": SUROK_LOGLEVEL
}
```
