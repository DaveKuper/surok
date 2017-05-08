# Группы в surok

В surok параметр group заполняется как в файле конфигурации, так и в файле
конфигурации приложения.

**/etc/surok/conf/surok.json**
```
{
    ...
    "group": "cfg.default.group"
    ...
}
```

**/etc/surok/conf.d/app.json**
```
{
    ...
    "group": "app.default.group",
    "services": [
        {
            ...
            "group": "srv.default.group",
            ...
        }
    ],
    ...
}
```
* "cfg.default.group" - Базовая группа (main group), должна быть всегда абсолютной.
* "app.default.group" - Группа приложения (app group)
* "srv.default.group" - Группа сервиса (service group)

## Формат записи:

* Абсолютная:
  + "aaaa.bbbb" - Формат записи тот же, что и в версии 0.7
  + "/bbbb/aaaa/" - Формат группы как в marathon. **Наличие символа "/" на конце обязательно!**
* Относительная:
  + "aaaa.bbbb*" - Формат записи тот же, что и в версии 0.7. Отличается от абсолютного формата
  наличием дополнительного симовла "*" на конце группы.
  + "bbbb/aaaa/" - Формат группы как в marathon. **Наличие символа "/" на конце обязательно!**
  Отличается от абсолютного формата записи отсутствием сомвола "/" в начале строки.

## Значения относительных групп

* "app.default.group" - "cfg.default.group" + "app.default.group"
* "srv.default.group" - "app.default.group" + "srv.default.group"

### Пример
```
cfg.default.group - "/aaa/bbb/"
app.default.group - "ccc/ddd/"
```
то в абсолютной форме значение для app.default.group будет "/aaa/bbb/ccc/ddd/".

Аналогичный алгоритм для app.default.group и srv.default.group.

Запись в формате marathon имеет преимущество использования символа "."(точка) в названиях групп.

## Значения по умолчанию
* "cfg.default.group" - для app.default.group
* "app.default.group" - для srv.default.group
