#openpower-automation

Quickstart
----------

Initilize the following environment variable which will used while testing
```shell
    $ export OPENPOWER_HOST=<openbmc machine ip address>
    $ export OPENPOWER_PASSWORD=<openbmc username>
    $ export OPENPOWER_USERNAME=<openbmc password>
```

Run tests using pybot
```shell
    $  pybot -v OPENPOWER_HOST:<ip> -v OPENPOWER_USERNAME:sysadmin -v OPENPOWER_PASSWORD:superuser -v OPENPOWER_LPAR:<lpar_host> -v HPM_IMG_PATH:<image path> tests
```

Run tests using python
```shell
    $  python -m robot -v OPENPOWER_HOST:hostname -v OPENPOWER_USERNAME:username -v OPENPOWER_PASSWORD:password -v OPENPOWER_LPAR:lpar_host tests
```
