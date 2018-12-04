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

import pytest

from kubernetes.client import CustomObjectsApi

from platform_resources.user import User, UserStatus
from platform_resources.user_utils import validate_user_name, is_user_created
from cli_text_consts import PlatformResourcesUsersTexts as Texts


TEST_USERS = [User(name='test-dev', uid=1, state=UserStatus.DEFINED,
                   creation_timestamp='2018-05-17T12:49:04Z',
                   experiment_runs=[]),
              User(name='test-user', uid=100,
                   state=UserStatus.DEFINED, creation_timestamp='2018-05-17T11:42:22Z',
                   experiment_runs=[])]

USER_CREATED = User(name='user-created', uid=1, state=UserStatus.CREATED,
                   creation_timestamp='2018-05-17T12:49:04Z',
                   experiment_runs=[])

@pytest.fixture()
def mock_k8s_api_client(mocker) -> CustomObjectsApi:
    mocker.patch('kubernetes.config.load_kube_config')
    mocker.patch('kubernetes.client.ApiClient')
    custom_objects_api_mocked_class = mocker.patch('platform_resources.platform_resource.PlatformResourceApiClient.get')
    return custom_objects_api_mocked_class.return_value


def test_list_users(mock_k8s_api_client, mocker):
    mocker.patch('platform_resources.user.Run.list')
    mock_k8s_api_client.list_cluster_custom_object.return_value = LIST_USERS_RESPONSE_RAW
    users = User.list()
    assert users == TEST_USERS


LIST_USERS_RESPONSE_RAW = {'apiVersion': 'aipg.intel.com/v1',
                           'items': [
                               {'apiVersion': 'aipg.intel.com/v1',
                                'kind': 'User',
                                'metadata': {'annotations':
                                                 {
                                                     'kubectl.kubernetes.io/last-applied-configuration':
                                                         '{"apiVersion":"aipg.intel.com/v1","kind":'
                                                         '"User",'
                                                         '"metadata":{"annotations":{},"name":"test-dev","namespace":""},'
                                                         '"spec":{"password":"bla","state":"DEFINED","uid":1}}\n'},
                                             'clusterName': '', 'creationTimestamp': '2018-05-17T12:49:04Z',
                                             'generation': 1, 'name': 'test-dev', 'namespace': '',
                                             'resourceVersion': '429638',
                                             'selfLink': '/apis/aipg.intel.com/v1/users/test-dev',
                                             'uid': 'ae1a69e8-59d0-11e8-b5db-527100001250'},
                                'spec': {'password': 'bla', 'state': 'DEFINED', 'uid': 1}},
                               {'apiVersion': 'aipg.intel.com/v1', 'kind': 'User',
                                'metadata': {'annotations': {
                                   'kubectl.kubernetes.io/last-applied-configuration':
                                       '{"apiVersion":"aipg.intel.com/v1",'
                                        '"kind":"User",'
                                        '"metadata":{"annotations":{},"name":"test-user","namespace":""},'
                                        '"spec":{"password":"bla","state":"DEFINED","uid":100}}\n'},
                                                 'clusterName': '',
                                                 'creationTimestamp': '2018-05-17T11:42:22Z',
                                                 'generation': 1,
                                                 'name': 'test-user',
                                                 'namespace': '',
                                                 'resourceVersion': '424142',
                                                 'selfLink': '/apis/aipg.intel.com/v1/users/test-user',
                                                 'uid': '5d13e21f-59c7-11e8-b5db-527100001250'},
                                'spec': {'password': 'bla', 'state': 'DEFINED', 'uid': 100}}], 'kind': 'UserList',
                           'metadata': {'continue': '', 'resourceVersion': '434920',
                                        'selfLink': '/apis/aipg.intel.com/v1/users'}}


def test_get_user_data(mock_k8s_api_client, mocker):
    mock_k8s_api_client.get_cluster_custom_object.return_value = LIST_USERS_RESPONSE_RAW["items"][0]

    user = User.get("user_name")
    assert user == TEST_USERS[0]


def test_validate_user_name_too_short():
    username = ""
    with pytest.raises(ValueError) as exe:
        validate_user_name(username)
    assert str(exe.value) == Texts.USERNAME_CANNOT_BE_EMPTY_ERROR_MSG


def test_validate_user_name_too_long():
    username = "a"*33
    with pytest.raises(ValueError) as exe:
        validate_user_name(username)
    assert str(exe.value) == Texts.USERNAME_TOO_LONG_ERROR_MSG


def test_validate_user_name_incorrect_k8s_string():
    username = "aBBcd.=-"
    with pytest.raises(ValueError) as exe:
        validate_user_name(username)
    assert str(exe.value) == Texts.INCORRECT_K8S_USERNAME_ERROR_MSG


def test_is_user_created_success(mocker):
    gud_mock = mocker.patch("platform_resources.user.User.get", return_value = USER_CREATED)
    result = is_user_created("test_user", timeout=10)

    assert result
    assert gud_mock.call_count == 1


def test_is_user_created_failure(mocker):
    gud_mock = mocker.patch("platform_resources.user.User.get", return_value = TEST_USERS[0])
    result = is_user_created("test_user", timeout=1)

    assert not result
    assert gud_mock.call_count == 2


def test_is_user_created_success_with_wait(mocker):
    gud_mock = mocker.patch("platform_resources.user.User.get", side_effect = [TEST_USERS[0], USER_CREATED])
    result = is_user_created("test_user", timeout=1)

    assert result
    assert gud_mock.call_count == 2
