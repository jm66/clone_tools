clone_tools.py
================

Pysphere implementation to clone or deploy multiple VMs

``` bash
 ./clone_tools.py -h
usage: clone_tools.py [-h] -s SERVER -u USERNAME [-p PASSWORD] -m VMNAME
                          [-v] [-d] [-l LOGFILE] [-V]
                          {single,bulk} ...

Deploy a template into multiple VMs or clone a single VM

positional arguments:
  {single,bulk}         commands
    single              Deploy or clone just one VM
    bulk                Deploy or clone multiple VMs

optional arguments:
  -h, --help            show this help message and exit
  -s SERVER, --server SERVER
                        The vCenter or ESXi server to connect to
  -u USERNAME, --user USERNAME
                        The username with which to connect to the server
  -p PASSWORD, --password PASSWORD
                        The password with which to connect to the host. If not
                        specified, the user is prompted at runtime for a
                        password
  -m VMNAME, --vm VMNAME
                        The Template deploy or Source Virtual Machine to clone
  -v, --verbose         Enable verbose output
  -d, --debug           Enable debug output
  -l LOGFILE, --log-file LOGFILE
                        File to log to (default = stdout)
  -V, --version         show program's version number and exit
```

## Single clone

``` bash
usage: clone_tools.py single [-h] -tn TARGETNAME -pu {Dev,QA,Prod,Test}
                                 -fo FOLDER -th TARGETHOST -td TARGETDS

optional arguments:
  -h, --help            show this help message and exit
  -tn TARGETNAME, --targetname TARGETNAME
                        Target VM name
  -pu {Dev,QA,Prod,Test}, --purpose {Dev,QA,Prod,Test}
                        Purpose of the VM
  -fo FOLDER, --folder FOLDER
                        Folder where new VM will be stored
  -th TARGETHOST, --targethost TARGETHOST
                        Target host
  -td TARGETDS, --targetds TARGETDS
                        Target datastore.
```

## Bulk deploy

``` bash
usage: clone_tools.py bulk [-h] -if INPUTFILE [-co {1,2,3}]

optional arguments:
  -h, --help            show this help message and exit
  -if INPUTFILE, --inputfile INPUTFILE
                        Full path of the CSV file in the following format:
                        vmName, purpose, folder, datastore, host
  -co {1,2,3}, --conncurrent {1,2,3}
                        Concurrent cloning processes. Only valid for VM
                        Templates and the maximum value is 4.
```
