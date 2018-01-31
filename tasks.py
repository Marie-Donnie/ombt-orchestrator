from abc import ABCMeta, abstractmethod
from enoslib.api import run_ansible, generate_inventory, emulate_network, validate_network
from enoslib.task import enostask
from enoslib.infra.enos_chameleonkvm.provider import Chameleonkvm
from enoslib.infra.enos_g5k.provider import G5k
from enoslib.infra.enos_vagrant.provider import Enos_vagrant
from qpid_generator.graph import generate
from qpid_generator.distribute import round_robin
from qpid_generator.configurations import get_conf

import os
import yaml

BROKER="qdr"

# DEFAULT PARAMETERS
NBR_CLIENTS=1
NBR_SERVERS=1
CALL_TYPE="rpc-call"
NBR_CALLS="100"
PAUSE=0
TIMEOUT=60
VERSION="beyondtheclouds/ombt:latest"
BACKUP_DIR="backup"
LENGTH="1024"
EXECUTOR="threading"


tc = {
    "enable": True,
    "default_delay": "20ms",
    "default_rate": "1gbit",
}

# The two following tasks are exclusive either you choose to go with g5k or
# vagrant you can't mix the two of them in the future we might want to
# factorize it and have a switch on the command line to choose.
@enostask(new=True)
def g5k(env=None, force=False, config=None,  **kwargs):
    provider = G5k(config["g5k"])
    roles, networks = provider.init(force_deploy=force)
    env["config"] = config
    env["roles"] = roles
    env["networks"] = networks


@enostask()
def inventory(env=None, **kwargs):
    roles = env["roles"]
    networks = env["networks"]
    env["inventory"] = os.path.join(env["resultdir"], "hosts")
    generate_inventory(roles, networks, env["inventory"] , check_networks=True)


@enostask()
def prepare(env=None, **kwargs):
    # Generate inventory
    extra_vars = {
        "registry": env["config"]["registry"]
    }
    # Preparing the installation of the bus under evaluation
    # Need to pass specific options
    # We generate a configuration dict that captures the minimal set of
    # parameters of each agents of the bus
    # This configuration dict is used in subsequent test* tasks to configure the
    # ombt agents.
    roles = env["roles"]
    # Get the specific configuration from the file
    config = env["config"]

    # use deploy of each role
    extra_vars.update({"enos_action": "deploy"})

    # Finally let's give ansible the bus_conf
    if config:
        extra_vars.update(config)

    run_ansible(["ansible/site.yml"], env["inventory"], extra_vars=extra_vars)


@enostask()
def test_case_1(
    nbr_clients=NBR_CLIENTS,
    nbr_servers=NBR_SERVERS,
    call_type=CALL_TYPE,
    nbr_calls=NBR_CALLS,
    pause=PAUSE,
    timeout=TIMEOUT,
    version=VERSION,
    backup_dir=BACKUP_DIR,
    length=LENGTH,
    executor=EXECUTOR,
    env=None, **kwargs):

    iteration_id = str("-".join([
        "nbr_servers__%s" % nbr_servers,
        "nbr_clients__%s" % nbr_clients,
        "call_type__%s" % call_type,
        "nbr_calls__%s" % nbr_calls,
        "pause__%s" % pause]))

    # Create the backup dir for this experiment
    # NOTE(msimonin): We don't need to identify the backup dir we could use a
    # dedicated env name for that
    backup_dir = os.path.join(os.getcwd(), "current/%s" % backup_dir)
    os.system("mkdir -p %s" % backup_dir)
    extra_vars = {
        "backup_dir": backup_dir,
    }

    descs = []

    run_ansible(["ansible/test_case_1.yml"], env["inventory"], extra_vars=extra_vars)


@enostask()
def emulate(env=None, **kwargs):
    inventory = env["inventory"]
    roles = env["roles"]
    emulate_network(roles, inventory, tc)


@enostask()
def validate(env=None, **kwargs):
    inventory = env["inventory"]
    roles = env["roles"]
    validate_network(roles, inventory)


@enostask()
def backup(env=None, **kwargs):
    extra_vars = {
        "enos_action": "backup",
        "backup_dir": os.path.join(os.getcwd(), "current")
    }
    run_ansible(["ansible/site.yml"], env["inventory"], extra_vars=extra_vars)


@enostask()
def destroy(env=None, **kwargs):
    extra_vars = {}
    # Call destroy on each component
    extra_vars.update({
        "enos_action": "destroy"
    })
    run_ansible(["ansible/site.yml"], env["inventory"], extra_vars=extra_vars)
