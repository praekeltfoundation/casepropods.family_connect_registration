import json
import responses
from django.apps import apps
from casepro.cases.models import Case
from casepro.test import BaseCasesTest
from .plugin import RegistrationPodConfig, RegistrationPod


class RegistrationPodTest(BaseCasesTest):
    def setUp(self):
        super(RegistrationPodTest, self).setUp()
        self.contact = self.create_contact(self.unicef, 'test_id', "Mother")
        self.msg1 = self.create_message(
            self.unicef, 123, self.contact, "Hello")
        self.case = Case.get_or_open(
            self.unicef, self.user1, self.msg1, "Summary", self.moh)
        self.url = 'http://hub/api/v1/registrations/?mother_id=' + \
            self.contact.uuid
        self.identity_store_url = ('http://identity-store/api/v1/'
                                   'identities/{0}/').format(self.contact.uuid)

        self.pod = RegistrationPod(
            apps.get_app_config('family_connect_registration_pod'),
            RegistrationPodConfig({
                'index': 23,
                'title': "My registration Pod",
                'hub_api_url': "http://hub/api/v1/",
                'hub_token': "test_token",
                'identity_store_api_url': 'http://identity-store/api/v1/',
                'identity_store_token': 'identity-store-token',
                'contact_id_fieldname': "mother_id",
                'field_mapping': [
                    {"field": "mama_name", "field_name": "Mother Name"},
                    {"field": "mama_surname",
                        "field_name": "Mother Surname"},
                    {"field": "last_period_date",
                        "field_name": "Date of last period"},
                    {"field": "language",
                        "field_name": "Language Preference"},
                    {"field": "mama_id_type", "field_name": "ID Type"},
                    {"field": "mama_id_no", "field_name": "ID Number"},
                    {"field": "msg_receiver",
                        "field_name": "Message Receiver"},
                    {"field": "receiver_id", "field_name": "Receiver ID"},
                    {"field": "hoh_name",
                        "field_name": "Head of Household Name"},
                    {"field": "hoh_surname",
                        "field_name": "Head of Household Surname"},
                    {"field": "hoh_id",
                        "field_name": "Head of Household ID"},
                    {"field": "operator_id", "field_name": "Operator ID"},
                    {"field": "msg_type",
                        "field_name": "Receives Messages As"},
                ]
            }))

    def registration_callback_no_matches(self, request):
        headers = {'Content-Type': "application/json"}
        resp = {
            'next': None,
            'previous': None,
            'results': []
        }
        return (200, headers, json.dumps(resp))

    def registration_callback_one_match(self, request):
        headers = {'Content-Type': "application/json"}
        resp = {
            "next": None,
            "previous": None,
            "results": [{
                "id": "b03d0ba0-3baf-4acb-9943-f9ff89ef2412",
                "stage": "postbirth",
                "mother_id": "test_id",
                "validated": True,
                "data": {
                    "hoh_id": "hoh00001-63e2-4acc-9b94-26663b9bc267",
                    "receiver_id": "hoh00001-63e2-4acc-9b94-26663b9bc267",
                    "operator_id": "hcw00001-63e2-4acc-9b94-26663b9bc267",
                    "language": "eng_UG",
                    "msg_type": "text",
                    "msg_receiver": "head_of_household",
                    "mama_id_no": "12345",
                    "last_period_date": "20150202",
                    "mama_surname": "zin",
                    "mama_id_type": "ugandan_id",
                    "hoh_name": "bob",
                    "mama_name": "sue"},
                "source": 1,
                "created_at": "2016-07-27T15:41:55.102172Z",
                "updated_at": "2016-07-27T15:41:55.102200Z",
                "created_by": 1,
                "updated_by": 1
            }]}
        return (200, headers, json.dumps(resp))

    def test_lookup_field_from_one_dictionary(self):
        field = 'test-field'
        list_one = [{'test-field': 'first-value'}]

        self.assertEqual(
            self.pod.lookup_field_from_dictionaries(field, list_one),
            'first-value'
        )

    def test_lookup_field_from_two_dictionaries(self):
        field = 'test-field'
        list_one = [
            {'test-field': 'first-value'},
            {'test-field': 'second-value'},
        ]

        self.assertEqual(
            self.pod.lookup_field_from_dictionaries(field, list_one),
            'first-value'
        )

    def test_lookup_field_from_two_dictionaries_no_match(self):
        field = 'test-field'
        list_one = [{'different-field': 'first-value'}]
        list_two = [{'test-field': 'second-value'}]

        self.assertEqual(
            self.pod.lookup_field_from_dictionaries(field, list_one, list_two),
            'second-value'
        )

    @responses.activate
    def test_read_data_no_registrations(self):
        # Add callback
        responses.add_callback(
            responses.GET, self.url,
            callback=self.registration_callback_no_matches,
            match_querystring=True, content_type="application/json")

        responses.add(
            responses.GET, self.identity_store_url,
            json={},
            match_querystring=True, content_type="application/json")

        result = self.pod.read_data({'case_id': self.case.id})

        self.assertEqual(result, {"items": [
            {"name": "Mother Name", "value": "Unknown"},
            {"name": "Mother Surname", "value": "Unknown"},
            {"name": "Date of last period", "value": "Unknown"},
            {"name": "Language Preference", "value": "Unknown"},
            {"name": "ID Type", "value": "Unknown"},
            {"name": "ID Number", "value": "Unknown"},
            {"name": "Message Receiver", "value": "Unknown"},
            {"name": "Receiver ID", "value": "Unknown"},
            {"name": "Head of Household Name", "value": "Unknown"},
            {"name": "Head of Household Surname", "value": "Unknown"},
            {"name": "Head of Household ID", "value": "Unknown"},
            {"name": "Operator ID", "value": "Unknown"},
            {"name": "Receives Messages As", "value": "Unknown"},
        ]})

    @responses.activate
    def test_read_data_one_registration(self):
        # Add callback
        responses.add_callback(
            responses.GET, self.url,
            callback=self.registration_callback_one_match,
            match_querystring=True, content_type="application/json")

        responses.add(
            responses.GET, self.identity_store_url,
            json={},
            match_querystring=True, content_type="application/json")

        result = self.pod.read_data({'case_id': self.case.id})

        self.assertEqual(result, {"items": [
            {"name": "Mother Name", "value": "sue"},
            {"name": "Mother Surname", "value": "zin"},
            {"name": "Date of last period", "value": "20150202"},
            {"name": "Language Preference", "value": "eng_UG"},
            {"name": "ID Type", "value": "ugandan_id"},
            {"name": "ID Number", "value": "12345"},
            {"name": "Message Receiver", "value": "head_of_household"},
            {"name": "Receiver ID", "value":
                "hoh00001-63e2-4acc-9b94-26663b9bc267"},
            {"name": "Head of Household Name", "value": "bob"},
            {"name": "Head of Household Surname", "value": "Unknown"},
            {"name": "Head of Household ID",
                "value": "hoh00001-63e2-4acc-9b94-26663b9bc267"},
            {"name": "Operator ID", "value":
                "hcw00001-63e2-4acc-9b94-26663b9bc267"},
            {"name": "Receives Messages As", "value": "text"},
        ]})

    @responses.activate
    def test_can_get_data_from_identity_store(self):
        responses.add(
            responses.GET, self.url,
            json={'results': []},
            match_querystring=True, content_type="application/json")

        responses.add(
            responses.GET, self.identity_store_url,
            json={
                'details': {
                    'mama_id_no': '12345'
                }
            },
            match_querystring=True, content_type="application/json")

        result = self.pod.read_data({'case_id': self.case.id})

        self.assertEqual(len(result['items']), 13)
        self.assertEqual(
            result['items'][5],
            {"name": "ID Number", "value": "12345"},
        )

    @responses.activate
    def test_no_http_request_if_contact_uuid_is_none(self):
        contact_no_uuid = self.create_contact(self.unicef, None, "Mother")
        message = self.create_message(
            self.unicef, 1234, contact_no_uuid, "Hello")
        case = Case.get_or_open(
            self.unicef, self.user1, message, "Summary", self.moh)

        result = self.pod.read_data({'case_id': case.id})

        self.assertEqual(len(responses.calls), 0)
        self.assertEqual(result, {'items': []})

    @responses.activate
    def test_top_level_results_precendence_over_data(self):
        responses.add(
            responses.GET, self.url,
            json={'results': [{
                'mama_name': 'sue-toplevel',
                'data': {
                    'mama_name': 'sue-data',
                },
            }]},
            match_querystring=True, content_type='application/json')

        responses.add(
            responses.GET, self.identity_store_url,
            json={},
            match_querystring=True, content_type="application/json")

        result = self.pod.read_data({'case_id': self.case.id})

        self.assertEqual(len(result['items']), 13)
        self.assertEqual(
            result['items'][0],
            {'name': 'Mother Name', 'value': 'sue-toplevel'},
        )

    @responses.activate
    def test_identity_store_precendence_over_hub(self):
        responses.add(
            responses.GET, self.url,
            json={'results': [{
                'mama_name': 'sue-hub',
                'data': {},
            }]},
            match_querystring=True, content_type='application/json')

        responses.add(
            responses.GET, self.identity_store_url,
            json={
                'details': {
                    'mama_name': 'sue-identity-store',
                },
            },
            match_querystring=True, content_type='application/json')

        result = self.pod.read_data({'case_id': self.case.id})

        self.assertEqual(len(result['items']), 13)
        self.assertEqual(
            result['items'][0],
            {'name': 'Mother Name', 'value': 'sue-identity-store'},
        )

    @responses.activate
    def test_multiple_results_uses_first_result(self):
        responses.add(
            responses.GET, self.url,
            json={'results': [{
                'mama_name': 'result-one',
                'data': {},
            }, {
                'mama_name': 'result-two',
                'data': {},
            }]},
            match_querystring=True, content_type='application/json')

        responses.add(
            responses.GET, self.identity_store_url,
            json={},
            match_querystring=True, content_type="application/json")

        result = self.pod.read_data({'case_id': self.case.id})

        self.assertEqual(len(result['items']), 13)
        self.assertEqual(
            result['items'][0],
            {'name': 'Mother Name', 'value': 'result-one'},
        )
