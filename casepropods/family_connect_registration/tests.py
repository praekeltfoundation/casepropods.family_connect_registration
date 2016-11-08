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
        self.url = 'http://example.com/registration/?mother_id=' + \
            self.contact.uuid

        self.pod = RegistrationPod(
            apps.get_app_config('family_connect_registration_pod'),
            RegistrationPodConfig({
                'index': 23,
                'title': "My registration Pod",
                'url': "http://example.com/registration/",
                'token': "test_token",
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
            'count': 0,
            'next': None,
            'previous': None,
            'results': []
        }
        return (200, headers, json.dumps(resp))

    def registration_callback_one_match(self, request):
        headers = {'Content-Type': "application/json"}
        resp = {
            "count": 1,
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

    @responses.activate
    def test_read_data_no_registrations(self):
        # Add callback
        responses.add_callback(
            responses.GET, self.url,
            callback=self.registration_callback_no_matches,
            match_querystring=True, content_type="application/json")

        result = self.pod.read_data({'case_id': self.case.id})

        auth_header = responses.calls[0].request.headers['Authorization']
        self.assertEqual(auth_header, "Token test_token")
        self.assertEqual(result, {"items": []})

    @responses.activate
    def test_read_data_one_registration(self):
        # Add callback
        responses.add_callback(
            responses.GET, self.url,
            callback=self.registration_callback_one_match,
            match_querystring=True, content_type="application/json")

        result = self.pod.read_data({'case_id': self.case.id})

        auth_header = responses.calls[0].request.headers['Authorization']
        self.assertEqual(auth_header, "Token test_token")
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
