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

from enum import Enum
from typing import Pattern, List


def filter_by_name_regex(resource_object_dict: dict, name_regex: Pattern = None, spec_location: bool = True):
    if spec_location:
        rod = resource_object_dict['spec']['name']
    else:
        rod = resource_object_dict['metadata']['name']

    return name_regex.search(rod) if name_regex else True


def filter_by_state(resource_object_dict: dict, state: Enum = None):
    return resource_object_dict['spec']['state'] == state.value if state else True


def filter_by_excl_state(resource_object_dict: dict, state: Enum = None):
    return resource_object_dict['spec']['state'] != state.value if state else True


def filter_by_experiment_name(resource_object_dict: dict, exp_name: List[str] = None):
    return resource_object_dict['spec']['experiment-name'] in exp_name if exp_name else True


