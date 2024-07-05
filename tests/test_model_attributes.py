import uuid
from typing import Annotated
from typing import List
from typing import Optional

import pytest

from scim2_models.attributes import validate_attribute_urn
from scim2_models.base import BaseModel
from scim2_models.base import ComplexAttribute
from scim2_models.base import Context
from scim2_models.base import Returned
from scim2_models.rfc7643.resource import Resource
from scim2_models.rfc7643.user import User


def test_get_attribute_urn():
    class Sub(ComplexAttribute):
        dummy: str

    class Sup(Resource):
        schemas: List[str] = ["urn:example:2.0:Sup"]
        dummy: str
        sub: Sub
        subs: List[Sub]

    sup = Sup(dummy="x", sub=Sub(dummy="x"), subs=[Sub(dummy="x")])

    assert sup.get_attribute_urn("dummy") == "urn:example:2.0:Sup:dummy"
    assert sup.get_attribute_urn("sub") == "urn:example:2.0:Sup:sub"
    assert sup.sub.get_attribute_urn("dummy") == "urn:example:2.0:Sup:sub.dummy"
    assert sup.subs[0].get_attribute_urn("dummy") == "urn:example:2.0:Sup:subs.dummy"


def test_guess_root_type():
    class Sub(ComplexAttribute):
        dummy: str

    class Sup(Resource):
        schemas: List[str] = ["urn:example:2.0:Sup"]
        dummy: str
        sub: Sub
        subs: List[Sub]

    assert Sup.get_field_root_type("dummy") is str
    assert Sup.get_field_root_type("sub") == Sub
    assert Sup.get_field_root_type("subs") == Sub


class ReturnedModel(BaseModel):
    always: Annotated[Optional[str], Returned.always] = None
    never: Annotated[Optional[str], Returned.never] = None
    default: Annotated[Optional[str], Returned.default] = None
    request: Annotated[Optional[str], Returned.request] = None


class Baz(ComplexAttribute):
    baz_snake_case: str


class Foo(Resource):
    schemas: List[str] = ["urn:example:2.0:Foo"]
    sub: Annotated[ReturnedModel, Returned.default]
    bar: str
    snake_case: str
    baz: Optional[Baz] = None


class Bar(Resource):
    schemas: List[str] = ["urn:example:2.0:Bar"]
    sub: Annotated[ReturnedModel, Returned.default]
    bar: str
    snake_case: str
    baz: Optional[Baz] = None


class Extension(Resource):
    schemas: List[str] = ["urn:example:2.0:Extension"]
    baz: str


def test_validate_attribute_urn():
    """Test the method that validates and normalizes attribute URNs."""

    assert validate_attribute_urn("bar", Foo) == "urn:example:2.0:Foo:bar"
    assert (
        validate_attribute_urn("urn:example:2.0:Foo:bar", Foo)
        == "urn:example:2.0:Foo:bar"
    )
    assert (
        validate_attribute_urn("urn:example:2.0:Foo:bar", User, resource_types=[Foo])
        == "urn:example:2.0:Foo:bar"
    )

    assert validate_attribute_urn("sub", Foo) == "urn:example:2.0:Foo:sub"
    assert (
        validate_attribute_urn("urn:example:2.0:Foo:sub", Foo)
        == "urn:example:2.0:Foo:sub"
    )
    assert (
        validate_attribute_urn("urn:example:2.0:Foo:sub", User, resource_types=[Foo])
        == "urn:example:2.0:Foo:sub"
    )

    assert validate_attribute_urn("sub.always", Foo) == "urn:example:2.0:Foo:sub.always"
    assert (
        validate_attribute_urn("urn:example:2.0:Foo:sub.always", Foo)
        == "urn:example:2.0:Foo:sub.always"
    )
    assert (
        validate_attribute_urn(
            "urn:example:2.0:Foo:sub.always", User, resource_types=[Foo]
        )
        == "urn:example:2.0:Foo:sub.always"
    )

    assert validate_attribute_urn("snakeCase", Foo) == "urn:example:2.0:Foo:snakeCase"
    assert (
        validate_attribute_urn("urn:example:2.0:Foo:snakeCase", Foo)
        == "urn:example:2.0:Foo:snakeCase"
    )

    assert (
        validate_attribute_urn("urn:example:2.0:Extension:baz", Foo[Extension])
        == "urn:example:2.0:Extension:baz"
    )
    assert (
        validate_attribute_urn(
            "urn:example:2.0:Extension:baz", resource_types=[Foo[Extension]]
        )
        == "urn:example:2.0:Extension:baz"
    )

    with pytest.raises(ValueError, match="No default schema and relative URN"):
        validate_attribute_urn("bar", resource_types=[Foo])

    with pytest.raises(
        ValueError, match="No resource matching schema 'urn:InvalidResource'"
    ):
        validate_attribute_urn("urn:InvalidResource:bar", Foo)

    with pytest.raises(
        ValueError, match="No resource matching schema 'urn:example:2.0:Foo'"
    ):
        validate_attribute_urn("urn:example:2.0:Foo:bar")

    with pytest.raises(
        ValueError, match="Model 'Foo' has no attribute named 'invalid'"
    ):
        validate_attribute_urn("urn:example:2.0:Foo:invalid", Foo)

    with pytest.raises(
        ValueError,
        match="Attribute 'bar' is not a complex attribute, and cannot have a 'invalid' sub-attribute",
    ):
        validate_attribute_urn("bar.invalid", Foo)


def test_payload_attribute_case_sensitivity():
    """RFC7643 §2.1 indicates that attribute names should be case insensitive.

    Attribute names are case insensitive and are often "camel-cased"
    (e.g., "camelCase").

    Reported by issue #39.
    """

    payload = {
        "UserName": "UserName123",
        "Active": True,
        "displayname": "BobIsAmazing",
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
        "externalId": uuid.uuid4().hex,
        "name": {
            "formatted": "Ryan Leenay",
            "familyName": "Leenay",
            "givenName": "Ryan",
        },
        "emails": [
            {"Primary": True, "type": "work", "value": "testing@bob.com"},
            {"Primary": False, "type": "home", "value": "testinghome@bob.com"},
        ],
    }
    user = User.model_validate(payload)
    assert user.user_name == "UserName123"
    assert user.display_name == "BobIsAmazing"


def test_attribute_inclusion_case_sensitivity():
    """Test that attribute inclusion supports any attribute case.

    Reported by #45.
    """

    user = User.model_validate({"userName": "foobar"})
    assert user.model_dump(
        scim_ctx=Context.RESOURCE_QUERY_RESPONSE, attributes=["userName"]
    ) == {
        "userName": "foobar",
        "schemas": [
            "urn:ietf:params:scim:schemas:core:2.0:User",
        ],
    }

    assert user.model_dump(
        scim_ctx=Context.RESOURCE_QUERY_RESPONSE, attributes=["username"]
    ) == {
        "userName": "foobar",
        "schemas": [
            "urn:ietf:params:scim:schemas:core:2.0:User",
        ],
    }

    assert user.model_dump(
        scim_ctx=Context.RESOURCE_QUERY_RESPONSE, attributes=["USERNAME"]
    ) == {
        "userName": "foobar",
        "schemas": [
            "urn:ietf:params:scim:schemas:core:2.0:User",
        ],
    }

    assert user.model_dump(
        scim_ctx=Context.RESOURCE_QUERY_RESPONSE,
        attributes=["urn:ietf:params:scim:schemas:core:2.0:User:userName"],
    ) == {
        "userName": "foobar",
        "schemas": [
            "urn:ietf:params:scim:schemas:core:2.0:User",
        ],
    }

    assert user.model_dump(
        scim_ctx=Context.RESOURCE_QUERY_RESPONSE,
        attributes=["urn:ietf:params:scim:schemas:core:2.0:User:username"],
    ) == {
        "userName": "foobar",
        "schemas": [
            "urn:ietf:params:scim:schemas:core:2.0:User",
        ],
    }
    assert user.model_dump(
        scim_ctx=Context.RESOURCE_QUERY_RESPONSE,
        attributes=["urn:ietf:params:scim:schemas:core:2.0:User:USERNAME"],
    ) == {
        "userName": "foobar",
        "schemas": [
            "urn:ietf:params:scim:schemas:core:2.0:User",
        ],
    }
