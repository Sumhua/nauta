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

import re
import sre_constants

from collections import namedtuple
from enum import Enum
from functools import partial
from typing import List, Dict

from kubernetes import client
from kubernetes.client import CustomObjectsApi
from marshmallow import Schema, fields, post_load, validates
from marshmallow_enum import EnumField

from cli_text_consts import PlatformResourcesExperimentsTexts as Texts
from platform_resources.custom_object_meta_model import validate_kubernetes_name
from platform_resources.platform_resource import PlatformResource, KubernetesObjectSchema, KubernetesObject, \
    PlatformResourceApiClient
from platform_resources.resource_filters import filter_by_name_regex, filter_by_state
from platform_resources.run import Run, RunKinds, filter_by_run_kinds
from util.exceptions import InvalidRegularExpressionError
from util.logger import initialize_logger
from util.system import format_timestamp_for_cli

logger = initialize_logger(__name__)

class ExperimentStatus(Enum):
    CREATING = 'CREATING'
    SUBMITTED = 'SUBMITTED'
    FAILED = 'FAILED'
    CANCELLING = 'CANCELLING'
    CANCELLED = 'CANCELLED'


class ExperimentSchema(Schema):
    name = fields.String(required=True, allow_none=False)
    parameters_spec = fields.List(fields.String, required=False, missing=None, allow_none=True,
                                  dump_to='parameters-spec', load_from='parameters-spec')
    state = EnumField(ExperimentStatus, required=True, allow_none=False, by_value=True)
    template_name = fields.String(required=True, allow_none=False, dump_to='template-name', load_from='template-name')
    template_namespace = fields.String(required=True, allow_none=False, dump_to='template-namespace',
                                       load_from='template-namespace')

    @post_load
    def make_experiment(self, data):
        return Experiment(**data)

    @validates('name')
    def validate_name(self, name: str):
        validate_kubernetes_name(name)


class ExperimentKubernetesSchema(KubernetesObjectSchema):
    spec = fields.Nested(ExperimentSchema(), required=True, allow_none=False)
    

class Experiment(PlatformResource):
    api_group_name = 'aipg.intel.com'
    crd_plural_name = 'experiments'
    crd_version = 'v1'

    ExperimentCliModel = namedtuple('Experiment', ['name', 'parameters_spec', 'creation_timestamp', 'submitter',
                                                   'status', 'template_name'])

    def __init__(self, name: str, template_name: str, template_namespace: str, parameters_spec: List[str]=None,
                 state: ExperimentStatus=ExperimentStatus.CREATING, creation_timestamp: str = None,
                 namespace: str = None, metadata: dict = None):
        super().__init__()
        self.name = name
        self.parameters_spec = parameters_spec
        self.state = state
        self.template_name = template_name
        self.template_namespace = template_namespace
        self.creation_timestamp = creation_timestamp
        self.namespace = namespace
        self.metadata = metadata

    @classmethod
    def from_k8s_response_dict(cls, object_dict: dict):
        return cls(name=object_dict['spec']['name'],
                   parameters_spec=object_dict['spec']['parameters-spec'],
                   creation_timestamp=object_dict['metadata']['creationTimestamp'],
                   namespace=object_dict['metadata']['namespace'],
                   state=ExperimentStatus[object_dict['spec']['state']],
                   template_name=object_dict['spec']['template-name'],
                   template_namespace=object_dict['spec']['template-namespace'],
                   metadata=object_dict['metadata'])

    @property
    def cli_representation(self):
        return Experiment.ExperimentCliModel(name=self.name, parameters_spec=' '.join(self.parameters_spec),
                                             creation_timestamp=format_timestamp_for_cli(self.creation_timestamp),
                                             submitter=self.namespace, status=self.state.value,
                                             template_name=self.template_name)


    def get_runs(self) -> List[Run]:
        return Run.list(namespace=self.metadata['namespace'], exp_name_filter=[self.name])

    def create(self, namespace: str, labels: Dict[str, str] = None,
               annotations: Dict[str, str] = None):
        # exclude labels with None values - labels won't be correctly added otherwise
        labels = {key: value for key, value in labels.items() if value} if labels else None

        exp_kubernetes = KubernetesObject(self, client.V1ObjectMeta(name=self.name, namespace=namespace, labels=labels),
                                          kind="Experiment", apiVersion=f"{self.api_group_name}/{self.crd_version}")
        schema = ExperimentKubernetesSchema()
        body, err = schema.dump(exp_kubernetes)
        if err:
            raise RuntimeError(Texts.K8S_DUMP_PREPARATION_ERROR_MSG.format(err=err))
        self.body = body

        response = super().create(namespace=namespace)
        created_exp, err = schema.load(response)
        if err:
            raise RuntimeError(Texts.K8S_RESPONSE_LOAD_ERROR_MSG.format(err=err))
        return created_exp

    def update(self):
        exp_kubernetes = KubernetesObject(self, client.V1ObjectMeta(name=self.name,
                                                                    namespace=self.namespace),
                                          kind="Experiment", apiVersion=f"{self.api_group_name}/{self.crd_version}")
        schema = ExperimentKubernetesSchema()
        body, err = schema.dump(exp_kubernetes)
        if err:
            raise RuntimeError(Texts.K8S_DUMP_PREPARATION_ERROR_MSG.format(err=err))
        self.body = body

        response = super().update()
        updated_exp, err = schema.load(response)
        if err:
            raise RuntimeError(Texts.K8S_RESPONSE_LOAD_ERROR_MSG.format(err=err))
        return updated_exp

    @classmethod
    def list(cls, namespace: str = None, state: ExperimentStatus = None, run_kinds_filter : List[RunKinds] = None,
             name_filter: str = None, custom_objects_api: CustomObjectsApi = None, label_selector: str = ""):
        """
        Return list of experiments.
        :param namespace: If provided, only experiments from this namespace will be returned
        :param state: If provided, only experiments with given state will be returned
        :param name_filter: If provided, only experiments matching name_filter regular expression will be returned
        :param run_kinds_filter: If provided, only experiments with a kind that matches to any of the run kinds
         from given  filtering list will be returned
        :param str label_selector: A selector to restrict the list of returned objects by their labels.
         Defaults to everything.
        :return: List of Experiment objects
        """
        logger.debug('Listing experiments.')
        raw_experiments = cls.list_raw_experiments(namespace=namespace, label_selector=label_selector)
        try:
            name_regex = re.compile(name_filter) if name_filter else None
        except sre_constants.error as e:
            error_msg = Texts.REGEX_COMPILATION_FAIL_MSG.format(name_filter=name_filter)
            logger.exception(error_msg)
            raise InvalidRegularExpressionError(error_msg) from e

        experiment_filters = [partial(filter_by_name_regex, name_regex=name_regex),
                              partial(filter_by_state, state=state),
                              partial(filter_by_run_kinds, run_kinds=run_kinds_filter)]

        experiments = [Experiment.from_k8s_response_dict(experiment_dict)
                       for experiment_dict in raw_experiments['items']
                       if all(f(experiment_dict) for f in experiment_filters)]

        return experiments

    @classmethod
    def list_raw_experiments(cls, namespace: str = None, label_selector: str = "",
                             custom_objects_api: CustomObjectsApi = None) -> dict:
        """
        Return raw list of experiments.
        :param namespace: If provided, only experiments from this namespace will be returned
        :param str label_selector: A selector to restrict the list of returned objects by their labels.
         Defaults to everything.
        """
        k8s_custom_object_api = custom_objects_api if custom_objects_api else PlatformResourceApiClient.get()
        if namespace:
            raw_experiments = k8s_custom_object_api.list_namespaced_custom_object(group=Experiment.api_group_name,
                                                                                  namespace=namespace,
                                                                                  plural=Experiment.crd_plural_name,
                                                                                  version=Experiment.crd_version,
                                                                                  label_selector=label_selector)
        else:
            raw_experiments = k8s_custom_object_api.list_cluster_custom_object(group=Experiment.api_group_name,
                                                                               plural=Experiment.crd_plural_name,
                                                                               version=Experiment.crd_version,
                                                                               label_selector=label_selector)
        return raw_experiments
