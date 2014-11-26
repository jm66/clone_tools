#!/usr/bin/python
import logging, sys, re, getpass, argparse, csv, time, Queue, threading, datetime
from pysphere import MORTypes, VIServer, VITask, VIProperty, VIMor, VIException
from pysphere.vi_virtual_machine import VIVirtualMachine
from threading import Thread
from time import sleep
from Queue import *

class ThreadCloneVM(threading.Thread):
  def __init__(self, queue, target, *args):
    self._target = target
    self._args = args
    threading.Thread.__init__(self)
    self.queue = queue

  def run(self):
    while True:
      #grabs host from queue
      now = datetime.datetime.now()
      vmc = self.queue.get()
      pars = (vmc[0], vmc[3], vmc[4], vmc[2], vmc[1])
      parsfin = ()
      parsfin = self._args + pars
      self._target(*parsfin)
      sleep(5)
      #signals to queue job is done
      self.queue.task_done()

def getResourcePoolByProperty(server, prop, value):
  mor = None
  for rp_mor, rp_path in server.get_resource_pools().items():
    p = server._get_object_properties(rp_mor, [prop])
    if p.PropSet[0].Val == value: mor = rp_mor; break 
  return mor

def find_vm(server, name):
  try:
    vm = server.get_vm_by_name(name)
    return vm
  except VIException:
    return None

def getTemplate(server,name):
  try:
    vm = server.get_vm_by_name(name)
    if vm.properties.config.template:
      logger.info('Found VM template %s' %vm.properties.config.name)
      return vm, vm.properties.config.template
    else:
      logger.warning('VM not a Template. You will not be able to do multiple VM cloning.')
      return vm, vm.properties.config.template
  except VIException as exc:
    logger.error('An error occurred - %s' % exc)
    return None, None

def getResourcePoolByHost(server, hostname):
  try:
    t_hs_mor = None
    rp_mor = None
    t_hs_a = [k for k, v in server.get_hosts().items() if v == hostname]
    if len(t_hs_a) > 0:
      t_hs_mor = t_hs_a[0]
      prop = server._get_object_properties(t_hs_mor,['parent'])
      parent = prop.PropSet[0].Val
      rp_mor = getResourcePoolByProperty(server,"parent", parent)
      if rp_mor is not None:
        logger.debug('Found resource pool %s for %s' %(rp_mor, t_hs_mor))
        return rp_mor, t_hs_mor 
      else:
        logger.error('Did not find resource pool for host %s' %hostname)
        return None, None
    else:
      logger.error('Hostname does not exist.')
      return None. None
  except VIException as exc:
    logger.error('An error occurred - %s' % exc)
    return None, None

def getDatastore(server, datastorename):
  t_ds_a = [k for k, v in server.get_datastores().items() if v == datastorename]
  if t_ds_a > 0:
    t_ds_mor = t_ds_a[0]
    return t_ds_mor
  else:
    logger.error('Datastore does not exist.')
    return None

def getFolderMOR(server,name):
  folders = server._get_managed_objects(MORTypes.Folder)
  try:
    for mor, folder_name in folders.iteritems():
      if folder_name == name:
        logger.debug('Folder %s found.' %name)
        return mor
  except IndexError:
    return None
  return None

def getDatePrefix():
  return time.strftime("%y%m")

def getPurposePrefix(name):
  purpose = {'Dev':'D','Test':'T','QA':'Q','Prod':'P',}
  return purpose[name]

def getVMPrefix(name, purpose):
  fullname = []
  fullname.append(getDatePrefix())
  fullname.append(getPurposePrefix(purpose))
  fullname.append('-')
  fullname.append(name)
  return ''.join(fullname)

def cloneVM(server, s_vm, s_vmIsTemplate, power_on, ssync, targetname, targetds, targethost, folder, purpose):
  try:
    clonedVM = None
    # Validating that the target VM does not exist
    logger.debug('Validating the existence of target VM')
    t_vm_name = getVMPrefix(targetname, purpose)
    if find_vm(server,t_vm_name):
      logger.error('Target VM exists. Please, double check the VM target name and try again. Skipping %s.' % t_vm_name)
      return None
    else:
      logger.debug('No VM was found under the name %s. Continuing with the cloning process.' % t_vm_name )

    logger.debug('Validating the existence of requested datastore MOR')
    ds_mor = getDatastore(server, targetds)
    if ds_mor is None:
      logger.error('No datastore was found under the name %s. Please, double check the Datastore name and try again. Skipping %s.' % (targetds, t_vm_name))
      logger.warning('Skipping %s ')
      return None
    else:
      logger.debug('Found target datastore %s with ID %s. Continuing with the cloning process' % (targetds, ds_mor))
      pass

    logger.debug('Validating the existence of requested Folder MOR')
    f_mor = getFolderMOR(server, folder)
    if f_mor is None:
      logger.error('Folder not found. Please, verify folder name %s and try again. Skipping %s.' % (folder, t_vm_name))
      return None
    else:
      logger.debug('Found target folder %s with ID %s' %(folder, f_mor))
      pass

    logger.debug('Validating the existence of requested Host MOR')
    rp_mor, host_mor = getResourcePoolByHost(server, targethost)
    if host_mor is None:
      logger.error('Folder not found. Please, verify host name and try again. Skipping %s.' % (targethost, t_vm_name))
      return None
    else:
      logger.debug('Found target host %s with ID %s' %(targethost, host_mor))
      pass
    
    logging.info('cloning %s to %s. This might take several minutes depending of the VM\'s size.' %(s_vm.properties.config.name, t_vm_name))
    clonedVM = s_vm.clone(t_vm_name, sync_run=ssync, folder=folder, resourcepool=rp_mor, datastore=ds_mor, host=host_mor, power_on=power_on)

    if clonedVM is not None:
      logger.info('Successfully created %s from %s' % (clonedVM.properties.config.name, s_vm.properties.config.name))
      return clonedVM
    else:
      logger.error('There was an error during cloning.')
      return None
  except VIException as exc:
    logger.warning('Skipping %s due to the following error: %s ' %(t_vm_name, exc))
    return None

def loadCSV(inputfile):
  try:
    # reading file
    cr = csv.reader(open(inputfile,"rb"))
    # retrieving header
    header = cr.next()
    
    #parsing data
    data = [row for row in cr]
    if len(data) > 0:
      return data
    else:
      logger.error('No data was found in the CSV file %s' %inputfile)
      return None
  except IOException as exc:
    logger.error('An error ocurred loading the CSV file. %s' %exc)
    return None

def get_args():
  # Creating the argument parser
  parser = argparse.ArgumentParser(description="Deploy a template into multiple VM's or clone a single VM")
  parser.add_argument('-s', '--server', nargs=1, required=True, help='The vCenter or ESXi server to connect to', dest='server', type=str)
  parser.add_argument('-u', '--user', nargs=1, required=True, help='The username with which to connect to the server', dest='username', type=str)
  parser.add_argument('-p', '--password', nargs=1, required=False, help='The password with which to connect to the host. If not specified, the user is prompted at runtime for a password', dest='password', type=str)
  parser.add_argument('-m', '--vm', nargs=1, required=True, help='The Template deploy or Source Virtual Machine to clone', dest='vmname', type=str)
  parser.add_argument('-v', '--verbose', required=False, help='Enable verbose output', dest='verbose', action='store_true')
  parser.add_argument('-d', '--debug', required=False, help='Enable debug output', dest='debug', action='store_true')
  parser.add_argument('-l', '--log-file', nargs=1, required=False, help='File to log to (default = stdout)', dest='logfile', type=str)
  parser.add_argument('-V', '--version', action='version', version="%(prog)s (version 0.1)")
  
  # configuring subparsers for actions
  subparsers = parser.add_subparsers(help='commands')

  # single command
  single_parser = subparsers.add_parser('single', help='Deploy or clone just one VM')
  single_parser.add_argument('-tn', '--targetname', required=True, action='store', help='Target VM name', dest='targetname', type=str)
  single_parser.add_argument('-pu', '--purpose', required=True, action='store', help='Purpose of the VM', choices=['Dev','QA','Prod','Test'], dest='purpose', type=str)
  single_parser.add_argument('-fo', '--folder', required=True, action='store', help='Folder where new VM will be stored', dest='folder', type=str)
  single_parser.add_argument('-th', '--targethost', required=True, action='store', help='Target host', dest='targethost', type=str)
  single_parser.add_argument('-td', '--targetds', required=True, action='store', help='Target datastore.', dest='targetds', type=str)
  
  # bulk command
  bulk_parser = subparsers.add_parser('bulk', help='Deploy or clone multiple VMs')
  bulk_parser.add_argument('-if', '--inputfile', required=True, action='store', help='Full path of the CSV file in the following format: vmName, purpose, folder, datastore, host', dest='inputfile', type=str)
  bulk_parser.add_argument('-co', '--conncurrent', required=False, action='store', help='Concurrent cloning processes. Only valid for VM Templates and the maximum value is 4.', dest='concurrent', type=int, choices=range(1,4), default=[1])
  
  args = parser.parse_args()
  return args

# Parsing values
args       = get_args()
argsdict   = vars(args)
server     = args.server[0]
username   = args.username[0]
verbose    = args.verbose
debug      = args.debug
log_file   = None
password   = None
vmname     = args.vmname[0]
concurrent = 0
targetname = None
purpose    = None
folder     = None
targethost = None
targetds   = None
inputfile  = None

if args.logfile:
  log_file = args.logfile[0]

if args.password:
  password = args.password[0]

if hasattr(args, 'targetname'):
  targetname = args.targetname

if hasattr(args, 'purpose'):
  purpose = args.purpose

if hasattr(args, 'folder'):
  folder = args.folder

if hasattr(args, 'targethost'):
  targethost = args.targethost

if hasattr(args, 'targetds'):
  targetds = args.targetds

if hasattr(args, 'concurrent'):
  concurrent = args.concurrent

if hasattr(args, 'inputfile'):
  inputfile = args.inputfile

# Logging settings
if debug:
  log_level = logging.DEBUG
elif verbose:
  log_level = logging.INFO
else:
  log_level = logging.WARNING

# Initializing logger
if log_file:
  logging.basicConfig(filename=log_file,format='%(asctime)s %(levelname)s %(message)s',level=log_level)
else: 
  logging.basicConfig(filename=log_file,format='%(asctime)s %(levelname)s %(message)s',level=log_level)

logger = logging.getLogger(__name__)
logger.debug('Logger initialized')

# Asking Users password for server
if password is None:
  logger.debug('No command line password received, requesting password from user')
  password = getpass.getpass(prompt='Enter password for vCenter %s for user %s: ' % (server, username))

# Connecting to server
logger.info('Connecting to server %s with username %s' % (server,username))

con = VIServer()
s_vmIsTemplate = False
s_vm = None
power_on = False
ssync = True

try:
  logger.debug('Trying to connect with provided credentials')
  con.connect(server,username,password)
  logger.info('Connected to server %s' % server)
  logger.debug('Server type: %s' % con.get_server_type())
  logger.debug('API version: %s' % con.get_api_version())
except VIException as ins:
  logger.error(ins)
  logger.debug('Loggin error. Program will exit now.')
  sys.exit()

# Finding the VM
logger.debug('Searching template or virtual machine %s.' % vmname)
s_vm, s_vmIsTemplate = getTemplate(con, vmname)

if s_vm:
  logger.info('Found %s. Defined as template: %s' % (s_vm.properties.config.name, s_vmIsTemplate))
else:
  logger.error('Template or Source VM cannot be found. ')
  if con is not None:
    con.disconnect()
  sys.exit()

if inputfile is not None:
  logging.debug('Bulk cloning action selected with input file %s' %inputfile)
  data = loadCSV(inputfile)
  if data is not None:
    size = len(data)
    logger.debug('%s rows in %s will be processed.'% (size, inputfile))
    logger.warning('Concurrency has been set to %s' % concurrent)
    if s_vmIsTemplate:
      jobs = Queue(15)
      run = 0

      for i in range(concurrent):
        run+=1
        #def cloneVM(server, s_vm, s_vmIsTemplate, power_on, ssync, targetname, targetds, targethost, folder, purpose):
        t = ThreadCloneVM(jobs, cloneVM, con, s_vm, s_vmIsTemplate, power_on, ssync )
        t.setDaemon(True)
        t.start()
        logger.debug('Thread %s started. ' % i)

      for vmc in data:
        jobs.put(vmc)

      jobs.join()
      logger.info('Jobs Successfully completed')
      if con is not None:
        con.disconnect()
  else:
    logger.error('No data was found. Please, verify %s and try again.' %inputfile)
    if con is not None:
      con.disconnect()
    sys.exit()
elif targetname is not None and purpose is not None:
  logging.debug('Single VM cloning action selected with target VM name %s' %targetname)
  clonedVM = cloneVM(con, s_vm, s_vmIsTemplate, power_on, ssync, targetname, targetds, targethost, folder, purpose)
  if clonedVM is not None:
    logger.info('Successfully created %s from %s' % (clonedVM.properties.config.name, s_vm.properties.config.name))
    if con is not None:
      con.disconnect()
  else:
    logger.error('There was an error during cloning.')
    if con is not None:
      con.disconnect()
    sys.exit()
