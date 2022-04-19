from requests_mock import Mocker

from accessdata.client import Client
from accessdata.api.extensions import (
    attribute_list_ext,
    case_create_ext,
    case_list_ext,
    evidence_list_ext,
    evidence_process_ext,
    export_natives_ext,
    job_status_ext,
    label_create_ext,
    label_list_ext,
    server_setting_ext,
    status_check_ext
)

from AccessdataV2 import (
    _create_case,
    _create_filter,
    _export_natives,
    _get_case_by_name,
    _get_job_status,
    _label_search_term,
    _process_evidence
)

API_URL = "http://randomurl.com/"
API_KEY = "API-TEST-KEY"


def generate_mock_client():
    """Creates a mock client using falsified
    information.

    :return: Client
    """

    with Mocker() as mocker:
        mocker.get(
            API_URL + status_check_ext[1],
            status_code=200,
            json="Ok"
        )
        client = Client(API_URL, API_KEY)

    return client


def test_mock_client():
    """Tests the client generator."""
    client = generate_mock_client()

    assert client.session.status_code == 200

    assert client.session.headers == {
        "EnterpriseApiKey": API_KEY
    }


def test_mock_case_list():
    """Tests the case list getter."""
    client = generate_mock_client()

    with Mocker() as mocker:
        mocker.get(
            API_URL + case_list_ext[1],
            status_code=200,
            json=[
                {
                    "id": 1,
                    "name": "Test Case",
                    "casepath": "\\\\FTKC\\Cases\\Test Case"
                }
            ]
        )
        mocker.get(
            API_URL + attribute_list_ext[1],
            status_code=200,
            json=[]
        )
        mocker.get(
            API_URL + server_setting_ext[1].format(setting="FTKDefaultPath"),
            status_code=200,
            json="\\\\FTKC\\Cases"
        )

        cases = client.cases

        assert len(cases) == 1

        results = _get_case_by_name(client, "Test Case")
        outputs = results.outputs

        assert outputs.get("ID") == 1
        assert outputs.get("Name") == "Test Case"


def test_mock_create_case():
    """Tests the case creation tool."""
    client = generate_mock_client()

    with Mocker() as mocker:
        mocker.get(
            API_URL + case_create_ext[1],
            status_code=200,
            json=1
        )
        mocker.get(
            API_URL + attribute_list_ext[1],
            status_code=200,
            json=[]
        )
        mocker.get(
            API_URL + server_setting_ext[1].format(setting="FTKDefaultPath"),
            status_code=200,
            json="\\\\FTKC\\Cases"
        )

        results = _create_case(client, name="Test Case")
        outputs = results.outputs

        assert outputs.get("ID") == 1
        assert outputs.get("Name") == "Test Case"


def test_mock_process_evidence():
    """Tests the evidence process instantiation."""
    client = generate_mock_client()

    with Mocker() as mocker:
        mocker.get(
            API_URL + job_status_ext[1].format(caseid=1, jobid=1),
            status_code=200,
            json=[
                {
                    "id": 1,
                    "state": 1,
                    "resultData": "{}"
                }
            ]
        )
        mocker.get(
            API_URL + evidence_process_ext[1].format(caseid=1),
            status_code=200,
            json=1
        )
        mocker.get(
            API_URL + attribute_list_ext[1],
            status_code=200,
            json=[]
        )
        mocker.get(
            API_URL + server_setting_ext[1].format(setting="FTKDefaultPath"),
            status_code=200,
            json="\\\\FTKC\\Cases"
        )

        results = _process_evidence(client, 1, "\\\\FTKC\\Evidence\\Test Evidence.ad1", 1)
        outputs = results.outputs

        assert outputs.get("ID") == 1
        assert outputs.get("State") == "JobState.InProgress"
        assert outputs.get("ResultData") == "{}"


def test_mock_export_natives():
    """Tests the export natives construct from evidence."""
    client = generate_mock_client()

    with Mocker() as mocker:
        mocker.get(
            API_URL + job_status_ext[1].format(caseid=1, jobid=1),
            status_code=200,
            json=[
                {
                    "id": 1,
                    "state": 1,
                    "resultData": "{}"
                }
            ]
        )
        mocker.get(
            API_URL + evidence_list_ext[1].format(caseid=1),
            status_code=200,
            json=[]
        )
        mocker.get(
            API_URL + export_natives_ext[1].format(caseid=1),
            status_code=200,
            json=1
        )
        mocker.get(
            API_URL + attribute_list_ext[1],
            status_code=200,
            json=[]
        )
        mocker.get(
            API_URL + server_setting_ext[1].format(setting="FTKDefaultPath"),
            status_code=200,
            json="\\\\FTKC\\Cases"
        )

        results = _export_natives(client, 1, "\\\\FTKC\\Export", {})
        outputs = results.outputs

        assert outputs.get("ID") == 1
        assert outputs.get("State") == "JobState.InProgress"
        assert outputs.get("ResultData") == "{}"


def test_mock_search_keywords():
    """Tests the keyword searching functionality."""
    client = generate_mock_client()

    with Mocker() as mocker:
        mocker.get(
            API_URL + job_status_ext[1].format(caseid=1, jobid=1),
            status_code=200,
            json=[
                {
                    "id": 1,
                    "state": 1,
                    "resultData": "{}"
                }
            ]
        )
        mocker.get(
            API_URL + label_create_ext[1].format(caseid=1),
            status_code=200,
            json=1
        )
        mocker.get(
            API_URL + label_list_ext[1].format(caseid=1),
            status_code=200,
            json=[]
        )
        mocker.get(
            API_URL + search_report_ext[1].format(caseid=1),
            status_code=200,
            json=1
        )
        mocker.get(
            API_URL + attribute_list_ext[1],
            status_code=200,
            json=[]
        )
        mocker.get(
            API_URL + server_setting_ext[1].format(setting="FTKDefaultPath"),
            status_code=200,
            json="\\\\FTKC\\Cases"
        )

        results = _label_search_term(client, 1, "test", {})
        outputs = results.outputs

        assert outputs.get("Name") == "test"


def test_mock_job_status():
    """Tests the job status retrieval."""
    client = generate_mock_client()

    with Mocker() as mocker:
        mocker.get(
            API_URL + job_status_ext[1].format(caseid=1, jobid=1),
            status_code=200,
            json=[
                {
                    "id": 1,
                    "state": 1,
                    "resultData": "{}"
                }
            ]
        )
        mocker.get(
            API_URL + attribute_list_ext[1],
            status_code=200,
            json=[]
        )
        mocker.get(
            API_URL + server_setting_ext[1].format(setting="FTKDefaultPath"),
            status_code=200,
            json="\\\\FTKC\\Cases"
        )

        results = _get_job_status(client, 1, 1)
        outputs = results.outputs

        assert outputs.get("JobID") == 1
        assert outputs.get("State") == "JobState.InProgress"
        assert outputs.get("ResultData") == "{}"


def test_mock_create_filter():
    """Tests the attribute filter creation."""
    client = generate_mock_client()

    with Mocker() as mocker:
        mocker.get(
            API_URL + attribute_list_ext[1],
            status_code=200,
            json=[
                {
                    "attributeUniqueName": "AccessMask",
                    "isColumnSetMember": False,
                    "description": "",
                    "displayName": "AccessMask",
                    "dataType": 7,
                    "productType": 200,
                    "isSystemField": False,
                    "isReadOnly": True,
                    "isGridEditable": False,
                    "isCustomField": False,
                    "isMappable": False,
                    "isFilterable": False,
                    "isBurnable": False,
                    "isAutoTextField": False,
                    "uiLayout": 0,
                    "isDefault": False,
                    "multiLine": None,
                    "maxLength": -1,
                    "isCategory": False,
                    "hasMetaDataValue": False,
                    "isVirtual": False,
                    "isLookup": False,
                    "isViewable": True,
                    "columnID": 10502,
                    "isProducable": False,
                    "state": 3,
                    "id": 161,
                    "lastModifiedDate": None,
                    "lastModifiedBy": None,
                    "hasSeqID": False,
                    "columnGUID": "00000000-0001-0000-fb38-080e06290000",
                    "columnClass": 0
                }
            ]
        )
        mocker.get(
            API_URL + server_setting_ext[1].format(setting="FTKDefaultPath"),
            status_code=200,
            json="\\\\FTKC\\Cases"
        )

        results = _create_filter(client, "AccessMask", "==", 1)
        outputs = results.outputs

        assert len(outputs.get("Filter")) > 1