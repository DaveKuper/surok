def from_file(self, path):
    try:
        f = open(path, 'r')
        data = f.read()
        f.close()
        return data
    except OSError as err:
        self._error()
        self._logger.error('File {0} open or read error: {1}'.format(path, err))
