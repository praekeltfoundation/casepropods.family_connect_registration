from confmodel import fields
from casepro.pods import Pod, PodConfig, PodPlugin
from seed_services_client import HubApiClient, IdentityStoreApiClient


class RegistrationPodConfig(PodConfig):
    hub_api_url = fields.ConfigText(
        "URL of the hub API service", required=True)
    hub_token = fields.ConfigText(
        "Authentication token for registration endpoint", required=True)
    identity_store_api_url = fields.ConfigText(
        "URL of the identity store API service", required=True)
    identity_store_token = fields.ConfigText(
        "Authentication token for identity store service", required=True)
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
    def __init__(self, pod_type, config):
        super(RegistrationPod, self).__init__(pod_type, config)

        self.identity_store = IdentityStoreApiClient(
            auth_token=self.config.identity_store_token,
            api_url=self.config.identity_store_api_url,
        )

        self.hub_api = HubApiClient(
            auth_token=self.config.hub_token,
            api_url=self.config.hub_api_url,
        )

    def lookup_field_from_dictionaries(self, field, *lists):
        """
        Receives a 'field' and one or more lists of dictionaries
        to search for the field. Returns the first match.
        """
        for results_list in lists:
            for result_dict in results_list:
                if field in result_dict:
                    return result_dict[field]

        return 'Unknown'

    def get_identity_registration_data(self, identity, registrations):
        """
        Given an identity and a list of registrations, formats the registration
        data into the pod format.
        """
        if identity is not None and 'details' in identity:
            identity_details = [identity['details']]
        else:
            identity_details = []

        registration_data_fields = [r['data'] for r in registrations]

        items = []
        for field in self.config.field_mapping:
            value = self.lookup_field_from_dictionaries(
                field['field'],
                identity_details,
                registrations,
                registration_data_fields,
            )
            items.append({
                'name': field['field_name'],
                'value': value,
            })
        return items

    def read_data(self, params):
        from casepro.cases.models import Case

        case_id = params["case_id"]
        case = Case.objects.get(pk=case_id)

        items = []
        actions = []
        result = {
            'items': items,
            'actions': actions,
        }

        if case.contact.uuid is None:
            return result

        registrations = self.hub_api.get_registrations(params={
            self.config.contact_id_fieldname: case.contact.uuid,
        })
        registrations = list(registrations['results'])
        identity = self.identity_store.get_identity(case.contact.uuid)

        items.extend(self.get_identity_registration_data(
            identity, registrations))

        return result


class RegistrationPlugin(PodPlugin):
    name = 'casepropods.family_connect_registration'
    label = 'family_connect_registration_pod'
    pod_class = RegistrationPod
    config_class = RegistrationPodConfig
    title = 'Registration Pod'
