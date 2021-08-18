import asyncio
import json
import pytest

from aiodocker.exceptions import DockerError
from aiodocker.utils import clean_map

# !!!WARNING !!!
# This test crashes dockerd, data may be lost.
# To recover, swarm must be reset :
#   rm -rf /var/lib/docker/swarm/* ;
#   systemctl reset-failed docker.service
#   systemctl stop docker
#   systemctl start docker
@pytest.mark.asyncio
async def test_service_wrapper_crash(swarm):
    TaskTemplate = {
        "ContainerSpec": {"Image": "alpine", "Args": "ping localhost".split()}
    }
    # create service
    service_name = "testcrash"
    service_id = (await swarm.services.create(task_template=TaskTemplate, name=service_name))["ID"]
    service = await swarm.services.inspect(service_id)

    # update service with a constraint
    constraint = ["node.role==manager"]
    service_spec = service["Spec"]
    service_spec["TaskTemplate"]["Placement"] = {}
    service_spec["TaskTemplate"]["Placement"]["Constraints"] = list(
        constraint
    )

    service_version = service["Version"]["Index"]
    update_params = {"version": service_version}
    update_data = json.dumps(clean_map(service_spec))
    
    await swarm._query_json(
        "services/{service_id}/update".format(service_id=service_id),
        method="POST",
        data=update_data,
        params=update_params,
    )

    # wait for service update
    for i in range(5 * 30):
        service = (await swarm.services.inspect(service_id))
        if "UpdateStatus" in service :
            if service["UpdateStatus"]["State"] in (
                "rollback_completed", "completed"
            ):
                break
        await asyncio.sleep(0.2)
            
    service_spec = service["Spec"]
    assert service_spec["TaskTemplate"]["Placement"]["Constraints"] == constraint

    # now rollback
    service_version = service["Version"]["Index"]
    await swarm.services.update(
        service_id, service_version, rollback=True
    )
