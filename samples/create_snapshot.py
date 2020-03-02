# Copyright 2015 Michael Rice <michael@michaelrice.org>
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

from __future__ import print_function

import atexit

import requests

import time

from pyVim.connect import SmartConnect, SmartConnectNoSSL, Disconnect

from tools import cli

requests.packages.urllib3.disable_warnings()

SNAPSHOT_LIMIT_SECONDS = 180

def setup_args():
    parser = cli.build_arg_parser()
    parser.add_argument('-j', '--uuid', required=True,
                        help="UUID of the VirtualMachine you want to find."
                             " If -i is not used BIOS UUID assumed.")
    parser.add_argument('-i', '--instance', required=False,
                        action='store_true',
                        help="Flag to indicate the UUID is an instance UUID")
    parser.add_argument('-d', '--description', required=False,
                        help="Description for the snapshot")
    parser.add_argument('-n', '--name', required=True,
                        help="Name for the Snapshot")
    parser.add_argument('-q', '--quiesce', required=False,
                        action='store_true',
                        help="Quiesce enabled for snapshot")
    parser.add_argument('-m', '--memory', required=False,
                        action='store_true',
                        help="Memory enabled for snapshot")
    my_args = parser.parse_args()
    return cli.prompt_for_password(my_args)


args = setup_args()
si = None
instance_search = False
try:
    if args.disable_ssl_verification:
        si = SmartConnectNoSSL(host=args.host,
                               user=args.user,
                               pwd=args.password,
                               port=int(args.port))
    else:
        si = SmartConnect(host=args.host,
                          user=args.user,
                          pwd=args.password,
                          port=int(args.port))

    atexit.register(Disconnect, si)
except IOError:
    pass

if not si:
    raise SystemExit("Unable to connect to host with supplied info.")
if args.instance:
    instance_search = True
vm = si.content.searchIndex.FindByUuid(None, args.uuid, True, instance_search)

if vm is None:
    raise SystemExit("Unable to locate VirtualMachine.")

desc = None
if args.description:
    desc = args.description

# memory and quiesce are mutually exclusive
quiesce_flag = False
memory_flag = False
if args.quiesce:
    quiesce_flag = True
else:
    if args.memory:
        memory_flag = True
        quiesce_flag = False

task = vm.CreateSnapshot_Task(name=args.name,
                              memory=memory_flag,
                              description=desc,
                              quiesce=quiesce_flag)

counter = 0
while task.info.state not in ['success','error'] and counter < SNAPSHOT_LIMIT_SECONDS:
    time.sleep(1)
    counter += 1
print("Snapshot final status after {0} seconds: {1}".format(counter, task.info.state))

del vm
vm = si.content.searchIndex.FindByUuid(None, args.uuid, True, instance_search)
# Enable a short delay or 3 seconds so the tree should include the current snapshot for fast snapshots
if counter < 10:
    time.sleep(3)
snap_info = vm.snapshot

if snap_info is not None:
    print("Existing snapshots:")
    tree = snap_info.rootSnapshotList
    while tree[0].childSnapshotList is not None:
        print("Snap: {0} => {1}".format(tree[0].name, tree[0].description))
        if len(tree[0].childSnapshotList) < 1:
            break
        tree = tree[0].childSnapshotList
else:
    print("No other snapshots currently exist. There was an error or the the snapshot happened too quickly to register.")
