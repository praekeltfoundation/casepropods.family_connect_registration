from confmodel import fields
from casepro.pods import Pod, PodConfig, PodPlugin
from demands import HTTPServiceError
try:
    import itertools.ifilter as filter
except ImportError:
    pass
import re
import requests
from seed_services_client import (
    HubApiClient, IdentityStoreApiClient, StageBasedMessagingApiClient)


class RegistrationPodConfig(PodConfig):
    hub_api_url = fields.ConfigText(
        "URL of the hub API service", required=True)
    hub_token = fields.ConfigText(
        "Authentication token for registration endpoint", required=True)
    identity_store_api_url = fields.ConfigText(
        "URL of the identity store API service", required=True)
    identity_store_token = fields.ConfigText(
        "Authentication token for identity store service", required=True)
    stage_based_messaging_url = fields.ConfigText(
        "URL of the stage based messaging API service", required=True)
    stage_based_messaging_token = fields.ConfigText(
        "Authentication token for stage based messaging endpoint",
        required=True)
    engage_url = fields.ConfigText(
        "URL for the engage API", required=True)
    engage_api_token = fields.ConfigText(
        "Url for engage API", required=True)
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

        self.stage_based_messaging = StageBasedMessagingApiClient(
            auth_token=self.config.stage_based_messaging_token,
            api_url=self.config.stage_based_messaging_url,
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

    def has_whatsapp_account(self, number):
        """
        Checks if the given number has a registered whatsapp account, using the
        Engage API
        """

        res = requests.post(
            self.config.engage_url,
            json={
                "contacts": [number],
                "blocking": "wait"
            },
            headers={
                'Authorization': 'Bearer {}'.format(
                    self.config.engage_api_token),
            },
        )
        res.raise_for_status()
        res = res.json()
        existing = filter(lambda d: d.get('status') == 'valid', res)
        return any(existing)

    def get_switch_channel_action(self, channel, identity):
        """
        Given the current channel that the user is on, returns a pod action
        for switching to the other channel choice
        """
        opposite_channel = 'whatsapp' if channel == 'sms' else 'sms'
        opposite_label = 'WhatsApp' if channel == 'sms' else 'SMS'
        return {
            'type': 'switch_channel',
            'name': 'Switch to {}'.format(opposite_label),
            'confirm': True,
            'busy_test': 'Processing...',
            'payload': {
                'channel': opposite_channel,
                'channel_label': opposite_label,
                'identity': identity['id'],
            },
        }

    def get_address_from_identity(self, identity):
        """
        Given an identity from the identity store, returns the active address
        for that identity. If no address exists, returns None
        """
        addresses = identity.get(
            'details', {}).get('addresses', {}).get('msisdn', {})
        msisdn = None
        for address, data in addresses.items():
            if data.get('optedout', False):
                continue
            if data.get('default', False):
                return address
            msisdn = address
        return msisdn

    def channel_switch_option_available(
                self, identity, active_subs, current_channel):
        """
        Returns True if the channel switch option should be shown, else
        returns False.
        """
        if len(active_subs) == 0:
            # If no active subscriptions, then cannot change channel
            return False

        # If they have any WhatsApp subscription, then they should be allowed
        # to switch back to SMS
        if current_channel == 'whatsapp':
            return True

        # Check if registered on WhatsApp network
        msisdn = self.get_address_from_identity(identity)
        return self.has_whatsapp_account(msisdn)

    def get_current_channel(self, subscriptions, messagesets):
        """
        Given the list of active subscriptions for a user, as well as a list
        of messagesets, returns the current channel that the user is receiving
        messages on.
        """
        messageset_mapping = {ms['id']: ms['short_name'] for ms in messagesets}
        for sub in subscriptions:
            messageset = messageset_mapping[sub['messageset']]
            if re.match(r'^whatsapp_', messageset):
                return 'whatsapp'
        return 'sms'

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

        subscriptions = self.stage_based_messaging.get_subscriptions(params={
            'active': True,
            'identity': case.contact.uuid,
        })
        subscriptions = list(subscriptions['results'])
        messagesets = self.stage_based_messaging.get_messagesets()
        messagesets = list(messagesets['results'])

        channel = self.get_current_channel(subscriptions, messagesets)
        if self.channel_switch_option_available(
                identity, subscriptions, channel):
            actions.append(self.get_switch_channel_action(channel, identity))

        return result

    def switch_channel(self, identity, channel):
        """
        Switches the channel of the specified identity to the specified channel
        """
        return self.hub_api.create_change({
            'action': 'switch_channel',
            'registrant_id': identity,
            'data': {
                'channel': channel,
            },
        })

    def perform_action(self, type_, params):
        if type_ == 'switch_channel':
            try:
                self.switch_channel(params['identity'], params['channel'])
                return (True, {
                    "message": "Successfully switched to {}".format(
                        params['channel_label']),
                })
            except HTTPServiceError:
                return (False, {
                    "message": "Failed to switch to {}".format(
                        params['channel_label']),
                })


class RegistrationPlugin(PodPlugin):
    name = 'casepropods.family_connect_registration'
    label = 'family_connect_registration_pod'
    pod_class = RegistrationPod
    config_class = RegistrationPodConfig
    title = 'Registration Pod'
