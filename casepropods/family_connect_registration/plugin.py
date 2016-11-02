from confmodel import fields
from casepro.pods import Pod, PodConfig, PodPlugin
import requests


class RegistrationPodConfig(PodConfig):
    url = fields.ConfigText("URL to query for the registration data",
                            required=True)
    token = fields.ConfigText("Authentication token for registration endpoint",
                              required=True)
    field_mapping = fields.ConfigList(
        "Mapping of field names to what should be displayed for them."
        "Example:"
        "[{'field': 'mama_name', 'field_name': 'Mother Name'},"
        "{'field': 'mama_surname', 'field_name': 'Mother Surname'}],",
        required=True)


class RegistrationPod(Pod):
    def read_data(self, params):
        from casepro.cases.models import Case

        # Setup
        url = self.config.url
        token = self.config.token
        mapping = self.config.field_mapping
        headers = {
            'Authorization': "Token " + token,
            'Content-Type': "application/json"
        }
        case_id = params["case_id"]
        case = Case.objects.get(pk=case_id)

        # Get and format registration response
        r = requests.get(url, params={'mother_id': case.contact.uuid},
                         headers=headers)
        r.raise_for_status()
        response = r.json()
        results = response["results"]

        content = {"items": []}
        for result in results:
            for obj in mapping:
                if obj["field"] in result:
                    value = result[obj["field"]]
                elif obj["field"] in result["data"]:
                    value = result["data"][obj["field"]]
                else:
                    value = "Unknown"
                content['items'].append(
                    {"name": obj["field_name"], "value": value})
        return content


class RegistrationPlugin(PodPlugin):
    name = 'casepropods.family_connect_registration'
    label = 'family_connect_registration_pod'
    pod_class = RegistrationPod
    config_class = RegistrationPodConfig
    title = 'Registration Pod'
