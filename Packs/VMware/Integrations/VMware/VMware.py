from typing import *  # noqa: F401
# pylint: disable=no-member
# pylint: disable=no-name-in-module
import ssl
import urllib3
import demistomock as demisto  # noqa: F401
import pyVim.task
from CommonServerPython import *  # noqa: F401
from cStringIO import StringIO

from pyVim.connect import Disconnect, SmartConnect
from pyVmomi import vim, vmodl
from vmware.vapi.vsphere.client import create_vsphere_client
from com.vmware.vapi.std_client import DynamicID


def login(params):
    full_url = params['url']
    url_arr = full_url.split(':')
    url = url_arr[0]
    port = str(url_arr[1])
    user_name = params['credentials']['identifier']
    passsword = params['credentials']['password']

    s = ssl.SSLContext(ssl.PROTOCOL_TLS)
    s.verify_mode = ssl.CERT_NONE
    session = requests.session()
    session.verify = False
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # Connect to a vCenter Server using username and password
    # vsphere_client = create_vsphere_client(server=full_url, username=user_name, password=passsword, session=session)
    vsphere_client = None
    try:
        si = SmartConnect(host=url,
                          user=user_name,
                          pwd=passsword,
                          port=port)
    except Exception:
        si = SmartConnect(host=url,
                          user=user_name,
                          pwd=passsword,
                          port=port,
                          sslContext=s)
    return si, vsphere_client


def logout(si):
    Disconnect(si)


def get_vm(si, uuid):
    vm = si.content.searchIndex.FindByUuid(None, uuid, True, True)  # type: ignore
    if vm is None:
        raise Exception('Unable to locate Virtual Machine.')
    return vm


def get_tag(vsphere_client, args):
    relevant_category = None
    relevant_tag = None
    categories = vsphere_client.tagging.Category.list()
    for category in categories:
        cat_details = vsphere_client.tagging.Category.get(category)
        if cat_details.name == args.get('category'):
            relevant_category = cat_details.id
            break
    tags = vsphere_client.tagging.Tag.list_tags_for_category(relevant_category)
    for tag in tags:
        tag_details = vsphere_client.tagging.Tag.get(tag)
        if tag_details.name == args.get('tag'):
            relevant_tag = tag_details.id
            break
    return relevant_tag


def search_for_obj(content, vim_type, name, folder=None, recurse=True):
    if folder is None:
        folder = content.rootFolder
    if not name:
        return None
    obj = None
    container = content.viewManager.CreateContainerView(folder, vim_type, recurse)

    for managed_object_ref in container.view:
        if managed_object_ref.name == name:
            obj = managed_object_ref
            break
    container.Destroy()
    if not obj:
        raise RuntimeError("Managed Object " + name + " not found.")
    return obj


def create_vm_config_creator(host, args):
    spec = vim.vm.ConfigSpec()
    files = vim.vm.FileInfo()
    files.vmPathName = "[" + host.datastore[0].name + "]" + args.get('name')
    resource_allocation_spec = vim.ResourceAllocationInfo()
    resource_allocation_info = vim.ResourceAllocationInfo()
    resource_allocation_spec.limit = arg_to_number(args.get('cpu-allocation'))
    resource_allocation_info.limit = arg_to_number(args.get('memory'))
    spec.name = args.get('name')
    spec.numCPUs = arg_to_number(args.get('cpu-num'))
    spec.cpuAllocation = resource_allocation_spec
    spec.memoryAllocation = resource_allocation_info
    spec.memoryMB = arg_to_number(args.get('virtual-memory'))
    spec.files = files
    if args.get('guestId'):
        spec.guestId = args.get('guestId')
    return spec


def create_rellocation_locator_spec(vm, datastore):
    template_disks = []
    disk_locators = []
    # collect template disks
    for device in vm.config.hardware.device:
        if type(device).__name__ == "vim.vm.device.VirtualDisk" and hasattr(device.backing, 'fileName'):
            template_disks.append(device)

    # construct locator for the disks
    for disk in template_disks:
        locator = vim.vm.RelocateSpec.DiskLocator()
        locator.diskBackingInfo = disk.backing  # Backing information for the virtual disk at the destination
        locator.diskId = int(disk.key)
        locator.datastore = datastore  # Destination datastore
        disk_locators.append(locator)

    return disk_locators


def apply_get_vms_filters(args, vm_summery):
    ips = argToList(args.get('ip'))
    names = argToList(args.get('name'))
    uuids = argToList(args.get('uuid'))

    ip = not vm_summery.guest.ipAddress or not args.get('ip') or vm_summery.guest.ipAddress in ips
    hostname = not vm_summery.guest.hostName or not args.get('hostname') or vm_summery.guest.hostName == args.get(
        'hostname')
    name = not args.get('name') or vm_summery.config.name in names
    uuid = not args.get('uuid') or vm_summery.config.instanceUuid in uuids

    return ip and hostname and name and uuid


def get_priority(priority):
    if priority == 'highPriority':
        return vim.VirtualMachine.MovePriority().highPriority
    elif priority == 'lowPriority':
        return vim.VirtualMachine.MovePriority().lowPriority
    else:
        return vim.VirtualMachine.MovePriority().defaultPriority


def get_vms(si, args):
    data = []
    content = si.RetrieveContent()  # type: ignore
    container = content.rootFolder
    view_type = [vim.VirtualMachine]
    recursive = True
    container_view = content.viewManager.CreateContainerView(container, view_type, recursive)
    children = container_view.view

    for child in children:
        summary = child.summary
        snapshot_create_date = datetime_to_string(
            child.snapshot.currentSnapshot.config.createDate) if child.snapshot else ' '
        snapshot_uuid = child.snapshot.currentSnapshot.config.uuid if child.snapshot else ' '
        if apply_get_vms_filters(args, summary):
            mac_address = ''
            try:
                for dev in child.config.hardware.device:
                    if isinstance(dev, vim.vm.device.VirtualEthernetCard):  # type: ignore
                        mac_address = dev.macAddress
                        break
            except Exception:  # noqa
                pass

            data.append({
                'Name': summary.config.name,
                'Template': summary.config.template,
                'Path': summary.config.vmPathName,
                'Guest': summary.config.guestFullName,
                'UUID': summary.config.instanceUuid,
                'IP': summary.guest.ipAddress if summary.guest.ipAddress else ' ',
                'State': summary.runtime.powerState,
                'HostName': summary.guest.hostName if summary.guest.hostName else ' ',
                'MACAddress': mac_address,
                'SnapshotCreateDate': snapshot_create_date,
                'SnapshotUUID': snapshot_uuid,
                'Deleted': 'False'
            })
    ec = {
        'VMWare(val.UUID && val.UUID === obj.UUID)': data
    }
    return create_entry(data, ec)


def create_entry(data, ec):
    return {
        'ContentsFormat': formats['json'],
        'Type': entryTypes['note'],
        'Contents': data,
        'ReadableContentsFormat': formats['markdown'],
        'HumanReadable': tableToMarkdown('Virtual Machines', data, headers=['Name', 'Template', 'Path', 'Guest', 'UUID',
                                                                            'IP', 'State', 'HostName', 'MACAddress',
                                                                            'SnapshotCreateDate',
                                                                            'SnapshotUUID',
                                                                            'Deleted']) if data else 'No result were found',
        'EntryContext': ec
    }


def power_on(si, uuid):
    vm = get_vm(si, uuid)

    if vm.runtime.powerState == 'poweredOn':
        raise Exception('Virtual Machine is already powered on.')
    task = vm.PowerOn()
    while task.info.state not in [vim.TaskInfo.State.success, vim.TaskInfo.State.error]:  # type: ignore
        time.sleep(1)
    if task.info.state == 'success':
        ec = {
            'VMWare(val.UUID && val.UUID === obj.UUID)': {
                'UUID': uuid,
                'State': 'poweredOn'
            }
        }
        return {
            'ContentsFormat': formats['json'],
            'Type': entryTypes['note'],
            'Contents': ec,
            'ReadableContentsFormat': formats['text'],
            'HumanReadable': 'Virtual Machine was powered on successfully.',
            'EntryContext': ec
        }
    elif task.info.state == 'error':
        raise Exception('Error occured while trying to power on Virtual Machine.')


def power_off(si, uuid):
    vm = get_vm(si, uuid)
    if vm.runtime.powerState == 'poweredOff':
        raise Exception('Virtual Machine is already powered off.')
    task = vm.PowerOff()
    while task.info.state not in [vim.TaskInfo.State.success, vim.TaskInfo.State.error]:  # type: ignore
        time.sleep(1)
    if task.info.state == 'success':
        ec = {
            'VMWare(val.UUID && val.UUID === obj.UUID)': {
                'UUID': uuid,
                'State': 'poweredOff'
            }
        }
        return {
            'ContentsFormat': formats['json'],
            'Type': entryTypes['note'],
            'Contents': ec,
            'ReadableContentsFormat': formats['text'],
            'HumanReadable': 'Virtual Machine was powered off successfully.',
            'EntryContext': ec
        }
    elif task.info.state == 'error':
        raise Exception('Error occured while trying to power off Virtual Machine.')


def suspend(si, uuid):
    vm = get_vm(si, uuid)
    if vm.runtime.powerState == 'suspended':
        raise Exception('Virtual Machine is already suspended.')
    task = vm.Suspend()
    while task.info.state not in [vim.TaskInfo.State.success, vim.TaskInfo.State.error]:  # type: ignore
        time.sleep(1)
    if task.info.state == 'success':
        ec = {
            'VMWare(val.UUID && val.UUID === obj.UUID)': {
                'UUID': uuid,
                'State': 'suspended'
            }
        }
        return {
            'ContentsFormat': formats['json'],
            'Type': entryTypes['note'],
            'Contents': ec,
            'ReadableContentsFormat': formats['text'],
            'HumanReadable': 'Virtual Machine was suspended successfully.',
            'EntryContext': ec
        }
    elif task.info.state == 'error':
        raise Exception('Error occured while trying to power on Virtual Machine.')


def hard_reboot(si, uuid):
    vm = get_vm(si, uuid)
    task = vm.ResetVM_Task()
    wait_for_tasks(si, [task])
    if task.info.state == 'success':
        ec = {
            'VMWare(val.UUID && val.UUID === obj.UUID)': {
                'UUID': uuid,
                'State': 'HardRebooted'
            }
        }
        return {
            'ContentsFormat': formats['json'],
            'Type': entryTypes['note'],
            'Contents': ec,
            'ReadableContentsFormat': formats['text'],
            'HumanReadable': 'Virtual Machine was rebooted successfully.',
            'EntryContext': ec
        }
    elif task.info.state == 'error':
        raise Exception('Error occured while trying to reboot Virtual Machine.')


def wait_for_tasks(si, tasks):
    propertyCollector = si.content.propertyCollector
    taskList = [str(task) for task in tasks]
    objSpecs = [vmodl.query.PropertyCollector.ObjectSpec(obj=task) for task in tasks]  # type: ignore
    propertySpec = vmodl.query.PropertyCollector.PropertySpec(type=vim.Task, pathSet=[], all=True)  # type: ignore
    filterSpec = vmodl.query.PropertyCollector.FilterSpec()
    filterSpec.objectSet = objSpecs
    filterSpec.propSet = [propertySpec]
    pcfilter = propertyCollector.CreateFilter(filterSpec, True)
    try:
        version, state = None, None
        while len(taskList):
            update = propertyCollector.WaitForUpdates(version)
            for filter_set in update.filterSet:
                for obj_set in filter_set.objectSet:
                    task = obj_set.obj
                    for change in obj_set.changeSet:
                        if change.name == 'info':
                            state = change.val.state
                        elif change.name == 'info.state':
                            state = change.val
                        else:
                            continue
                        if not str(task) in taskList:
                            continue
                        if state == vim.TaskInfo.State.success:  # type: ignore
                            taskList.remove(str(task))
                        elif state == vim.TaskInfo.State.error:  # type: ignore
                            raise task.info.error
            version = update.version
    finally:
        if pcfilter:
            pcfilter.Destroy()


def soft_reboot(si, uuid):
    vm = get_vm(si, uuid)
    vm.RebootGuest()
    return 'A request to reboot the guest has been sent.'


def create_snapshot(si, args):
    uuid = args['vm-uuid']
    vm = get_vm(si, uuid)
    d = str(datetime.now())
    if args['memory'] == 'True':
        mem = True
    else:
        mem = False
    if args['quiesce'] == 'True':
        qui = True
    else:
        qui = False
    name = args.get('name', uuid + ' snapshot ' + d)
    desc = args.get('description', 'Snapshot of VM UUID ' + uuid + ' taken on ' + d)
    pyVim.task.WaitForTask(vm.CreateSnapshot(name=name, description=desc, memory=mem, quiesce=qui))
    return 'Snapshot ' + name + ' completed.'


def revert_snapshot(si, name, uuid):
    vm = get_vm(si, uuid)
    snapObj = get_snapshots(vm.snapshot.rootSnapshotList, name)
    if len(snapObj) == 1:
        snapObj = snapObj[0].snapshot
        pyVim.task.WaitForTask(snapObj.RevertToSnapshot_Task())
        ec = {
            'VMWare(val.UUID && val.UUID === obj.UUID)': {
                'UUID': uuid,
                'Snapshot': 'Reverted to ' + name
            }
        }
        return {
            'ContentsFormat': formats['json'],
            'Type': entryTypes['note'],
            'Contents': ec,
            'ReadableContentsFormat': formats['text'],
            'HumanReadable': 'Reverted to snapshot ' + name + ' successfully.',
            'EntryContext': ec
        }
    else:
        return 'No snapshots found with name: ' + name + ' on VM: ' + uuid


def get_snapshots(snapshots, snapname):
    snapObj = []
    for snapshot in snapshots:
        if snapshot.name == snapname:
            snapObj.append(snapshot)
        else:
            snapObj = snapObj + get_snapshots(snapshot.childSnapshotList, snapname)
    return snapObj


def get_events(si, args):
    vm = get_vm(si, args.get('uuid'))
    hr = []
    content = si.RetrieveServiceContent()  # type: ignore
    eventManager = content.eventManager
    time = vim.event.EventFilterSpec.ByTime()
    time.beginTime = arg_to_datetime(args.get('start-date'))
    time.endTime = arg_to_datetime(args.get('end-date'))
    filter = vim.event.EventFilterSpec.ByEntity(entity=vm, recursion="self")  # type: ignore
    filterSpec = vim.event.EventFilterSpec()
    ids = args.get('event-type').split(',')
    filterSpec.eventTypeId = ids  # type: ignore
    filterSpec.entity = filter  # type: ignore
    filterSpec.time = time
    filterSpec.userName = args.get('user')
    filterSpec.maxCount = arg_to_number(args.get('limit', 50))
    eventRes = eventManager.QueryEvents(filterSpec)
    for e in eventRes:
        hr.append({
            'Event': e.fullFormattedMessage,
            'Created Time': e.createdTime.strftime("%Y-%m-%d %H:%M:%S")
        })
    return {
        'ContentsFormat': formats['json'],
        'Type': entryTypes['note'],
        'Contents': hr,
        'ReadableContentsFormat': formats['markdown'],
        'HumanReadable': tableToMarkdown('VM ' + vm.summary.config.name + ' Events',
                                         hr) if hr else 'No result were found'
    }


def change_nic_state(si, args): # pragma: no cover
    uuid = args['vm-uuid']
    new_nic_state = args['nic-state']
    nic_number = args['nic-number']
    vm = get_vm(si, uuid)
    nic_prefix_header = "Network adapter "
    nic_label = nic_prefix_header + str(nic_number)
    virtual_nic_device = None
    for dev in vm.config.hardware.device:
        if isinstance(dev, vim.vm.device.VirtualEthernetCard) and dev.deviceInfo.label == nic_label:  # type: ignore
            virtual_nic_device = dev
    if not virtual_nic_device:
        raise Exception("Virtual {} could not be found.".format(nic_label))

    virtual_nic_spec = vim.vm.device.VirtualDeviceSpec()  # type: ignore
    if new_nic_state == 'delete':
        virtual_nic_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.remove  # type: ignore
    else:
        virtual_nic_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.edit  # type: ignore
    virtual_nic_spec.device = virtual_nic_device
    virtual_nic_spec.device.key = virtual_nic_device.key
    virtual_nic_spec.device.macAddress = virtual_nic_device.macAddress
    virtual_nic_spec.device.backing = virtual_nic_device.backing
    virtual_nic_spec.device.wakeOnLanEnabled = virtual_nic_device.wakeOnLanEnabled
    connectable = vim.vm.device.VirtualDevice.ConnectInfo()  # type: ignore
    if new_nic_state == 'connect':
        connectable.connected = True
        connectable.startConnected = True
    elif new_nic_state == 'disconnect':
        connectable.connected = False
        connectable.startConnected = False
    else:
        connectable = virtual_nic_device.connectable
    virtual_nic_spec.device.connectable = connectable
    dev_changes = []
    dev_changes.append(virtual_nic_spec)
    spec = vim.vm.ConfigSpec()  # type: ignore
    spec.deviceChange = dev_changes
    task = vm.ReconfigVM_Task(spec=spec)
    wait_for_tasks(si, [task])

    res_new_nic_state = (new_nic_state + "ed").replace("eed", "ed")

    if task.info.state == 'success':
        ec = {
            'VMWare(val.UUID && val.UUID === obj.UUID)': {
                'UUID': uuid,
                'NICState': res_new_nic_state
            }
        }
        return {
            'ContentsFormat': formats['json'],
            'Type': entryTypes['note'],
            'Contents': ec,
            'ReadableContentsFormat': formats['text'],
            'HumanReadable': 'Virtual Machine\'s NIC was {} successfully.'.format(res_new_nic_state),
            'EntryContext': ec
        }
    elif task.info.state == 'error':
        raise Exception('Error occurred while trying to clone VM.')


def list_vms_by_tag(vsphere_client, args):
    relevant_tag = get_tag(vsphere_client, args)
    vms = vsphere_client.tagging.TagAssociation.list_attached_objects(relevant_tag)
    vms = filter(lambda vm: vm.type == 'VirtualMachine', vms)
    vms_details = vsphere_client.vcenter.VM.list(
        vsphere_client.vcenter.VM.FilterSpec(vms=set([str(vm.id) for vm in vms])))
    data = []
    for vm in vms_details:
        data.append({
            'TagName': args.get('tag'),
            'Category': args.get('category'),
            'VM': vm.name
        })
    ec = {
        'VMWare.Tag(val.Tag && val.Category && val.TagName === obj.TagName && va.Category == obj.Category)': data
    }
    return {
        'ContentsFormat': formats['json'],
        'Type': entryTypes['note'],
        'Contents': data,
        'ReadableContentsFormat': formats['markdown'],
        'HumanReadable': tableToMarkdown('Virtual Machines with Tag {}'.format(args.get('tag')), data),
        'EntryContext': ec
    }


def create_vm(si, args):
    content = si.RetrieveContent()
    folder = search_for_obj(content, [vim.Folder], args.get('folder'))
    host = search_for_obj(content, [vim.HostSystem], args.get('host'))
    pool = search_for_obj(content, [vim.ResourcePool], args.get('pool'))
    spec = create_vm_config_creator(host, args)
    if not host:
        raise Exception('The host provided is not valid.')
    task = folder.CreateVM_Task(config=spec, pool=pool, host=host)
    wait_for_tasks(si, [task])

    if task.info.state == 'success':
        mac_address = ''
        summary = task.info.result.summary

        try:
            for dev in task.info.result.config.hardware.device:
                if isinstance(dev, vim.vm.device.VirtualEthernetCard):  # type: ignore
                    mac_address = dev.macAddress
                    break
        except Exception:  # noqa
            pass

        data = {
            'Name': summary.config.name,
            'Template': summary.config.template,
            'Path': summary.config.vmPathName,
            'Guest': summary.config.guestFullName,
            'UUID': summary.config.instanceUuid,
            'IP': summary.guest.ipAddress if summary.guest.ipAddress else ' ',
            'State': summary.runtime.powerState,
            'HostName': summary.guest.hostName if summary.guest.hostName else ' ',
            'MACAddress': mac_address,
            'Snapshot': task.info.result.snapshot.currentSnapshot if task.info.result.snapshot else ' ',
            'SnapshotCreateDate': '',
            'SnapshotUUID': '',
            'Deleted': 'False'
        }
        ec = {
            'VMWare(val.UUID && val.UUID === obj.UUID)': data
        }
        return {
            'ContentsFormat': formats['json'],
            'Type': entryTypes['note'],
            'Contents': data,
            'ReadableContentsFormat': formats['markdown'],
            'HumanReadable': tableToMarkdown('Virtual Machine', data,
                                             headers=['Name', 'Template', 'Path', 'Guest', 'UUID',
                                                      'IP', 'State', 'HostName', 'MACAddress', 'SnapshotCreateDate',
                                                      'SnapshotUUID', 'Deleted']),
            'EntryContext': ec
        }
    elif task.info.state == 'error':
        raise Exception('Error occurred while trying to create a VM.')


def clone_vm(si, args):
    vm = get_vm(si, args.get('uuid'))
    content = si.RetrieveContent()
    spec = vim.vm.CloneSpec()
    relocate_spec = vim.vm.RelocateSpec()
    relocate_spec.datastore = search_for_obj(content, [vim.Datastore], args.get('datastore'))
    relocate_spec.host = search_for_obj(content, [vim.HostSystem], args.get('host'))
    relocate_spec.pool = search_for_obj(content, [vim.ResourcePool], args.get('pool'))
    spec.location = relocate_spec
    spec.template = argToBoolean(args.get('template', False))
    spec.powerOn = argToBoolean(args.get('powerOn'))

    folder = search_for_obj(content, [vim.Folder], args.get('folder'))
    task = vm.CloneVM_Task(folder=folder, name=args.get('name'), spec=spec)
    wait_for_tasks(si, [task])

    if task.info.state == 'success':
        mac_address = ''
        summary = task.info.result.summary
        try:
            for dev in task.info.result.config.hardware.device:
                if isinstance(dev, vim.vm.device.VirtualEthernetCard):  # type: ignore
                    mac_address = dev.macAddress
                    break
        except Exception:  # noqa
            pass

        data = {
            'Name': summary.config.name,
            'Template': summary.config.template,
            'Path': summary.config.vmPathName,
            'Guest': summary.config.guestFullName,
            'UUID': summary.config.instanceUuid,
            'IP': summary.guest.ipAddress if summary.guest.ipAddress else ' ',
            'State': summary.runtime.powerState,
            'HostName': summary.guest.hostName if summary.guest.hostName else ' ',
            'MACAddress': mac_address,
            'SnapshotCreateDate': '',
            'SnapshotUUID': '',
            'Deleted': 'False'
        }
        ec = {
            'VMWare(val.UUID && val.UUID === obj.UUID)': data
        }
        return {
            'ContentsFormat': formats['json'],
            'Type': entryTypes['note'],
            'Contents': data,
            'ReadableContentsFormat': formats['markdown'],
            'HumanReadable': tableToMarkdown('Virtual Machine', data,
                                             headers=['Name', 'Template', 'Path', 'Guest', 'UUID',
                                                      'IP', 'State', 'HostName', 'MACAddress', 'SnapshotCreateDate',
                                                      'SnapshotUUID', 'Deleted']),
            'EntryContext': ec
        }
    elif task.info.state == 'error':
        raise Exception('Error occurred while trying to clone VM.')


def relocate_vm(si, args):
    content = si.RetrieveContent()
    vm = get_vm(si, args.get('uuid'))

    priority = get_priority(args.get('priority'))
    spec = vim.VirtualMachineRelocateSpec()
    spec.folder = search_for_obj(content, [vim.Folder], args.get('folder'))
    spec.host = search_for_obj(content, [vim.HostSystem], args.get('host'))
    spec.pool = search_for_obj(content, [vim.ResourcePool], args.get('pool'))
    datastore = search_for_obj(content, [vim.Datastore], args.get('datastore'))

    if datastore:
        spec.datastore = datastore
        spec.disks = create_rellocation_locator_spec(vm, datastore)
    task = vm.RelocateVM_Task(spec, priority)
    wait_for_tasks(si, [task])

    if task.info.state == 'success':
        return {
            'ContentsFormat': formats['json'],
            'Type': entryTypes['note'],
            'Contents': {},
            'ReadableContentsFormat': formats['text'],
            'HumanReadable': 'Virtual Machine was relocated successfully.',
            'EntryContext': {}
        }
    elif task.info.state == 'error':
        raise Exception('Error occurred while trying to relocate VM.')


def delete_vm(si, args):
    vm = get_vm(si, args.get('uuid'))
    if vm.runtime.powerState == 'poweredOff':
        raise Exception("Virtual Machine should be powered off before deleting.")
    task = vm.Destroy_Task()
    wait_for_tasks(si, [task])
    if task.info.state == 'success':
        data = {
            'UUID': args.get('uuid'),
            'Deleted': 'True'
        }
        ec = {
            'VMWare(val.UUID && val.UUID === obj.UUID)': data
        }
        return {
            'ContentsFormat': formats['json'],
            'Type': entryTypes['note'],
            'Contents': {},
            'ReadableContentsFormat': formats['text'],
            'HumanReadable': 'Virtual Machine was deleted successfully.',
            'EntryContext': ec
        }
    elif task.info.state == 'error':
        raise Exception('Error occurred while trying to delete VM.')


def register_vm(si, args):
    content = si.RetrieveContent()
    folder = search_for_obj(content, [vim.Folder], args.get('folder'))
    host = search_for_obj(content, [vim.HostSystem], args.get('host'))
    pool = search_for_obj(content, [vim.ResourcePool], args.get('pool'))

    task = folder.RegisterVM_Task(path=args.get('path'), name=args.get('name'),
                                  asTemplate=args.get('asTemplate', False), pool=pool, host=host)
    wait_for_tasks(si, [task])
    if task.info.state == 'success':
        return {
            'ContentsFormat': formats['json'],
            'Type': entryTypes['note'],
            'Contents': {},
            'ReadableContentsFormat': formats['text'],
            'HumanReadable': 'Virtual Machine was registered successfully.',
            'EntryContext': {}
        }
    elif task.info.state == 'error':
        raise Exception('Error occurred while trying to register VM.')


def unregister_vm(si, args):
    vm = get_vm(si, args.get('uuid'))
    vm.UnregisterVM()
    return {
        'ContentsFormat': formats['json'],
        'Type': entryTypes['note'],
        'Contents': {},
        'ReadableContentsFormat': formats['text'],
        'HumanReadable': 'Virtual Machine was unregistered successfully.',
        'EntryContext': {}
    }


def main():  # pragma: no cover
    sout = sys.stdout
    sys.stdout = StringIO()
    res = []
    si = None
    vsphere_client = None
    try:
        si, vsphere_client = login(demisto.params())

        if demisto.command() == 'test-module':
            result = 'ok'
        if demisto.command() == 'vmware-get-vms':
            result = get_vms(si, demisto.args())
        if demisto.command() == 'vmware-poweron':
            result = power_on(si, demisto.args()['vm-uuid'])
        if demisto.command() == 'vmware-poweroff':
            result = power_off(si, demisto.args()['vm-uuid'])
        if demisto.command() == 'vmware-hard-reboot':
            result = hard_reboot(si, demisto.args()['vm-uuid'])
        if demisto.command() == 'vmware-suspend':
            result = suspend(si, demisto.args()['vm-uuid'])
        if demisto.command() == 'vmware-soft-reboot':
            result = soft_reboot(si, demisto.args()['vm-uuid'])
        if demisto.command() == 'vmware-create-snapshot':
            result = create_snapshot(si, demisto.args())
        if demisto.command() == 'vmware-revert-snapshot':
            result = revert_snapshot(si, demisto.args()['snapshot-name'], demisto.args()['vm-uuid'])
        if demisto.command() == 'vmware-get-events':
            result = get_events(si, demisto.args())
        if demisto.command() == 'vmware-change-nic-state':
            result = change_nic_state(si, demisto.args())
        if demisto.command() == 'vmware-list-vms-by-tag':
            result = list_vms_by_tag(vsphere_client, demisto.args())
        if demisto.command() == 'vmware-create-vm':
            result = create_vm(si, demisto.args())
        if demisto.command() == 'vmware-clone-vm':
            result = clone_vm(si, demisto.args())
        if demisto.command() == 'vmware-relocate-vm':
            result = relocate_vm(si, demisto.args())
        if demisto.command() == 'vmware-delete-vm':
            result = delete_vm(si, demisto.args())
        if demisto.command() == 'vmware-register-vm':
            result = register_vm(si, demisto.args())
        if demisto.command() == 'vmware-unregister-vm':
            result = unregister_vm(si, demisto.args())
        res.append(result)
    except Exception as ex:
        res.append(
            {"Type": entryTypes["error"], "ContentsFormat": formats["text"], "Contents": str(ex)})  # type: ignore

    try:
        logout(si)
    except Exception as ex:
        res.append({  # type: ignore
            "Type": entryTypes["error"], "ContentsFormat": formats["text"], "Contents": "Logout failed. " + str(ex)})

    sys.stdout = sout
    demisto.results(res)


if __name__ in ('__main__', '__builtin__', 'builtins'):
    main()
