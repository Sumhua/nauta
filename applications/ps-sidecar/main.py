#
# INTEL CONFIDENTIAL
# Copyright (c) 2018 Intel Corporation
#
# The source code contained or described herein and all documents related to
# the source code ("Material") are owned by Intel Corporation or its suppliers
# or licensors. Title to the Material remains with Intel Corporation or its
# suppliers and licensors. The Material contains trade secrets and proprietary
# and confidential information of Intel or its suppliers and licensors. The
# Material is protected by worldwide copyright and trade secret laws and treaty
# provisions. No part of the Material may be used, copied, reproduced, modified,
# published, uploaded, posted, transmitted, distributed, or disclosed in any way
# without Intel's prior express written permission.
#
# No license under any patent, copyright, trade secret or other intellectual
# property right is granted to or conferred upon you by disclosure or delivery
# of the Materials, either expressly, by implication, inducement, estoppel or
# otherwise. Any license under such intellectual property rights must be express
# and approved by Intel in writing.
#

import logging as log
from os import getenv
from sys import exit
from time import sleep

from kubernetes import client, config
from kubernetes.client import V1Pod, V1ObjectMeta

log.basicConfig(level=log.DEBUG)

config.load_incluster_config()

my_pod_name = getenv("MY_POD_NAME")

if my_pod_name is None:
    raise RuntimeError("MY_POD_NAME env var is not defined!")

with open("/var/run/secrets/kubernetes.io/serviceaccount/namespace", mode='r') as file:
    my_current_namespace = file.read()

if not my_current_namespace:
    raise RuntimeError(f"error reading my current namespace {str(my_current_namespace)}")


v1 = client.CoreV1Api()

my_pod: V1Pod = v1.read_namespaced_pod(name=my_pod_name, namespace=my_current_namespace)

my_pod_metadata: V1ObjectMeta = my_pod.metadata

try:
    my_tfjob_name = my_pod_metadata.owner_references[0].name
except IndexError:
    raise RuntimeError("couldn't read my pod tf_job_key - no owner reference!")

if my_tfjob_name is None or my_tfjob_name == "":
    raise RuntimeError("my_tfjob_name is not defined!")


coAPI = client.CustomObjectsApi()

log.info("initialization succeeded")

while True:
    log.info(f"fetching tfjob: {my_tfjob_name} ...")
    my_tfjob = coAPI.get_namespaced_custom_object(group="kubeflow.org",
                                                  version="v1alpha2",
                                                  namespace=my_current_namespace,
                                                  plural="tfjobs",
                                                  name=my_tfjob_name)

    workers_statuses = my_tfjob["status"]["tfReplicaStatuses"]["Worker"]

    active_workers = workers_statuses.get("active", 0)
    succeeded_workers = workers_statuses.get("succeeded", 0)

    log.info(f"active workers: {active_workers}")

    if active_workers == 0 and succeeded_workers > 0:
        log.info("active workers == 0 and succeeded_workers > 0, creating END hook")
        open("/pod-data/END", 'a').close()
        log.info("exiting...")
        exit(0)

    sleep(1)