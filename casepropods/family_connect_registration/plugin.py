from confmodel import fields
from casepro.pods import Pod, PodConfig, PodPlugin
from seed_services_client import HubApiClient


class RegistrationPodConfig(PodConfig):
    url = fields.ConfigText("URL of the hub API service", required=True)
    token = fields.ConfigText("Authentication token for registration endpoint",
                              required=True)
    contact_id_fieldname = fields.ConfigText(
        "The field-name to identify the contact in the registration service"
        "Example: 'mother_id'",
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
        content = {"items": []}
        contact_id_fieldname = self.config.contact_id_fieldname
        mapping = self.config.field_mapping
        case_id = params["case_id"]
        case = Case.objects.get(pk=case_id)

        if case.contact.uuid is None:
            return content

        hub_api = HubApiClient(
            auth_token=self.config.token,
            api_url=self.config.url,
        )

        response = hub_api.get_registrations(
            params={contact_id_fieldname: case.contact.uuid})

        for result in response["results"]:
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
