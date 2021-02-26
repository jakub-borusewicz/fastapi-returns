from __future__ import annotations

from random import random

from typing import Any, ClassVar, Dict, Union

import pytest
from fastapi import FastAPI
from pydantic import BaseModel
from returns.result import Failure, Result, Success
from starlette import status
from starlette.testclient import TestClient

from lib.router import ApiError, ErrorDetails, ErrorHandlingRouter

router = ErrorHandlingRouter()


class DummyResultModelA(BaseModel):
    some_field: str


class DummyResultModelB(BaseModel):
    some_other_field: str


class DummyErrorResultModel(BaseModel):
    some_error_msg: str


# TODO prevent using multiple errors with the same status code in single endpoint
class DummyErrorA(ApiError):
    status_code = 400
    details = ErrorDetails(message="some message")


class DummyErrorB(ApiError):
    status_code = 401
    details = ErrorDetails(message="some other message")


class InvalidException(Exception):
    ...


DUMMY_VIEW_URL = "/some_get_endpoint/{result_number}"


@router.get(DUMMY_VIEW_URL)
def dummy_view(result_number: int) -> Result[DummyResultModelA, Union[DummyErrorA, DummyErrorB]]:
    if result_number == 1:
        return Success(DummyResultModelA(some_field="some value"))
    elif result_number == 2:
        return Failure(DummyErrorA())
    else:
        return Failure(DummyErrorB())


DUMMY_STANDARD_VIEW_URL = "/standard_view"


@router.get(DUMMY_STANDARD_VIEW_URL, responses={"404": {"model": DummyErrorResultModel}})
def dummy_standard_view() -> DummyResultModelA:
    return DummyResultModelA(some_field="some value")


@pytest.fixture()
def app() -> FastAPI:
    _app = FastAPI()
    _app.include_router(router)
    return _app


@pytest.fixture()
def api_client(app: FastAPI) -> TestClient:
    return TestClient(app)


class _ExpectedResponseItem(BaseModel):
    status_code: int
    description: str
    content: Dict[str, Any]


class _ExpectedErrorResponseItem(_ExpectedResponseItem):
    content: Dict[str, Any] = {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorDetails"}}}


def _get_expected_responses(
    *resp_items: _ExpectedResponseItem, include_validation_error: bool = True
) -> Dict[str, Any]:
    responses = {str(resp_item.status_code): resp_item.dict(exclude={"status_code"}) for resp_item in resp_items}

    if include_validation_error:
        responses["422"] = {
            "description": "Validation Error",
            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/HTTPValidationError"}}},
        }
    return responses


class TestRouter:
    class BaseDummyViewTest:
        URL: ClassVar[str]
        EXPECTED_RESPONSES: ClassVar[Dict[str, Any]]

        def test_openapi_json_is_correct(self, api_client: TestClient) -> None:
            # given

            # when
            response = api_client.get("/openapi.json")

            # then
            assert response.status_code == status.HTTP_200_OK
            resp_json = response.json()
            assert resp_json["paths"][self.URL]["get"]["responses"] == self.EXPECTED_RESPONSES

    class TestDummyView(BaseDummyViewTest):
        URL = DUMMY_VIEW_URL
        EXPECTED_RESPONSES = _get_expected_responses(
            _ExpectedResponseItem(
                status_code=status.HTTP_200_OK,
                description="Successful Response",
                content={"application/json": {"schema": {"$ref": "#/components/schemas/DummyResultModel"}}},
            ),
            _ExpectedErrorResponseItem(status_code=status.HTTP_400_BAD_REQUEST, description="Bad Request"),
            _ExpectedErrorResponseItem(status_code=status.HTTP_401_UNAUTHORIZED, description="Unauthorized"),
        )

        @pytest.mark.parametrize(
            "result_number, expected_status_code, expected_result",
            (
                (1, status.HTTP_200_OK, {"some_field": "some value"}),
                (2, status.HTTP_400_BAD_REQUEST, {"detail": {"message": "some message"}}),
                (3, status.HTTP_401_UNAUTHORIZED, {"detail": {"message": "some other message"}}),
            ),
        )
        def test_returns_expected_response(
            self, api_client: TestClient, result_number: int, expected_status_code: int, expected_result: Dict[str, Any]
        ) -> None:
            # given

            # when
            response = api_client.get(self.URL.format(result_number=result_number))

            # then
            assert response.status_code == expected_status_code, response.json()
            assert response.json() == expected_result

    class TestDummyStandardView(BaseDummyViewTest):
        URL = DUMMY_STANDARD_VIEW_URL

        EXPECTED_RESPONSES = _get_expected_responses(
            _ExpectedResponseItem(
                status_code=status.HTTP_200_OK,
                description="Successful Response",
                content={"application/json": {"schema": {"$ref": "#/components/schemas/DummyResultModel"}}},
            ),
            _ExpectedResponseItem(
                status_code=status.HTTP_404_NOT_FOUND,
                description="Not Found",
                content={"application/json": {"schema": {"$ref": "#/components/schemas/DummyErrorResultModel"}}},
            ),
            include_validation_error=False,
        )

        def test_returns_expected_response(
            self,
            api_client: TestClient,
        ) -> None:
            # given

            # when
            response = api_client.get(self.URL)

            # then
            assert response.status_code == status.HTTP_200_OK, response.json()
            assert response.json() == {"some_field": "some value"}

    class TestInvalidErrorEndpoint:

        def test_endpoint_returning_invalid_error_raises_exception_on_adding_route(
                self, ) -> None:
            # given
            def invalid_error_endpoint() -> Result[DummyResultModelA, InvalidException]:
                if random() > 0.5:
                    return Success(DummyResultModelA(some_field="some value"))
                else:
                    return Failure(InvalidException())

            # when
            router.get("/some_path")(invalid_error_endpoint)

            # then
            assert False
