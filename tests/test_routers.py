from __future__ import annotations

from pprint import pprint

from starlette.testclient import TestClient
from typing import Union, Dict

import pytest
from fastapi import FastAPI
from pydantic import BaseModel
from returns.result import Result, Success, Failure

from lib.router import ErrorHandlingRouter, ApiError

router = ErrorHandlingRouter()


class DummyResultModel(BaseModel):
    some_field: str


# TODO prevent using multiple errors with the same status code in single endpoint
class DummyErrorA(ApiError):
    status_code = 400
    details = "some message"


class DummyErrorB(ApiError):
    status_code = 401
    details = "some other message"


DUMMY_VIEW_URL = "/some_get_endpoint/{result_number}"


@router.get(DUMMY_VIEW_URL)
def dummy_view(result_number: int) -> Result[DummyResultModel, Union[DummyErrorA, DummyErrorB]]:
    if result_number == 1:
        return Success(DummyResultModel(some_field="some value"))
    elif result_number == 2:
        return Failure(DummyErrorA())
    else:
        return Failure(DummyErrorB())


@pytest.fixture()
def app() -> FastAPI:
    _app = FastAPI()
    _app.include_router(router)
    return _app


@pytest.fixture()
def api_client(app: FastAPI) -> TestClient:
    return TestClient(app)


class TestRouter:
    @pytest.mark.parametrize(
        "result_number, expected_status_code, expected_result", (
                (1, 200, {'some_field': 'some value'}),
                (2, 400, {'detail': 'some message'}),
                (3, 401, {'detail': 'some other message'}),
    ))
    def test_returns_expected_response(
        self, api_client: TestClient, result_number: int, expected_status_code: int, expected_result: Dict
    ) -> None:
        # given

        # when
        response = api_client.get(DUMMY_VIEW_URL.format(result_number=result_number))

        # then
        assert response.status_code == expected_status_code, response.json()
        assert response.json() == expected_result

    def test_openapi_schema_contains_all_possible_results_documentation(
            self, api_client: TestClient) -> None:
        # given

        # when
        response1 = api_client.get(f"/openapi.json")

        resp_json = response1.json()
        # then
        assert resp_json["paths"][DUMMY_VIEW_URL]["get"]["responses"] == {'200': {'description': 'Successful Response', 'content': {'application/json': {'schema': {'$ref': '#/components/schemas/DummyResultModel'}}}}, '400': {'description': 'Bad Request', 'content': {'application/json': {'schema': {'title': 'Response 400 Dummy View Some Get Endpoint  Result Number  Get', 'type': 'string'}}}}, '401': {'description': 'Unauthorized', 'content': {'application/json': {'schema': {'title': 'Response 401 Dummy View Some Get Endpoint  Result Number  Get', 'type': 'string'}}}}, '422': {'description': 'Validation Error', 'content': {'application/json': {'schema': {'$ref': '#/components/schemas/HTTPValidationError'}}}}}
